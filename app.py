from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="Attendance Admin")

# static + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS (handy later if your API base is different)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ------------ UI PAGES ------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "nav": "home"})

@app.get("/attendance-ui", response_class=HTMLResponse)
def attendance_page(request: Request):
    return templates.TemplateResponse("attendance.html", {"request": request, "nav": "attendance"})

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "nav": "settings"})

# ------------ MOCK API (replace with real later) ------------
class Student(BaseModel):
    id: int
    index_no: str
    full_name: str

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
sessions: List[Session] = []
attendance: List[AttendanceLog] = []

@app.get("/students", response_model=List[Student])
def list_students(search: Optional[str] = None):
    if not search:
        return students
    q = search.lower()
    return [s for s in students if q in s.full_name.lower() or q in s.index_no.lower()]

@app.post("/students", response_model=Student)
def create_student(payload: dict):
    new = Student(id=len(students)+1, index_no=payload["index_no"], full_name=payload["full_name"])
    students.append(new)
    return new

@app.get("/sessions/active")
def get_active():
    return sessions[-1] if sessions else None

@app.post("/sessions", response_model=Session)
def create_session(payload: dict):
    code = str(payload.get("course_code","")).upper()
    if not code:
        raise HTTPException(400, "course_code required")
    new = Session(id=len(sessions)+1, course_code=code, started_at=datetime.utcnow().isoformat()+"Z")
    sessions.append(new)
    return new

@app.get("/attendance", response_model=List[AttendanceLog])
def list_attendance(session_id: int):
    return [a for a in attendance if a.session_id == session_id]

@app.post("/attendance", response_model=AttendanceLog)
def mark(payload: dict):
    new = AttendanceLog(
        id=len(attendance)+1,
        session_id=payload["session_id"],
        student_id=payload["student_id"],
        rfid_ok=bool(payload.get("rfid_ok", False)),
        face_ok=bool(payload.get("face_ok", False)),
        created_at=datetime.utcnow().isoformat()+"Z"
    )
    attendance.append(new)
    return new

# placeholder for future Pi command bridge
@app.post("/cmd")
def send_cmd(payload: dict):
    # Example payload: {"type":"start_attendance", "course_code":"CPEN104"}
    print("CMD ->", payload)  # replace with MQTT/HTTP to Pi later
    return {"ok": True, "echo": payload}
