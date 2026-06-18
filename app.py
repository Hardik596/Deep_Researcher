from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from functools import wraps
from pipeline import run_research_pipeline
import os, json, threading, queue, sys
from dotenv import load_dotenv
import hashlib

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

# ── Users store ───────────────────────────────────────────────────────────────
# Add your users here as "username": "password"
# Passwords are plain text here — see note below for hashed version
USERS = {
    os.environ.get("ADMIN_USERNAME", "admin"): os.environ.get("ADMIN_PASSWORD", "change-me"),
    # Add more users like this:
    # "alice": "alicepassword",
    # "bob": "bobpassword",
}

def check_credentials(username, password):
    expected = USERS.get(username)
    if not expected:
        return False
    return expected == password

# ── Log streaming ─────────────────────────────────────────────────────────────
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

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("research_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "user" in session:
        return redirect(url_for("research_page"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if check_credentials(username, password):
            session["user"] = {"name": username, "email": ""}
            return redirect(url_for("research_page"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)

@app.route("/app")
@login_required
def research_page():
    return render_template("index.html", user=session["user"])

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})

# ── Research API ──────────────────────────────────────────────────────────────
@app.route("/research", methods=["POST"])
@login_required
def research():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Topic is required"}), 400

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
