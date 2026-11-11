"""Small worker invoked only by newspaper_ner.demo in the layout venv."""

from __future__ import annotations

import sys
from pathlib import Path

from paddleocr import LayoutDetection


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: predict_layout_paddle.py PAGE_IMAGE OUTPUT_JSON", file=sys.stderr)
        return 2
    image_path, output_path = Path(sys.argv[1]), Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = LayoutDetection(
        model_name="PP-DocLayout_plus-L",
        device="cpu",
        enable_mkldnn=False,
    )
    results = list(model.predict(input=str(image_path), batch_size=1))
    if not results:
        print("PaddleOCR returned no layout result.", file=sys.stderr)
        return 1
    results[0].save_to_json(save_path=str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
