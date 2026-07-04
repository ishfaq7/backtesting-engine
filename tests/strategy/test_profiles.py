import pytest

from btengine.strategy.profiles import StrategyProfile, StrategyProfileName


def test_valid_profile_construction() -> None:
    profile = StrategyProfile(
        name=StrategyProfileName.BALANCED,
        max_risk_per_trade_pct=1.0,
        max_concurrent_positions=2,
        max_portfolio_exposure_pct=50.0,
    )
    assert profile.name == StrategyProfileName.BALANCED


@pytest.mark.parametrize(
    "field, value",
    [("max_risk_per_trade_pct", 0), ("max_concurrent_positions", 0), ("max_portfolio_exposure_pct", 0)],
)
def test_rejects_nonpositive_fields(field: str, value: float) -> None:
    kwargs = dict(
        name=StrategyProfileName.AGGRESSIVE,
        max_risk_per_trade_pct=1.0,
        max_concurrent_positions=2,
        max_portfolio_exposure_pct=50.0,
    )
    kwargs[field] = value
    with pytest.raises(ValueError):
        StrategyProfile(**kwargs)


def test_profile_is_frozen() -> None:
    profile = StrategyProfile(
        name=StrategyProfileName.CONSERVATIVE,
        max_risk_per_trade_pct=0.5,
        max_concurrent_positions=1,
        max_portfolio_exposure_pct=25.0,
    )
    with pytest.raises(Exception):
        profile.max_concurrent_positions = 5  # type: ignore[misc]


def test_profile_name_enum_values() -> None:
    assert {p.value for p in StrategyProfileName} == {"CONSERVATIVE", "BALANCED", "AGGRESSIVE"}
