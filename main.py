import os
import shutil
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from openai import OpenAI

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_FOLDER = os.path.join(BASE_DIR, "uploads")  # <-- Fixed for Render
CSV_FILE = os.path.join(UPLOADS_FOLDER, "catalog_output.csv")
PUBLIC_BASE_URL = "https://auction-ai-catalog.onrender.com/uploads"
client = OpenAI()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static site (index.html, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Make sure uploads folder exists
os.makedirs(UPLOADS_FOLDER, exist_ok=True)

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("static/index.html", "r") as f:
        return f.read()


@app.post("/upload")
async def upload_files(files: list[UploadFile]):
    saved_files = []
    for file in files:
        file_path = os.path.join(UPLOADS_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        saved_files.append(file.filename)
    return {"uploaded": saved_files}


@app.post("/generate")
async def generate_catalog():
    images = [f for f in os.listdir(UPLOADS_FOLDER) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not images:
        return JSONResponse({"error": "No images found in uploads folder"}, status_code=400)

    data = []
    for idx, image_name in enumerate(images, start=1):
        image_url = f"{PUBLIC_BASE_URL}/{image_name}"
        prompt = f"Create a short auction catalog title and description for this image: {image_url}"
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {"role": "user", "content": prompt}
                ]
            )
            text = response.output[0].content[0].text
        except Exception as e:
            text = f"Error: {e}"

        data.append({
            "Lot #": idx,
            "Image": image_name,
            "Description": text
        })

    df = pd.DataFrame(data)
    df.to_csv(CSV_FILE, index=False)
    return FileResponse(CSV_FILE, filename="catalog_output.csv")


@app.delete("/delete-uploads")
async def delete_uploads():
    for file in os.listdir(UPLOADS_FOLDER):
        file_path = os.path.join(UPLOADS_FOLDER, file)
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting {file}: {e}")
    return {"status": "All images deleted successfully"}
