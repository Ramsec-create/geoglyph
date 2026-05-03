"""GeoGlyph Engine — Stitch NASA Landsat letter images into a name."""

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps
import os
import json
import numpy as np

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


def apply_filter(img: Image.Image, filter_name: str | None) -> Image.Image:
    """Apply CSS-matching filter effects via Pillow.

    Mirrors the CSS filter classes in the frontend:
    - natural / None: no change
    - infrared: saturate(3) hue-rotate(-20deg) contrast(1.2)
    - thermal: invert(0.85) sepia(0.6) saturate(1.5) contrast(1.1)
    - contrast: contrast(1.6) saturate(1.3) brightness(1.1)
    - grayscale: grayscale(1)
    - falsecolor: saturate(2.5) hue-rotate(100deg)
    """
    if not filter_name or filter_name == "natural":
        return img

    img = img.copy()

    if filter_name == "grayscale":
        return ImageOps.grayscale(img).convert("RGB")

    if filter_name == "contrast":
        img = ImageEnhance.Contrast(img).enhance(1.6)
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.1)
        return img

    if filter_name == "infrared":
        img = ImageEnhance.Color(img).enhance(3.0)
        img = _hue_rotate(img, -20)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        return img

    if filter_name == "thermal":
        img = _invert_blend(img, 0.85)
        img = _sepia(img, 0.6)
        img = ImageEnhance.Color(img).enhance(1.5)
        img = ImageEnhance.Contrast(img).enhance(1.1)
        return img

    if filter_name == "falsecolor":
        img = ImageEnhance.Color(img).enhance(2.5)
        img = _hue_rotate(img, 100)
        return img

    return img


def _hue_rotate(img: Image.Image, degrees: float) -> Image.Image:
    """Rotate the hue channel by degrees."""
    arr = np.array(img.convert("HSV"), dtype=np.uint8)
    h = arr[:, :, 0].astype(np.int16)
    shift = int(degrees * 255 / 360)
    h = (h + shift + 256) % 256
    arr[:, :, 0] = h.astype(np.uint8)
    return Image.fromarray(arr, "HSV").convert("RGB")


def _invert_blend(img: Image.Image, factor: float = 1.0) -> Image.Image:
    """Blend with inverted version (like CSS invert filter)."""
    inverted = ImageOps.invert(img.convert("RGB"))
    return Image.blend(img, inverted, factor)


def _sepia(img: Image.Image, factor: float = 1.0) -> Image.Image:
    """Apply sepia tone blended with original."""
    gray = ImageOps.grayscale(img)
    sepia = Image.merge("RGB", (
        gray.point(lambda x: min(int(x * 1.2), 255)),
        gray.point(lambda x: min(int(x * 1.08), 255)),
        gray.point(lambda x: min(int(x * 0.76), 255)),
    ))
    return Image.blend(img, sepia, factor)


def load_locations() -> dict:
    """Load location metadata from locations.json."""
    loc_path = os.path.join(os.path.dirname(__file__), "locations.json")
    if not os.path.exists(loc_path):
        return {}
    with open(loc_path) as f:
        return json.load(f)


_LOCATIONS_CACHE: dict | None = None


def location_for_file(filename: str) -> tuple[str, str] | None:
    """Get (title, coords) for a letter filename like 'a_0.jpg'."""
    global _LOCATIONS_CACHE
    if _LOCATIONS_CACHE is None:
        _LOCATIONS_CACHE = load_locations()
    entry = _LOCATIONS_CACHE.get(filename)
    if entry:
        return entry.get("title", ""), entry.get("coords", "")
    return None


def overlay_location_label(img: Image.Image, title: str, coords: str) -> Image.Image:
    """Draw a semi-transparent label bar at the bottom with location info."""
    bar_height = max(36, img.height // 25)
    overlay = Image.new("RGBA", (img.width, bar_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Dark semi-transparent bar
    draw.rectangle([(0, 0), (img.width, bar_height)], fill=(0, 0, 0, 160))

    try:
        title_font = ImageFont.truetype(WATERMARK_FONT, size=max(12, bar_height // 3))
        coord_font = ImageFont.truetype(WATERMARK_FONT, size=max(10, bar_height // 4))
    except (IOError, OSError):
        title_font = ImageFont.load_default()
        coord_font = title_font

    # Title (place name) — left-aligned with padding
    padding = 8
    draw.text((padding, 3), title, font=title_font, fill=(255, 255, 255, 230))

    # Coord string — right-aligned, smaller
    cb = draw.textbbox((0, 0), coords, font=coord_font)
    cw = cb[2] - cb[0]
    draw.text((img.width - cw - padding, 3), coords, font=coord_font, fill=(200, 200, 200, 180))

    # Compose onto the full image
    img_rgba = img.convert("RGBA")
    img_rgba.paste(overlay, (0, img.height - bar_height), overlay)
    return img_rgba.convert("RGB")


def apply_watermark(img: Image.Image, text: str = "leadvector.sh — Automated Lead Pipeline") -> Image.Image:
    """Overlay a semi-transparent branding band at the bottom of the image.

    The band is positioned at the bottom edge, spanning the full image width,
    making it hard to crop out without losing tile content.
    """
    try:
        font = ImageFont.truetype(WATERMARK_FONT, size=30)
    except (IOError, OSError):
        font = ImageFont.load_default()

    band_height = 56
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm)

    # Full-width dark bar at bottom
    draw.rectangle(
        [0, img.height - band_height, img.width, img.height],
        fill=(0, 0, 0, 160),
    )

    # Centered text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (img.width - tw) // 2
    y = img.height - band_height + (band_height - (bbox[3] - bbox[1])) // 2 - 2
    draw.text((x, y), text, font=font, fill=(200, 200, 200, 220))

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
    filter_name: str | None = None,
    letter_filters: dict[str, str] | None = None,
    show_locations: bool = False,
) -> Image.Image:
    """Stitch letter images for a name into a single image.

    Args:
        name: The text to render.
        variants: Optional dict of letter→variant_index overrides.
        height: Target height in pixels for each letter image (default 1200).
        watermarked: If True, overlay 'leadvector.sh' watermark.
        square: If set, pad to this size (e.g. 1080) with branding.
        filter_name: Global filter to apply (natural, contrast, infrared, etc.).
        letter_filters: Per-letter filter overrides {letter: filter_name}.
        show_locations: If True, overlay location place names on each tile.
    """
    name = name.strip().lower()
    if not name:
        raise ValueError("Name cannot be empty")

    variants = variants or {}
    letter_filters = letter_filters or {}

    images = []
    for c in name:
        v = variants.get(c, 0)
        img = image_for_char(c, v)
        if img.height != height:
            ratio = height / img.height
            new_w = int(img.width * ratio)
            img = img.resize((new_w, height), Image.LANCZOS)
        # Apply per-letter filter override, else global, else none
        lf = letter_filters.get(c, filter_name or "")
        if lf and lf != "natural":
            img = apply_filter(img, lf)
        # Overlay location label if requested
        if show_locations:
            loc = location_for_file(f"{c}_{v}.jpg")
            if loc:
                img = overlay_location_label(img, loc[0], loc[1])
        images.append(img)

    max_h = max(img.height for img in images)
    total_w = sum(img.width for img in images)
    canvas = Image.new("RGB", (total_w, max_h), (10, 10, 15))

    x = 0
    for img in images:
        canvas.paste(img, (x, 0))
        x += img.width

    if square:
        canvas = make_square(canvas, size=square, branding="leadvector.sh — Automated Lead Pipeline")

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
