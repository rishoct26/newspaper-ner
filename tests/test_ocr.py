import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from newspaper_ner import ocr


class CropOffsetTests(unittest.TestCase):
    def test_word_box_is_shifted_into_full_page_coordinates(self):
        outputs_directory = Path(__file__).resolve().parents[1] / "outputs"
        with tempfile.TemporaryDirectory(dir=outputs_directory) as temporary_directory:
            temporary_path = Path(temporary_directory)
            image_path = temporary_path / "crop.png"
            tesseract_path = temporary_path / "tesseract.exe"
            tessdata_path = temporary_path / "tessdata"
            tessdata_path.mkdir()
            model_path = tessdata_path / "eng.traineddata"
            tesseract_path.write_bytes(b"mock executable")
            model_path.write_bytes(b"mock OCR model")
            Image.new("L", (20, 10), color=255).save(image_path)

            tesseract_data = {
                "text": ["Jones"],
                "conf": [91],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
                "word_num": [1],
                "left": [3],
                "top": [4],
                "width": [8],
                "height": [5],
            }
            with (
                patch.object(ocr, "PROJECT_ROOT", temporary_path),
                patch.object(ocr, "TESSDATA_DIR", tessdata_path),
                patch.object(ocr, "_find_tesseract", return_value=tesseract_path),
                patch.object(ocr.pytesseract, "image_to_data", return_value=tesseract_data),
            ):
                result = ocr.recognize_page(
                    image_path,
                    "en",
                    psm=6,
                    offset_x=100,
                    offset_y=200,
                    full_page_width=500,
                    full_page_height=400,
                )

        self.assertEqual(result["words"][0]["bbox"], {
            "x": 103,
            "y": 204,
            "width": 8,
            "height": 5,
        })


if __name__ == "__main__":
    unittest.main()
