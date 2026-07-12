from datetime import datetime, timedelta, timezone

import pytest

from btengine.data.schema import Candle, FundingRate, Timeframe
from btengine.feature_store.local_store import LocalFeatureStore
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule
from btengine.features.pipeline.funding import FundingFeatures
from btengine.features.pipeline.pipeline import FeaturePipeline, FeaturePipelineResult
from btengine.features.pipeline.price import PriceFeatures
from btengine.features.pipeline.validation import FeatureValidationIssue

UTC = timezone.utc


def _candle(hour: int, close: float) -> Candle:
    return Candle(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        open=close, high=close + 1, low=close - 1, close=close, volume=100.0,
    )


def _funding(hour: int, rate: float) -> FundingRate:
    return FundingRate(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        funding_rate=rate,
    )


class _ExplodingModule(BaseFeatureModule):
    @property
    def module_name(self) -> str:
        return "exploding"

    def compute(self, symbol: str, records) -> list[FeatureValue]:
        raise NotImplementedError("framework only")


def test_run_with_no_modules_returns_empty_result() -> None:
    pipeline = FeaturePipeline([])
    result = pipeline.run("BTCUSDT", {})
    assert result == FeaturePipelineResult(symbol="BTCUSDT", features=[], issues=[])


def test_run_skips_modules_whose_input_is_absent() -> None:
    pipeline = FeaturePipeline([PriceFeatures(), FundingFeatures()])
    result = pipeline.run("BTCUSDT", {"price": [_candle(h, 100.0 + h) for h in range(5)]})
    assert all(f.feature_name.startswith("price.") for f in result.features)


def test_run_combines_output_from_multiple_modules() -> None:
    pipeline = FeaturePipeline([PriceFeatures(), FundingFeatures()])
    result = pipeline.run(
        "BTCUSDT",
        {
            "price": [_candle(h, 100.0 + h) for h in range(5)],
            "funding_standard": [_funding(h, 0.0001 * h) for h in range(5)],
        },
    )
    prefixes = {f.feature_name.split(".")[0] for f in result.features}
    assert prefixes == {"price", "funding_standard"}


def test_run_returns_no_issues_for_well_formed_input() -> None:
    pipeline = FeaturePipeline([PriceFeatures()])
    result = pipeline.run("BTCUSDT", {"price": [_candle(h, 100.0 + h) for h in range(5)]})
    assert result.issues == []
    assert result.is_valid is True


def test_run_propagates_exceptions_from_framework_only_modules() -> None:
    pipeline = FeaturePipeline([_ExplodingModule()])
    with pytest.raises(NotImplementedError):
        pipeline.run("BTCUSDT", {"exploding": []})


def test_run_persists_to_feature_store_when_configured(tmp_path) -> None:
    store = LocalFeatureStore(tmp_path)
    pipeline = FeaturePipeline([PriceFeatures()], feature_store=store)
    pipeline.run("BTCUSDT", {"price": [_candle(h, 100.0 + h) for h in range(5)]})

    stored = store.read(
        symbol="BTCUSDT", feature_name="price.return_pct",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(stored) == 4


def test_run_does_not_persist_when_persist_is_false(tmp_path) -> None:
    store = LocalFeatureStore(tmp_path)
    pipeline = FeaturePipeline([PriceFeatures()], feature_store=store)
    pipeline.run("BTCUSDT", {"price": [_candle(h, 100.0 + h) for h in range(5)]}, persist=False)

    stored = store.read(
        symbol="BTCUSDT", feature_name="price.return_pct",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert stored == []


def test_run_without_feature_store_does_not_error(tmp_path) -> None:
    pipeline = FeaturePipeline([PriceFeatures()])
    result = pipeline.run("BTCUSDT", {"price": [_candle(h, 100.0 + h) for h in range(5)]})
    assert len(result.features) > 0


def test_run_with_no_features_does_not_touch_feature_store(tmp_path) -> None:
    store = LocalFeatureStore(tmp_path)
    pipeline = FeaturePipeline([PriceFeatures()], feature_store=store)
    result = pipeline.run("BTCUSDT", {"price": []})
    assert result.features == []
    assert not any(tmp_path.iterdir())


def test_result_is_valid_false_when_error_issue_present() -> None:
    naive_feature = FeatureValue(
        symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1), value=1.0
    )
    result = FeaturePipelineResult(
        symbol="BTCUSDT",
        features=[naive_feature],
        issues=[FeatureValidationIssue("ERROR", "x", "naive timestamp")],
    )
    assert result.is_valid is False
