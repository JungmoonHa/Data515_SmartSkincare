# Smart Skincare — Project summary: flow and data usage

## 1. Overall flow (6 steps + pre-recommendation caches)

| Step | Purpose | Script / module | Output |
|------|---------|-----------------|--------|
| **STEP 1** | Ingredient universe (Paula canonical) | `scripts/match_pipeline.py` | Paula canonical set `paula_set` (~26k) |
| **STEP 2** | Unmatched ingredient cleanup | `scripts/ingredient_cleaning.py` | Parentheses/%, compound split, noise removed |
| **STEP 3** | INCI Decoder match for top-frequency ingredients | `scripts/match_pipeline.run_matching()` | Top ~1k INCI-based match, product coverage extended |
| **STEP 4** | Manual curation CSV export and fill | `scripts/export_top_unmatched_for_curation.py` → `scripts/fill_manual_curation.py` | `data/manual_curation.csv` (ingredient, skin_type, effect, confidence) |
| **STEP 5** | Ingredient → 6 types + effect map build | `scripts/build_ingredient_skin_map.py` | **`cache/ingredient_skin_map.json`** (~23k ingredients, 100% product coverage). Merges: 6types, inferred, missing_ingredients_for_curation, filled_latin_v2, withSearch_filled_v2, withSearch_filled_remaining, manual_curation |
| **STEP 6** | Profile-based score and driver recommendation | `scripts/recommend_mvp.py` | Top N products + score + key drivers + Avoid/Watch (cosmetics + Sephora pool) |
| **(Cache)** | Product similarity (KNN) cache | `scripts/build_vector_cache.py` | `cache/product_knn_topk.json` (optional, similarity smoothing) |
| **(Cache)** | Review stats cache | `scripts/build_review_stats_cache.py` | `cache/review_stats.json` (optional, review quality signal) |

---

## 2. Data actually used (input → intermediate → final)

### 2.1 Input data

| File | Role |
|------|------|
| **cosmetics.csv** | Product list. Columns: Brand, Name, **Ingredients** (comma-separated), Rating, etc. ~1.4k products. |
| **Sephora_all_423.csv** | Second product source, same schema. Merged with cosmetics for recommendation pool. |

**Recommendation pool vs CSV row count**
- Raw CSV rows: cosmetics ~1.4k + Sephora ~36k = ~37k rows.
- After parsing and filters (disclaimer, dynamic formula, non-cosmetic, marketing-only, etc.) the **recommendation pool** is **~3.6k products** (e.g. 3,646). So "~3.6k" is the post–exclude_recommendation / empty-ingredient count, not raw CSV size.

| **Paula_embedding_SUMLIST_before_422.csv** / **Paula_SUM_LIST.csv** | Paula ingredient dictionary: ingredient_name, **rating**, functions, benefits. ~26k ingredients. |
| **ingredient_6types.json** | Ingredient → 6-type list (dry, normal, oily, pigmentation, sensitive, wrinkle). |
| **review_data.csv** | Review source: item_reviewed, rating_value, best_rating, date_published. |

### 2.2 Pipeline-generated intermediate / cache

| File | Description |
|------|-------------|
| **pubchem_synonyms_cache.json** | Paula-unmatched → PubChem synonym lookup (matching aid). |
| **pubchem_compound_info_cache.json** | PubChem compound info cache. |
| **incidecoder_cache.json** | INCI Decoder lookup cache. |
| **top1000_unmatched_for_curation.csv** | Top unmatched ingredients exported for manual curation. |
| **manual_curation.csv** | Human-filled skin_type, **effect** (good/avoid/neutral), confidence per ingredient. |
| **needs_human_filtered_v2.csv** | Output of apply_curation_rules_v2; input to fill_needs_human_withSearch. |
| **withSearch_filled_v2.csv** | Output of fill_needs_human_withSearch (rule/keyword filled). |
| **withSearch_filled_remaining.csv** | Output of fill_remaining_not_in_map (ingredients in products but not in map). |
| **ingredient_aliases.json** | Normalization / synonym mapping (canonical names). |
| **product_knn_topk.json** | Per-product KNN neighbors and similarity (build_vector_cache). |
| **review_stats.json** | Per-product review stats (build_review_stats_cache). |

### 2.3 Final data used by recommendation

| Data | Source | Format / meaning |
|------|--------|------------------|
| **ingredient_skin_map.json** | STEP 5 merge (~23k ingredients, 100% product coverage) | **ingredient → `{ skin_types, effect, confidence }`**. good → bonus, avoid → penalty, neutral → 0. |
| **Paula CSV** | STEP 1 | **ingredient (canonical) → rating**. "poor" adds penalty. |
| **cosmetics.csv** / **Sephora_all_423.csv** | Raw | **Ingredients string per product** → parsed and normalized to ingredient list. |
| **product_knn_topk.json** | build_vector_cache | If present, **sim_score** added to final score (SIM_WEIGHT). |
| **review_stats.json** | build_review_stats_cache (~2k products) | If present, **review_score** added (REVIEW_WEIGHT). Matching: normalized Brand+Name → name only → substring (name↔key, length ≥ 12) then **average** of matched review_scores; no match → 0. |

