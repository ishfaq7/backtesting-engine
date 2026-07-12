from datetime import datetime, timezone

import pytest

from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.scoring.aggregation import ScoreAggregator, WeightedSumAggregator
from btengine.scoring.config import ConfidenceAggregationMethod, ScoringEngineConfig, ScoreWeights
from btengine.scoring.engine import ScoringEngine
from btengine.scoring.models import FeatureStatus, ScoreComponent, ValidationStatus
from btengine.scoring.providers.base import ScoreProvider
from btengine.scoring.providers.funding import FundingScoreProvider
from btengine.scoring.validation import StrategyScoreValidator

UTC = timezone.utc


def _funding_analysis(confidence: float = 1.0) -> FundingAnalysis:
    return FundingAnalysis(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), current_funding=0.0001,
        previous_funding=0.0001, funding_change=0.0, funding_change_pct=0.0,
        funding_trend=FundingDirection.FLAT, funding_trend_value=0.0,
        funding_momentum=FundingDirection.FLAT, funding_momentum_value=0.0, funding_volatility=0.0,
        historical_average=0.0001, historical_maximum=0.0001, historical_minimum=0.0001,
        sample_size=30, confidence_level=confidence,
    )


def _liquidity_analysis(confidence: float = 1.0) -> LiquidityAnalysis:
    return LiquidityAnalysis(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), sample_size=30, confidence_level=confidence,
        long_liquidation_volume=1000.0, short_liquidation_volume=500.0, total_liquidation_volume=1500.0,
        liquidation_event_count=30, liquidation_bias=0.33, liquidation_intensity=None,
        is_abnormal_liquidation=None, long_short_ratio=None, top_trader_account_bias=None,
        top_trader_position_bias=None, top_trader_bias=None, market_crowdedness=None,
        market_participation=None, current_open_interest=None, current_price=None,
        liquidity_pressure=None, liquidity_shift=None,
    )


class _FakeProvider(ScoreProvider[FundingAnalysis]):
    """Test double that actually computes a value (real providers never do)."""

    def __init__(self, *, name: str, value: float | None, version: str = "v1") -> None:
        self._name = name
        self._value = value
        self._version = version

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._version

    def compute(self, analysis) -> ScoreComponent:
        return ScoreComponent(
            provider_name=self._name, provider_version=self._version, value=self._value,
            weight=None, confidence=analysis.confidence_level,
        )


def test_score_with_no_analyses_is_all_missing() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    result = engine.score("btcusdt", datetime(2024, 1, 1, tzinfo=UTC))
    assert result.symbol == "BTCUSDT"
    assert result.funding_score is None
    assert result.total_score is None
    assert result.confidence is None
    assert result.feature_status == {
        "funding": FeatureStatus.MISSING, "open_interest": FeatureStatus.MISSING,
        "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
    }
    assert result.validation_status == ValidationStatus.VALID


def test_score_version_matches_config() -> None:
    config = ScoringEngineConfig(engine_version="v42")
    engine = ScoringEngine(config)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    assert result.score_version == "v42"


def test_framework_only_provider_yields_not_implemented_status() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config, funding_provider=FundingScoreProvider(version="v1"))
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.NOT_IMPLEMENTED
    assert result.funding_score is None
    assert result.total_score is None


def test_analysis_given_but_no_provider_configured_is_missing() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)  # no providers injected
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.MISSING


def test_fake_provider_produces_available_component() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    provider = _FakeProvider(name="funding", value=0.8)
    engine = ScoringEngine(config, funding_provider=provider)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.AVAILABLE
    assert result.funding_score.value == 0.8


def test_invalid_nan_component_is_flagged_invalid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    provider = _FakeProvider(name="funding", value=float("nan"))
    engine = ScoringEngine(config, funding_provider=provider)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.INVALID
    assert result.validation_status == ValidationStatus.INVALID


def test_infinite_component_is_flagged_invalid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    provider = _FakeProvider(name="funding", value=float("inf"))
    engine = ScoringEngine(config, funding_provider=provider)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.INVALID


def test_component_with_none_value_is_flagged_invalid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    provider = _FakeProvider(name="funding", value=None)
    engine = ScoringEngine(config, funding_provider=provider)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.feature_status["funding"] == FeatureStatus.INVALID


def test_total_score_computed_from_available_components_and_weights() -> None:
    config = ScoringEngineConfig(
        engine_version="v1", weights=ScoreWeights(funding=1.0, liquidity=1.0)
    )
    engine = ScoringEngine(
        config,
        funding_provider=_FakeProvider(name="funding", value=0.8),
        liquidity_provider=_FakeProvider(name="liquidity", value=0.2),
    )
    result = engine.score(
        "BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC),
        funding=_funding_analysis(), liquidity=_liquidity_analysis(),
    )
    assert result.total_score == pytest.approx(0.5)


