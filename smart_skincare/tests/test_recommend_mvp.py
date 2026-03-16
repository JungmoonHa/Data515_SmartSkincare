"""Tests for recommend_mvp.py — product scoring & recommendation logic."""
from recommend_mvp import (
    _confidence_weight,
    _has_inci_like_pattern,
    _infer_tier,
    _ingredient_family,
    _is_marketing_no_score_ingredient,
    _normalize,
    _raw_ingredients_classification,
    _saturate,
    _should_drop_ingredient_token,
    count_active_wrinkle_hits,
    fallback_entry_from_family,
    get_key_ingredients,
    score_product_mvp,
    top_types,
    user_input_to_profile,
)


# ---------- _confidence_weight ----------
class TestConfidenceWeight:
    def test_high(self):
        assert _confidence_weight("high") == 1.0

    def test_medium(self):
        assert _confidence_weight("medium") == 0.6

    def test_low(self):
        assert _confidence_weight("low") == 0.3

    def test_default(self):
        assert _confidence_weight("unknown") == 0.3

    def test_none(self):
        assert _confidence_weight(None) == 0.3


# ---------- _saturate ----------
class TestSaturate:
    def test_zero(self):
        assert _saturate(0, 10) == 0.0

    def test_positive(self):
        result = _saturate(5, 10)
        assert 0 < result < 10

    def test_large_x_diminishing_returns(self):
        """Growth slows for large x (log-based saturation, not hard cap)."""
        result = _saturate(100, 10)
        assert result > _saturate(10, 10)  # still grows
        assert result < 100  # but much less than linear

    def test_cap_zero(self):
        assert _saturate(5, 0) == 0.0

    def test_monotonic(self):
        a = _saturate(3, 10)
        b = _saturate(5, 10)
        c = _saturate(10, 10)
        assert a < b < c


# ---------- _infer_tier ----------
class TestInferTier:
    def test_retinol_is_active(self):
        assert _infer_tier("retinol") == "active"

    def test_peptide_is_active(self):
        assert _infer_tier("palmitoyl tripeptide-1") == "active"

    def test_niacinamide_is_active(self):
        assert _infer_tier("niacinamide") == "active"

    def test_glycerin_is_base(self):
        assert _infer_tier("glycerin") == "base"

    def test_shea_butter_is_base(self):
        assert _infer_tier("shea butter") == "base"

    def test_unknown_is_other(self):
        assert _infer_tier("phenoxyethanol") == "other"

    def test_empty(self):
        assert _infer_tier("") == "other"


# ---------- _ingredient_family ----------
class TestIngredientFamily:
    def test_retinoid(self):
        assert _ingredient_family("retinol") == "retinoid"
        assert _ingredient_family("retinal") == "retinoid"

    def test_peptide(self):
        assert _ingredient_family("hexapeptide-9") == "peptide"
        assert _ingredient_family("copper tripeptide-1") == "peptide"

    def test_aha_bha(self):
        assert _ingredient_family("glycolic acid") == "aha_bha"
        assert _ingredient_family("salicylic acid") == "aha_bha"

    def test_humectant(self):
        assert _ingredient_family("hyaluronic acid") == "humectant"
        assert _ingredient_family("glycerin") == "humectant"

    def test_barrier(self):
        assert _ingredient_family("ceramide np") == "barrier"

    def test_emollient(self):
        assert _ingredient_family("squalane") == "emollient"
        assert _ingredient_family("jojoba seed oil") == "emollient"

    def test_sebum_control(self):
        assert _ingredient_family("niacinamide") == "sebum_control"
        assert _ingredient_family("kaolin") == "sebum_control"

    def test_antioxidant(self):
        assert _ingredient_family("ascorbic acid") == "antioxidant"
        assert _ingredient_family("tocopherol") == "antioxidant"

    def test_other(self):
        assert _ingredient_family("phenoxyethanol") == "other"


# ---------- fallback_entry_from_family ----------
class TestFallbackEntryFromFamily:
    def test_retinoid_fallback(self):
        entry = fallback_entry_from_family("retinol")
        assert entry is not None
        assert "wrinkle" in entry["skin_types"]
        assert entry["effect"] == "good"
        assert entry["source"] == "fallback_family"

    def test_fragrance_avoid(self):
        entry = fallback_entry_from_family("fragrance")
        assert entry is not None
        assert entry["effect"] == "avoid"

    def test_parfum_avoid(self):
        entry = fallback_entry_from_family("parfum")
        assert entry["effect"] == "avoid"

    def test_unknown_returns_none(self):
        assert fallback_entry_from_family("phenoxyethanol") is None

    def test_empty(self):
        assert fallback_entry_from_family("") is None

    def test_humectant_fallback(self):
        entry = fallback_entry_from_family("hyaluronic acid")
        assert entry is not None
        assert "dry" in entry["skin_types"]


