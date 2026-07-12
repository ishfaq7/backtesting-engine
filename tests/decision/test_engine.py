from datetime import datetime, timedelta, timezone

import pytest

from btengine.decision.checks.base import DecisionValidationCheck
from btengine.decision.config import DecisionEngineConfig
from btengine.decision.context import DecisionRequest
from btengine.decision.engine import DecisionEngine
from btengine.decision.models import DecisionOutcome, DecisionStatus, DecisionValidationIssue
from btengine.decision.providers.base import DecisionProvider
from btengine.scoring.models import ValidationStatus
from tests.decision.conftest import (
    make_funding_analysis,
    make_strategy_score,
    make_validated_strategy_state,
)

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def test_decide_uppercases_symbol() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    context = engine.decide("btcusdt", NOW, validated_state=make_validated_strategy_state())
    assert context.symbol == "BTCUSDT"


def test_decide_carries_as_of_and_strategy_version_from_state() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    state = make_validated_strategy_state(as_of=NOW, strategy_version="v7")
    context = engine.decide("BTCUSDT", NOW, validated_state=state)
    assert context.as_of == NOW
    assert context.strategy_version == "v7"
    assert context.timestamp == NOW


def test_decide_with_no_providers_is_pending_and_not_execution_ready() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.PENDING
    assert context.execution_ready is False
    assert "no decision providers configured" in context.decision_reason


def test_decide_no_trading_content_in_output() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    for forbidden in ("BUY", "SELL", "buy", "sell"):
        assert forbidden not in context.decision_reason


# --- NOT_READY: validation errors -------------------------------------------------


def test_decide_not_ready_on_invalid_score() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    score = make_strategy_score(symbol="")
    state = make_validated_strategy_state(score=score)
    context = engine.decide("BTCUSDT", NOW, validated_state=state)
    assert context.decision_status == DecisionStatus.NOT_READY
    assert context.validation_status == ValidationStatus.INVALID
    assert len(context.validation_errors) >= 1
    assert "validation error" in context.decision_reason


def test_decide_not_ready_on_upstream_validation_failure() -> None:
    config = DecisionEngineConfig(engine_version="v1", require_validation_passed=True)
    engine = DecisionEngine(config)
    state = make_validated_strategy_state(validation_passed=False)
    context = engine.decide("BTCUSDT", NOW, validated_state=state)
    assert context.decision_status == DecisionStatus.NOT_READY
    assert "upstream signal validation failed" in context.decision_reason


def test_decide_ignores_upstream_validation_failure_when_configured() -> None:
    config = DecisionEngineConfig(engine_version="v1", require_validation_passed=False)
    engine = DecisionEngine(config)
    state = make_validated_strategy_state(validation_passed=False)
    context = engine.decide("BTCUSDT", NOW, validated_state=state)
    assert context.decision_status != DecisionStatus.NOT_READY


def test_decide_warnings_alone_do_not_block_pending_status() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    # missing analyses are WARNING-level only
    assert len(context.validation_warnings) == 4
    assert context.validation_status == ValidationStatus.WARNING
    assert context.decision_status == DecisionStatus.PENDING


# --- decision providers ------------------------------------------------------------


class _StubProvider(DecisionProvider):
    def __init__(self, name: str, status: DecisionStatus, version: str = "v1") -> None:
        self._name = name
        self._status = status
        self._version = version

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._version

    def decide(self, request: DecisionRequest) -> DecisionOutcome:
        return DecisionOutcome(
            provider_name=self._name, provider_version=self._version, status=self._status,
            reason="stub outcome",
        )


class _NotImplementedProvider(DecisionProvider):
    @property
    def provider_name(self) -> str:
        return "unimplemented"

    @property
    def provider_version(self) -> str:
        return "v1"

    def decide(self, request: DecisionRequest) -> DecisionOutcome:
        raise NotImplementedError("no formula yet")


