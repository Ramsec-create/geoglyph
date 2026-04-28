"""GeoGlyph — FastAPI app with shuffle interaction, watermark, share, and payments."""

import io
import json
import os
import uuid
from pathlib import Path

from dodopayments import DodoPayments
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

# Dodo Payments config
DODO_API_KEY = os.environ.get("DODO_PAYMENTS_API_KEY", "")
DODO_PRODUCT_ID = os.environ.get("DODO_PRODUCT_ID", "")
DODO_ENV = os.environ.get("DODO_ENVIRONMENT", "test_mode")

# In-memory payment records (replace with DB in production)
_paid_sessions: dict[str, bool] = {}


@app.get("/", response_class=HTMLResponse)
async def home():
    html = (Path(__file__).parent / "templates" / "index.html").read_text()
    return HTMLResponse(html)


@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Create a Dodo Payments Checkout Session for HD unlock ($4)."""
    body = await request.json()
    token = body.get("session_token") or str(uuid.uuid4())

    if DODO_API_KEY and DODO_PRODUCT_ID:
        try:
            client = DodoPayments(
                bearer_token=DODO_API_KEY,
                environment=DODO_ENV,
            )
            return_url = str(request.url_for("payment_success")) + f"?session_token={token}"
            session = client.checkout_sessions.create(
                product_cart=[{
                    "product_id": DODO_PRODUCT_ID,
                    "quantity": 1,
                }],
                return_url=return_url,
                cancel_url=str(request.url_for("home")),
                metadata={"session_token": token},
            )
            return JSONResponse({"url": session.checkout_url, "session_token": token, "mock": False})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    else:
        return JSONResponse({
            "url": str(request.url_for("payment_success")) + f"?session_token={token}&session_id=mock_dev",
            "session_token": token,
            "mock": True,
        })


@app.get("/payment-success")
async def payment_success(request: Request, session_token: str, session_id: str = ""):
    """Handle Dodo Payments redirect after payment. Marks session as paid."""
    # In production, optionally verify the session via Dodo API
    # GET /checkouts/{session_id} to check status
    if session_id == "mock_dev" or session_token:
        _paid_sessions[session_token] = True
        html = f"""<!DOCTYPE html><html><head><title>Payment Successful</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{background:#0a0a0f;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;}}</style>
</head><body>
<div>
<h2 style="color:#4caf50">Payment Successful!</h2>
<p>Your HD download is now unlocked. You can close this tab and go back to GeoGlyph.</p>
<script>
  if (window.opener) {{
    window.opener.postMessage({{type:'geoglyph-paid', sessionToken:'{session_token}'}}, '*');
  }}
  setTimeout(() => window.close(), 3000);
</script>
</div></body></html>"""
        return HTMLResponse(html)
    return HTMLResponse("<h2>Payment could not be verified.</h2>", status_code=400)


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
    session_token: str | None = Query(None, description="Paid session token (removes watermark)"),
    filter: str | None = Query(None, description="Global CSS filter to apply (natural, contrast, infrared, thermal, grayscale, falsecolor)"),
    letter_filters: str | None = Query(None, description='Per-letter filter overrides JSON, e.g. {"a":"infrared","b":"thermal"}'),
):
    """Generate satellite name image. Free tier gets watermarked; paid tier can get clean."""
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

    # Check if this session has paid
    is_paid = session_token and _paid_sessions.get(session_token, False)

    # Free users always get watermarked; paid can opt out
    should_watermark = watermarked and not is_paid

    # Decide square output
    square_size = 1080 if format == "square" else None

    img = generate(cleaned, variant_dict, height=height, watermarked=should_watermark, square=square_size, filter_name=filter, letter_filters=letter_filter_dict)
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
