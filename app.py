"""GeoGlyph — FastAPI app with shuffle interaction, watermark, and share."""

import io
import json
import os
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from engine import generate, VARIANT_MAP

LOCATIONS_PATH = Path(__file__).parent / "locations.json"
_LOCATIONS_CACHE = None


def _get_locations():
    global _LOCATIONS_CACHE
    if _LOCATIONS_CACHE is None:
        _LOCATIONS_CACHE = json.loads(LOCATIONS_PATH.read_text())
    return _LOCATIONS_CACHE

ASSETS_ALL = Path(__file__).parent / "assets" / "all"
STATIC_DIR = Path(__file__).parent / "static"
OUTPUT_DIR = Path(__file__).parent / "output"

STATIC_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_ALL.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="GeoGlyph", description="Spell names with NASA Landsat satellite imagery")



@app.get("/", response_class=HTMLResponse)
async def home():
    html = (Path(__file__).parent / "templates" / "index.html").read_text()
    return HTMLResponse(html)


@app.get("/variants")
async def get_variants():
    """Return variant count for every letter as JSON."""
    return JSONResponse(VARIANT_MAP)


@app.get("/locations")
async def get_locations():
    """Return location data for all letter variants as JSON."""
    return JSONResponse(_get_locations())


@app.get("/letter/{letter}")
async def get_letter_image(letter: str, v: int = Query(0, ge=0, description="Variant index")):
    """Serve a specific letter variant image."""
    lc = letter.lower()
    if lc not in VARIANT_MAP:
        return Response("Letter not supported", status_code=404)

    max_v = VARIANT_MAP[lc] - 1
    variant = min(v, max_v)
    fname = f"{lc}_{variant}.jpg"
    path = ASSETS_ALL / fname
    if not path.exists():
        return Response("Variant not found", status_code=404)
    return FileResponse(str(path), media_type="image/jpeg")


@app.get("/generate")
async def generate_image(
    name: str = Query(..., min_length=1, max_length=50, description="Name to render"),
    variants: str | None = Query(None, description='JSON string of letter→variant choices, e.g. {"a":2,"b":0}'),
    height: int = Query(1200, ge=200, le=4000, description="Output height in pixels per letter"),
    watermarked: bool = Query(True, description="Apply watermark overlay"),
    format: str = Query("standard", regex="^(standard|square)$", description="Output format: standard=horizontal, square=1080x1080"),
    filter: str = Query("infrared", description="Global CSS filter to apply (natural, contrast, infrared, thermal, grayscale, falsecolor)"),
    letter_filters: str | None = Query(None, description='Per-letter filter overrides JSON, e.g. {"a":"infrared","b":"thermal"}'),
    show_locations: bool = Query(False, description="Overlay location place names on each letter tile"),
):
    """Generate satellite name image. Watermark controlled by the `watermarked` flag."""
    cleaned = "".join(c for c in name if c.isalpha() or c == " ")
    if not cleaned.strip():
        return Response("Invalid name — only letters and spaces allowed", status_code=400)

    variant_dict = {}
    if variants:
        try:
            variant_dict = json.loads(variants)
        except (json.JSONDecodeError, TypeError):
            return Response("Invalid variants JSON", status_code=400)

    letter_filter_dict = {}
    if letter_filters:
        try:
            letter_filter_dict = json.loads(letter_filters)
        except (json.JSONDecodeError, TypeError):
            return Response("Invalid letter_filters JSON", status_code=400)

    should_watermark = watermarked

    # Decide square output
    square_size = 1080 if format == "square" else None

    img = generate(cleaned, variant_dict, height=height, watermarked=should_watermark, square=square_size, filter_name=filter, letter_filters=letter_filter_dict, show_locations=show_locations)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    buf.seek(0)

    safe_filename = "".join(c for c in cleaned if c.isalnum() or c in "_- ").strip().replace(" ", "_")
    suffix = "_share" if format == "square" else ""
    return Response(
        content=buf.getvalue(),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}{suffix}.jpg"',
            "Cache-Control": "no-cache",
        },
    )
