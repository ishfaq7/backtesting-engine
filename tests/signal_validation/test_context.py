from datetime import datetime, timezone

from btengine.signal_validation.config import SignalValidationConfig
from btengine.signal_validation.context import ValidationContext
from tests.signal_validation.conftest import (
    make_funding_analysis,
    make_liquidity_analysis,
    make_strategy_score,
)

UTC = timezone.utc


def test_analyses_property_maps_provider_names() -> None:
    funding = make_funding_analysis()
    liquidity = make_liquidity_analysis()
    context = ValidationContext(
        symbol="BTCUSDT", reference_time=datetime(2024, 1, 1, tzinfo=UTC), score=make_strategy_score(),
        funding=funding, open_interest=None, premium_discount=None, liquidity=liquidity,
        config=SignalValidationConfig(engine_version="v1"),
    )
    assert context.analyses == {
        "funding": funding, "open_interest": None, "premium_discount": None, "liquidity": liquidity,
    }
