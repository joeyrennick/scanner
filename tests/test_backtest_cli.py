import pytest

from backtest import (
    _parse_sweep_overlap,
    _parse_sweep_strategy_params,
    _parse_sweep_value,
)


def test_parse_sweep_overlap_maps_cli_terms_to_booleans():
    assert _parse_sweep_overlap(["allowed", "blocked"]) == [True, False]
    assert _parse_sweep_overlap(None) is None


def test_parse_sweep_strategy_params_parses_value_types():
    parsed = _parse_sweep_strategy_params(
        [
            "min_relative_volume=1.0,1.5",
            "require_prior_day_high_confirmation=true,false",
            "anchor=ma20,ma50",
            "optional_threshold=none",
        ]
    )

    assert parsed == {
        "min_relative_volume": [1.0, 1.5],
        "require_prior_day_high_confirmation": [True, False],
        "anchor": ["ma20", "ma50"],
        "optional_threshold": [None],
    }


def test_parse_sweep_strategy_params_requires_name_value_format():
    with pytest.raises(ValueError, match="NAME=VALUE"):
        _parse_sweep_strategy_params(["min_relative_volume"])


def test_parse_sweep_value_prefers_numbers_before_strings():
    assert _parse_sweep_value("3") == 3
    assert _parse_sweep_value("0.05") == 0.05
    assert _parse_sweep_value("false") is False
    assert _parse_sweep_value("ma20") == "ma20"
