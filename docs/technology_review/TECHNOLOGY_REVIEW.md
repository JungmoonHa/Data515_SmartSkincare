# Technology Review: Web Scraping for Product Image Fetching

**Smart Skincare Project**  
DATA 515 — Software Design for Data Scientists  
Technology Review Assignment

---

## 1. Background and Problem Statement

### 1.1 Project Context

Smart Skincare is a cosmetics recommendation system that suggests products based on user skin type (dry, oily, pigmentation, sensitive, wrinkle). The system uses ingredient-based scoring. Each product's ingredients are matched against an ingredient-skin-type map, and products are ranked by compatibility with the user's profile.

During development, we faced three main technology choices:

1. **Ingredient data source** — Where to get detailed ingredient information (skin-type fit, effects, synonyms)  
   - *Decision:* Paula CSV + PubChem API (urllib) + INCI Decoder (urllib scraping) + manual curation. No dedicated scraping library; standard library only.

2. **Product image fetching** — How to obtain product images for the recommendation UI  
   - *Decision:* Serper API (search) + HTTP client + HTML parsing to extract `og:image`. **This review focuses on this choice.**

3. **Recommendation algorithm** — How to score and rank products  
   - *Decision:* Custom scoring logic (profile weights × ingredient map × Paula rating × INCI order bonus). No external library used; excluded from this review.

### 1.2 Technology Need

Our product data (`cosmetics.csv`, `Sephora_all_423.csv`) includes brand, name, ingredients, and URLs, but **not product images**. To show product cards in the dashboard, we need to:

1. **Search** for product pages (e.g., by "brand + product name")
2. **Fetch** the HTML of candidate pages
3. **Extract** the main product image (typically via `og:image` meta tags or image search results)

This requires:

- **HTTP client** — To call search APIs and fetch web pages
- **HTML parsing** — To extract `og:image` or other image URLs from HTML (regex or parser)

We need a Python library (or combination) that:

- Works with Python 3
- Integrates with our existing pipeline (Serper API for search, JSON output)
- Is easy to use and maintain
- Handles our scale (~3.6k products, with rate limiting)
- Avoids known bugs that would block our use case

---

## 2. Candidate Libraries

### 2.1 Option A: requests + regex (current implementation)

| Attribute | Details |
|-----------|---------|
| **Name** | requests, re (standard library) |
| **Authors** | Kenneth Reitz (requests), Python standard library |
| **License** | Apache 2.0 (requests), PSF (re) |
| **Summary** | `requests` is the standard HTTP client for Python. For simple `og:image` extraction, we use `re` (regex) instead of a full HTML parser. |
| **Install** | `pip install requests` |

**Use case fit:**  
- `requests`: Call Serper API (POST), fetch product pages (GET)  
- `re`: Extract `og:image` from HTML via regex (simple meta tag pattern)  

**Note:** `BeautifulSoup4` is in `requirements.txt` and imported in `fetch_product_images_byHand.py`, but the actual `og:image` extraction uses regex. BeautifulSoup is available for more complex parsing if needed.

### 2.2 Option B: requests + BeautifulSoup4

| Attribute | Details |
|-----------|---------|
| **Name** | requests, BeautifulSoup4 |
| **Authors** | Kenneth Reitz (requests), Leonard Richardson (BeautifulSoup) |
| **License** | Apache 2.0 (requests), MIT (BeautifulSoup) |
| **Summary** | `requests` for HTTP; `BeautifulSoup4` parses HTML/XML and provides a simple API for navigating and querying the document. |
| **Install** | `pip install requests beautifulsoup4` |

**Use case fit:**  
- `requests`: Call Serper API (POST), fetch product pages (GET)  
- `BeautifulSoup4`: Parse HTML to extract `og:image` meta tags or image URLs  

### 2.3 Option C: Scrapy

| Attribute | Details |
|-----------|---------|
| **Name** | Scrapy |
| **Authors** | Scrapy developers (Zyte, community) |
| **License** | BSD |
| **Summary** | `Scrapy` is a full web scraping framework. It includes spiders, pipelines, middleware, scheduling, and rate limiting. It is designed for large-scale crawling and structured data extraction. |
| **Install** | `pip install scrapy` |

**Use case fit:**  
- Spiders can be defined to crawl search results and product pages  
- Built-in pipelines for extracting and storing image URLs  
- Built-in rate limiting and retry logic  

---

## 3. Side-by-Side Comparison

We implemented the same task (fetch a URL and extract `og:image`) with each option and compared them.

### 3.1 Task: Fetch Product Page and Extract og:image

**Input:** A product page URL (e.g., Sephora product page)  
**Output:** The `og:image` URL if present, or empty string

### 3.2 Implementation Comparison

#### Option A: requests + regex (current project implementation)

```python
import re
import requests

def fetch_og_image(url: str) -> str:
    r = requests.get(
        url,
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SmartSkincare/1.0)"},
    )
    r.raise_for_status()
    html = r.text
    m = re.search(
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    return m.group(1).strip() if m else ""
```

#### Option B: requests + BeautifulSoup4

```python
import requests
from bs4 import BeautifulSoup

def fetch_og_image_requests(url: str) -> str:
    r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (compatible; SmartSkincare/1.0)"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.find("meta", property="og:image")
    return meta["content"] if meta and meta.get("content") else ""
```