What the recommendation engine actually uses:

1. **Product list and ingredient lists** — `cosmetics.csv` + `Sephora_all_423.csv` parsed with `_parse_ingredients()` (token cleanup, length/sentence/marketing filters). Pool: exclude_recommendation excluded → ~3.6k products.
2. **Ingredient type / effect / confidence** — `ingredient_skin_map.json` (~23k). Fallback (weight 0.7) only when not in map.
3. **Bad rating** — Paula CSV "poor" (canonical lookup).
4. **Similarity and review** — `product_knn_topk.json`, `review_stats.json` when present.

---

## 3. STEP 6 recommendation logic summary

- **Profile**: 6-type weights (dry, normal, oily, pigmentation, sensitive, wrinkle). E.g. dry+wrinkle → those types 0.9.
- **Base score (ingredient-based)**  
  - good → profile weight × TYPE_MULT × confidence × tier (active/base/other).  
  - avoid → penalty. Paula poor → extra penalty.  
  - oily-only: retinoid/emollient in oily bucket suppressed (OILY_SUPPRESS_MULT).  
  - Ingredients not in map use `fallback_entry_from_family()` (weight 0.7). With 100% map coverage, fallback is minimal.  
  - **INCI order bonus**: For allowed families per type (e.g. oily→aha_bha, sebum_control; wrinkle→retinoid, peptide, aha_bha, antioxidant; dry→humectant, barrier), index 0–4 → high, 5–14 → medium, 15+ → low bonus. Only tokens passing `_should_drop_ingredient_token` apply.
- **Token cleanup**: length>60, words>8, `:`, `™`, `http`, marketing keywords → removed from ingredient candidates; same in `_ingredient_family()` → "other" to avoid fallback drivers.
- **Final score**:  
  `final_score = base_score + SIM_WEIGHT * sim_score + REVIEW_WEIGHT * review_score`  
  - sim_score from `product_knn_topk.json` (anchor = top base_score products). No cache → 0.  
  - review_score from `review_stats.json`: 1) normalized Brand+Name exact → 2) name only → 3) substring (name↔key, name length ≥ 12) → **average** of matched review_scores. Cache value: avg_norm_rating × log1p(count) × recentness (180-day decay). No cache or no match → 0.
- **Drivers**: Top types from profile `top_types(profile, k=6, min_w=0.1)` → per-type allowed families (TYPE_FAMILY_ALLOW). Fallback ingredients with effect=good can be candidates.
- **Avoid / Watch**: effect=avoid ingredients collected as (ingredient name, reason). Reason = skin_types string (e.g. "sensitive", "oily, sensitive"). If none: "Avoid ingredients not found".

---

## 4. Execution order (before demo)

1. **Build ingredient map (STEP 5, if needed)**
   - One shot: `python scripts/run_pipeline.py` (filter_needs_human → apply_curation_rules_v2 → fill_needs_human_withSearch → fill_remaining_not_in_map → build_ingredient_skin_map)
   - Or step by step: `python scripts/filter_needs_human.py` → … → `python scripts/build_ingredient_skin_map.py`
   - With recommendation: `python scripts/run_pipeline.py --recommend`
2. **Build caches (optional)**
   - `python scripts/build_review_stats_cache.py` → cache/review_stats.json
   - `python scripts/build_vector_cache.py` → cache/product_knn_topk.json
3. **Run recommendation**
   - `python scripts/recommend_mvp.py` (internal 3 profiles, Top 30)
   - Or `python scripts/run_recommendation.py --dry --wrinkle --top 10` etc.

4. **Demo dashboard**
   - `pip install flask` then `python scripts/dashboard.py` → http://127.0.0.1:5000
   - Select skin concerns (dry/oily/pigmentation/sensitive/wrinkle) and optional age → "Get recommendations" for ingredient-based Top 30 product cards (key ingredients and avoid list). First load may take 20–30s for full pool scoring.
   - **Product images**: Shown from JSON when available; otherwise "No image" placeholder. See "5. Product image URL fetch" below.

5. **Product image URL fetch**
   - **Script**: `scripts/fetch_product_images_byHand.py`. Serper-only: search query = "brand name" → Serper search → og:image; on failure, Serper image search. Only processes **recommendation pool** products that do not yet have an image.
   - **Target**: Only products in the pool missing from `cache/cosmetics_image_urls.json` / `cache/sephora_image_urls.json`.
   - **Run**: `SERPER_API_KEY=xxx python scripts/fetch_product_images_byHand.py` (no limit) or `--max N`.
   - **Env**: `SERPER_API_KEY` required.
   - **Save**: Writes to `cache/cosmetics_image_urls.json`, `cache/sephora_image_urls.json`. Ctrl+C saves progress.
   - **Dashboard**: Reads those JSONs (cosmetics key = normalized "brand name"; sephora = product_url or normalized name).

---

## 5. Folder structure

