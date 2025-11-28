"""Tests for pollutant library."""

import pytest
from app.core.pollutant_library import (
    POLLUTANT_MAP,
    get_pollutant_info,
    get_pollutant_name,
    get_all_pollutant_codes,
    is_known_pollutant,
    format_value,
    get_pollutant_column_name,
    get_tdengine_columns_definition,
    get_pollutants_by_category,
    get_all_categories,
    POLLUTANT_CATEGORIES,
)


class TestPollutantLibrary:
    """Test cases for pollutant library."""

    def test_pollutant_map_not_empty(self):
        """Pollutant map should have many entries."""
        assert len(POLLUTANT_MAP) >= 60, "Should have at least 60 pollutants"

    def test_get_pollutant_info_known(self):
        """Should return info for known pollutant."""
        info = get_pollutant_info("w01018")
        assert info is not None
        assert info["name"] == "化学需氧量(CODcr)"
        assert info["unit"] == "mg/L"
        assert info["precision"] == 2

    def test_get_pollutant_info_unknown(self):
        """Should return None for unknown pollutant."""
        info = get_pollutant_info("w99999")
        assert info is None

    def test_get_pollutant_info_case_insensitive(self):
        """Should be case insensitive."""
        info = get_pollutant_info("W01018")
        assert info is not None
        assert info["name"] == "化学需氧量(CODcr)"

    def test_get_pollutant_name_known(self):
        """Should return name for known pollutant."""
        name = get_pollutant_name("w21003")
        assert name == "氨氮"

    def test_get_pollutant_name_unknown(self):
        """Should return code itself for unknown pollutant."""
        name = get_pollutant_name("w99999")
        assert name == "w99999"

    def test_get_all_pollutant_codes(self):
        """Should return all codes."""
        codes = get_all_pollutant_codes()
        assert len(codes) >= 60
        assert "w01018" in codes
        assert "w21003" in codes

    def test_is_known_pollutant(self):
        """Should correctly identify known pollutants."""
        assert is_known_pollutant("w01018") is True
        assert is_known_pollutant("w99999") is False
        assert is_known_pollutant("W01018") is True

    def test_format_value_known(self):
        """Should format value with correct precision."""
        # CODcr has precision 2
        result = format_value("w01018", 45.6789)
        assert result == "45.68"

        # 总汞 has precision 5
        result = format_value("w20111", 0.0001234)
        assert result == "0.00012"

    def test_format_value_unknown(self):
        """Should use default precision 2 for unknown."""
        result = format_value("w99999", 45.6789)
        assert result == "45.68"

    def test_get_pollutant_column_name(self):
        """Should return lowercase column name."""
        assert get_pollutant_column_name("W01018") == "w01018"
        assert get_pollutant_column_name("w21003") == "w21003"

    def test_get_tdengine_columns_definition(self):
        """Should generate valid SQL column definitions."""
        columns_sql = get_tdengine_columns_definition()
        assert "w01018_val DOUBLE" in columns_sql
        assert "w01018_flag NCHAR(8)" in columns_sql
        assert "w21003_val DOUBLE" in columns_sql

    def test_pollutant_categories_exist(self):
        """Should have defined categories."""
        categories = get_all_categories()
        assert len(categories) > 0
        assert "physical" in categories
        assert "heavy_metals_class1" in categories

    def test_get_pollutants_by_category(self):
        """Should return pollutants in category."""
        heavy_metals = get_pollutants_by_category("heavy_metals_class1")
        assert len(heavy_metals) > 0
        codes = [p["code"] for p in heavy_metals]
        assert "w20111" in codes  # 总汞
        assert "w20115" in codes  # 总镉

    def test_heavy_metals_high_precision(self):
        """Heavy metals should have high precision."""
        # Class 1 heavy metals (most toxic)
        hg_info = get_pollutant_info("w20111")  # 总汞
        cd_info = get_pollutant_info("w20115")  # 总镉
        assert hg_info["precision"] >= 5
        assert cd_info["precision"] >= 5

    def test_all_category_codes_in_map(self):
        """All category codes should exist in POLLUTANT_MAP."""
        for category, codes in POLLUTANT_CATEGORIES.items():
            for code in codes:
                assert code in POLLUTANT_MAP, f"{code} in category {category} not in POLLUTANT_MAP"


class TestPollutantCoverage:
    """Test coverage of HJ 212 standard pollutants."""

    def test_physical_parameters(self):
        """Should have common physical parameters."""
        physical = ["w01001", "w01010", "w01003", "w01014", "w01009"]
        for code in physical:
            assert code in POLLUTANT_MAP, f"Missing physical parameter: {code}"

    def test_organic_parameters(self):
        """Should have organic pollutant parameters."""
        organic = ["w01018", "w01019", "w01017"]
        for code in organic:
            assert code in POLLUTANT_MAP, f"Missing organic parameter: {code}"

    def test_nitrogen_phosphorus(self):
        """Should have nitrogen and phosphorus parameters."""
        np_codes = ["w21003", "w21001", "w21011", "w21006", "w21007"]
        for code in np_codes:
            assert code in POLLUTANT_MAP, f"Missing N/P parameter: {code}"

    def test_heavy_metals(self):
        """Should have key heavy metals."""
        metals = [
            "w20111", "w20115", "w20117", "w20119", "w20120",  # Class 1
            "w20122", "w20123", "w20121", "w20124", "w20125",  # Class 2
        ]
        for code in metals:
            assert code in POLLUTANT_MAP, f"Missing heavy metal: {code}"
