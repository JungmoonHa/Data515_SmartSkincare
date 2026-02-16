# Component Spec — Smart Skincare

## 1. Skin type / profile input

We need a single place that turns “how’s your skin” into the 6 weights we use everywhere: dry, normal, oily, pigmentation, sensitive, wrinkle. That’s `user_input_to_profile` in recommend_mvp (and the CLI in run_recommendation.py just calls it).

You pass in: hydration (low/normal/high), oil level, sensitivity, age if you have it (35+ bumps wrinkle), and optionally a list of concerns like dryness or pigmentation. Out comes a dict with those 6 keys and floats 0–1; anything you didn’t set is 0. We assume the caller stays within the allowed choices and doesn’t add extra keys.

---

## 2. Products and ingredients data

Everything that “loads the world” lives around recommend_mvp: cosmetics.csv → parsed product list (id, name, brand, ingredients list, rating), ingredient_skin_map.json → skin_map (ingredient → skin_types, effect, confidence), and optionally Paula CSV and product_knn_topk.json. The Ingredients column is expected to be a normal comma-separated string we can parse; if an ingredient isn’t in the map we fall back to family-based rules.

---

## 3. Recommendation / scoring

`get_top_products(profile, n, max_products)` is the main entry. It scores each product: good ingredients add (profile weight × type × tier × confidence), avoid ingredients subtract, Paula “poor” subtracts a bit more. If we have the KNN cache we add a similarity term so base_score + SIM_WEIGHT * sim_score gives the final score.

Return shape: list of dicts. Each has `product`, `score`, `base_score`, `sim_score`, `key_ingredients`, `key_by_type`, `active_wrinkle_hits`, and `avoid_ingredients` — that last one is a list of (ingredient_name, reason) like ("linalool", "sensitive"), or empty. No cache → sim_score is just 0; everything else still works.

---

## 4. Building the ingredient–skin map

`build_ingredient_skin_map.py` glues ingredient_6types.json and manual_curation.csv into one ingredient_skin_map.json. Curation wins when both exist: effect (good/avoid/neutral) and confidence (high/medium/low). Skin types stay in the fixed six; we don’t invent new ones.

---

## 5. KNN cache

`build_vector_cache.py` uses the same product/ingredient loading as recommend_mvp, turns ingredient lists into a binary matrix (MultiLabelBinarizer), runs KNN with cosine distance, and dumps product_knn_topk.json. That file is optional — if it’s there we use it for sim_score; if not we skip it. Needs scikit-learn.

---

## How it fits together

Offline you run the map builder (and optionally the KNN cache). At runtime: user input → profile dict → load products + skin map (and cache if present) → get_top_products → top N with key ingredients, drivers per type, and avoid/watch with reasons (or “no avoid ingredient” when the list is empty).
