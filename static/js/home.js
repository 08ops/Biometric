const el = id => document.getElementById(id);
const api = async (p,o={})=>{
  const r = await fetch(p,{headers:{'Content-Type':'application/json'},...o});
  if(!r.ok) throw new Error(await r.text()); return r.json();
};
async function search(){
  const q = el('q').value.trim();
  const url = q ? `/students?search=${encodeURIComponent(q)}` : '/students';
  const rows = await api(url);
  const body = el('resultsBody');
  body.innerHTML = rows.length ? rows.map(s=>`
    <tr>
      <td>${s.id}</td><td>${s.index_no}</td><td>${s.full_name}</td>
      <td><button class="btn-ghost" onclick="alert('Open student ${s.id}')">View</button></td>
    </tr>`).join('')
    : `<tr><td colspan="4" class="py-6 text-center text-slate-500">No matches.</td></tr>`;
}
el('searchBtn').onclick = search;
el('q').addEventListener('keydown', e => { if(e.key==='Enter') search(); });

el('addBtn').onclick = async ()=>{
  const index_no = el('idx').value.trim();
  const full_name = el('name').value.trim();
  if(!index_no || !full_name) return alert('Provide both fields');
  await api('/students',{method:'POST',body:JSON.stringify({index_no, full_name})});
  el('idx').value = ""; el('name').value = "";
  search();

};
// ================= MQTT for Face Capture =================
const faceStatus = el("faceStatus");
let mqttClient = null;

function initMQTT() {
  mqttClient = new Paho.MQTT.Client(
    "656341057f74454aba2968cc5609344d.s1.eu.hivemq.cloud", 8883, "webclient-" + Math.random()
  );

  mqttClient.onConnectionLost = err => {
    console.error("MQTT connection lost:", err.errorMessage);
    faceStatus.textContent = "❌ MQTT disconnected.";
  };

  mqttClient.onMessageArrived = msg => {
    if (msg.destinationName === "attendance/enroll/response") {
      const payload = JSON.parse(msg.payloadString);
      if (payload.status === "success") {
        faceStatus.textContent = `✅ Face captured successfully from ${payload.pi}`;
      } else {
        faceStatus.textContent = `❌ Capture failed: ${payload.message}`;
      }
    }
  };

  mqttClient.connect({
  useSSL: true, // true if using port 8884 (wss://)
  onSuccess: () => {
    mqttClient.subscribe("attendance/enroll/response");
    faceStatus.textContent = "✅ MQTT connected. Ready to capture.";
  },
  onFailure: e => {
    faceStatus.textContent = "❌ MQTT failed to connect.";
    console.error("MQTT connection error:", e.errorMessage);
  }
});


el("faceBtn").onclick = () => {
  if (!mqttClient || !mqttClient.isConnected()) {
    faceStatus.textContent = "❌ MQTT not connected.";
    return;
  }

  const msg = new Paho.MQTT.Message("{}");
  msg.destinationName = "attendance/enroll/face";
  mqttClient.send(msg);
  faceStatus.textContent = "⏳ Sending capture command...";
};

initMQTT();
