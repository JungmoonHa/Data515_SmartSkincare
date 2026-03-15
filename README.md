# Smart Skincare: Personalized Skincare Products Recommendation Tool

[![CI](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare/graph/badge.svg)](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare)

## Team Members
- DH Lee
- Emily Tran
- Jungmoon Ha
- Wonjoon Hwang

## Project Type
Interactive Data Analysis & Recommendation Tool

## Questions of Interest
1. How can cosmetic ingredient data be used to recommend products based on individual skin types?
2. Can user ratings improve the accuracy and trustworthiness of product recommendations?
3. How can we design a reusable system that supports better skincare decision-making rather than one-time analysis?

## Goal / Project Output
Our goal is to build an **interactive recommendation tool** that helps users select skincare products suitable for their skin type.

Planned Outputs:
- A web application interface where users input their skin type
- An intelligent matching engine that analyzes ingredient compatibility
- Rating display for transparency
- Reusable recommendation system architecture
- Final report and reproducible analysis notebooks

## Data Sources
- **Cosmetic Ingredients Dataset**  
  ~1,500 skincare products including ingredient lists, product categories, and labeled skin types (dry, oily, combination, etc.)
  https://www.kaggle.com/code/kingabzpro/cosmetics-ingredients
  https://www.kaggle.com/datasets/autumndyer/skincare-products-and-ingredients

- **Skincare Product Reviews Dataset**
  2,000+ products with user reviews and ratings providing real-world feedback on product performance
  https://www.kaggle.com/code/natashamessier/sephora-data-analysis/input

---

## Setting up the virtual environment

We use a **virtual environment** so everyone can install the same dependencies and run tests/lint the same way (easy collaboration).

### 1. Clone and enter the project

```bash
git clone https://github.com/JungmoonHa/Data515_SmartSkincare.git
cd Data515_SmartSkincare
```

### 2. Create and activate a virtual environment

**On macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows (Command Prompt):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**On Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install the project and dev dependencies

From the project root (where `pyproject.toml` is):

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

Alternatively, use the requirements files:

```bash
pip install -r requirements-dev.txt
pip install -e .
```

### 4. Run tests

```bash
pytest src/smart_skincare -v
```

Or with coverage:

```bash
pytest src/smart_skincare --cov=src/smart_skincare --cov-report=term-missing
```

(Use `PYTHONPATH=src/smart_skincare` if you run from the project root and tests fail to import.)

### 5. Lint

```bash
ruff check src/smart_skincare
```

### 6. Run the web app

```bash
python src/smart_skincare/dashboard.py
```

