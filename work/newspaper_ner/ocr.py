from pathlib import Path
import os
import hashlib
import shutil

from PIL import Image
import pytesseract
from pytesseract import Output

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESSDATA_DIR = PROJECT_ROOT / "models" / "tessdata"

LANGUAGE_MODELS = {"en": "eng", "hi": "hin"}


def _find_tesseract() -> Path | None:
    configured = os.environ.get("TESSERACT_CMD")
    if configured:
        resolved = shutil.which(configured) or configured
        return Path(resolved).expanduser().resolve()

    found = shutil.which("tesseract")
    return Path(found).resolve() if found else None


def recognize_page(
    image_path: str | Path,
    language: str,
    psm: int = 3,
    offset_x: int = 0,
    offset_y: int = 0,
    full_page_width: int | None = None,
    full_page_height: int | None = None,
) -> dict:
    if language not in LANGUAGE_MODELS:
        raise ValueError("Language must be 'en' or 'hi'.")

    if not 0 <= psm <= 13:
        raise ValueError("PSM must be an integer from 0 to 13.")
    if offset_x < 0 or offset_y < 0:
        raise ValueError("Crop offsets must be zero or positive pixel values.")
    if (full_page_width is None) != (full_page_height is None):
        raise ValueError("Provide both full-page dimensions, or neither.")
    if (offset_x or offset_y) and full_page_width is None:
        raise ValueError("Crop offsets require --page-width and --page-height.")

    tesseract_exe = _find_tesseract()
    if tesseract_exe is None or not tesseract_exe.is_file():
        raise FileNotFoundError(
            "Tesseract was not found. Add it to PATH or set TESSERACT_CMD "
            "to the full path of tesseract.exe in this PowerShell session."
        )
    pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)

    model = LANGUAGE_MODELS[language]
    model_path = TESSDATA_DIR / f"{model}.traineddata"
    if not model_path.is_file():
        raise FileNotFoundError(f"Missing OCR model: {model}")

    # Tesseract reads this setting directly. It avoids Windows command-line
    # quoting problems when the project path contains spaces.
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)

    image_path = Path(image_path).resolve()

    with Image.open(image_path) as image:
        input_width, input_height = image.size
        page_width = full_page_width or input_width
        page_height = full_page_height or input_height
        if offset_x + input_width > page_width or offset_y + input_height > page_height:
            raise ValueError("Crop image and offsets extend beyond the full-page dimensions.")
        data = pytesseract.image_to_data(
            image,
            lang=model,
            config=f"--oem 3 --psm {psm}",
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
            "block_num": int(data["block_num"][index]),
            "par_num": int(data["par_num"][index]),
            "line_num": int(data["line_num"][index]),
            "word_num": int(data["word_num"][index]),
            "bbox": {
                "x": int(data["left"][index]) + offset_x,
                "y": int(data["top"][index]) + offset_y,
                "width": int(data["width"][index]),
                "height": int(data["height"][index]),
            },
        })

    return {
        "stage": "ocr",
        "source_image": str(image_path),
        "page_width": page_width,
        "page_height": page_height,
        "ocr_input_width": input_width,
        "ocr_input_height": input_height,
        "coordinate_offset": {"x": offset_x, "y": offset_y},
        "ocr_mode": (
            "page"
            if offset_x == 0 and offset_y == 0
            and input_width == page_width and input_height == page_height
            else "region"
        ),
        "ocr_settings": {
            "tesseract_executable": str(tesseract_exe),
            "tesseract_language": model,
            "oem": 3,
            "psm": psm,
            "tessdata_dir": str(TESSDATA_DIR),
            "model_file": model_path.name,
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        },
        "words": words,
    }
