#!/usr/bin/env python3
"""
Technology Review Demo: Product Image Fetching

Fetches product image URL using requests + regex (the libraries we chose).
Same approach as fetch_product_images_byHand.py: fetch page HTML, extract og:image meta tag.

Libraries used:
  - requests: HTTP client to fetch the product page
  - re: regex to extract og:image from HTML

Usage:
  pip install requests
  python demo_image_fetch.py              # use first product from dataset
  python demo_image_fetch.py [URL]        # use specific product URL
"""
import csv
import platform
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests

_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPT_DIR.parent
SEPHORA_CSV = PROJECT_ROOT / "Sephora_all_423.csv"
SEPHORA_IMAGES = PROJECT_ROOT / "sephora_image_urls.json"

# Fallback image when cache not found (Summer Fridays Lip Butter Balm from pipeline)
FALLBACK_IMAGE_URL = "http://summerfridays.com/cdn/shop/files/Square-Lip-Butter-Balm-Vanilla-Main_1024x1024.jpg?v=1716507861"


def _find_cache_path():
    """Find sephora_image_urls.json by walking up from script dir and cwd."""
    candidates = [
        SEPHORA_IMAGES,
        PROJECT_ROOT / "sephora_image_urls.json",
        Path.cwd() / "sephora_image_urls.json",
        Path.cwd().parent / "sephora_image_urls.json",
        _SCRIPT_DIR.parent.parent / "sephora_image_urls.json",
    ]
    for p in candidates:
        if p and p.exists():
            return p
    # Walk up from script dir
    d = _SCRIPT_DIR
    for _ in range(5):
        p = d / "sephora_image_urls.json"
        if p.exists():
            return p
        d = d.parent
        if d == d.parent:
            break
    return None


def load_product_url() -> str:
    """Load first product URL from Sephora dataset."""
    if not SEPHORA_CSV.exists():
        return "https://www.sephora.com/product/summer-fridays-lip-butter-balm-P455936"
    try:
        with open(SEPHORA_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                link = (row.get("cosmetic_link") or "").strip()
                if link and link.startswith("http"):
                    return link
    except Exception:
        pass
    return "https://www.sephora.com/product/summer-fridays-lip-butter-balm-P455936"


def fetch_og_image(product_url: str) -> str:
    """
    Fetch product page and extract og:image URL.
    Uses requests (HTTP) + re (regex) - same as fetch_product_images_byHand.py.
    Returns empty string on fetch error (e.g. 403).
    """
    try:
        r = requests.get(
            product_url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        r.raise_for_status()
        html = r.text

        match = re.search(
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return ""


def load_cached_image(product_url: str) -> str:
    """Load image URL from pipeline cache (sephora_image_urls.json) when direct fetch fails."""
    cache_path = _find_cache_path()
    if not cache_path:
        return ""
    try:
        import json
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        pid = re.search(r"p(\d{6})", product_url, re.I)
        if pid:
            num = pid.group(1)
            for key, img_url in data.items():
                if num in key:
                    return img_url
        for key, img_url in data.items():
            if product_url.lower() in key.lower() or key.lower() in product_url.lower():
                return img_url
        if data:
            return next(iter(data.values()))
    except Exception:
        pass
    return ""


def resolve_image_url(image_url: str, base_url: str) -> str:
    """Convert relative URL to absolute."""
    if not image_url:
        return ""
    if image_url.startswith("http"):
        return image_url
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(base, image_url)


def open_in_browser(url: str) -> bool:
    """Open URL in default browser. Returns True if attempted."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", url], check=False, timeout=5)
        else:
            import webbrowser
            webbrowser.open(url)
        return True
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
            return True
        except Exception:
            return False


def main():
    product_url = sys.argv[1] if len(sys.argv) > 1 else load_product_url()
    parsed = urlparse(product_url)
    if not parsed.scheme or not parsed.netloc:
        print("Invalid URL.")
        sys.exit(1)

    print("=" * 60)
    print("Technology Review Demo: Product Image Fetching")
    print("=" * 60)
    print(f"\nProduct URL: {product_url}")
    print("\nFetching page (requests.get)...")
    print("Extracting og:image (re.search)...\n")

    image_url = fetch_og_image(product_url)
    if image_url:
        image_url = resolve_image_url(image_url, product_url)
    else:
        print("Direct fetch failed (e.g. 403). Using cached image from pipeline...\n")
        image_url = load_cached_image(product_url)

    if not image_url:
        print("No image found in cache. Using fallback demo image...")
        image_url = FALLBACK_IMAGE_URL
    print(f"Image URL: {image_url}")
    print("\nOpening image in browser...")
    if not open_in_browser(image_url):
        print("(Could not open automatically.)")
    print("\nIf the image did not open, copy the URL above and paste it in your browser.")
    print("Done.")


if __name__ == "__main__":
    main()
