"""Entry point kept at this path so `uvicorn main:app` keeps working. The app lives in app/."""

from app.main import app  # noqa: F401
