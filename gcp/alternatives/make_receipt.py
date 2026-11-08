"""Generate a synthetic OCR fixture; no personal or purchase data."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[2]
out = ROOT / 'docs/lab9-evidence'
image = Image.new('RGB', (1100, 820), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 38)
text = 'PEACH LAB DEMO\nSYNTHETIC RECEIPT\nDate: 2026-11-08\n\nNotebook       2 x 3.00\nPen            1 x 2.00\nTOTAL USD         8.00\n\nNOT A REAL PURCHASE'
draw.multiline_text((60, 60), text, font=font, fill='black', spacing=25)
image.save(out / 'synthetic-receipt.png')
(out / 'ocr-expected.txt').write_text(text + '\n')
