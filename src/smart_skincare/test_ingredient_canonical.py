"""Tests for ingredient_canonical.py — ingredient name normalization."""
import pytest
from ingredient_canonical import (
    normalize_ingredient,
    paula_canonicalize,
    normalize_strict,
    normalize_with_abbreviations,
    canonicalize_ingredient,
    build_initial_aliases_from_paula,
    add_aliases_from_synonyms,
    COMMON_ABBREVIATIONS,
)


# ---------- normalize_ingredient ----------
class TestNormalizeIngredient:
    def test_basic(self):
        assert normalize_ingredient("  Glycerin  ") == "glycerin"

    def test_collapse_spaces(self):
        assert normalize_ingredient("sodium   hyaluronate") == "sodium hyaluronate"

    def test_empty(self):
        assert normalize_ingredient("") == ""

    def test_none(self):
        assert normalize_ingredient(None) == ""

    def test_non_string(self):
        assert normalize_ingredient(42) == ""


# ---------- paula_canonicalize ----------
class TestPaulaCanonicalize:
    def test_removes_parens(self):
        assert paula_canonicalize("Glycerin (Glycerol)") == "glycerin"

    def test_removes_periods(self):
        assert paula_canonicalize("Vit. C") == "vit c"

    def test_combined(self):
        assert paula_canonicalize("  Alpha Hydroxy Acid (AHA) 2.0  ") == "alpha hydroxy acid 20"

    def test_empty(self):
        assert paula_canonicalize("") == ""

    def test_none(self):
        assert paula_canonicalize(None) == ""


# ---------- normalize_strict ----------
class TestNormalizeStrict:
    def test_trailing_asterisks(self):
        result = normalize_strict("ingredient**")
        assert result == "ingredient"

    def test_leading_dots(self):
        result = normalize_strict("..ingredient")
        assert result == "ingredient"

    def test_slash_to_space(self):
        assert normalize_strict("a / b") == "a b"
        assert normalize_strict("a/b") == "a b"

    def test_drop_parentheses_true(self):
        assert normalize_strict("glycerin (glycerol)", drop_parentheses=True) == "glycerin"

    def test_drop_parentheses_false(self):
        result = normalize_strict("glycerin (glycerol)", drop_parentheses=False)
        assert "glycerol" in result

    def test_empty(self):
        assert normalize_strict("") == ""

    def test_none(self):
        assert normalize_strict(None) == ""


# ---------- normalize_with_abbreviations ----------
class TestNormalizeWithAbbreviations:
    def test_ha_expansion(self):
        assert normalize_with_abbreviations("HA") == "hyaluronic acid"

    def test_bha_expansion(self):
        assert normalize_with_abbreviations("BHA") == "salicylic acid"

    def test_non_abbreviation(self):
        assert normalize_with_abbreviations("glycerin") == "glycerin"

    def test_custom_map(self):
        custom = {"vit c": "ascorbic acid"}
        assert normalize_with_abbreviations("Vit C", abbr_map=custom) == "ascorbic acid"


# ---------- canonicalize_ingredient ----------
class TestCanonicalizeIngredient:
    def test_with_alias(self):
        aliases = {"glycerol": "glycerin"}
        result = canonicalize_ingredient("  Glycerol  ", alias_map=aliases)
        assert result == "glycerin"

    def test_without_alias(self):
        result = canonicalize_ingredient("niacinamide", alias_map={})
        assert result == "niacinamide"

    def test_empty(self):
        assert canonicalize_ingredient("") == ""

    def test_abbreviation_then_alias(self):
        aliases = {"hyaluronic acid": "sodium hyaluronate"}
        result = canonicalize_ingredient("HA", alias_map=aliases)
        assert result == "sodium hyaluronate"


# ---------- build_initial_aliases_from_paula ----------
class TestBuildInitialAliases:
    def test_self_mapping(self):
        paula_set = {"glycerin", "niacinamide", "retinol"}
        aliases = build_initial_aliases_from_paula(paula_set)
        for name in paula_set:
            assert aliases[name] == name

    def test_empty_set(self):
        assert build_initial_aliases_from_paula(set()) == {}


# ---------- add_aliases_from_synonyms ----------
class TestAddAliasesFromSynonyms:
    def test_adds_pairs(self):
        alias_map = {"glycerin": "glycerin"}
        pairs = [("glycerol", "glycerin"), ("vitamin b3", "niacinamide")]
        result = add_aliases_from_synonyms(alias_map, pairs)
        assert result["glycerol"] == "glycerin"
        assert result["vitamin b3"] == "niacinamide"

    def test_skips_same(self):
        alias_map = {}
        pairs = [("glycerin", "glycerin")]
        result = add_aliases_from_synonyms(alias_map, pairs)
        assert "glycerin" not in result

    def test_skips_empty(self):
        alias_map = {}
        pairs = [("", "glycerin"), ("water", "")]
        result = add_aliases_from_synonyms(alias_map, pairs)
        assert result == {}
