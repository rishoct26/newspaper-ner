from pathlib import Path
import os
import shutil

from PIL import Image
import pytesseract
from pytesseract import Output

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESSERACT_EXE = Path(os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or "tesseract")
pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_EXE)
TESSDATA_DIR = PROJECT_ROOT / "models" / "tessdata"

LANGUAGE_MODELS = {"en": "eng", "hi": "hin"}


def recognize_page(image_path: str | Path, language: str) -> dict:
    if language not in LANGUAGE_MODELS:
        raise ValueError("Language must be 'en' or 'hi'.")

    if not TESSERACT_EXE.is_file():
        raise FileNotFoundError(f"Tesseract was not found at {TESSERACT_EXE}")

    model = LANGUAGE_MODELS[language]
    if not (TESSDATA_DIR / f"{model}.traineddata").is_file():
        raise FileNotFoundError(f"Missing OCR model: {model}")

    image_path = Path(image_path).resolve()

    with Image.open(image_path) as image:
        page_width, page_height = image.size
        data = pytesseract.image_to_data(
            image,
            lang=model,
            config=f'--tessdata-dir {TESSDATA_DIR}',
            output_type=Output.DICT,
        )

    words = []
    for index, text in enumerate(data["text"]):
        text = text.strip()
        confidence = float(data["conf"][index])

        if not text or confidence < 0:
            continue

        words.append({
            "text": text,
            "language": language,
            "ocr_confidence": round(confidence, 2),
            "bbox": {
                "x": int(data["left"][index]),
                "y": int(data["top"][index]),
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
            },
        })

    return {
        "stage": "ocr",
        "source_image": str(image_path),
        "page_width": page_width,
        "page_height": page_height,
        "words": words,
    }
