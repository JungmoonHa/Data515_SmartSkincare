"""Tests for skin_type_engine.py — skin type mapping & scoring."""
import pytest
from skin_type_engine import (
    _text_matches_types,
    user_input_to_profile,
    score_product,
    normalize_ingredient,
    KEYWORDS_FOR_TYPE,
)


# ---------- _text_matches_types ----------
class TestTextMatchesTypes:
    def test_hydration_keyword(self):
        types = _text_matches_types("Provides deep hydration and moisturizing")
        assert "dry" in types

    def test_anti_aging(self):
        types = _text_matches_types("Anti-aging peptide for wrinkle reduction")
        assert "wrinkle" in types

    def test_brightening(self):
        types = _text_matches_types("Brightening agent that evens skin tone")
        assert "pigmentation" in types

    def test_soothing(self):
        types = _text_matches_types("Soothing and calming for sensitive skin")
        assert "sensitive" in types

    def test_oily_keywords(self):
        types = _text_matches_types("Controls sebum and minimizes pore appearance")
        assert "oily" in types

    def test_no_match(self):
        assert _text_matches_types("A common preservative") == []

    def test_empty(self):
        assert _text_matches_types("") == []

    def test_multiple_types(self):
        types = _text_matches_types("hydration soothing anti-aging")
        assert len(types) >= 2

    def test_no_duplicates(self):
        types = _text_matches_types("hydration moisturizing humectant emollient")
        assert len(types) == len(set(types))


# ---------- user_input_to_profile ----------
class TestUserInputToProfile:
    def test_default_profile(self):
        profile = user_input_to_profile()
        assert profile["normal"] == 0.5
        assert profile["dry"] == 0.3
        assert profile["oily"] == 0.3
        assert profile["sensitive"] == 0.2

    def test_low_hydration(self):
        profile = user_input_to_profile(hydration_level="low")
        assert profile["dry"] == 0.9

    def test_high_oil(self):
        profile = user_input_to_profile(oil_level="high")
        assert profile["oily"] == 0.9

    def test_high_sensitivity(self):
        profile = user_input_to_profile(sensitivity="high")
        assert profile["sensitive"] == 0.9

    def test_pigmentation_concern(self):
        profile = user_input_to_profile(concerns=["pigmentation"])
        assert profile["pigmentation"] == 0.9

    def test_wrinkle_by_age(self):
        profile = user_input_to_profile(age=40)
        assert profile["wrinkle"] == 0.9

    def test_wrinkle_by_concern(self):
        profile = user_input_to_profile(concerns=["wrinkles"])
        assert profile["wrinkle"] == 0.9

    def test_dryness_concern(self):
        profile = user_input_to_profile(concerns=["dryness"])
        assert profile["dry"] == 0.9

    def test_all_keys_present(self):
        profile = user_input_to_profile()
        for key in KEYWORDS_FOR_TYPE:
            assert key in profile


# ---------- score_product ----------
class TestScoreProduct:
    def setup_method(self):
        self.type_map = {
            "glycerin": ["dry", "sensitive"],
            "niacinamide": ["oily", "pigmentation"],
            "retinol": ["wrinkle"],
        }

    def test_dry_profile_glycerin(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product(["glycerin"], profile, self.type_map)
        assert score > 0

    def test_oily_profile_niacinamide(self):
        profile = {"dry": 0.0, "normal": 0.0, "oily": 0.9,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product(["niacinamide"], profile, self.type_map)
        assert score > 0

    def test_no_matching_ingredients(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product(["unknown_ingredient"], profile, self.type_map)
        assert score == 0.0

    def test_empty_ingredients(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product([], profile, self.type_map)
        assert score == 0.0

    def test_higher_score_for_better_match(self):
        dry_profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                       "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score_match = score_product(["glycerin"], dry_profile, self.type_map)
        score_no_match = score_product(["retinol"], dry_profile, self.type_map)
        assert score_match > score_no_match

    def test_custom_normalize_fn(self):
        profile = {"dry": 0.9, "normal": 0.0, "oily": 0.0,
                   "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0}
        score = score_product(["GLYCERIN"], profile, self.type_map,
                              normalize_fn=lambda x: x.lower())
        assert score > 0
