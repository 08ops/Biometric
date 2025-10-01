# cmd_probe.py
import json
from fastapi import FastAPI, Body
import paho.mqtt.client as mqtt

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
PI_ID       = "pi-1"

app = FastAPI(title="CMD Probe")

_client = mqtt.Client(client_id="cmd-probe")
_client.connect(BROKER_HOST, BROKER_PORT, 30)
_client.loop_start()

def publish_cmd(cmd: dict):
    _client.publish(f"attend/cmd/{PI_ID}", json.dumps(cmd), qos=1)

@app.post("/cmd")
def post_cmd(payload: dict = Body(...)):
    if "type" not in payload: return {"ok": False, "error": "missing 'type'"}
    publish_cmd(payload)
    return {"ok": True}
