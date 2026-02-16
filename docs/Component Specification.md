# Component Specification — Smart Skincare

## Component 1: Skin Type / User Profile Input

* **Name:** SkinTypeInput (user_input_to_profile)
* **What it does:**
  * Converts user skin type and concerns into 6-type weights (dry, normal, oily, pigmentation, sensitive, wrinkle).
  * Callable from CLI (`run_recommendation.py`) or from code.
* **Inputs:**
  * `hydration_level` (str): "low" | "normal" | "high" — hydration level.
  * `oil_level` (str): "low" | "normal" | "high" — oil level.
  * `sensitivity` (str): "low" | "normal" | "high" — sensitivity.
  * `age` (int, optional): Age. Values such as 35+ adjust wrinkle weight.
  * `concerns` (list, optional): Additional concerns, e.g. ["dryness", "wrinkles", "pigmentation"].
* **Outputs (with type information):**
  * `user_profile` (dict): `{ "dry": float, "normal": float, "oily": float, "pigmentation": float, "sensitive": float, "wrinkle": float }` — weight per type (0–1). Unspecified types are 0.
* **Assumptions:**
  * Input values are within the defined choices.
  * Profile contains only the normalized 6-type keys.

---

## Component 2: Cosmetic Products & Ingredients Data Interface

* **Name:** ProductIngredientData (load_products_with_ingredients, load_ingredient_skin_map, etc.)
* **What it does:**
  * Reads the product list (cosmetics.csv), parses and normalizes ingredient strings, and provides a per-product ingredient list.
  * Loads the ingredient→skin type / effect / confidence map (ingredient_skin_map.json).
  * Optionally loads Paula rating CSV and KNN similarity cache (product_knn_topk.json).
* **Inputs (data sources):**
  * `cosmetics.csv`: Brand, Name, Ingredients (comma-separated string), Rating, etc.
  * `ingredient_skin_map.json`: ingredient name → `{ skin_types, effect, confidence }`.
  * `Paula_SUM_LIST.csv` (or same format): ingredient ratings (canonical name, rating, etc.).
  * `product_knn_topk.json` (optional): per-product KNN neighbor list — used for similarity-based score adjustment.
* **Outputs (in-memory):**
  * Product list: each item `{ id, name, brand, ingredients: list[str], rating, ... }`.
  * `skin_map`: dict — ingredient → `{ skin_types, effect, confidence }`.
  * (optional) KNN cache dict.
* **Assumptions:**
  * The Ingredients column in cosmetics.csv is a parseable string.
  * Ingredients not in ingredient_skin_map can be handled via family-based fallback.

---

## Component 3: Recommendation / Scoring Engine

* **Name:** RecommendationEngine (get_top_products)
* **What it does:**
  * Scores each product using user profile (6-type weights), product ingredient lists, and the ingredient map.
  * Good ingredients add score by profile weight × type × tier (active/base/other) × confidence; avoid adds penalty; Paula "poor" adds extra penalty.
  * When cache exists: final score = base_score + SIM_WEIGHT * similarity_score.
  * Returns top N products with type-specific key drivers and avoid/watch ingredients (including where they are bad).
* **Inputs:**
  * `user_profile` (dict): 6-type weights.
  * `n` (int): Number of recommendations (default 10).
  * `max_products` (int): Maximum number of products to score (default 5000).
* **Outputs (with type information):**
  * `list[dict]`: each item —
    * `product` (dict): Product info (id, name, brand, ingredients, rating, etc.).
    * `score` (float): Final score.
    * `base_score` (float): Ingredient-based score.
    * `sim_score` (float): KNN similarity contribution (0 if cache is missing).
    * `key_ingredients` (list[str]): Core ingredient names for explanation.
    * `key_by_type` (dict): Driver ingredients per type.
    * `active_wrinkle_hits` (list): Wrinkle-related active ingredient hits.
    * `avoid_ingredients` (list[(str, str)]): (ingredient name, reason e.g. "sensitive" or "oily, sensitive") — empty list if none.
* **Assumptions:**
  * ingredient_skin_map and product data are loadable.
  * Engine works without KNN cache; in that case sim_score is 0.

---

## Component 4: Ingredient–Skin Map Builder

* **Name:** IngredientSkinMapBuilder (build_ingredient_skin_map)
* **What it does:**
  * Merges ingredient_6types.json (ingredient→6-type list) with manual curation (manual_curation.csv) to produce ingredient_skin_map.json.
  * Manual curation effect (good/avoid/neutral) and confidence (high/medium/low) take precedence.
* **Inputs:**
  * `ingredient_6types.json`: ingredient → list of skin_types (default effect good, confidence medium).
  * `manual_curation.csv`: ingredient, skin_type (comma-separated), effect, confidence.
* **Outputs:**
  * `ingredient_skin_map.json`: ingredient → `{ skin_types: list, effect: str, confidence: str }`.
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

## Sequence Diagram (Overall Flow)

1. **Data preparation (offline)**  
   IngredientSkinMapBuilder → ingredient_skin_map.json  
   (optional) ProductKNNCacheBuilder → product_knn_topk.json  

2. **User input**  
   SkinTypeInput (CLI or API) → user_profile  

3. **Recommendation run**  
   Load ProductIngredientData → RecommendationEngine(user_profile, n, max_products) → Top N list + key_ingredients, key_by_type, avoid_ingredients (including where each is bad)  

4. **Output**  
   Per product: score, drivers by type, Avoid / Watch: ingredient (reason) or "no avoid ingredient"
