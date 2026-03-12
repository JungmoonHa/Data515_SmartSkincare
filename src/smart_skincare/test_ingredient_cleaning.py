"""Tests for ingredient_cleaning.py — raw ingredient string cleaning."""
import pytest
from ingredient_cleaning import (
    _remove_percent,
    _remove_parentheses,
    _normalize_space,
    clean_one_ingredient,
    is_junk,
    split_on_ingredients_label,
    split_compound,
    clean_raw_ingredient,
)


# ---------- _remove_percent ----------
class TestRemovePercent:
    def test_trailing_percent(self):
        assert _remove_percent("zinc oxide (6.993%)") == "zinc oxide"

    def test_trailing_integer_percent(self):
        assert _remove_percent("niacinamide (10%)") == "niacinamide"

    def test_no_percent(self):
        assert _remove_percent("glycerin") == "glycerin"

    def test_middle_percent(self):
        result = _remove_percent("a (5%) b")
        assert "5%" not in result

    def test_empty(self):
        assert _remove_percent("") == ""


# ---------- _remove_parentheses ----------
class TestRemoveParentheses:
    def test_simple(self):
        assert _remove_parentheses("glycerin (glycerol)").strip() == "glycerin"

    def test_no_parens(self):
        assert _remove_parentheses("water") == "water"

    def test_multiple_parens(self):
        result = _remove_parentheses("a (b) c (d)")
        assert "b" not in result
        assert "d" not in result


# ---------- _normalize_space ----------
class TestNormalizeSpace:
    def test_basic(self):
        assert _normalize_space("  Hello   World  ") == "hello world"

    def test_tabs(self):
        assert _normalize_space("a\t\tb") == "a b"

    def test_empty(self):
        assert _normalize_space("") == ""


# ---------- clean_one_ingredient ----------
class TestCleanOneIngredient:
    def test_full_clean(self):
        assert clean_one_ingredient("  Glycerin (Glycerol) (6.993%)  ") == "glycerin"

    def test_removes_periods(self):
        assert clean_one_ingredient("Vit. C") == "vit c"

    def test_empty_input(self):
        assert clean_one_ingredient("") == ""

    def test_none_input(self):
        assert clean_one_ingredient(None) == ""

    def test_non_string(self):
        assert clean_one_ingredient(123) == ""

    def test_lowercase(self):
        assert clean_one_ingredient("WATER") == "water"


# ---------- is_junk ----------
class TestIsJunk:
    def test_short_is_junk(self):
        assert is_junk("") is True
        assert is_junk("a") is True

    def test_normal_ingredient_not_junk(self):
        assert is_junk("glycerin") is False

    def test_long_with_visit(self):
        text = "x" * 40 + " visit our website for more info"
        assert is_junk(text) is True

    def test_visit_boutique(self):
        assert is_junk("visit the boutique for more") is True

    def test_short_with_visit_ok(self):
        assert is_junk("visit") is False  # len < 40


# ---------- split_on_ingredients_label ----------
class TestSplitOnIngredientsLabel:
    def test_with_label(self):
        result = split_on_ingredients_label("Product X Ingredients: water, glycerin, niacinamide")
        assert result == ["water", "glycerin", "niacinamide"]

    def test_without_label(self):
        assert split_on_ingredients_label("water, glycerin") == ["water, glycerin"]

    def test_empty(self):
        assert split_on_ingredients_label("") == []

    def test_none(self):
        assert split_on_ingredients_label(None) == []

    def test_label_at_end(self):
        assert split_on_ingredients_label("Ingredients:") == []


# ---------- split_compound ----------
class TestSplitCompound:
    def test_basic(self):
        assert split_compound("phenoxyethanol, 1,2-hexanediol") == [
            "phenoxyethanol",
            "1,2-hexanediol",
        ]

    def test_single(self):
        assert split_compound("water") == ["water"]

    def test_empty(self):
        assert split_compound("") == []

    def test_none(self):
        assert split_compound(None) == []


# ---------- clean_raw_ingredient ----------
class TestCleanRawIngredient:
    def test_compound(self):
        result = clean_raw_ingredient("Water, Glycerin, Niacinamide")
        assert "water" in result
        assert "glycerin" in result
        assert "niacinamide" in result

    def test_drops_junk(self):
        junk = "visit the boutique for more info about this product"
        result = clean_raw_ingredient(junk)
        assert result == []

    def test_with_ingredients_label(self):
        result = clean_raw_ingredient("Product Ingredients: water, glycerin")
        assert "water" in result
        assert "glycerin" in result

    def test_empty(self):
        assert clean_raw_ingredient("") == []

    def test_none(self):
        assert clean_raw_ingredient(None) == []

    def test_drops_short(self):
        result = clean_raw_ingredient("ab")
        assert result == []
