"""Comic panel assembler — combines individual panels into a comic grid."""

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


PANEL_W, PANEL_H = 512, 512
BORDER, MARGIN, PADDING = 4, 8, 20
TITLE_H = 80


def assemble_comic(panels: list[tuple[bytes, str]], title: str, num_panels: int) -> bytes:
    """Assemble panels into a combined comic grid. Returns PNG bytes."""
    if num_panels <= 6:
        cols, rows = 2, 3
    elif num_panels <= 9:
        cols, rows = 3, 3
    elif num_panels <= 12:
        cols, rows = 3, 4
    else:
        cols = 3
        rows = (num_panels + 2) // 3

    pw = PANEL_W + 2 * BORDER
    ph = PANEL_H + 2 * BORDER
    cw = cols * pw + (cols - 1) * MARGIN + 2 * PADDING
    ch = TITLE_H + rows * ph + (rows - 1) * MARGIN + 2 * PADDING

    comic = Image.new("RGB", (cw, ch), (24, 24, 27))
    draw = ImageDraw.Draw(comic)

    # Title
    try:
        tf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
    except Exception:
        tf = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), title, font=tf)
    draw.text(((cw - bbox[2]) // 2, 25), title, fill=(255, 255, 255), font=tf)

    # Dialogue font
    try:
        df = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        df = ImageFont.load_default()

    for i, (img_bytes, dialogue) in enumerate(panels):
        row, col = i // cols, i % cols
        img = Image.open(BytesIO(img_bytes)).convert("RGB").resize((PANEL_W, PANEL_H))

        bordered = Image.new("RGB", (pw, ph), (0, 0, 0))
        bordered.paste(img, (BORDER, BORDER))

        x = PADDING + col * (pw + MARGIN)
        y = TITLE_H + PADDING + row * (ph + MARGIN)
        comic.paste(bordered, (x, y))

        if dialogue:
            _draw_bubble(draw, dialogue, x, y, pw, ph, df)

    buf = BytesIO()
    comic.save(buf, format="PNG", quality=95)
    return buf.getvalue()


def _draw_bubble(draw, text, px, py, pw, ph, font, bh=140):
    words = text.split()
    max_w = pw - 30
    lines, cur = [], []
    for w in words:
        t = " ".join(cur + [w])
        if draw.textbbox((0, 0), t, font=font)[2] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    if not lines:
        return

    x, y = px + 10, py + ph - bh - 10
    bw = pw - 20
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=10, fill=(255, 255, 255, 245), outline=(0, 0, 0), width=2)
    tx = x + bw // 3
    draw.polygon([(tx, y), (tx + 15, y), (tx + 7, y - 12)], fill=(255, 255, 255), outline=(0, 0, 0))

    line_h = font.size + 4
    total_h = len(lines) * line_h
    sy = y + (bh - total_h) // 2
    for i, line in enumerate(lines):
        draw.text((x + 10, sy + i * line_h), line, fill=(0, 0, 0), font=font)
