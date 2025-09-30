# main.py — PC base station (MQTT broker + admin API + verify endpoint)
import os, json, pathlib
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import paho.mqtt.client as mqtt

# ------- config -------
BROKER_HOST = os.getenv("MQTT_HOST", "127.0.0.1")  # your PC (broker)
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
PI_ID       = os.getenv("PI_ID", "pi-1")

# uploads (optional)
UPLOADS = pathlib.Path("uploads"); UPLOADS.mkdir(exist_ok=True)

# ------- app + static -------
app = FastAPI(title="Attendance Admin")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ------- simple UI pages -------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "nav":"home"})

@app.get("/attendance-ui", response_class=HTMLResponse)
def attendance_page(request: Request):
    return templates.TemplateResponse("attendance.html", {"request": request, "nav":"attendance"})

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "nav":"settings"})

# ------- data models (mock/in-memory for now) -------
class Student(BaseModel):
    id: int
    index_no: str
    full_name: str

class RFIDCard(BaseModel):
    id: int
    student_id: int
    uid_hex: str

class Session(BaseModel):
    id: int
    course_code: str
    started_at: str

class AttendanceLog(BaseModel):
    id: int
    session_id: int
    student_id: int
    rfid_ok: bool
    face_ok: bool
    created_at: str

students: List[Student] = []
rfid_cards: List[RFIDCard] = []
sessions: List[Session] = []
attendance: List[AttendanceLog] = []

def find_student_id_by_uid(uid_hex: str) -> Optional[int]:
    for c in rfid_cards:
        if c.uid_hex.lower() == uid_hex.lower():
            return c.student_id
    return None

# ------- REST API (UI uses these) -------
@app.get("/students", response_model=List[Student])
def list_students(search: Optional[str] = None):
    if not search: return students
    q = search.lower()
    return [s for s in students if q in s.full_name.lower() or q in s.index_no.lower()]

@app.post("/students", response_model=Student)
def create_student(payload: dict):
    new = Student(id=len(students)+1, index_no=payload["index_no"], full_name=payload["full_name"])
    students.append(new); return new

@app.post("/rfid", response_model=RFIDCard)
def link_rfid(payload: dict):
    uid = payload["uid_hex"]; sid = int(payload["student_id"])
    if find_student_id_by_uid(uid): raise HTTPException(409, "UID already linked")
    new = RFIDCard(id=len(rfid_cards)+1, student_id=sid, uid_hex=uid)
    rfid_cards.append(new); return new

@app.get("/sessions/active")
def get_active():
    return sessions[-1] if sessions else None

@app.post("/sessions", response_model=Session)
def create_session(payload: dict):
    code = str(payload.get("course_code","")).upper()
    if not code: raise HTTPException(400, "course_code required")
    new = Session(id=len(sessions)+1, course_code=code, started_at=datetime.utcnow().isoformat()+"Z")
    sessions.append(new); return new

@app.get("/attendance", response_model=List[AttendanceLog])
def list_attendance(session_id: int):
    return [a for a in attendance if a.session_id == session_id]

# ------- MQTT bridge (frontend buttons -> Pi) -------
mqtt_client = mqtt.Client(client_id="admin-backend")
def mqtt_connect():
    mqtt_client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    mqtt_client.loop_start()
mqtt_connect()

def publish_cmd(cmd: dict):
    topic = f"attend/cmd/{PI_ID}"
    mqtt_client.publish(topic, json.dumps(cmd), qos=1, retain=False)

def publish_event(evt: dict):
    topic = f"attend/events/{PI_ID}"
    mqtt_client.publish(topic, json.dumps(evt), qos=1, retain=False)

@app.post("/cmd")
def post_cmd(payload: dict = Body(...)):
    if "type" not in payload: raise HTTPException(400, "missing 'type'")
    publish_cmd(payload)
    return {"ok": True}

# ------- Pi -> PC: verify face + log attendance -------
@app.post("/verify-face")
async def verify_face(uid_hex: str = Form(...), image: UploadFile = File(...)):
    if not sessions: raise HTTPException(400, "No active session")
    student_id = find_student_id_by_uid(uid_hex)
    if not student_id: raise HTTPException(404, "RFID not linked to a student")

    # save image (optional) then "verify" (stub true)
    data = await image.read()
    (UPLOADS / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uid_hex}.jpg").write_bytes(data)
    face_ok = True

    log = AttendanceLog(
        id=len(attendance)+1,
        session_id=sessions[-1].id,
        student_id=student_id,
        rfid_ok=True, face_ok=face_ok,
        created_at=datetime.utcnow().isoformat()+"Z"
    )
    attendance.append(log)
    publish_event({"type":"attendance_logged","student_id":student_id,"session_id":log.session_id,"ts":log.created_at})

    return {"ok": True, "student_id": student_id, "attendance_id": log.id, "face_ok": face_ok}
