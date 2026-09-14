import json
import os
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
FILE_DIR = os.path.join(UPLOAD_DIR, "files")
THUMB_DIR = os.path.join(UPLOAD_DIR, "thumbs")
DATA_DIR = os.path.join(APP_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "research.json")

ACCESS_CODE = "090308"
ALLOWED_DOCS = {".pdf", ".docx"}
ALLOWED_IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

for path in (FILE_DIR, THUMB_DIR, DATA_DIR):
    os.makedirs(path, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024  # 80 MB

def load_items():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_items(items):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def ext_of(filename):
    return os.path.splitext(filename or "")[1].lower()

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/login")
def login():
    code = str((request.get_json(silent=True) or {}).get("code", "")).strip()
    if code == ACCESS_CODE:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Invalid access code"}), 401

@app.get("/api/research")
def list_research():
    q = request.args.get("q", "").strip().lower()
    items = load_items()
    if q:
        items = [
            item
            for item in items
            if q in item.get("title", "").lower()
            or q in item.get("keywords", "").lower()
        ]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(items)

@app.post("/api/research")
def add_research():
    title = (request.form.get("title") or "").strip()
    keywords = (request.form.get("keywords") or "").strip()
    doc = request.files.get("file")
    thumb = request.files.get("thumbnail")

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not doc or not doc.filename:
        return jsonify({"error": "Upload a PDF or DOCX file"}), 400
    if not thumb or not thumb.filename:
        return jsonify({"error": "Add a thumbnail image"}), 400

    doc_ext = ext_of(doc.filename)
    thumb_ext = ext_of(thumb.filename)
    if doc_ext not in ALLOWED_DOCS:
        return jsonify({"error": "Only PDF or DOCX files are allowed"}), 400
    if thumb_ext not in ALLOWED_IMAGES:
        return jsonify({"error": "Thumbnail must be an image"}), 400

    item_id = uuid.uuid4().hex[:12]
    doc_name = f"{item_id}{doc_ext}"
    thumb_name = f"{item_id}{thumb_ext}"
    doc.save(os.path.join(FILE_DIR, doc_name))
    thumb.save(os.path.join(THUMB_DIR, thumb_name))

    item = {
        "id": item_id,
        "title": title,
        "keywords": keywords,
        "file_name": secure_filename(doc.filename),
        "file_type": doc_ext.replace(".", "").upper(),
        "file_url": f"/uploads/files/{doc_name}",
        "thumb_url": f"/uploads/thumbs/{thumb_name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_ts": int(time.time()),
    }
    items = load_items()
    items.append(item)
    save_items(items)
    return jsonify(item), 201

@app.delete("/api/research/<item_id>")
def delete_research(item_id):
    items = load_items()
    match = next((item for item in items if item["id"] == item_id), None)
    if not match:
        abort(404)
    for folder, url_key in ((FILE_DIR, "file_url"), (THUMB_DIR, "thumb_url")):
        name = os.path.basename(match.get(url_key, ""))
        path = os.path.join(folder, name)
        if name and os.path.exists(path):
            os.remove(path)
    save_items([item for item in items if item["id"] != item_id])
    return jsonify({"ok": True})

@app.get("/uploads/files/<path:filename>")
def serve_file(filename):
    return send_from_directory(FILE_DIR, filename)

@app.get("/uploads/thumbs/<path:filename>")
def serve_thumb(filename):
    return send_from_directory(THUMB_DIR, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)