# ---------- top_types ----------
class TestTopTypes:
    def test_basic(self):
        profile = {"dry": 0.9, "oily": 0.5, "wrinkle": 0.3, "normal": 0.0}
        result = top_types(profile, k=2)
        assert result == ["dry", "oily"]

    def test_min_weight(self):
        profile = {"dry": 0.05, "oily": 0.05}
        result = top_types(profile, k=2, min_w=0.1)
        assert result == []

    def test_empty_profile(self):
        assert top_types({}, k=2) == []

    def test_none_profile(self):
        assert top_types(None, k=2) == []


# ---------- _normalize ----------
class TestNormalize:
    def test_basic(self):
        assert _normalize("  Glycerin  ") == "glycerin"

    def test_empty(self):
        assert _normalize("") == ""

    def test_none(self):
        assert _normalize(None) == ""


# ---------- user_input_to_profile ----------
class TestUserInputToProfile:
    def test_default(self):
        profile = user_input_to_profile()
        assert profile["normal"] == 0.5
        assert profile["dry"] == 0.0

    def test_low_hydration(self):
        profile = user_input_to_profile(hydration_level="low")
        assert profile["dry"] == 0.9

    def test_oily(self):
        profile = user_input_to_profile(oil_level="high")
        assert profile["oily"] == 0.9

    def test_sensitive(self):
        profile = user_input_to_profile(sensitivity="high")
        assert profile["sensitive"] == 0.9

    def test_pigmentation_concern(self):
        profile = user_input_to_profile(concerns=["pigmentation"])
        assert profile["pigmentation"] == 0.9

    def test_wrinkle_age(self):
        profile = user_input_to_profile(age=40)
        assert profile["wrinkle"] == 0.9

    def test_wrinkle_concern(self):
        profile = user_input_to_profile(concerns=["wrinkles"])
        assert profile["wrinkle"] == 0.9

    def test_normal_only_when_all_zero(self):
        profile = user_input_to_profile()
        assert profile["normal"] == 0.5


# ---------- _is_marketing_no_score_ingredient ----------
class TestIsMarketingNoScore:
    def test_complex(self):
        assert _is_marketing_no_score_ingredient("moisture complex") is True

    def test_technology(self):
        assert _is_marketing_no_score_ingredient("hydra technology") is True

    def test_normal_ingredient(self):
        assert _is_marketing_no_score_ingredient("glycerin") is False

    def test_empty(self):
        assert _is_marketing_no_score_ingredient("") is True


# ---------- _should_drop_ingredient_token ----------
class TestShouldDropToken:
    def test_normal_ingredient(self):
        assert _should_drop_ingredient_token("glycerin") is False

    def test_too_long(self):
        assert _should_drop_ingredient_token("x" * 61) is True

    def test_url_marker(self):
        assert _should_drop_ingredient_token("see http://example.com") is True

    def test_marketing_keyword(self):
        assert _should_drop_ingredient_token("clinically proven formula") is True

    def test_empty(self):
        assert _should_drop_ingredient_token("") is True

    def test_unit_marker(self):
        assert _should_drop_ingredient_token("retinol 5 mg dose") is True


# ---------- _has_inci_like_pattern ----------
class TestHasInciLikePattern:
    def test_inci_with_parens(self):
        raw = "Rosa Canina (Rosehip), Glycerin, Water, Niacinamide, Retinol"
        assert _has_inci_like_pattern(raw) is True

    def test_seed_oil(self):
        raw = "jojoba seed oil, water, glycerin, niacinamide, retinol"
        assert _has_inci_like_pattern(raw) is True

    def test_no_inci(self):
        assert _has_inci_like_pattern("hello world") is False

    def test_few_commas(self):
        assert _has_inci_like_pattern("a, b, c") is False


