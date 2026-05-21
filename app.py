from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from functools import wraps
from pipeline import run_research_pipeline
from supabase import create_client, Client
import os, json, threading, queue, sys
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

# ── Supabase client ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "admin123")  # set a strong value in .env

# ── Log streaming ────────────────────────────────────────────────────────────
log_queue = queue.Queue()

class StreamToQueue:
    def __init__(self, q):
        self.queue = q
        self.original = sys.stdout
    def write(self, text):
        self.original.write(text)
        if text.strip():
            self.queue.put({"type": "log", "message": text.rstrip()})
    def flush(self):
        self.original.flush()

# ── Auth decorators ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ── Pages ────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("research_page"))

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("research_page"))
    return render_template("login.html",
                           supabase_url=SUPABASE_URL,
                           supabase_anon_key=SUPABASE_ANON_KEY)

@app.route("/app")
@login_required
def research_page():
    return render_template("index.html", user=session["user"])

@app.route("/auth/callback")
def auth_callback():
    return render_template("callback.html",
                           supabase_url=SUPABASE_URL,
                           supabase_anon_key=SUPABASE_ANON_KEY)

@app.route("/admin/<secret>")
def admin_dashboard(secret):
    if secret != ADMIN_SECRET:
        return "Not found", 404
    session["is_admin"] = True
    return redirect(url_for("admin_page"))

@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")

# ── Auth API ─────────────────────────────────────────────────────────────────
@app.route("/api/session", methods=["POST"])
def set_session():
    """Called from frontend after Supabase JS auth succeeds."""
    data = request.get_json()
    access_token = data.get("access_token")
    if not access_token:
        return jsonify({"error": "No token"}), 400
    try:
        user_resp = supabase.auth.get_user(access_token)
        user = user_resp.user
        session["user"] = {
            "id": user.id,
            "email": user.email,
            "name": user.user_metadata.get("full_name") or user.user_metadata.get("name") or user.email.split("@")[0],
            "avatar": user.user_metadata.get("avatar_url", ""),
            "provider": user.app_metadata.get("provider", "email"),
        }
        session["access_token"] = access_token

        # Upsert into custom users table
        supabase.table("users").upsert({
            "id": user.id,
            "email": user.email,
            "name": session["user"]["name"],
            "avatar": session["user"]["avatar"],
            "provider": session["user"]["provider"],
        }, on_conflict="id").execute()

        return jsonify({"status": "ok", "user": session["user"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})

# ── Admin API ─────────────────────────────────────────────────────────────────
@app.route("/api/admin/users")
@admin_required
def get_users():
    try:
        resp = supabase.table("users").select("*").order("created_at", desc=True).execute()
        return jsonify(resp.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/stats")
@admin_required
def get_stats():
    try:
        users = supabase.table("users").select("id, provider, created_at").execute().data
        queries = supabase.table("research_queries").select("id, created_at").execute().data
        return jsonify({
            "total_users": len(users),
            "google_users": sum(1 for u in users if u.get("provider") == "google"),
            "email_users": sum(1 for u in users if u.get("provider") == "email"),
            "total_queries": len(queries),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Research API ──────────────────────────────────────────────────────────────
@app.route("/research", methods=["POST"])
@login_required
def research():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    # Log the query
    try:
        supabase.table("research_queries").insert({
            "user_id": session["user"]["id"],
            "topic": topic,
        }).execute()
    except Exception:
        pass  # non-fatal

    result_container = {}
    error_container = {}

    def run():
        old_stdout = sys.stdout
        sys.stdout = StreamToQueue(log_queue)
        try:
            state = run_research_pipeline(topic)
            result_container["state"] = state
        except Exception as e:
            error_container["error"] = str(e)
        finally:
            sys.stdout = old_stdout
            log_queue.put({"type": "done",
                           "result": result_container.get("state"),
                           "error": error_container.get("error")})

    threading.Thread(target=run).start()
    return jsonify({"status": "started"})

@app.route("/stream")
@login_required
def stream():
    def generate():
        while True:
            try:
                item = log_queue.get(timeout=300)
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("type") == "done":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type':'error','message':'Timeout'})}\n\n"
                break
    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
