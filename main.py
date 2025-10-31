from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
import pandas as pd
from openai import OpenAI

# ---------------- CONFIG ----------------
UPLOADS_FOLDER = "uploads"  # Local folder containing images
CSV_FILE = "catalog_output.csv"
PUBLIC_BASE_URL = "https://yourwebsite.com/uploads"  # Public URL for your uploads

# Initialize FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

# Initialize CSV if missing
if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=[
        "Lot Number", "Image Filenames", "Public URLs",
        "Base Caption", "Refined Text", "Enhanced Description"
    ]).to_csv(CSV_FILE, index=False)

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Track last lot number
lot_counter = 1
if os.path.exists(CSV_FILE):
    df_existing = pd.read_csv(CSV_FILE)
    if not df_existing.empty:
        lot_counter = df_existing["Lot Number"].max() + 1

# ---------------- GENERATE CATALOG ----------------
@app.post("/generate-catalog")
def generate_catalog():
    """
    Generate auction descriptions for each lot based on images in /uploads/ folder.
    Uses numbering system: 1-1.jpg, 1-2.jpg, etc.
    """
    global lot_counter
    if not os.path.exists(UPLOADS_FOLDER):
        return {"error": f"Uploads folder '{UPLOADS_FOLDER}' does not exist."}

    # Collect image files
    image_files = [f for f in os.listdir(UPLOADS_FOLDER)
                   if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]

    if not image_files:
        return {"message": "No images found in uploads folder."}

    # Group images by lot number (before the dash)
    lots = {}
    for image_file in image_files:
        try:
            lot_number_str = image_file.split("-")[0]
            lots.setdefault(lot_number_str, []).append(image_file)
        except Exception as e:
            print(f"Skipping invalid filename: {image_file} ({e})")

    new_entries = []

    for lot_str, images in sorted(lots.items(), key=lambda x: int(x[0])):
        public_urls = [f"{PUBLIC_BASE_URL}/{img}" for img in images]
        file_names = ", ".join(images)

        try:
            # GPT request with all images for this lot
            messages = [
                {"role": "system", "content": "You are an expert auction catalog writer."},
                {
                    "role": "user",
                    "content": f"Describe this auction item using the following image URLs: {', '.join(public_urls)}\n"
                               "Provide three levels of text:\n"
                               "1. Base Caption (short, simple)\n"
                               "2. Refined Catalog Text (professional auction style)\n"
                               "3. Enhanced Marketing Description (engaging, detailed)"
                },
            ]

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )

            text_output = response.choices[0].message.content
            lines = [line.strip() for line in text_output.split("\n") if line.strip()]
            base_caption = lines[0] if len(lines) > 0 else "No base caption generated."
            refined_text = lines[1] if len(lines) > 1 else "No refined text generated."
            enhanced_description = lines[2] if len(lines) > 2 else "No enhanced description generated."

        except Exception as e:
            print(f"AI error for lot {lot_str}: {e}")
            base_caption = "AI failed to generate description."
            refined_text = base_caption
            enhanced_description = base_caption

        # Add entry
        entry = {
            "Lot Number": lot_counter,
            "Image Filenames": file_names,
            "Public URLs": ", ".join(public_urls),
            "Base Caption": base_caption,
            "Refined Text": refined_text,
            "Enhanced Description": enhanced_description
        }
        new_entries.append(entry)
        lot_counter += 1

    # Append to CSV
    df = pd.DataFrame(new_entries)
    df.to_csv(CSV_FILE, mode='a', header=False, index=False)

    return {"message": f"Generated descriptions for {len(new_entries)} lots.", "entries": new_entries}


# ---------------- CSV DOWNLOAD ----------------
@app.get("/download-csv")
def download_csv():
    if os.path.exists(CSV_FILE):
        return FileResponse(CSV_FILE, filename="catalog_output.csv", media_type="text/csv")
    return {"error": "CSV file not found"}
