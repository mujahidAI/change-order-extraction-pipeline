import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from . import pipeline
from .schema import Result

app = FastAPI(title="Change-Order Extraction")


@app.post("/extract", response_model=Result)
def extract(file: UploadFile | None = File(None), text: str | None = Form(None)) -> Result:
    """Upload a PDF/image/text file, or send raw text."""
    if text:
        return pipeline.run_text(text)
    if not file:
        raise HTTPException(400, "Send a file or a text field.")
    suffix = Path(file.filename or "").suffix or ".pdf"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(file.file.read())
        try:
            return pipeline.run_path(path)
        except ValueError as e:
            raise HTTPException(400, str(e))
