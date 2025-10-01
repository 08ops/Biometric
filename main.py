# main.py — Flask version of the PC base station
import os, json, pathlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import paho.mqtt.client as mqtt

# ------- config -------
BROKER_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
PI_ID       = os.getenv("PI_ID", "pi-1")

BASE_DIR = pathlib.Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)

# ------- Flask app -------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
app.config["UPLOAD_FOLDER"] = str(UPLOADS)

# ------- mock in-memory data -------
students = []
rfid_cards = []
sessions = []
attendance = []

# ------- helpers -------
def find_student_id_by_uid(uid_hex):
    for c in rfid_cards:
        if c["uid_hex"].lower() == uid_hex.lower():
            return c["student_id"]
    return None

# ------- UI routes -------
@app.route("/")
def home():
    return render_template("home.html", nav="home")

@app.route("/attendance-ui")
def attendance_ui():
    return render_template("attendance.html", nav="attendance")

@app.route("/settings")
def settings_ui():
    return render_template("settings.html", nav="settings")

# ------- API routes -------
@app.route("/students", methods=["GET"])
def list_students():
    search = request.args.get("search", "").lower()
    if not search:
        return jsonify(students)
    results = [s for s in students if search in s["full_name"].lower() or search in s["index_no"].lower()]
    return jsonify(results)

@app.route("/students", methods=["POST"])
def create_student():
    data = request.get_json()
    new = {
        "id": len(students) + 1,
        "index_no": data["index_no"],
        "full_name": data["full_name"]
    }
    students.append(new)
    return jsonify(new), 201

@app.route("/rfid", methods=["POST"])
def link_rfid():
    data = request.get_json()
    uid = data["uid_hex"]
    sid = int(data["student_id"])
    if find_student_id_by_uid(uid):
        return jsonify({"error": "UID already linked"}), 409
    new = {
        "id": len(rfid_cards) + 1,
        "student_id": sid,
        "uid_hex": uid
    }
    rfid_cards.append(new)
    return jsonify(new), 201

@app.route("/sessions/active")
def get_active_session():
    return jsonify(sessions[-1] if sessions else None)

@app.route("/sessions", methods=["POST"])
def create_session():
    data = request.get_json()
    code = data.get("course_code", "").strip().upper()
    if not code:
        return jsonify({"error": "course_code required"}), 400
    new = {
        "id": len(sessions) + 1,
        "course_code": code,
        "started_at": datetime.utcnow().isoformat() + "Z"
    }
    sessions.append(new)
    return jsonify(new), 201

@app.route("/attendance")
def list_attendance():
    session_id = request.args.get("session_id", type=int)
    if session_id is None:
        return jsonify({"error": "Missing session_id"}), 400
    logs = [a for a in attendance if a["session_id"] == session_id]
    return jsonify(logs)

# ------- MQTT setup -------
mqtt_client = mqtt.Client(client_id="admin-backend")

def mqtt_connect():
    try:
        mqtt_client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
        mqtt_client.loop_start()
        print("MQTT connected.")
    except Exception as e:
        print(f"MQTT connection failed: {e}")

mqtt_connect()

def publish_cmd(cmd):
    topic = f"attend/cmd/{PI_ID}"
    mqtt_client.publish(topic, json.dumps(cmd), qos=1, retain=False)

def publish_event(evt):
    topic = f"attend/events/{PI_ID}"
    mqtt_client.publish(topic, json.dumps(evt), qos=1, retain=False)

@app.route("/cmd", methods=["POST"])
def post_cmd():
    data = request.get_json()
    if "type" not in data:
        return jsonify({"error": "missing 'type'"}), 400
    publish_cmd(data)
    return jsonify({"ok": True})

# ------- verify face & upload -------
@app.route("/verify-face", methods=["POST"])
def verify_face():
    if not sessions:
        return jsonify({"error": "No active session"}), 400

    uid_hex = request.form.get("uid_hex")
    image = request.files.get("image")

    if not uid_hex or not image:
        return jsonify({"error": "uid_hex and image required"}), 400

    student_id = find_student_id_by_uid(uid_hex)
    if not student_id:
        return jsonify({"error": "RFID not linked to a student"}), 404

    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{secure_filename(uid_hex)}.jpg"
    save_path = UPLOADS / filename
    image.save(save_path)

    face_ok = True  # Stub for actual face recognition

    log = {
        "id": len(attendance) + 1,
        "session_id": sessions[-1]["id"],
        "student_id": student_id,
        "rfid_ok": True,
        "face_ok": face_ok,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    attendance.append(log)

    publish_event({
        "type": "attendance_logged",
        "student_id": student_id,
        "session_id": log["session_id"],
        "ts": log["created_at"]
    })

    return jsonify({
        "ok": True,
        "student_id": student_id,
        "attendance_id": log["id"],
        "face_ok": face_ok
    })

# ------- static file serving (if needed) -------
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# ------- main -------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
