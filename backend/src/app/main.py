"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="Travel Agent API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
