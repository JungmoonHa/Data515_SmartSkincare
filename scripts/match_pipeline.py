"""
Smart Skincare - Matching pipeline
1. Keep Paula direct matches
2. Rematch via PubChem synonyms (Paula-unmatched ingredients -> PubChem synonyms -> match to Paula)
3. Remaining ingredients: check Paula linkability via pre_alternatives
"""
import csv
import re
import json
import time
from pathlib import Path
from collections import defaultdict

try:
    import difflib
except Exception:
    difflib = None

try:
    import urllib.request
    import urllib.parse
    import urllib.error
    import ssl
    _HAS_URLLIB = True
except Exception:
    _HAS_URLLIB = False

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
PUBCHEM_CACHE_PATH = CACHE_DIR / "pubchem_synonyms_cache.json"

try:
    from ingredient_canonical import (
        canonicalize_ingredient,
        merge_aliases_from_matching_results,
    )
except Exception:
    canonicalize_ingredient = None
    merge_aliases_from_matching_results = lambda *a, **k: {}
PUBCHEM_COMPOUND_CACHE_PATH = CACHE_DIR / "pubchem_compound_info_cache.json"  # NCBI info for unmatched ingredients
INCIDECODER_CACHE_PATH = CACHE_DIR / "incidecoder_cache.json"  # https://incidecoder.com/ingredients
PUBCHEM_DELAY = 0.25  # stay under 5 req/sec (NCBI policy)
INCIDECODER_DELAY = 1.5  # Delay between requests (ease server load)


