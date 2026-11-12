"""Run PDFium in a disposable subprocess with a parent-enforced timeout."""

import sys
from pathlib import Path
import pypdfium2 as pdfium
from services.api.config import MAX_PAGES, MAX_PIXELS


def render(source, output):
    with pdfium.PdfDocument(source) as doc:
        if len(doc) < 1 or len(doc) > MAX_PAGES:
            raise ValueError(f"PDF must contain 1-{MAX_PAGES} pages")
        for i in range(len(doc)):
            page = doc[i]
            try:
                w, h = page.get_size()
                if w <= 0 or h <= 0 or w * h > MAX_PIXELS:
                    raise ValueError("PDF page dimensions exceed limits")
                scale = min(150 / 72, 1200 / max(w, h))
                bitmap = page.render(scale=scale)
                try:
                    bitmap.to_pil().convert("RGB").save(Path(output) / f"{i + 1:03d}.png")
                finally:
                    bitmap.close()
            finally:
                page.close()


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
