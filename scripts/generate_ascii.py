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


# High-detail ASCII ramp.
RAMP = " .'`^\",:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


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

    return rgba.crop(
        (
            max(0, xs.min() - px),
            max(0, ys.min() - py),
            min(arr.shape[1], xs.max() + px + 1),
            min(arr.shape[0], ys.max() + py + 1),
        )
    )


def process_grayscale(rgba):
    arr = np.array(rgba)

    rgb = arr[:, :, :3].copy()
    alpha = arr[:, :, 3]

    # Transparent background becomes white.
    rgb[alpha < 8] = 255

    gray = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2GRAY
    )

    # Light smoothing while preserving facial features.
    gray = cv2.bilateralFilter(
        gray,
        5,
        18,
        18
    )

    # Local contrast enhancement.
    gray = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    ).apply(gray)

    # Preserve fine edges.
    blurred = cv2.GaussianBlur(
        gray,
        (0, 0),
        0.8
    )

    gray = cv2.addWeighted(
        gray,
        1.35,
        blurred,
        -0.35,
        0
    )

    # Preserve more mid-tone information.
    x = gray.astype(
        np.float32
    ) / 255.0

    x = np.power(
        x,
        1.12
    )

    return np.clip(
        x * 255.0,
        0,
        255
    ).astype(np.uint8)


def ascii_rows(gray, columns=180):
    h, w = gray.shape

    # Compensate for monospace character proportions.
    rows = max(
        1,
        round(
            columns
            * (h / w)
            * 0.48
        )
    )

    small = cv2.resize(
        gray,
        (columns, rows),
        interpolation=cv2.INTER_AREA
    )

    # Convert brightness to ASCII density.
    idx = np.rint(
        (255 - small)
        / 255.0
        * (len(RAMP) - 1)
    ).astype(int)

    idx = np.clip(
        idx,
        0,
        len(RAMP) - 1
    )

    return [
        "".join(
            RAMP[i]
            for i in row
        )
        for row in idx
    ]


def embedded_font(font_path):
    if not font_path.exists():
        return ""

    data = base64.b64encode(
        font_path.read_bytes()
    ).decode("ascii")

    return (
        f'''<style>@font-face {{'''
        f'''font-family:JBMonoEmbedded;'''
        f'''src:url(data:font/woff2;base64,{data}) '''
        f'''format("woff2");'''
        f'''font-weight:400;'''
        f'''font-style:normal;'''
        f'''}}</style>'''
    )


def generate_ascii_svg(
    source_path,
    output_path,
    columns=180,
    display_width=500,
    font_size=6.5
):
    image = Image.open(
        source_path
    ).convert("RGBA")

    subject = crop_subject(
        remove_background(image)
    )

    gray = process_grayscale(
        subject
    )

    rows = ascii_rows(
        gray,
        columns
    )

    font_path = (
        Path(__file__).resolve().parents[1]
        / "fonts"
        / "JetBrainsMono-Regular.woff2"
    )

    line_height = font_size * 1.03

    height = math.ceil(
        len(rows)
        * line_height
        + 14
    )

    char_width = font_size * 0.600

    total_width = (
        columns
        * char_width
    )

    # Typing animation.
    row_delay = 0.065

    duration = max(
        row_delay * len(rows),
        0.1
    )

    # Reduced brightness.
    PORTRAIT_COLOR = "#c4c8cc"

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',

        (
            f'<svg '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 '
            f'{total_width:.2f} '
            f'{height:.2f}" '
            f'width="{display_width}" '
            f'role="img" '
            f'aria-label="Animated ASCII portrait" '
            f'style="color:{PORTRAIT_COLOR};">'
        ),

        embedded_font(
            font_path
        ),

        "<defs>",
    ]

    # Row-by-row reveal animation.
    for i in range(len(rows)):
        y = 10 + i * line_height

        out.append(
            f'<clipPath id="r{i}">'
            f'<rect '
            f'x="0" '
            f'y="{y-line_height:.2f}" '
            f'width="0" '
            f'height="{line_height*1.5:.2f}">'
            f'<animate '
            f'attributeName="width" '
            f'from="0" '
            f'to="{total_width:.2f}" '
            f'dur="{row_delay:.3f}s" '
            f'begin="{i*row_delay:.3f}s" '
            f'fill="freeze"/>'
            f'</rect>'
            f'</clipPath>'
        )

    out.append("</defs>")

    # ASCII portrait.
    for i, row in enumerate(rows):
        y = 10 + i * line_height

        out.append(
            f'<text '
            f'x="0" '
            f'y="{y:.2f}" '
            f'font-family="JBMonoEmbedded,monospace" '
            f'font-size="{font_size}px" '
            f'xml:space="preserve" '
            f'clip-path="url(#r{i})" '
            f'fill="{PORTRAIT_COLOR}">'
            f'{html.escape(row)}'
            f'</text>'
        )

    # Typing cursor.
    out.append(
        f'<rect '
        f'width="{char_width:.2f}" '
        f'height="{font_size:.2f}" '
        f'fill="{PORTRAIT_COLOR}">'
        f'<animate '
        f'attributeName="y" '
        f'from="10" '
        f'to="{10+(len(rows)-1)*line_height:.2f}" '
        f'dur="{duration:.2f}s" '
        f'fill="freeze"/>'
        f'<animate '
        f'attributeName="x" '
        f'from="0" '
        f'to="{max(total_width-char_width,0):.2f}" '
        f'dur="{duration:.2f}s" '
        f'fill="freeze"/>'
        f'</rect>'
    )

    out.append("</svg>")

    output_path.write_text(
        "\n".join(out),
        encoding="utf-8"
    )