def normalize_ingredient(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def paula_canonicalize(name: str) -> str:
    """
    Paula reference universe: lower(), remove parentheses, remove periods, normalize space.
    """
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Paula synonym matching: weak fuzzy when exact fails (normalize + similarity)
PAULA_FUZZY_THRESHOLD = 0.88  # SequenceMatcher ratio lower bound


def match_paula_fuzzy(norm_synonym: str, paula_set: set) -> str:
    """
    If normalized synonym has exact match in Paula, return it.
    Else return best fuzzy match (SequenceMatcher ratio >= threshold), or "".
    """
    if not norm_synonym or not paula_set:
        return ""
    if norm_synonym in paula_set:
        return norm_synonym
    if not difflib:
        return ""
    best_ratio = PAULA_FUZZY_THRESHOLD
    best_paula = ""
    for p in paula_set:
        r = difflib.SequenceMatcher(None, norm_synonym, p).ratio()
        if r >= best_ratio:
            best_ratio = r
            best_paula = p
    return best_paula


def load_paula_ingredients(use_embedding_file=True):
    """
    Load Paula ingredients. Names are canonicalized (STEP 1): lower, no parens, no periods, normalized space.
    paula_set = set(canonicalized_paula_names) is the reference universe.
    """
    path = DATA_DIR / "Paula_embedding_SUMLIST_before_422.csv"
    if not use_embedding_file or not path.exists():
        path = DATA_DIR / "Paula_SUM_LIST.csv"
    if not path.exists():
        return set(), {}
    names = set()
    by_name = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("ingredient_name", "").strip()
            norm = paula_canonicalize(raw)
            if norm:
                names.add(norm)
                by_name[norm] = {
                    "raw": raw,
                    "rating": row.get("rating"),
                    "functions": row.get("functions", "")[:80],
                    "benefits": row.get("benefits", "") if "benefits" in row else "",
                }
    return names, by_name


def load_alternatives():
    """pre_alternatives.csv: (component1, component2) pairs. Per-ingredient set of linked alternatives."""
    path = DATA_DIR / "pre_alternatives.csv"
    pair_set = set()  # (norm1, norm2)
    by_ingredient = defaultdict(set)  # norm -> set of paired norms
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c1 = normalize_ingredient(row.get("component1", ""))
            c2 = normalize_ingredient(row.get("component2", ""))
            if c1 and c2 and c1 != c2:
                pair_set.add((c1, c2))
                by_ingredient[c1].add(c2)
                by_ingredient[c2].add(c1)
    return pair_set, dict(by_ingredient)


def _cleaned_ingredients_from_raw(raw: str, use_cleaning: bool, use_canonical: bool):
    """Apply STEP 2 cleaning then optional canonical. Yields normalized ingredient strings."""
    try:
        from ingredient_cleaning import clean_raw_ingredient
    except Exception:
        clean_raw_ingredient = None
    if not raw or not raw.strip():
        return
    if use_cleaning and clean_raw_ingredient:
        cleaned_list = clean_raw_ingredient(raw.strip())
        for n in cleaned_list:
            if n and len(n) > 2:
                yield canonicalize_ingredient(n) if use_canonical and canonicalize_ingredient else n
        return
    parts = [p.strip() for p in re.split(r",\s*(?=[A-Z\(])", raw) if p.strip()]
    for x in parts:
        n = normalize_ingredient(x)
        if n and len(n) > 2:
            yield canonicalize_ingredient(n) if use_canonical and canonicalize_ingredient else n


def load_all_unmapped_ingredients(use_canonical: bool = False, use_cleaning: bool = True):
    """
    Unique ingredients from cosmetics + binary. STEP 2: when use_cleaning=True, applies
    clean_raw_ingredient (remove parens, %, split compounds, filter junk).
    use_canonical=True: alias table for unified names.
    """
    ingredients = set()

    # cosmetics
    path = DATA_DIR / "cosmetics.csv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = row.get("Ingredients", "")
                for n in _cleaned_ingredients_from_raw(raw, use_cleaning, use_canonical):
                    ingredients.add(n)

    # binary
    path = DATA_DIR / "binary_cosmetic_ingredient.csv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = row.get("ingredient", "")
                for n in _cleaned_ingredients_from_raw(raw, use_cleaning, use_canonical):
                    ingredients.add(n)

    return ingredients


def load_ingredient_frequency(use_canonical: bool = True, use_cleaning: bool = True) -> dict:
    """Ingredient count from cosmetics + binary (same cleaning/canonical as load_all). STEP 3: order by this for INCI top 200/1000."""
    cnt = defaultdict(int)
    path = DATA_DIR / "cosmetics.csv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                raw = row.get("Ingredients", "")
                for n in _cleaned_ingredients_from_raw(raw, use_cleaning, use_canonical):
                    if n and len(n) > 2:
                        cnt[n] += 1
    path = DATA_DIR / "binary_cosmetic_ingredient.csv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                raw = row.get("ingredient", "")
                for n in _cleaned_ingredients_from_raw(raw, use_cleaning, use_canonical):
                    if n and len(n) > 2:
                        cnt[n] += 1
    return dict(cnt)


def load_pubchem_cache():
    if PUBCHEM_CACHE_PATH.exists():
        try:
            with open(PUBCHEM_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_pubchem_cache(cache: dict):
    with open(PUBCHEM_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


def fetch_pubchem_synonyms(ingredient_name: str, cache: dict) -> list:
    """Look up synonyms by ingredient name from PubChem. Uses cache."""
    key = ingredient_name
    if key in cache:
        return cache[key] if isinstance(cache[key], list) else []

    synonyms = []
    if _HAS_URLLIB:
        try:
            url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/" + urllib.parse.quote(
                ingredient_name.replace(" ", "+"), safe=""
            ) + "/synonyms/JSON"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartSkincare/1.0"})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                if "InformationList" in data and "Information" in data["InformationList"]:
                    infos = data["InformationList"]["Information"]
                    if infos and "Synonym" in infos[0]:
                        synonyms = infos[0]["Synonym"]
            time.sleep(PUBCHEM_DELAY)
        except Exception as e:
            synonyms = []  # keep empty on error
        cache[key] = synonyms
    return synonyms


def load_compound_cache():
    if PUBCHEM_COMPOUND_CACHE_PATH.exists():
        try:
            with open(PUBCHEM_COMPOUND_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_compound_cache(cache: dict):
    with open(PUBCHEM_COMPOUND_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


def incidecoder_slug(name: str) -> str:
    """Guess slug for INCI Decoder URL: lowercase, spaces/slash to -, remove parentheses/special chars. Fallback when search fails."""
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s*/\s*", " ", s)
    s = re.sub(r"\([^)]*\)", "", s)  # Remove parentheses and contents
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


SEARCH_SLUG_CACHE_KEY_PREFIX = "search_slug:"


def search_incidecoder_for_slug(query: str, cache: dict) -> str:
    """
    Find slug via site search. https://incidecoder.com/search?query=<query>
    Extract /ingredients/<slug> links from result HTML, return first ingredient slug.
    """
    key = SEARCH_SLUG_CACHE_KEY_PREFIX + query
    if key in cache:
        return cache[key] or ""
    slug = ""
    if _HAS_URLLIB and query and len(query.strip()) >= 2:
        try:
            url = "https://incidecoder.com/search?query=" + urllib.parse.quote(query.strip().replace(" ", "+"), safe="")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SmartSkincare/1.0)"})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            time.sleep(INCIDECODER_DELAY)
            # Extract /ingredients/<slug> in Ingredients section (exclude products)
            # Link pattern: href="/ingredients/glycerin" or "incidecoder.com/ingredients/..."
            matches = re.findall(r"/ingredients/([a-z0-9][a-z0-9\-]*)", raw, re.I)
            # Dedupe, keep order. First is usually closest to query
            seen = set()
            for m in matches:
                s = m.lower()
                if s not in seen and s not in ("new", "create"):
                    seen.add(s)
                    slug = s
                    break
        except Exception:
            pass
        cache[key] = slug
    return slug


def load_incidecoder_cache():
    if INCIDECODER_CACHE_PATH.exists():
        try:
            with open(INCIDECODER_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_incidecoder_cache(cache: dict):
    with open(INCIDECODER_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


def _parse_details_section(raw: str) -> str:
    """Extract Details section text from INCI Decoder page (feature description)."""
    # From "Details" until "Show me some proof" or "Products with"
    start = re.search(r"Details\s*</h2>|##\s*Details", raw, re.I)
    end = re.search(r"Show me some proof|Products with\s+[A-Z]|Something incorrect", raw, re.I)
    if not start or not end or end.start() <= start.end():
        return ""
    block = raw[start.end() : end.start()]
    block = re.sub(r"<[^>]+>", " ", block)
    block = re.sub(r"\[more\]\s*\[less\]", "", block, flags=re.I)
    block = re.sub(r"\s+", " ", block).strip()
    return block[:2000]


def _parse_also_called_section(raw: str) -> list:
    """
    Extract section after "Also-called:", then clean split by ; , |
    """
    # Section after Also-called(:-like-this)?: until What-it-does etc.
    m = re.search(
        r"Also-called(?:-like-this)?\s*:\s*([\s\S]*?)(?=What-it-does|Irritancy:|Comedogenicity:)",
        raw,
        re.I,
    )
    if not m:
        return []
    block = re.sub(r"<[^>]+>", " ", m.group(1))
    block = re.sub(r"\s+", " ", block).strip()
    # Split by ; , | then trim
    parts = re.split(r"\s*[;,|]\s*", block)
    return [x.strip() for x in parts if x.strip()]


def fetch_incidecoder_ingredient(ingredient_name: str, cache: dict) -> dict:
    """
    INCI Decoder: 1) find slug via search 2) fetch ingredient page 3) extract Also-called section (split by ; , |).
    """
    key = ingredient_name
    if key in cache and isinstance(cache[key], dict):
        return cache[key]

    out = {"source": "INCI Decoder", "synonyms": [], "what_it_does": [], "details": "", "slug_used": ""}
    if not _HAS_URLLIB:
        cache[key] = out
        return out
    # 1) Find slug via search (reduce 404s)
    slug = search_incidecoder_for_slug(ingredient_name, cache)
    if not slug:
        slug = incidecoder_slug(ingredient_name)
    if not slug or len(slug) < 2:
        cache[key] = out
        return out
    out["slug_used"] = slug
    try:
        url = f"https://incidecoder.com/ingredients/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SmartSkincare/1.0)"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        time.sleep(INCIDECODER_DELAY)
        # 2) Extract Also-called section, split by ; , |
        out["synonyms"] = _parse_also_called_section(raw)
        # What-it-does
        for line in raw.split("\n"):
            if "What-it-does" in line or "what-it-does" in line:
                what_do = re.findall(r"\[([^\]/]+)(?:/[^\]]*)?\]", line)
                what_do.extend(re.findall(r">([^<]+)</a>", line))
                if what_do:
                    out["what_it_does"] = list(dict.fromkeys(what_do))[:15]
                    break
        # 3) Details section (feature text) - used for display even without Paula
        out["details"] = _parse_details_section(raw)
    except Exception:
        pass
    cache[key] = out
    return out


def fetch_pubchem_compound_info(ingredient_name: str, cache: dict) -> dict:
    """
    Fetch ingredient info via NCBI PubChem API (for unmatched ingredients).
    REST API only, no scraping: https://pubchem.ncbi.nlm.nih.gov/rest/pug/
    """
    key = ingredient_name
    if key in cache and isinstance(cache[key], dict):
        return cache[key]

    out = {"source": "NCBI PubChem", "cid": None, "synonyms": [], "molecular_formula": None, "iupac_name": None}
    if not _HAS_URLLIB:
        cache[key] = out
        return out
    try:
        # 1) Name -> CID
        url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/" + urllib.parse.quote(
            ingredient_name.replace(" ", "+"), safe=""
        ) + "/cids/JSON"
        req = urllib.request.Request(url, headers={"User-Agent": "SmartSkincare/1.0"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        cids = data.get("IdentifierList", {}).get("CID", [])
        time.sleep(PUBCHEM_DELAY)
        if not cids:
            cache[key] = out
            return out
        cid = cids[0]
        out["cid"] = cid
        # 2) CID -> synonyms
        url2 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "SmartSkincare/1.0"})
        with urllib.request.urlopen(req2, timeout=15, context=ctx) as resp2:
            data2 = json.loads(resp2.read().decode())
        syns = data2.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
        out["synonyms"] = syns[:30] if syns else []
        time.sleep(PUBCHEM_DELAY)
        # 3) CID -> properties (MolecularFormula, IUPACName)
        url3 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/MolecularFormula,IUPACName/JSON"
        req3 = urllib.request.Request(url3, headers={"User-Agent": "SmartSkincare/1.0"})
        with urllib.request.urlopen(req3, timeout=15, context=ctx) as resp3:
            data3 = json.loads(resp3.read().decode())
        props = data3.get("PropertyTable", {}).get("Properties", [{}])
        if props:
            out["molecular_formula"] = props[0].get("MolecularFormula")
            out["iupac_name"] = props[0].get("IUPACName")
        time.sleep(PUBCHEM_DELAY)
    except Exception:
        pass
    cache[key] = out
    return out


def run_matching(
    paula_set: set,
    all_ingredients: set,
    alternatives_by_ingredient: dict,
    use_pubchem: bool = True,
    pubchem_sample_max: int = 0,
    use_incidecoder: bool = True,
    incidecoder_sample_max: int = 200,
    incidecoder_priority_order: list = None,
):
    """
    Returns:
      paula_direct, paula_via_pubchem, paula_via_incidecoder,
      linkable_via_alternatives, unmatched
    STEP 3: If incidecoder_priority_order is set (e.g. ingredients sorted by frequency),
    INCI Decoder is run on top N of that order (within still_remaining) for MVP efficiency.
    """
    paula_direct = all_ingredients & paula_set
    remaining = all_ingredients - paula_set

    paula_via_pubchem = {}
    cache = load_pubchem_cache()
    to_try_pubchem = list(remaining)
    if pubchem_sample_max > 0:
        to_try_pubchem = to_try_pubchem[:pubchem_sample_max]
    if use_pubchem and to_try_pubchem:
        for i, ing in enumerate(to_try_pubchem):
            syns = fetch_pubchem_synonyms(ing, cache)
            for s in syns:
                norm = normalize_ingredient(s)
                if norm in paula_set:
                    paula_via_pubchem[ing] = norm
                    break
            if (i + 1) % 50 == 0:
                save_pubchem_cache(cache)
        save_pubchem_cache(cache)

    still_remaining = remaining - set(paula_via_pubchem.keys())

    # INCI Decoder: search-based slug, top N by frequency (STEP 3)
    paula_via_incidecoder = {}
    if use_incidecoder and still_remaining:
        id_cache = load_incidecoder_cache()
        if incidecoder_priority_order:
            to_try_id = [x for x in incidecoder_priority_order if x in still_remaining][:incidecoder_sample_max]
        else:
            to_try_id = list(still_remaining)
            if incidecoder_sample_max > 0:
                to_try_id = to_try_id[:incidecoder_sample_max]
        for i, ing in enumerate(to_try_id):
            info = fetch_incidecoder_ingredient(ing, id_cache)
            for s in info.get("synonyms", []):
                norm = normalize_ingredient(s)
                matched = match_paula_fuzzy(norm, paula_set)
                if matched:
                    paula_via_incidecoder[ing] = matched
                    break
            if (i + 1) % 30 == 0:
                save_incidecoder_cache(id_cache)
        save_incidecoder_cache(id_cache)
        still_remaining = still_remaining - set(paula_via_incidecoder.keys())

    linkable_via_alternatives = {}
    for ing in still_remaining:
        partners = alternatives_by_ingredient.get(ing, set())
        in_paula = [p for p in partners if p in paula_set]
        if in_paula:
            linkable_via_alternatives[ing] = in_paula

    unmatched = still_remaining - set(linkable_via_alternatives.keys())

    return paula_direct, paula_via_pubchem, paula_via_incidecoder, linkable_via_alternatives, unmatched


def main():
    print("=" * 60)
    print("Smart Skincare - Match pipeline: Paula -> PubChem -> Alternatives")
    print("=" * 60)

    paula_set, paula_info = load_paula_ingredients(use_embedding_file=True)
    if not paula_set:
        paula_set, paula_info = load_paula_ingredients(use_embedding_file=False)
    print(f"\n[Paula] unique ingredients: {len(paula_set)}")

    _, alternatives_by_ingredient = load_alternatives()
    print(f"[pre_alternatives] ingredients with at least one pair: {len(alternatives_by_ingredient)}")

    use_canonical = bool(canonicalize_ingredient)
    all_ingredients = load_all_unmapped_ingredients(use_canonical=use_canonical)
    print(f"[Cosmetics + Binary] unique ingredients (combined): {len(all_ingredients)}" + (" [canonicalized]" if use_canonical else ""))

    # STEP 3: INCI Decoder on top N by frequency (MVP: 1000 covers ~80% of products)
    freq = load_ingredient_frequency(use_canonical=use_canonical)
    incidecoder_order = sorted(all_ingredients, key=lambda x: -freq.get(x, 0))

    paula_direct, paula_via_pubchem, paula_via_incidecoder, linkable_via_alternatives, unmatched = run_matching(
        paula_set,
        all_ingredients,
        alternatives_by_ingredient,
        use_pubchem=True,
        pubchem_sample_max=0,
        use_incidecoder=True,
        incidecoder_sample_max=1000,  # MVP: top 1000 by frequency
        incidecoder_priority_order=incidecoder_order,
    )

    print("\n--- Matching result ---")
    print(f"  1. Paula direct match:         {len(paula_direct)}")
    print(f"  2. Paula via PubChem synonym:  {len(paula_via_pubchem)}")
    print(f"  3. Paula via INCI Decoder:     {len(paula_via_incidecoder)} (incidecoder.com synonyms)")
    print(f"  4. Linkable via alternatives:  {len(linkable_via_alternatives)} (partner in Paula)")
    print(f"  5. Unmatched:                  {len(unmatched)}")

    if paula_via_pubchem:
        print("\n  Sample: Paula via PubChem")
        for k, v in list(paula_via_pubchem.items())[:8]:
            print(f"    {k[:45]:45} -> Paula: {v[:40]}")

    if paula_via_incidecoder:
        print("\n  Sample: Paula via INCI Decoder")
        for k, v in list(paula_via_incidecoder.items())[:8]:
            print(f"    {k[:45]:45} -> Paula: {v[:40]}")

    if linkable_via_alternatives:
        print("\n  Sample: Linkable via alternatives (can attach to Paula via pair)")
        for k, v in list(linkable_via_alternatives.items())[:8]:
            print(f"    {k[:40]:40} -> Paula partners: {v[:3]}")

    if unmatched:
        print("\n  Sample: Unmatched")
        for x in list(unmatched)[:12]:
            try:
                print(f"    {x[:55]}")
            except UnicodeEncodeError:
                print(f"    {x.encode('ascii', 'replace').decode()[:55]}")

    total_mapped = len(paula_direct) + len(paula_via_pubchem) + len(paula_via_incidecoder)
    total_linkable = len(linkable_via_alternatives)
    rate = (total_mapped / len(all_ingredients) * 100) if all_ingredients else 0
    print("\n--- Summary ---")
    print(f"  Mapped to Paula (direct + PubChem + INCI Decoder): {total_mapped}  ({rate:.1f}%)")
    print(f"  Can use alternatives to attach:                    {total_linkable}")
    print(f"  Remaining unmatched:                               {len(unmatched)}")

    # Unmatched ingredients: fetch info via NCBI PubChem API (REST only)
    if unmatched and _HAS_URLLIB:
        print("\n--- Fetching NCBI PubChem info for unmatched (API, no crawling) ---")
        compound_cache = load_compound_cache()
        unmatch_list = list(unmatched)[:150]
        for i, ing in enumerate(unmatch_list):
            fetch_pubchem_compound_info(ing, compound_cache)
            if (i + 1) % 30 == 0:
                save_compound_cache(compound_cache)
                print(f"  Cached compound info: {i+1}/{len(unmatch_list)}")
        save_compound_cache(compound_cache)
        with_cid = sum(1 for ing in unmatch_list if compound_cache.get(ing, {}).get("cid"))
        print(f"  Unmatched with NCBI info: {with_cid}/{len(unmatch_list)} (cache: {PUBCHEM_COMPOUND_CACHE_PATH.name})")

    if merge_aliases_from_matching_results and (paula_via_incidecoder or paula_via_pubchem):
        merge_aliases_from_matching_results(paula_via_incidecoder, paula_via_pubchem, save=True)
        print("\n  [ingredient_aliases] updated from this run (INCI Decoder + PubChem -> Paula)")

    print("=" * 60)


if __name__ == "__main__":
    main()