```
smartskincare/
├── data/               # CSV data files (16)
├── cache/              # JSON cache/map files (12)
├── scripts/            # Python scripts (25)
├── templates/          # HTML templates (dashboard)
├── requirements.txt
└── PROJECT_SUMMARY.md
```

| Folder | Contents | Notes |
|--------|----------|-------|
| **data/** | `cosmetics.csv`, `Sephora_all_423.csv`, `Paula_SUM_LIST.csv`, `Paula_embedding_SUMLIST_before_422.csv`, `review_data.csv`, `pre_alternatives.csv`, `binary_cosmetic_ingredient.csv`, `manual_curation.csv`, `top1000_unmatched_for_curation.csv`, `needs_human.csv`, `needs_human_filtered.csv`, `needs_human_filtered_v2.csv`, `filled_latin_v2.csv`, `withSearch_filled_v2.csv`, `withSearch_filled_remaining.csv`, `missing_ingredients_for_curation.csv` | Input + intermediate CSV |
| **cache/** | `ingredient_skin_map.json`, `ingredient_6types.json`, `ingredient_aliases.json`, `ingredient_info_incidecoder.json`, `inferred_ingredient_skin_map.json`, `pubchem_synonyms_cache.json`, `pubchem_compound_info_cache.json`, `incidecoder_cache.json`, `product_knn_topk.json`, `review_stats.json`, `cosmetics_image_urls.json`, `sephora_image_urls.json` | JSON caches and maps |
| **scripts/** | All 25 .py files (recommend_mvp, match_pipeline, dashboard, build_*, fill_*, filter_*, run_*, etc.) | All scripts use `ROOT = Path(__file__).resolve().parent.parent` |
| **templates/** | `dashboard_index.html` | Flask dashboard template |

---

## 6. Quick command reference

> All commands should be run from the project root (`smartskincare/`).

| Task | Command |
|-----|--------|
| **View recommendation results (CLI)** | `python3 scripts/run_recommendation.py --dry --wrinkle --top 10` |
| **Run recommendation dashboard** | `pip install flask && python3 scripts/dashboard.py` → http://127.0.0.1:5000 |
| **Rebuild full ingredient_skin_map** | `python3 scripts/run_pipeline.py` |
| **Rebuild ingredient_skin_map + run recommendations** | `python3 scripts/run_pipeline.py --recommend` |
| **Refresh review cache** | `python3 scripts/build_review_stats_cache.py` |
| **Refresh KNN similarity cache** | `python3 scripts/build_vector_cache.py` (requires scikit-learn) |
| **Fetch product image URLs** | `SERPER_API_KEY=xxx python3 scripts/fetch_product_images_byHand.py` |
| **Check missing image status** | `python3 scripts/count_missing_images.py` |
| **Run Paula matching pipeline** | `python3 scripts/match_pipeline.py` |
| **Export Top 1000 unmatched ingredients CSV** | `python3 scripts/export_top_unmatched_for_curation.py` |
| **Fill rules in manual_curation.csv** | `python3 scripts/fill_manual_curation.py` |
| **List products with empty ingredients** | `python3 scripts/list_empty_ingredients.py` |
| **Classify product categories** | `python3 scripts/categorize_products.py` |
| **Validate recommendation score distribution** | `python3 scripts/verify_recommendation_scores.py` |
| **Run sanity check on 10 profiles** | `python3 scripts/sanity_check_profiles.py` |

### run_recommendation.py 옵션

```
--hydration low/normal/high    수분 레벨
--oil low/normal/high          유분 레벨
--sensitivity low/normal/high  민감도
--age 40                       나이 (35+ → wrinkle 가중)
--dry                          건성 고민
--oily                         지성 고민
--wrinkle                      주름 고민
--pigmentation                 색소침착 고민
--top 10                       상위 N개 (기본 10)
--max-products 500             스코어링 대상 제한 (테스트용)
```

**예시:**
```bash
python scripts/run_recommendation.py --dry --wrinkle --top 5
python scripts/run_recommendation.py --oily --sensitivity high --age 30 --top 20
python scripts/run_recommendation.py --pigmentation --top 10
```

---

## 7. One-line summary

- **Flow**: Paula-based (~26k) ingredient normalization and matching; INCI, manual, and rule-based curation (6types, inferred, missing_curation, withSearch_filled_v2, withSearch_filled_remaining, manual) → **ingredient → 6 types + effect + confidence** map (`ingredient_skin_map.json`, ~23k, 100% product coverage). Then parse and clean cosmetics+Sephora ingredient lists, score with this map, Paula rating, and INCI order bonus → **base_score**; add (optional) KNN and review caches → **sim_score**, **review_score** → **profile-based Top N + type key drivers + Avoid/Watch (with reason)**.
- **Data used**: **Products** from `cosmetics.csv` + `Sephora_all_423.csv` (parsed Ingredients); **ingredient knowledge** from `ingredient_skin_map.json` (~23k) + **Paula CSV** (poor penalty); **quality/similarity** from `review_stats.json` and `product_knn_topk.json` when present; other caches and synonyms from pubchem, incidecoder, rules, withSearch fill, and manual_curation.
