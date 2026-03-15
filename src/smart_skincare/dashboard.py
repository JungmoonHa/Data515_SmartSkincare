"""
Demo dashboard: select profile then get ingredient-based product recommendations.

Run from project root: python src/smart_skincare/dashboard.py
Then open: http://127.0.0.1:5001 (default port 5001; use PORT=5000 if you want 5000)

Product images: loaded from cosmetics_image_urls.json (key: normalized "brand name")
and sephora_image_urls.json (key: product_url). Populate with fetch_product_images_byHand.py.
"""
import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request

# Import from parent so run from project root (cwd = smartskincare)
from recommend_mvp import get_top_products, user_input_to_profile

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "cache"

COSMETICS_IMAGES_PATH = CACHE_DIR / "cosmetics_image_urls.json"
SEPHORA_IMAGES_PATH = CACHE_DIR / "sephora_image_urls.json"

_image_caches = {"cosmetics": None, "sephora": None}


def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return " ".join(str(s).strip().lower().split())


def _load_image_url(key: str, source: str) -> str:
    """Resolve image URL: cosmetics → normalized brand+name; sephora → product_url."""
    global _image_caches
    if _image_caches["cosmetics"] is None and COSMETICS_IMAGES_PATH.exists():
        try:
            _image_caches["cosmetics"] = json.loads(COSMETICS_IMAGES_PATH.read_text(encoding="utf-8"))
        except Exception:
            _image_caches["cosmetics"] = {}
    if _image_caches["sephora"] is None and SEPHORA_IMAGES_PATH.exists():
        try:
            _image_caches["sephora"] = json.loads(SEPHORA_IMAGES_PATH.read_text(encoding="utf-8"))
        except Exception:
            _image_caches["sephora"] = {}
    if source == "cosmetics":
        m = _image_caches["cosmetics"] or {}
        return (m.get(key) or "").strip()
    if source == "sephora":
        m = _image_caches["sephora"] or {}
        return (m.get(key) or "").strip()
    return ""


def _serialize_item(item):
    """Make recommendation item JSON-serializable."""
    p = item.get("product") or {}
    brand = p.get("brand") or ""
    name = p.get("name") or ""
    source = p.get("source") or "cosmetics"
    image_url = ""
    if source == "cosmetics":
        image_url = _load_image_url(_normalize(brand + " " + name), "cosmetics")
    elif source == "sephora":
        product_url = (p.get("product_url") or "").strip()
        if product_url:
            image_url = _load_image_url(product_url, "sephora")
        if not image_url:
            image_url = _load_image_url(_normalize(brand + " " + name), "sephora")
    return {
        "product": {
            "id": p.get("id"),
            "brand": brand,
            "name": name,
            "rating": float(p.get("rating") or 0),
            "ingredients": p.get("ingredients") or [],
            "image_url": image_url or None,
        },
        "score": round(float(item.get("score") or 0), 2),
        "base_score": round(float(item.get("base_score") or 0), 2),
        "review_contribution": round(float(item.get("review_contribution") or 0), 2),
        "key_ingredients": item.get("key_ingredients") or [],
        "key_ingredients_why": [(str(a), str(b)) for a, b in (item.get("key_ingredients_why") or [])],
        "key_by_type": item.get("key_by_type") or {},
        "avoid_ingredients": [(str(a), str(b)) for a, b in (item.get("avoid_ingredients") or [])],
    }


@app.route("/")
def index():
    with open(ROOT / "templates" / "dashboard_index.html", encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html; charset=utf-8")


@app.route("/api/profile", methods=["POST"])
def api_profile():
    """Build 6-type profile from form-like inputs."""
    data = request.get_json() or {}
    profile = user_input_to_profile(
        hydration_level=data.get("hydration_level", "normal"),
        oil_level=data.get("oil_level", "normal"),
        sensitivity=data.get("sensitivity", "normal"),
        age=data.get("age"),
        concerns=data.get("concerns"),
    )
    return jsonify(profile)


@app.route("/api/recommend", methods=["GET", "POST"])
def api_recommend():
    """Get top N recommendations for a 6-type profile."""
    if request.method == "POST":
        data = request.get_json() or {}
        profile = data.get("profile")
        if not profile:
            return jsonify({"error": "Missing profile"}), 400
    else:
        profile = {
            "dry": float(request.args.get("dry", 0)),
            "normal": float(request.args.get("normal", 0)),
            "oily": float(request.args.get("oily", 0)),
            "pigmentation": float(request.args.get("pigmentation", 0)),
            "sensitive": float(request.args.get("sensitive", 0)),
            "wrinkle": float(request.args.get("wrinkle", 0)),
        }
        if all(profile[k] == 0 for k in profile):
            profile["normal"] = 0.5

    n = int(request.args.get("n", 30) if request.method == "GET" else (request.get_json() or {}).get("n", 30))
    n = min(max(n, 1), 50)

    try:
        top = get_top_products(profile, n=n)
        return jsonify({
            "profile": profile,
            "items": [_serialize_item(x) for x in top],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