def test_decide_pending_when_provider_returns_pending_outcome() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    provider = _StubProvider("stub", DecisionStatus.PENDING)
    engine = DecisionEngine(config, providers=[provider])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.PENDING
    assert len(context.provider_outcomes) == 1
    assert context.execution_ready is False


def test_decide_evaluated_when_provider_returns_evaluated_outcome() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    provider = _StubProvider("stub", DecisionStatus.EVALUATED)
    engine = DecisionEngine(config, providers=[provider])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.EVALUATED
    assert context.execution_ready is True


def test_decide_handles_not_implemented_provider_gracefully() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config, providers=[_NotImplementedProvider()])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.PENDING
    assert context.provider_outcomes[0].status == DecisionStatus.PENDING
    assert "not implemented" in context.provider_outcomes[0].reason


def test_decide_providers_run_in_configured_priority_order() -> None:
    config = DecisionEngineConfig(
        engine_version="v1", provider_priorities={"second": 1, "first": 0}
    )
    provider_a = _StubProvider("first", DecisionStatus.PENDING)
    provider_b = _StubProvider("second", DecisionStatus.PENDING)
    engine = DecisionEngine(config, providers=[provider_b, provider_a])  # injected out of order
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    names = [outcome.provider_name for outcome in context.provider_outcomes]
    assert names == ["first", "second"]


def test_decide_required_provider_missing_causes_not_ready() -> None:
    config = DecisionEngineConfig(engine_version="v1", required_providers=("rule_based",))
    engine = DecisionEngine(config)  # nothing registered
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.NOT_READY
    assert any("rule_based" in i.message for i in context.validation_errors)


def test_decide_metadata_lists_registered_providers() -> None:
    config = DecisionEngineConfig(engine_version="v2")
    provider = _StubProvider("stub", DecisionStatus.PENDING)
    engine = DecisionEngine(config, providers=[provider])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.metadata["registered_providers"] == ["stub"]
    assert context.metadata["engine_version"] == "v2"


# --- duplicate processing -----------------------------------------------------------


def test_duplicate_processing_flagged_on_second_call() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    state = make_validated_strategy_state()
    first = engine.decide("BTCUSDT", NOW, validated_state=state)
    second = engine.decide("BTCUSDT", NOW, validated_state=state)
    assert not any("duplicate" in i.message for i in first.validation_warnings)
    assert any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_processing_not_flagged_for_different_as_of() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state(as_of=NOW))
    second = engine.decide(
        "BTCUSDT", NOW, validated_state=make_validated_strategy_state(as_of=NOW + timedelta(hours=1))
    )
    assert not any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_processing_not_flagged_for_different_symbol() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state(symbol="BTCUSDT"))
    second = engine.decide("ETHUSDT", NOW, validated_state=make_validated_strategy_state(symbol="ETHUSDT"))
    assert not any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_processing_case_insensitive_symbol() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config)
    engine.decide("btcusdt", NOW, validated_state=make_validated_strategy_state())
    second = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert any("duplicate" in i.message for i in second.validation_warnings)


# --- dependency injection: custom checks ---------------------------------------------


class _AlwaysFailsCheck(DecisionValidationCheck):
    @property
    def check_name(self) -> str:
        return "always_fails"

    def run(self, request) -> list[DecisionValidationIssue]:
        return [DecisionValidationIssue("ERROR", "custom", "custom failure")]


def test_custom_checks_are_used_instead_of_defaults() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config, checks=[_AlwaysFailsCheck()])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.decision_status == DecisionStatus.NOT_READY
    assert any(i.message == "custom failure" for i in context.validation_errors)


def test_empty_checks_list_runs_no_stateless_checks() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    engine = DecisionEngine(config, checks=[])
    context = engine.decide("BTCUSDT", NOW, validated_state=make_validated_strategy_state())
    assert context.validation_errors == ()
    assert context.validation_warnings == ()
