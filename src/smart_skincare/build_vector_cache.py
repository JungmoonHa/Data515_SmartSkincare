"""
Build product ingredient vector cache + KNN neighbors (cosine similarity).

Outputs:
  - product_knn_topk.json : {product_id: [[neighbor_id, sim], ...], ...}

Usage:
  python build_vector_cache.py
"""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    cache_dir = root / "cache"
    out_path = cache_dir / "product_knn_topk.json"

    try:
        from sklearn.preprocessing import MultiLabelBinarizer
        from sklearn.neighbors import NearestNeighbors
    except Exception as e:
        raise SystemExit(
            "ERROR: scikit-learn is required for build_vector_cache.py\n"
            "Install: pip install scikit-learn\n"
            f"Original error: {e}"
        )

    # Reuse STEP6 parsing so we don't create a second parser
    try:
        import recommend_mvp as rec
    except Exception as e:
        raise SystemExit(
            "ERROR: cannot import recommend_mvp.py. Make sure build_vector_cache.py is in the same folder.\n"
            f"Original error: {e}"
        )

    products = rec.load_products_with_ingredients(max_products=None)
    if not products:
        raise SystemExit("ERROR: No products loaded. Check cosmetics.csv path and format.")

    ids = [p["id"] for p in products]
    ing_lists = [p.get("ingredients", []) for p in products]

    # Binary ingredient presence matrix
    mlb = MultiLabelBinarizer(sparse_output=True)
    X = mlb.fit_transform(ing_lists)  # csr_matrix

    # KNN on cosine distance (cosine sim = 1 - dist)
    TOPK = 50
    nn = NearestNeighbors(n_neighbors=min(TOPK + 1, X.shape[0]), metric="cosine", algorithm="brute")
    nn.fit(X)
    dists, idxs = nn.kneighbors(X, return_distance=True)

    cache = {}
    for row_i, (dist_row, idx_row) in enumerate(zip(dists, idxs)):
        pid = ids[row_i]
        neighbors = []
        for dist, j in zip(dist_row, idx_row):
            if j == row_i:
                continue
            sim = float(max(0.0, 1.0 - float(dist)))
            if sim <= 0:
                continue
            neighbors.append([ids[j], round(sim, 6)])
        cache[pid] = neighbors[:TOPK]

    out_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Wrote KNN cache: {out_path} (products={len(products)}, topk={TOPK})")


if __name__ == "__main__":
    main()