Then open [http://127.0.0.1:5001](http://127.0.0.1:5001). (Default port is 5001 to avoid conflict with macOS AirPlay on 5000.)

---

## Continuous integration

- **CI** runs on every push and pull request to `main` (see the [CI](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml) workflow).
- It runs **Ruff** (lint), **pytest** (tests), and **pytest-cov** (code coverage). Coverage is uploaded to **Codecov** when the token is configured; the badge above shows the latest coverage.

### Setting up Codecov (one-time)

1. **Sign up for Codecov**
   - Go to [https://codecov.io](https://codecov.io) and sign in with **Sign in with GitHub**.

2. **Add the repository**
   - After signing in, choose **Add new repository** or **Set up a repository**.
   - Select **JungmoonHa/Data515_SmartSkincare** from the list, then **Add** (or **Save**).

3. **Copy the token**
   - On the repository page, find **Repository token** (or **Settings → General → Repository token**), a value like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.
   - Copy it and keep it for the next step.

4. **Add the token to GitHub Secrets**
   - Open the [Data515_SmartSkincare](https://github.com/JungmoonHa/Data515_SmartSkincare) repo on GitHub.
   - Go to **Settings** → **Secrets and variables** → **Actions**.
   - Click **New repository secret**.
   - **Name:** `CODECOV_TOKEN`  
   - **Secret:** Paste the token from step 3 → **Add secret**.

5. **Verify**
   - Push to `main` or run **Re-run all jobs** for the **CI** workflow from the **Actions** tab.
   - Once a run succeeds, coverage will appear on the Codecov dashboard and the README codecov badge will update.

> For public repos, the badge may appear after adding the repo on Codecov alone, but you need **CODECOV_TOKEN** for uploads to succeed on every push and for the badge percentage to be accurate.

---

## Project Structure

### What Actually Runs

The production system is `src/smart_skincare/recommend_mvp.py` backed by `Datasets/final_data.csv` and the JSON caches in `cache/`. Everything else is either a preprocessing script used to build those files, intermediate data, or a utility/test.

---

### `Datasets/`

**Final data (active)**

| File | Description |
|------|-------------|
| `final_data.csv` | Master product dataset (3,427 products). Combined and cleaned from cosmetics + Sephora sources. Contains `source`, `brand`, `name`, `rating`, `ingredients_raw`, `ingredients_parsed`, `product_url`, `image_url`. This is the only dataset read at recommendation time. |
| `Paula_embedding_SUMLIST_before_422.csv` | Paula's Choice ingredient ratings (good/poor/etc.) used to penalize problematic ingredients during scoring. |
| `Paula_SUM_LIST.csv` | Fallback version of the Paula's Choice ratings list. |
| `review_data.csv` | Raw user review data used to build `cache/review_stats.json`. |

**Preprocessing intermediates (not used at runtime)**

| File | Description |
|------|-------------|
| `cosmetics.csv` | Original cosmetics dataset (raw, pre-merge). |
| `Sephora_all_423.csv` | Original Sephora dataset (raw, pre-merge). |
| `Filltered_combined_data_fixed.csv` | Intermediate merged dataset before final cleanup. |
| `binary_cosmetic_ingredient.csv` | Binary ingredient-skin-type matrix used during map building. |
| `pre_alternatives.csv` | Candidate ingredient alternatives for curation. |
| `needs_human.csv`, `needs_human_filtered.csv`, `needs_human_filtered_v2.csv` | Ingredients that couldn't be auto-matched and were queued for manual/rule curation. |
| `manual_curation.csv` | Hand-curated ingredient skin-type labels. |
| `missing_ingredients_for_curation.csv` | Ingredients still missing data after automated passes. |
| `top1000_unmatched_for_curation.csv` | Top 1,000 unmatched ingredients exported for manual review. |
| `withSearch_filled_remaining.csv`, `withSearch_filled_v2.csv` | Ingredient fill results from search-assisted heuristic pass. |
| `filled_latin_v2.csv` | Ingredients filled via Latin/INCI name matching. |

---

### `cache/`

All cache files are built by scripts in `src/` and read at recommendation time. Delete and rebuild if source data changes.

| File | Built by | Description |
|------|----------|-------------|
| `ingredient_skin_map.json` | `build_ingredient_skin_map.py` | Core knowledge base. Maps each ingredient to skin-type effects (good/avoid/neutral) with confidence levels. |
| `review_stats.json` | `build_review_stats_cache.py` | Aggregated review scores per product used to blend into final recommendation score. |
| `product_knn_topk.json` | `build_vector_cache.py` | KNN neighbor index for ingredient-vector similarity between products. |
| `ingredient_skin_map.json` | `build_ingredient_skin_map.py` | Core knowledge base mapping ingredients to skin-type effects. |
| `ingredient_aliases.json` | `ingredient_canonical.py` | Synonym/alias map to normalize ingredient name variants. |
| `ingredient_info_incidecoder.json` | `fill_missing_ingredient_data.py` | Ingredient function/family data scraped from INCIDecoder. |
| `incidecoder_cache.json` | `fill_missing_ingredient_data.py` | Raw INCIDecoder API response cache. |
| `inferred_ingredient_skin_map.json` | `build_ingredient_skin_map.py` | Intermediate map before final merge. |
| `ingredient_6types.json` | `skin_type_engine.py` | Keyword-based ingredient-to-skin-type assignments. |
| `pubchem_compound_info_cache.json`, `pubchem_synonyms_cache.json` | `match_pipeline.py` | PubChem API response cache for ingredient synonym lookup. |
| `cosmetics_image_urls.json`, `sephora_image_urls.json` | `fetch_product_images_byHand.py` | Product image URL lookup by product name (legacy, superseded by `image_url` in `final_data.csv`). |

---

### `src/smart_skincare/`

**Core (used at runtime)**

| File | Description |
|------|-------------|
| `recommend_mvp.py` | Main recommendation engine. Loads `final_data.csv` + caches, scores products against a user skin profile, returns top-N products with key ingredients. |
| `skin_type_engine.py` | Builds the 6-skin-type ingredient mapping from Paula's Choice and INCIDecoder keywords. |
| `categorize_products.py` | Assigns product categories (moisturizer, serum, cleanser, etc.) by keyword matching on product names. |
| `ingredient_canonical.py` | Normalizes ingredient name variants using the alias map. |
| `ingredient_cleaning.py` | Low-level ingredient string cleaning (strips percentages, parenthetical notes, etc.). |
| `run_recommendation.py` | CLI entry point — pass skin profile flags to get recommendations printed to terminal. |

**Cache builders (run once to build `cache/`)**

| File | Description |
|------|-------------|
| `build_ingredient_skin_map.py` | Merges all curation sources into `ingredient_skin_map.json`. |
| `build_review_stats_cache.py` | Aggregates `review_data.csv` into `review_stats.json`. |
| `build_vector_cache.py` | Builds KNN ingredient-vector index into `product_knn_topk.json`. |
| `run_pipeline.py` | Runs the full curation + cache build pipeline in sequence. |

**Curation / preprocessing (used to build `final_data.csv` and `ingredient_info_combined.csv`)**

| File | Description |
|------|-------------|
| `match_pipeline.py` | Matches raw ingredients against Paula's ratings via PubChem synonym lookup. |
| `fill_missing_ingredient_data.py` | Fetches missing ingredient data from INCIDecoder. |
| `fill_curation_rules.py` | Rule-based auto-fill for ingredients that couldn't be matched. |
| `apply_curation_rules_v2.py` | Applies rule passes A–D on the needs-human queue. |
| `fill_manual_curation.py` | Merges hand-curated labels into the ingredient map. |
| `fill_needs_human_withSearch.py` | Heuristic/keyword fill pass for remaining unmatched ingredients. |
| `fill_remaining_not_in_map.py` | Fills ingredients present in products but absent from the map. |
| `filter_needs_human.py` | Filters the needs-human queue to keep only plausible ingredient tokens. |
| `export_top_unmatched_for_curation.py` | Exports top 1,000 unmatched ingredients to CSV for manual review. |
| `fetch_product_images_byHand.py` | Fetches product image URLs via Serper API (legacy, image URLs now in `final_data.csv`). |
| `export_ingredient_info_csv.py`| produce 'ingredient_info_combined.csv' from'ingredient_skin_map.json' and 'ingredient_info_incidecoder.json'|

**Tests / verification**

| File | Description |
|------|-------------|
| `test_recommend_mvp.py` | Unit tests for the recommendation engine. |
| `test_skin_type_engine.py` | Unit tests for the skin type engine. |
| `test_ingredient_canonical.py` | Unit tests for ingredient name normalization. |
| `test_ingredient_cleaning.py` | Unit tests for ingredient string cleaning. |
| `verify_recommendation_scores.py` | Checks all recommendation-pool products have valid scores. |
| `sanity_check_profiles.py` | Runs recommendations across 10 profiles to verify no crashes. |

**Utilities**

| File | Description |
|------|-------------|
| `list_empty_ingredients.py` | Lists products with empty ingredient data for debugging. |
| `count_missing_images.py` | Reports how many products in the recommendation pool lack an image URL. |
