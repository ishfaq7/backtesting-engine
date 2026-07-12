from datetime import datetime, timezone

from btengine.decision.config import DecisionEngineConfig
from btengine.decision.context import DecisionRequest
from tests.decision.conftest import make_funding_analysis, make_liquidity_analysis, make_validated_strategy_state

UTC = timezone.utc


def test_analyses_property_maps_provider_names() -> None:
    funding = make_funding_analysis()
    liquidity = make_liquidity_analysis()
    request = DecisionRequest(
        symbol="BTCUSDT", reference_time=datetime(2024, 1, 1, tzinfo=UTC),
        validated_state=make_validated_strategy_state(), funding=funding, open_interest=None,
        premium_discount=None, liquidity=liquidity, config=DecisionEngineConfig(engine_version="v1"),
        provider_names=(),
    )
    assert request.analyses == {
        "funding": funding, "open_interest": None, "premium_discount": None, "liquidity": liquidity,
    }
