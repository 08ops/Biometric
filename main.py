from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Ping")

@app.get("/", response_class=PlainTextResponse)
def root():
    return "OK"
