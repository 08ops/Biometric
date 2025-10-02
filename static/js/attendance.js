const el = id => document.getElementById(id);
const api = async (p, o = {}) => {
  const r = await fetch(p, {
    headers: { 'Content-Type': 'application/json' },
    ...o
  });

  if (!r.ok) {
    throw new Error(await r.text());
  }

  return r.json();
};

let activeSessionId = null;

// async function sendCommand(cmd, payload={}){
//   // Replace with real bridge later (MQTT/HTTP to Pi)
//   await api('/cmd', { method:'POST', body: JSON.stringify({ type: cmd, ...payload }) });
// }

async function refreshSession(){
  const s = await api('/sessions/active');
  if(!s || !s.id){
    activeSessionId = null;
    el('sessionBanner').classList.add('hidden');
    return;
  }
  activeSessionId = s.id;
  el('sessionBanner').classList.remove('hidden');
  el('sessionBanner').innerHTML = `
    <div class="flex items-center justify-between">
      <div>
        <div class="font-semibold">Active: ${s.course_code} (ID ${s.id})</div>
        <div class="text-xs text-slate-500">Started: ${new Date(s.started_at).toLocaleString()}</div>
      </div>
      <div class="text-xs text-green-600">Live</div>
    </div>`;
  loadLogs();
}

async function startAttendance(){
  const code = prompt('Course code?', 'CPEN104');
  if(!code) return;
  await api('/sessions', { method:'POST', body: JSON.stringify({ course_code: code })});
  await sendCommand('start_attendance', { course_code: code });
  refreshSession();
}

async function endAttendance() {
  // Ask user to confirm the course code of the session to end
  const rawCode = prompt('Confirm course code to end session:', 'CPEN104');
  const code = rawCode?.trim().toUpperCase();  // normalize input

  if (!code) {
    alert('No session code provided.');
    return;
  }

  // Send request to backend to mark session as ended
  try {
    const res = await api(`/sessions/${code}/end`, { method: 'POST' });
    console.log('Backend response:', res);
    alert('Session successfully ended.');
  } catch (err) {
    console.error('Failed to end session:', err);
    alert('Failed to end session on the server.');
    return;
  }

  // Refresh UI: hide banner, clear logs
  activeSessionId = null;
  el('sessionBanner').classList.add('hidden');
  el('logsBody').innerHTML = `
    <tr><td colspan="4" class="py-6 text-center text-slate-500">Session ended.</td></tr>`;
}




async function loadLogs(){
  if(!activeSessionId) return;
  const rows = await api('/attendance?session_id=' + activeSessionId);
  const body = el('logsBody');
  body.innerHTML = rows.length ? rows.map(r=>`
    <tr>
      <td>${new Date(r.created_at).toLocaleTimeString()}</td>
      <td>${r.student_id}</td>
      <td>${r.rfid_ok ? '✔️' : '—'}</td>
      <td>${r.face_ok ? '✔️' : '—'}</td>
    </tr>`).join('')
    : `<tr><td colspan="4" class="py-6 text-center text-slate-500">No logs yet.</td></tr>`;
}

async function beginAttendance() {
  alert("Please scan your RFID card now")
  try {
    const result = await api('/begin-attendance', { method: 'POST' });

    if (!result || !result.timestamp || !result.student_id) {
      alert('Invalid data received from reader.');
      return;
    }

    // Add entry to the table
    const row = `
      <tr>
        <td>${new Date(result.timestamp).toLocaleTimeString()}</td>
        <td>${result.student_id}</td>
        <td>${result.rfid_uid || '—'}</td>
        <td>${result.registration_number || '—'}</td>
      </tr>
    `;

    const body = el('logsBody');
    const emptyRow = body.querySelector('.text-slate-500');
    if (emptyRow) emptyRow.remove(); // remove "No logs yet"
    body.insertAdjacentHTML('afterbegin', row);

  } catch (err) {
    console.error(err);
    alert('Failed to start RFID reading or log attendance.');
  }
}


el('startBtn').onclick = startAttendance;
el('endBtn').onclick = endAttendance;
el('beginBtn').onclick = beginAttendance;
refreshSession();
setInterval(loadLogs, 4000);