def test_total_score_is_none_when_weight_is_missing() -> None:
    config = ScoringEngineConfig(engine_version="v1")  # no weights configured
    engine = ScoringEngine(config, funding_provider=_FakeProvider(name="funding", value=0.8))
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.total_score is None


def test_total_score_is_none_when_validation_status_is_invalid() -> None:
    config = ScoringEngineConfig(
        engine_version="v1", weights=ScoreWeights(funding=1.0), required_providers=("liquidity",)
    )
    engine = ScoringEngine(config, funding_provider=_FakeProvider(name="funding", value=0.8))
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.validation_status == ValidationStatus.INVALID
    assert result.total_score is None


# --- confidence aggregation ----------------------------------------------------------


def test_confidence_is_none_with_no_analyses() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    assert result.confidence is None


def test_confidence_min_aggregation_is_default() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    result = engine.score(
        "BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC),
        funding=_funding_analysis(confidence=0.3), liquidity=_liquidity_analysis(confidence=0.9),
    )
    assert result.confidence == pytest.approx(0.3)


def test_confidence_aggregation_rejects_unsupported_method() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    object.__setattr__(engine._config, "confidence_aggregation", "UNSUPPORTED")  # noqa: SLF001
    with pytest.raises(NotImplementedError):
        engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())


def test_confidence_mean_aggregation() -> None:
    config = ScoringEngineConfig(
        engine_version="v1", confidence_aggregation=ConfidenceAggregationMethod.MEAN
    )
    engine = ScoringEngine(config)
    result = engine.score(
        "BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC),
        funding=_funding_analysis(confidence=0.2), liquidity=_liquidity_analysis(confidence=0.8),
    )
    assert result.confidence == pytest.approx(0.5)


# --- required providers / missing modules ---------------------------------------------


def test_required_provider_missing_yields_invalid_status_and_error_issue() -> None:
    config = ScoringEngineConfig(engine_version="v1", required_providers=("funding",))
    engine = ScoringEngine(config)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    assert result.validation_status == ValidationStatus.INVALID
    assert any(i.severity == "ERROR" for i in result.validation_issues)


# --- version mismatch ------------------------------------------------------------------


def test_version_mismatch_is_flagged_as_warning() -> None:
    config = ScoringEngineConfig(engine_version="v2")
    engine = ScoringEngine(config, funding_provider=_FakeProvider(name="funding", value=0.5, version="v1"))
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.validation_status == ValidationStatus.WARNING
    assert any("version" in i.message for i in result.validation_issues)


# --- duplicate calculation ---------------------------------------------------------------


def test_duplicate_calculation_is_flagged_on_second_call() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    as_of = datetime(2024, 1, 1, tzinfo=UTC)
    first = engine.score("BTCUSDT", as_of)
    second = engine.score("BTCUSDT", as_of)
    assert first.validation_status == ValidationStatus.VALID
    assert second.validation_status == ValidationStatus.WARNING
    assert any("duplicate" in i.message for i in second.validation_issues)


def test_different_as_of_is_not_a_duplicate() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    second = engine.score("BTCUSDT", datetime(2024, 1, 2, tzinfo=UTC))
    assert second.validation_status == ValidationStatus.VALID


def test_different_symbol_is_not_a_duplicate() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    as_of = datetime(2024, 1, 1, tzinfo=UTC)
    engine.score("BTCUSDT", as_of)
    second = engine.score("ETHUSDT", as_of)
    assert second.validation_status == ValidationStatus.VALID


def test_symbol_case_does_not_bypass_duplicate_detection() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    as_of = datetime(2024, 1, 1, tzinfo=UTC)
    engine.score("btcusdt", as_of)
    second = engine.score("BTCUSDT", as_of)
    assert second.validation_status == ValidationStatus.WARNING


# --- dependency injection ----------------------------------------------------------------


class _StubAggregator(ScoreAggregator):
    def aggregate(self, components, weights) -> float | None:
        return 0.42


def test_custom_aggregator_is_used() -> None:
    config = ScoringEngineConfig(engine_version="v1", weights=ScoreWeights(funding=1.0))
    engine = ScoringEngine(
        config, funding_provider=_FakeProvider(name="funding", value=0.1), aggregator=_StubAggregator()
    )
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC), funding=_funding_analysis())
    assert result.total_score == 0.42


def test_default_aggregator_is_weighted_sum_aggregator() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    engine = ScoringEngine(config)
    assert isinstance(engine._aggregator, WeightedSumAggregator)  # noqa: SLF001


def test_custom_validator_is_used() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    custom_validator = StrategyScoreValidator(ScoringEngineConfig(engine_version="v1", required_providers=("liquidity",)))
    engine = ScoringEngine(config, validator=custom_validator)
    result = engine.score("BTCUSDT", datetime(2024, 1, 1, tzinfo=UTC))
    assert result.validation_status == ValidationStatus.INVALID
