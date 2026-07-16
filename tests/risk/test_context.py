from btengine.risk.config import RiskEngineConfig, RiskProfile
from btengine.risk.context import RiskRequest
from tests.risk.conftest import NOW, make_decision_context, make_portfolio, make_strategy_score


def _request(config: RiskEngineConfig) -> RiskRequest:
    return RiskRequest(
        symbol="BTCUSDT", reference_time=NOW, decision_context=make_decision_context(),
        score=make_strategy_score(), portfolio=make_portfolio(), market_data=None, config=config,
    )


def test_profile_property_is_none_without_active_profile() -> None:
    assert _request(RiskEngineConfig(engine_version="v1")).profile is None


def test_profile_property_returns_active_profile() -> None:
    profile = RiskProfile(name="p", max_leverage=2.0)
    config = RiskEngineConfig(engine_version="v1", profiles={"p": profile}, active_profile="p")
    assert _request(config).profile is profile