#### Option C: Scrapy

```python
# Scrapy requires a Spider class and project structure
# Simplified for comparison:
import scrapy
from scrapy.crawler import CrawlerProcess

class OgImageSpider(scrapy.Spider):
    name = "og_image"
    def start_requests(self):
        yield scrapy.Request(self.url, callback=self.parse)
    def parse(self, response):
        og = response.css('meta[property="og:image"]::attr(content)').get()
        return {"og_image": og or ""}
# Requires process.start() and process.join() - more setup
```

### 3.3 Comparison Table

| Criterion | requests + regex | requests + BeautifulSoup | Scrapy |
|-----------|------------------|--------------------------|--------|
| **Python 3** | O | O | O |
| **Ease of use** | Very simple | Simple | Requires Spider, project structure |
| **Learning curve** | Low | Low | Medium–High |
| **Lines of code (our task)** | ~6 | ~8 | ~20+ (Spider + runner) |
| **Serper API integration** | Direct `requests.post()` | Direct `requests.post()` | Custom middleware or separate script |
| **HTTP/2** | X | X | Optional |
| **Async support** | X | X (need grequests) | O (built-in) |
| **Rate limiting** | Manual (`time.sleep`) | Manual | Built-in |
| **Memory (small scale)** | Low | Low | Higher (framework overhead) |
| **Dependencies** | 1 package | 2 packages | 1 package (many transitive deps) |
| **Maturity** | Very mature | Very mature | Mature |
| **Known issues** | Blocking I/O | Blocking I/O | Heavier for simple tasks |

### 3.4 Performance

For our scale (~3.6k products, 1.5s delay between requests per `fetch_product_images_byHand.py`), the **bottleneck is rate limiting**, not the HTTP client or parsing method. All options perform similarly under this constraint. Comparative benchmarks (e.g., requests vs httpx vs Scrapy for concurrent fetches) would only matter if we relaxed rate limits, which we do not.

---

## 4. Final Choice: requests + regex

We chose **requests** for HTTP and **regex** (`re`) for `og:image` extraction for the following reasons:

1. **Alignment with actual implementation**

   - Our flow in `fetch_product_images_byHand.py` is: Serper API (search) → fetch candidate URLs → extract `og:image` via regex or fallback to image search.
   - For the simple `og:image` meta tag, regex is sufficient and avoids an extra dependency for this specific task.

2. **Compatibility**

   - `requests` works with Python 3 and is widely used.
   - Flask and our other dependencies already use `requests`; adding another HTTP client would add unnecessary complexity.
   - `re` is part of the standard library; no extra install.

3. **Ease of use**

   - Simple, synchronous API. `requests.get()` and `re.search()` are easy to read and debug.
   - No need for Spider classes or project structure, unlike Scrapy.

4. **Scale**

   - Our rate limit (1.5s between requests) dominates total time; HTTP client and parsing performance are not the bottleneck.
   - Async (httpx) or Scrapy would help only if we removed or relaxed rate limits, which we do not want.

5. **Stability**

   - `requests` and `re` are mature and well-documented.
   - We avoid known bugs that would affect our use case (og:image extraction).

6. **Maintainability**

   - Minimal dependencies for this task.
   - Easy for future teammates to understand and modify.

**Note:** `BeautifulSoup4` remains in `requirements.txt` for potential future use (e.g., more complex HTML parsing). The current `og:image` extraction path uses regex only.

---

## 5. Drawbacks and Concerns

### 5.1 Drawbacks of Our Choice

1. **Blocking I/O**

   - Requests are synchronous. For many concurrent fetches, we would need threading or multiprocessing.
   - For our current rate-limited setup, this is acceptable.

2. **No HTTP/2**

   - `requests` does not support HTTP/2. Some sites may prefer HTTP/2, but for our use case it has not caused issues.

3. **Manual rate limiting**

   - We must implement `time.sleep()` ourselves. Scrapy provides this out of the box.
   - We mitigate this with clear constants (`REQUEST_DELAY_SEC = 1.5`) and comments in the code.

4. **Regex for HTML**

   - Regex can be fragile for complex HTML. For the simple `og:image` meta tag pattern, it works reliably.
   - If we need to parse more complex structures, we would use BeautifulSoup (already in requirements).

### 5.2 Alternatives Considered

- **requests + BeautifulSoup**: Could replace regex for consistency with a full parser; we kept regex for simplicity.
- **Scrapy**: Would be more appropriate if we later add large-scale crawling (e.g., multiple sites, many pages per product).
- **urllib (standard library)**: Used in `match_pipeline.py` for PubChem and INCI Decoder. For consistency we could have used `urllib` for product images too, but `requests` is simpler and more readable for our use case.

---

## 6. References

- [requests documentation](https://requests.readthedocs.io/)
- [Python re module](https://docs.python.org/3/library/re.html)
- [BeautifulSoup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Scrapy documentation](https://docs.scrapy.org/)
- [Serper API](https://serper.dev/) — Google search API used for product search

---

## 7. Demo

The demo script `demo_image_fetch.py` fetches a product image using **requests + regex** (our chosen approach). Run:

```bash
cd docs/technology_review
pip install requests
python demo_image_fetch.py
```

Output: product URL → fetch page → extract og:image → open image in browser.