# ---------- _raw_ingredients_classification ----------
class TestRawIngredientsClassification:
    def test_normal_text(self):
        result = _raw_ingredients_classification("Water, Glycerin, Niacinamide")
        assert result["use_parser"] is True

    def test_dynamic_formula(self):
        result = _raw_ingredients_classification("ingredients will be based on your quiz results")
        assert result["use_parser"] is False
        assert result["reason"] == "dynamic_formula"

    def test_non_cosmetic(self):
        result = _raw_ingredients_classification("100% long-fiber mulberry silk pillowcase")
        assert result["use_parser"] is False
        assert result["reason"] == "non_cosmetic_material"

    def test_empty(self):
        result = _raw_ingredients_classification("")
        assert result["use_parser"] is True


# ---------- score_product_mvp ----------
class TestScoreProductMvp:
    def setup_method(self):
        self.skin_map = {
            "glycerin": {"skin_types": ["dry", "sensitive"], "effect": "good", "confidence": "high"},
            "niacinamide": {"skin_types": ["oily", "pigmentation"], "effect": "good", "confidence": "high"},
            "retinol": {"skin_types": ["wrinkle"], "effect": "good", "confidence": "high", "tier": "active"},
            "fragrance": {"skin_types": ["sensitive"], "effect": "avoid", "confidence": "high"},
        }
        self.paula_rating = {}

    def test_good_ingredient_positive_score(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product_mvp(["glycerin"], profile, self.skin_map, self.paula_rating)
        assert score > 0

    def test_avoid_ingredient_lowers_score(self):
        profile = {"dry": 0.0, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.9, "wrinkle": 0.0}
        score_no_frag = score_product_mvp(
            ["glycerin"], profile, self.skin_map, self.paula_rating)
        score_with_frag = score_product_mvp(
            ["glycerin", "fragrance"], profile, self.skin_map, self.paula_rating)
        assert score_with_frag < score_no_frag

    def test_empty_ingredients(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product_mvp([], profile, self.skin_map, self.paula_rating)
        assert score == 0.0

    def test_rating_bonus(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score_no_rating = score_product_mvp(
            ["glycerin"], profile, self.skin_map, self.paula_rating, rating=0)
        score_with_rating = score_product_mvp(
            ["glycerin"], profile, self.skin_map, self.paula_rating, rating=5.0)
        assert score_with_rating > score_no_rating

    def test_poor_paula_rating_penalty(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        paula = {"glycerin": "poor"}
        score_poor = score_product_mvp(["glycerin"], profile, self.skin_map, paula)
        score_ok = score_product_mvp(["glycerin"], profile, self.skin_map, {})
        assert score_poor < score_ok


# ---------- get_key_ingredients ----------
class TestGetKeyIngredients:
    def setup_method(self):
        self.skin_map = {
            "glycerin": {"skin_types": ["dry"], "effect": "good", "confidence": "high"},
            "retinol": {"skin_types": ["wrinkle"], "effect": "good", "confidence": "high", "tier": "active"},
            "niacinamide": {"skin_types": ["oily"], "effect": "good", "confidence": "high"},
            "fragrance": {"skin_types": ["sensitive"], "effect": "avoid", "confidence": "high"},
        }

    def test_returns_good_only(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        keys = get_key_ingredients(
            ["glycerin", "fragrance"], profile, self.skin_map, n=3)
        assert "glycerin" in keys
        assert "fragrance" not in keys

    def test_respects_n(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.9}
        keys = get_key_ingredients(
            ["glycerin", "retinol", "niacinamide"], profile, self.skin_map, n=2)
        assert len(keys) <= 2

    def test_empty_ingredients(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        keys = get_key_ingredients([], profile, self.skin_map, n=3)
        assert keys == []


# ---------- count_active_wrinkle_hits ----------
class TestCountActiveWrinkleHits:
    def test_one_active(self):
        skin_map = {
            "retinol": {"skin_types": ["wrinkle"], "effect": "good", "confidence": "high", "tier": "active"},
        }
        count = count_active_wrinkle_hits(["retinol", "glycerin"], skin_map)
        assert count == 1

    def test_no_wrinkle(self):
        skin_map = {
            "glycerin": {"skin_types": ["dry"], "effect": "good", "confidence": "high"},
        }
        count = count_active_wrinkle_hits(["glycerin"], skin_map)
        assert count == 0

    def test_deduplicates(self):
        skin_map = {
            "retinol": {"skin_types": ["wrinkle"], "effect": "good", "confidence": "high", "tier": "active"},
        }
        count = count_active_wrinkle_hits(["retinol", "retinol", "retinol"], skin_map)
        assert count == 1
