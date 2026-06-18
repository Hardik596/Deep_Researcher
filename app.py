from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from pipeline import run_research_pipeline
import os, json, threading, queue, sys
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
@app.route("/app")
def research_page():
    return render_template("index.html", user={"name": "Researcher", "email": "", "avatar": ""})

# ── Research API ──────────────────────────────────────────────────────────────
@app.route("/research", methods=["POST"])
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
