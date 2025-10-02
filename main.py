from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from db import get_db_connection
import psycopg2
import pathlib

now = datetime.now(timezone.utc)


# ------- Flask app -------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

#path to store uploads
BASE_DIR = pathlib.Path(__file__).resolve().parent
UPLOADS = BASE_DIR / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

# ------- helpers -------
def find_student_id_by_uid(uid_hex):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE LOWER(rfid_uid) = LOWER(%s)", (uid_hex,))
            student = cur.fetchone()
            return student["id"] if student else None

# Temporary debug route to test DB connection
@app.route("/test-students")
def test_students():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM sessions")
                count = cur.fetchone()["count"]
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



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
# search students with optional search : name or index_no will make changes in funtion later
@app.route("/students", methods=["GET"])
def list_students():
    print("search for student...")
    search = request.args.get("search", "").lower()
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            if search:
                cur.execute("""
                    SELECT id, registration_number AS index_no, name AS full_name
                    FROM students
                    WHERE LOWER(name) LIKE %s OR LOWER(registration_number) LIKE %s
                """, (f"%{search}%", f"%{search}%"))
            else:
                cur.execute("""
                    SELECT id, registration_number AS index_no, name AS full_name
                    FROM students
                """)
            students = cur.fetchall()
    except Exception as e:
        print(f"DB Error: {e}")
        return jsonify({"error": "An error occurred while querying the database."}), 500

    if not students:
        msg = "Student database is empty." if not search else "No matching student found."
        return jsonify({"error": msg}), 404

    return jsonify(students)



# create a new student
@app.route("/add-student", methods=["POST"])
def create_student():
    data = request.get_json()
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO students (name, registration_number, rfid_uid, class, photo_path) VALUES (%s, %s, %s, %s, %s)" \
        " RETURNING *", (
                          data["name"], 
                          data["registration_number"], 
                          data.get("rfid_uid"), 
                          data.get("class"), 
                          data.get("photo_path")))
        new_student = cur.fetchone()
        conn.commit()
    return jsonify(new_student), 201

@app.route("/rfid", methods=["POST"])
def link_rfid():
    data = request.get_json()
    uid = data["uid_hex"]
    sid = int(data["student_id"])

    if find_student_id_by_uid(uid):
        return jsonify({"error": "UID already linked"}), 409

    if not uid or not sid:
        return jsonify({"error": "uid_hex and student_id are required"}), 400

    with get_db_connection() as conn:
        cur = conn.cursor()
         # Check if UID is already in use
        cur.execute("SELECT id FROM students WHERE rfid_uid = %s", (uid,))

        if cur.fetchone():
            return jsonify({"error": "UID already linked to a student"}), 409

        # Update the student record with the new UID
        cur.execute("""
            UPDATE students
            SET rfid_uid = %s
            WHERE id = %s
            RETURNING id, name, registration_number, rfid_uid
            """, (uid, sid))

        updated = cur.fetchone()
        if not updated:
            return jsonify({"error": "Student not found"}), 404

        conn.commit()
    return jsonify(updated), 200

@app.route("/sessions/active")
def get_active_session():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1")
        session = cur.fetchone()
    if not session:
        return jsonify({"error": "No active session"}), 404
    return jsonify(session)

@app.route("/sessions", methods=["POST"])
def create_session():
    data = request.get_json()
    code = data.get("course_code").strip().upper()
    # Validate course code format
    if not code:
        return jsonify({"error": "course_code required"}), 400
    with get_db_connection() as conn:
        cur = conn.cursor()
        # Check if there's already an active session for this course
        cur.execute("INSERT INTO sessions (course_code, started_at) VALUES (%s, %s) RETURNING *",
                    (code, now))
        new_session = cur.fetchone()
        conn.commit()
    return jsonify(new_session), 201

@app.route("/sessions/<string:session_id>/end", methods=["POST"])
def end_session(session_id):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE sessions SET ended_at = %s WHERE course_code = %s RETURNING *",
                    (now, session_id))
        ended_session = cur.fetchone()
        if not ended_session:
            return jsonify({"error": "Session not found"}), 404
        conn.commit()
    return jsonify(ended_session)

@app.route("/begin-attendance", methods=["POST"])
def begin_attendance():
    try:
        # 🔌 Call your actual RFID reader function here
        uid = read_rfid()  # Implement this in rfid_reader.py

        if not uid:
            return jsonify({"error": "No RFID UID received"}), 400

        timestamp = datetime.now(timezone.utc)

        # Lookup student by UID
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, registration_number, rfid_uid
                FROM students
                WHERE rfid_uid = %s
            """, (uid,))
            student = cur.fetchone()

        if not student:
            return jsonify({"error": "RFID not linked to any student"}), 404

        return jsonify({
            "timestamp": timestamp.isoformat(),
            "student_id": student["id"],
            "registration_number": student["registration_number"],
            "rfid_uid": student["rfid_uid"]
        })

    except Exception as e:
        print("Error in begin_attendance:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/attendance", methods=["POST"])
def log_attendance():
    uid = request.form.get("rfid_uid")
    photo = request.files.get("photo")

    if not uid or not photo:
        return jsonify({"error": "rfid_uid and photo are required"}), 400

    # Save photo to /static/uploads
    filename = secure_filename(f"{datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uid}.jpg")
    save_path = UPLOADS / filename
    photo.save(save_path)
    photo_url = f"/static/uploads/{filename}"

    with get_db_connection() as conn:
        cur = conn.cursor()
        # Get student by UID
        cur.execute("SELECT id FROM students WHERE rfid_uid = %s", (uid,))
        student = cur.fetchone()
        if not student:
            return jsonify({"error": "RFID not linked to any student"}), 404

        student_id = student["id"]

        # Get current active session (if using sessions)
        cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1")
        session = cur.fetchone()
        if not session:
            return jsonify({"error": "No active sessions"}), 400

        session_id = session["id"]

        # Log attendance
        try:
            cur.execute("""
                INSERT INTO attendance (student_id, session_id, live_photo_path, status)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (student_id, session_id, photo_url, "present"))
            log = cur.fetchone()
            conn.commit()
            return jsonify(log), 201

        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({"error": "Attendance already logged for this session or today"}), 409
        
# ------- main -------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
