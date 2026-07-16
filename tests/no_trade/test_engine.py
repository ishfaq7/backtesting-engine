import pytest

from btengine.no_trade.checks.base import NoTradeValidationCheck
from btengine.no_trade.config import NoTradeEngineConfig
from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.engine import NoTradeEngine
from btengine.no_trade.filters.base import NoTradeFilter
from btengine.no_trade.filters.builtin import default_filters
from btengine.no_trade.models import FilterResult, FilterVerdict, NoTradeValidationIssue
from btengine.scoring.models import ValidationStatus
from tests.no_trade.conftest import NOW, make_decision_context, make_strategy_score


def _evaluate(engine: NoTradeEngine, *, score=None):
    return engine.evaluate(
        "btcusdt", NOW, decision_context=make_decision_context(), score=score or make_strategy_score()
    )


class _StubFilter(NoTradeFilter):
    def __init__(self, name: str, verdict: FilterVerdict, *, reason: str = "stub") -> None:
        self._name = name
        self._verdict = verdict
        self._reason = reason

    @property
    def filter_name(self) -> str:
        return self._name

    @property
    def filter_version(self) -> str:
        return "v1"

    def evaluate(self, request: NoTradeRequest) -> FilterResult:
        return FilterResult(
            filter_name=self._name, filter_version="v1", verdict=self._verdict, reason=self._reason
        )


def test_evaluate_uppercases_symbol_and_carries_versions() -> None:
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"))
    result = _evaluate(engine)
    assert result.symbol == "BTCUSDT"
    assert result.as_of == NOW
    assert result.strategy_version == "v1"
    assert result.timestamp == NOW


# --- fail-safe gating semantics -----------------------------------------------------


def test_no_filters_registered_blocks_trading_with_explicit_reason() -> None:
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"))
    result = _evaluate(engine)
    assert result.trading_allowed is False
    assert any("no active no-trade filters" in reason for reason in result.blocked_reasons)


def test_framework_only_filters_block_trading() -> None:
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=default_filters())
    result = _evaluate(engine)
    assert result.trading_allowed is False
    assert len(result.filter_results) == 8
    assert all(r.verdict is FilterVerdict.CANNOT_EVALUATE for r in result.filter_results)
    assert len(result.blocked_reasons) == 8  # one per unevaluable filter


def test_cannot_evaluate_blocks_even_alongside_allowing_filters() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW), _StubFilter("b", FilterVerdict.CANNOT_EVALUATE)]
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=filters)
    assert _evaluate(engine).trading_allowed is False


def test_explicit_block_blocks_trading_with_its_reason() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW), _StubFilter("b", FilterVerdict.BLOCK, reason="blocked by b")]
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=filters)
    result = _evaluate(engine)
    assert result.trading_allowed is False
    assert "b: blocked by b" in result.blocked_reasons


def test_all_filters_allowing_permits_trading() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW), _StubFilter("b", FilterVerdict.ALLOW)]
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=filters)
    result = _evaluate(engine)
    assert result.trading_allowed is True
    assert result.blocked_reasons == ()


def test_validation_error_blocks_trading_and_skips_filters() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW)]
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=filters)
    result = _evaluate(engine, score=make_strategy_score(symbol=""))
    assert result.trading_allowed is False
    assert result.validation_status == ValidationStatus.INVALID
    assert result.filter_results == ()
    assert any("validation failed" in reason for reason in result.blocked_reasons)


# --- enabled_filters ------------------------------------------------------------------


def test_enabled_filters_restricts_which_filters_run() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW), _StubFilter("b", FilterVerdict.BLOCK)]
    config = NoTradeEngineConfig(engine_version="v1", enabled_filters=("a",))
    engine = NoTradeEngine(config, filters=filters)
    result = _evaluate(engine)
    assert result.active_filters == ("a",)
    assert result.metadata["skipped_filters"] == ["b"]
    assert result.trading_allowed is True  # only "a" ran, and it allowed


def test_enabled_filters_naming_unregistered_filter_is_an_error() -> None:
    config = NoTradeEngineConfig(engine_version="v1", enabled_filters=("ghost",))
    engine = NoTradeEngine(config, filters=[_StubFilter("a", FilterVerdict.ALLOW)])
    result = _evaluate(engine)
    assert result.validation_status == ValidationStatus.INVALID
    assert result.trading_allowed is False


def test_duplicate_filter_registration_is_an_error() -> None:
    filters = [_StubFilter("a", FilterVerdict.ALLOW), _StubFilter("a", FilterVerdict.ALLOW)]
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), filters=filters)
    result = _evaluate(engine)
    assert result.validation_status == ValidationStatus.INVALID
    assert result.trading_allowed is False


# --- warnings / metadata ----------------------------------------------------------------


def test_warning_messages_collect_warning_issue_messages() -> None:
    engine = NoTradeEngine(
        NoTradeEngineConfig(engine_version="v1"), filters=[_StubFilter("a", FilterVerdict.ALLOW)]
    )
    result = _evaluate(engine)  # analyses/risk/market/portfolio all missing -> warnings
    assert len(result.warning_messages) == 7
    assert result.validation_status == ValidationStatus.WARNING
    assert result.trading_allowed is True  # warnings alone don't close the gate


def test_metadata_lists_registered_filters_and_engine_version() -> None:
    engine = NoTradeEngine(
        NoTradeEngineConfig(engine_version="v9"), filters=[_StubFilter("a", FilterVerdict.ALLOW)]
    )
    result = _evaluate(engine)
    assert result.metadata["registered_filters"] == ["a"]
    assert result.metadata["engine_version"] == "v9"
    assert result.metadata["skipped_filters"] == []


# --- DI: custom checks ---------------------------------------------------------------------


class _AlwaysFailsCheck(NoTradeValidationCheck):
    @property
    def check_name(self) -> str:
        return "always_fails"

    def run(self, request, registered_filter_names) -> list[NoTradeValidationIssue]:
        return [NoTradeValidationIssue("ERROR", "custom", "custom failure")]


def test_custom_checks_are_used_instead_of_defaults() -> None:
    engine = NoTradeEngine(NoTradeEngineConfig(engine_version="v1"), checks=[_AlwaysFailsCheck()])
    result = _evaluate(engine)
    assert result.validation_status == ValidationStatus.INVALID
    assert any(i.message == "custom failure" for i in result.errors)


def test_empty_checks_list_runs_no_checks() -> None:
    engine = NoTradeEngine(
        NoTradeEngineConfig(engine_version="v1"), filters=[_StubFilter("a", FilterVerdict.ALLOW)],
        checks=[],
    )
    result = _evaluate(engine)
    assert result.errors == ()
    assert result.warnings == ()
    assert result.trading_allowed is True
