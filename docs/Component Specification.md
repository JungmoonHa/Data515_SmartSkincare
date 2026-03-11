# Component Specification - Smart Skincare

## Component 1: Skin Type / User Profile Input

* **Name:** SkinTypeInput (user_input_to_profile)
* **What it does:**
  * Converts user skin type and concerns into 6-type weights (dry, normal, oily, pigmentation, sensitive, wrinkle).
  * Callable from CLI (`run_recommendation.py`) or from code.
* **Inputs:**
  * `hydration_level` (str): "low" | "normal" | "high" - hydration level.
  * `oil_level` (str): "low" | "normal" | "high" - oil level.
  * `sensitivity` (str): "low" | "normal" | "high" - sensitivity.
  * `age` (int, optional): Age. Values such as 35+ adjust wrinkle weight.
  * `concerns` (list, optional): Additional concerns, e.g. ["dryness", "wrinkles", "pigmentation"].
* **Outputs (with type information):**
  * `user_profile` (dict): `{ "dry": float, "normal": float, "oily": float, "pigmentation": float, "sensitive": float, "wrinkle": float }` - weight per type (0-1). Unspecified types are 0.
* **Assumptions:**
  * Input values are within the defined choices.
  * Profile contains only the normalized 6-type keys.

---

## Component 2: Cosmetic Products & Ingredients Data Interface

* **Name:** ProductIngredientData (load_products_with_ingredients, load_ingredient_skin_map, etc.)
* **What it does:**
  * Reads the product list (cosmetics.csv), parses and normalizes ingredient strings, and provides a per-product ingredient list.
  * Loads the ingredient-to-skin type / effect / confidence map (ingredient_skin_map.json).
  * Optionally loads Paula rating CSV, KNN similarity cache (product_knn_topk.json), and review stats cache (review_stats.json).
* **Inputs (data sources):**
  * `cosmetics.csv`: Brand, Name, Ingredients (comma-separated string), Rating, etc.
  * `ingredient_skin_map.json`: ingredient name to `{ skin_types, effect, confidence }`.
  * `Paula_SUM_LIST.csv` (or same format): ingredient ratings (canonical name, rating, etc.).
  * `product_knn_topk.json` (optional): per-product KNN neighbor list - used for similarity-based score adjustment.
  * `review_stats.json` (optional): per-product review stats (avg, count, recentness, review_score) - used for review-based quality signal.
* **Outputs (in-memory):**
  * Product list: each item `{ id, name, brand, ingredients: list[str], rating, ... }`.
  * `skin_map`: dict - ingredient to `{ skin_types, effect, confidence }`.
  * (optional) KNN cache dict.
  * (optional) Review stats dict (key = normalized "Brand + Name").
* **Assumptions:**
  * The Ingredients column in cosmetics.csv is a parseable string.
  * Ingredients not in ingredient_skin_map can be handled via family-based fallback.
  * Review stats are joined by normalizing "Brand + Name" and exact match with cache keys; no match yields review_score 0.

---

## Component 3: Recommendation / Scoring Engine

* **Name:** RecommendationEngine (get_top_products)
* **What it does:**
  * Scores each product using user profile (6-type weights), product ingredient lists, and the ingredient map.
  * **Base score:** Good ingredients add by profile weight x type x tier (active/base/other) x confidence; avoid adds penalty; Paula "poor" adds extra penalty. **INCI order-based strength bonus:** For types that matter (top 2 by profile weight), ingredients in allowed families (e.g. oily: aha_bha, sebum_control; wrinkle: retinoid, peptide, aha_bha, antioxidant; dry: humectant, barrier) get a small bonus added to the type bucket by position: index 0-4 = high, 5-14 = medium, 15+ = low. Tokens that fail _should_drop_ingredient_token are excluded from this bonus.
  * **Final score:** base_score + SIM_WEIGHT * sim_score + REVIEW_WEIGHT * review_score. sim_score from KNN cache (anchor = top base_score products); review_score from review_stats cache (exact match on normalized Brand + Name). Missing caches contribute 0.
  * Returns top N products with type-specific key drivers (top_types k=6, min_w=0.1) and avoid/watch ingredients with reason (skin_types); if no avoid ingredients, output "Avoid ingredients not found".
* **Inputs:**
  * `user_profile` (dict): 6-type weights.
  * `n` (int): Number of recommendations (default 10).
  * `max_products` (int): Maximum number of products to score (default 5000).
