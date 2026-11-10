from pathlib import Path
import sys

from PIL import Image

folder = Path(sys.argv[1] if len(sys.argv) > 1 else "scans/en_dev")

for source in folder.glob("*.jp2"):
    target = source.with_suffix(".png")
    if target.exists():
        continue
    with Image.open(source) as image:
        image.save(target)
        print(f"{source.name} -> {target.name}  size={image.size}  mode={image.mode}")