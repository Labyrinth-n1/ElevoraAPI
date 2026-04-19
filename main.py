from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import json

from blocs import analyse_cv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "API Elevora "}

@app.post("/analyse_cv/")
async def analyse_cv_endpoint(
    job_text: str = Form(...),
    cv_file: UploadFile = File(...)
):
    temp_file_path = None

    try:
        content = await cv_file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            temp_file_path = tmp.name

        result = analyse_cv(job_text, temp_file_path)

        return json.loads(result)

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