* **Outputs (with type information):**
  * `list[dict]`: each item -
    * `product` (dict): Product info (id, name, brand, ingredients, rating, etc.).
    * `score` (float): Final score (base + SIM_WEIGHT*sim + REVIEW_WEIGHT*review).
    * `base_score` (float): Ingredient-based score including INCI strength bonus.
    * `sim_score` (float): KNN similarity contribution (0 if cache missing).
    * `review_score` (float): Review-based quality contribution (0 if cache missing or no match).
    * `key_ingredients` (list[str]): Core ingredient names for explanation.
    * `key_by_type` (dict): Driver ingredients per type (TYPE_FAMILY_ALLOW).
    * `active_wrinkle_hits` (list): Wrinkle-related active ingredient hits.
    * `avoid_ingredients` (list[(str, str)]): (ingredient name, reason e.g. "sensitive" or "oily, sensitive") - empty list if none.
* **Assumptions:**
  * ingredient_skin_map and product data are loadable.
  * Engine works without KNN or review cache; missing caches contribute 0 to final score.

---

## Component 4: Ingredient-Skin Map Builder

* **Name:** IngredientSkinMapBuilder (build_ingredient_skin_map)
* **What it does:**
  * Merges ingredient_6types.json (ingredient-to-6-type list) with manual curation (manual_curation.csv) to produce ingredient_skin_map.json.
  * Manual curation effect (good/avoid/neutral) and confidence (high/medium/low) take precedence.
* **Inputs:**
  * `ingredient_6types.json`: ingredient to list of skin_types (default effect good, confidence medium).
  * `manual_curation.csv`: ingredient, skin_type (comma-separated), effect, confidence.
* **Outputs:**
  * `ingredient_skin_map.json`: ingredient to `{ skin_types: list, effect: str, confidence: str }`.
* **Assumptions:**
  * skin_type values are limited to the fixed 6 types (dry, normal, oily, pigmentation, sensitive, wrinkle).
  * effect is good | avoid | neutral; confidence is high | medium | low.

---

## Component 5: KNN Similarity Cache Builder

* **Name:** ProductKNNCacheBuilder (build_vector_cache)
* **What it does:**
  * Vectorizes per-product ingredient lists with MultiLabelBinarizer, then computes KNN neighbors by cosine distance and writes product_knn_topk.json.
  * Used by the recommendation engine to compute similarity-based score adjustment (sim_score).
* **Inputs:**
  * Product and ingredient data: list loaded via recommend_mvp.load_products_with_ingredients().
* **Outputs:**
  * `product_knn_topk.json`: `{ product_id: [[neighbor_id, similarity], ...], ... }`.
* **Assumptions:**
  * Ingredient lists are produced with the same parsing logic as recommend_mvp.
  * scikit-learn (NearestNeighbors, MultiLabelBinarizer) is available.

---

## Component 6: Review Stats Cache Builder

* **Name:** ReviewStatsCacheBuilder (build_review_stats_cache)
* **What it does:**
  * Reads review_data.csv (item_reviewed, rating_value, best_rating, date_published), aggregates per normalized product name (item_reviewed), computes avg = mean(rating_value/best_rating), count, recentness = exp(-days_since_last/180), and review_score = avg * log1p(count) * recentness. Writes review_stats.json. Matching to cosmetics at recommendation time is by normalizing "Brand + Name" and exact lookup; no fuzzy matching.
* **Inputs:**
  * `review_data.csv`: item_reviewed, rating_value, best_rating, date_published.
* **Outputs:**
  * `review_stats.json`: `{ normalized_product_name: { avg, count, recentness, review_score }, ... }`.
* **Assumptions:**
  * best_rating > 0 (default 5 if missing). Unmatched products at recommendation time get review_score 0.

---

## Sequence Diagram (Overall Flow)

1. **Data preparation (offline)**
   * IngredientSkinMapBuilder to ingredient_skin_map.json
   * (optional) ProductKNNCacheBuilder to product_knn_topk.json
   * (optional) ReviewStatsCacheBuilder to review_stats.json

2. **User input**
   * SkinTypeInput (CLI or API) to user_profile

3. **Recommendation run**
   * Load ProductIngredientData (products, skin_map, optional KNN cache, optional review stats). RecommendationEngine(user_profile, n, max_products): base_score (ingredient map + family fallback + Paula poor + rating + INCI strength bonus), then final_score = base_score + SIM_WEIGHT*sim_score + REVIEW_WEIGHT*review_score. Returns Top N with key_ingredients, key_by_type, avoid_ingredients (with reason).

4. **Output**
   * Per product: score, drivers by type, Avoid / Watch: ingredient (reason) or "Avoid ingredients not found"
