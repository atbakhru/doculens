"""Deterministic synthetic documents. No customer data, downloads, or OCR labels."""

from io import BytesIO
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def document(layout: int, variant: int, seed=42):
    rng = np.random.default_rng(seed + variant + layout * 100)
    im = Image.new("RGB", (720, 960), "white")
    d = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=12)
    ink = "#253446"
    d.text(
        (46, 35),
        ["NORTHSTAR / INVOICE", "FIELDNOTES / REPORT", "MERIDIAN / APPLICATION"][layout],
        fill=ink,
        font=font,
    )
    d.text((46, 68), f"SYNTHETIC SAMPLE  /  {variant + 1:03d}", fill="#708090", font=small)
    if layout == 0:
        d.rectangle((46, 120, 350, 220), outline=ink, width=2)
        d.text((60, 135), "BILL TO: SAMPLE COMPANY", fill=ink, font=small)
        d.text((490, 140), "INVOICE DETAILS", fill=ink, font=small)
        d.rectangle((46, 280, 674, 320), fill=ink)
        for x, label in [(60, "DESCRIPTION"), (420, "QTY"), (550, "AMOUNT")]:
            d.text((x, 292), label, fill="white", font=small)
        for i in range(8):
            y = 320 + i * 47
            d.line((46, y + 47, 674, y + 47), fill="#9ba7b3")
            d.text(
                (60, y + 15),
                f"Service item {i + 1} - reference {rng.integers(100, 999)}",
                fill=ink,
                font=small,
            )
            d.text((440, y + 15), str(rng.integers(1, 9)), fill=ink, font=small)
            d.text((560, y + 15), f"{rng.integers(50, 900)}.00", fill=ink, font=small)
        d.rectangle((430, 750, 674, 820), fill="#e4eaf0")
        d.text((450, 778), "TOTAL   $ 2,840.00", fill=ink, font=font)
    elif layout == 1:
        for col in range(2):
            x = 46 + col * 330
            for block in range(3):
                y = 130 + block * 235
                d.rectangle((x, y, x + 270, y + 22), fill=ink)
                for line in range(11):
                    width = int(rng.integers(160, 270))
                    d.rectangle((x, y + 38 + line * 14, x + width, y + 41 + line * 14), fill="#657586")
        d.text((46, 875), "RESEARCH BRIEF / INTERNAL SAMPLE", fill=ink, font=small)
    else:
        for i in range(6):
            y = 130 + i * 110
            d.text(
                (46, y),
                ["FULL NAME", "CONTACT", "ADDRESS", "DEPARTMENT", "REFERENCE", "COMMENTS"][i],
                fill=ink,
                font=small,
            )
            d.rectangle((46, y + 25, 674, y + 70), outline=ink, width=2)
            d.text((62, y + 40), f"Sample entry {rng.integers(1000, 9999)}", fill="#67788b", font=small)
        for x in (46, 260, 470):
            d.rectangle((x, 845, x + 20, 865), outline=ink, width=2)
            d.text((x + 30, 850), "OPTION", fill=ink, font=small)
    d.line((46, 912, 674, 912), fill="#aab5c0")
    d.text((46, 925), "DOCULENS EVALUATION CORPUS / NOT A REAL DOCUMENT", fill=ink, font=small)
    return im


def png(im):
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def corpus(seed=42):
    samples = []
    for layout in range(3):
        for variant in range(4):
            name = f"{['invoice', 'report', 'application'][layout]}-{variant + 1:02d}.png"
            samples.append((name, png(document(layout, variant, seed)), layout, f"{layout}-{variant}"))
    samples.append(("invoice-01-copy.png", samples[0][1], 0, "0-0"))
    for layout in range(3):
        im = document(layout, 0, seed).rotate(1.4, resample=Image.Resampling.BICUBIC, fillcolor="white")
        samples.append(
            (f"{['invoice', 'report', 'application'][layout]}-rescanned.png", png(im), layout, f"{layout}-0")
        )
    return samples


if __name__ == "__main__":
    root = Path(".data/fixtures")
    root.mkdir(parents=True, exist_ok=True)
    labels = []
    for name, data, layout, identity in corpus():
        (root / name).write_bytes(data)
        labels.append(dict(filename=name, layout=layout, identity=identity))
    (root / "labels.json").write_text(json.dumps(labels, indent=2))
    print(f"Generated {len(labels)} labeled pages in {root}")
