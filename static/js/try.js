// ================= MQTT for Face Capture =================
const faceStatus = el("faceStatus");
let mqttClient = null;

function initMQTT() {
  mqttClient = new Paho.MQTT.Client(
    "656341057f74454aba2968cc5609344d.s1.eu.hivemq.cloud", 8884, "webclient-" + Math.random()
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
    useSSL: true,
    userName: "your-hivemq-username",
    password: "your-hivemq-password",
    onSuccess: () => {
      mqttClient.subscribe("attendance/enroll/response");
      faceStatus.textContent = "✅ MQTT connected. Ready to capture.";
    },
    onFailure: e => {
      faceStatus.textContent = "❌ MQTT failed to connect.";
      console.error("MQTT connection error:", e.errorMessage);
    }
  });
}

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
