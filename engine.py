"""GeoGlyph Engine — Stitch NASA Landsat letter images into a name."""

from PIL import Image, ImageDraw, ImageFont
import os
import json

WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "all")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Known variant counts per letter (from NASA's "Your Name in Landsat")
VARIANT_MAP = {
    'a': 5, 'b': 2, 'c': 3, 'd': 2, 'e': 4, 'f': 2, 'g': 1,
    'h': 2, 'i': 5, 'j': 3, 'k': 2, 'l': 4, 'm': 3, 'n': 3,
    'o': 2, 'p': 2, 'q': 2, 'r': 4, 's': 3, 't': 2, 'u': 2,
    'v': 4, 'w': 2, 'x': 3, 'y': 3, 'z': 2,
}


def max_variant(letter: str) -> int:
    """Get max variant index (0-based) for a letter."""
    return VARIANT_MAP.get(letter.lower(), 0) - 1


def image_for_char(char: str, variant: int = 0) -> Image.Image:
    """Load the satellite image for a letter and variant number."""
    c = char.lower()
    if c not in VARIANT_MAP:
        return Image.new("RGB", (500, 500), (20, 20, 20))

    v = min(variant, VARIANT_MAP[c] - 1)
    path = os.path.join(ASSETS_DIR, f"{c}_{v}.jpg")
    if not os.path.exists(path):
        return Image.new("RGB", (500, 500), (20, 20, 20))
    return Image.open(path).convert("RGB")


def apply_watermark(img: Image.Image, text: str = "geoglyph.earth") -> Image.Image:
    """Overlay a semi-transparent watermark in the bottom-right corner."""
    try:
        font = ImageFont.truetype(WATERMARK_FONT, size=36)
    except (IOError, OSError):
        font = ImageFont.load_default()

    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm)

    # Measure text width
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    padding = 20
    x = img.width - tw - padding - 16
    y = img.height - th - padding - 12

    # Dark pill background
    bg_w = tw + padding * 2 + 8
    bg_h = th + padding
    draw.rounded_rectangle(
        [x - 8, y - 6, x + bg_w, y + bg_h],
        radius=8,
        fill=(0, 0, 0, 140),
    )

    draw.text((x, y - 2), text, font=font, fill=(255, 255, 255, 200))

    return Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")


def make_square(img: Image.Image, size: int = 1080, bg_color=(10, 10, 15), branding: str = "") -> Image.Image:
    """Pad a horizontal letter image into a square with dark background.
    Optionally add branding text at the bottom.
    """
    # Calculate scaling so the letter row fits within the square with padding
    max_letter_w = size - 80  # 40px padding each side
    if img.width > max_letter_w:
        ratio = max_letter_w / img.width
        new_h = int(img.height * ratio)
        img = img.resize((int(img.width * ratio), new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (size, size), bg_color)

    # Center the image horizontally, position at ~30% from top
    x = (size - img.width) // 2
    y = int(size * 0.20)
    canvas.paste(img, (x, y))

    # Add branding at bottom
    if branding:
        try:
            font = ImageFont.truetype(WATERMARK_FONT, size=28)
        except (IOError, OSError):
            font = ImageFont.load_default()
        draw = ImageDraw.Draw(canvas)
        bbox = draw.textbbox((0, 0), branding, font=font)
        tw = bbox[2] - bbox[0]
        bx = (size - tw) // 2
        by = size - 60
        draw.text((bx, by), branding, font=font, fill=(100, 100, 100, 180))

    return canvas


def generate(
    name: str,
    variants: dict[str, int] | None = None,
    height: int = 1200,
    watermarked: bool = False,
    square: int | None = None,
) -> Image.Image:
    """Stitch letter images for a name into a single image.

    Args:
        name: The text to render.
        variants: Optional dict of letter→variant_index overrides.
        height: Target height in pixels for each letter image (default 1200).
        watermarked: If True, overlay 'geoglyph.earth' watermark.
        square: If set, pad to this size (e.g. 1080) with branding.
    """
    name = name.strip().lower()
    if not name:
        raise ValueError("Name cannot be empty")

    variants = variants or {}

    images = []
    for c in name:
        v = variants.get(c, 0)
        img = image_for_char(c, v)
        if img.height != height:
            ratio = height / img.height
            new_w = int(img.width * ratio)
            img = img.resize((new_w, height), Image.LANCZOS)
        images.append(img)

    max_h = max(img.height for img in images)
    total_w = sum(img.width for img in images)
    canvas = Image.new("RGB", (total_w, max_h), (10, 10, 15))

    x = 0
    for img in images:
        canvas.paste(img, (x, 0))
        x += img.width

    if square:
        canvas = make_square(canvas, size=square, branding="geoglyph.earth")

    if watermarked and not square:
        canvas = apply_watermark(canvas)

    return canvas


def generate_and_save(name: str, variants: dict[str, int] | None = None) -> str:
    """Generate and save to disk. Returns the output path."""
    img = generate(name, variants)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ") or "unnamed"
    out_path = os.path.join(OUTPUT_DIR, f"{safe_name.strip().replace(' ', '_')}.jpg")
    img.save(out_path, "JPEG", quality=95)
    return out_path
