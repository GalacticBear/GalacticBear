from pathlib import Path
import base64
import html
import math
import cv2
import numpy as np
from PIL import Image

try:
    from rembg import remove
except Exception:
    remove = None

# Light/background -> space. Dark facial features -> heavier characters.
RAMP = " .:-=+*#%@"

def remove_background(image):
    return remove(image).convert("RGBA") if remove else image.convert("RGBA")

def crop_subject(rgba):
    arr = np.array(rgba)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        return rgba
    px = max(8, int((xs.max() - xs.min()) * 0.04))
    py = max(8, int((ys.max() - ys.min()) * 0.04))
    return rgba.crop((max(0, xs.min()-px), max(0, ys.min()-py),
                      min(arr.shape[1], xs.max()+px+1), min(arr.shape[0], ys.max()+py+1)))

def process_grayscale(rgba):
    arr = np.array(rgba)
    rgb = arr[:, :, :3].copy()
    alpha = arr[:, :, 3]
    rgb[alpha < 8] = 255
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 45, 45)
    gray = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    x = gray.astype(np.float32) / 255.0
    return np.clip((x ** 1.7) * 255.0, 0, 255).astype(np.uint8)

def ascii_rows(gray, columns=90):
    h, w = gray.shape
    rows = max(1, round(columns * (h / w) * 0.48))
    small = cv2.resize(gray, (columns, rows), interpolation=cv2.INTER_AREA)
    idx = np.rint((255-small) / 255.0 * (len(RAMP)-1)).astype(int)
    idx = np.clip(idx, 0, len(RAMP)-1)
    return ["".join(RAMP[i] for i in row) for row in idx]

def embedded_font(font_path):
    if not font_path.exists():
        return ""
    data = base64.b64encode(font_path.read_bytes()).decode("ascii")
    return f'''<style>@font-face {{font-family:JBMonoEmbedded;src:url(data:font/woff2;base64,{data}) format("woff2");font-weight:400;font-style:normal;}}</style>'''

def generate_ascii_svg(source_path, output_path, columns=90, display_width=460, font_size=12.9):
    image = Image.open(source_path).convert("RGBA")
    subject = crop_subject(remove_background(image))
    gray = process_grayscale(subject)
    rows = ascii_rows(gray, columns)

    font_path = Path(__file__).resolve().parents[1] / "fonts" / "JetBrainsMono-Regular.woff2"
    line_height = font_size * 1.02
    height = math.ceil(len(rows) * line_height + 16)
    char_width = font_size * 0.600
    total_width = columns * char_width
    duration = max(0.09 * len(rows), 0.1)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width:.2f} {height:.2f}" width="{display_width}" role="img" aria-label="Animated ASCII portrait">',
        embedded_font(font_path),
        "<defs>",
    ]
    for i in range(len(rows)):
        y = 12 + i * line_height
        out.append(f'<clipPath id="r{i}"><rect x="0" y="{y-line_height:.2f}" width="0" height="{line_height*1.5:.2f}"><animate attributeName="width" from="0" to="{total_width:.2f}" dur="0.09s" begin="{i*0.09:.2f}s" fill="freeze"/></rect></clipPath>')
    out.append("</defs>")
    for i, row in enumerate(rows):
        y = 12 + i * line_height
        out.append(f'<text x="0" y="{y:.2f}" font-family="JBMonoEmbedded,monospace" font-size="{font_size}px" xml:space="preserve" clip-path="url(#r{i})" fill="currentColor">{html.escape(row)}</text>')
    out.append(f'<rect width="{char_width:.2f}" height="{font_size:.2f}" fill="currentColor"><animate attributeName="y" from="12" to="{12+(len(rows)-1)*line_height:.2f}" dur="{duration:.2f}s" fill="freeze"/><animate attributeName="x" from="0" to="{max(total_width-char_width,0):.2f}" dur="{duration:.2f}s" fill="freeze"/></rect>')
    out.append("</svg>")
    output_path.write_text("\n".join(out), encoding="utf-8")
