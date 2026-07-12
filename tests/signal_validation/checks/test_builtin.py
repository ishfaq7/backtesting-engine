from datetime import datetime, timedelta, timezone

from btengine.scoring.models import FeatureStatus
from btengine.signal_validation.checks.builtin import (
    ConflictingModuleOutputsCheck,
    DataFreshnessCheck,
    InvalidAnalyticalObjectsCheck,
    InvalidConfidenceValuesCheck,
    MissingFeatureInputsCheck,
    MissingScoreProvidersCheck,
    StrategyCompletenessCheck,
    VersionMismatchCheck,
    default_checks,
)
from btengine.signal_validation.config import SignalValidationConfig
from btengine.signal_validation.context import ValidationContext
from tests.signal_validation.conftest import (
    make_funding_analysis,
    make_liquidity_analysis,
    make_oi_analysis,
    make_premium_discount_analysis,
    make_score_component,
    make_strategy_score,
)

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def _context(
    config: SignalValidationConfig | None = None,
    *,
    symbol: str = "BTCUSDT",
    reference_time: datetime = NOW,
    score=None,
    funding=None,
    open_interest=None,
    premium_discount=None,
    liquidity=None,
) -> ValidationContext:
    return ValidationContext(
        symbol=symbol, reference_time=reference_time, score=score or make_strategy_score(),
        funding=funding, open_interest=open_interest, premium_discount=premium_discount,
        liquidity=liquidity, config=config or SignalValidationConfig(engine_version="v1"),
    )


def test_default_checks_returns_eight_checks() -> None:
    assert len(default_checks()) == 8


def test_default_checks_have_unique_stable_names() -> None:
    names = [check.check_name for check in default_checks()]
    assert names == [
        "missing_feature_inputs", "invalid_analytical_objects", "missing_score_providers",
        "conflicting_module_outputs", "invalid_confidence_values", "version_mismatch",
        "data_freshness", "strategy_completeness",
    ]
    assert len(set(names)) == len(names)


# --- MissingFeatureInputsCheck --------------------------------------------------


def test_missing_feature_inputs_flags_every_absent_analysis() -> None:
    context = _context()
    issues = MissingFeatureInputsCheck().run(context)
    names = {i.provider_name for i in issues}
    assert names == {"funding", "open_interest", "premium_discount", "liquidity"}
    assert all(i.severity == "WARNING" for i in issues)


def test_missing_feature_inputs_does_not_flag_supplied_analyses() -> None:
    context = _context(funding=make_funding_analysis())
    issues = MissingFeatureInputsCheck().run(context)
    assert "funding" not in {i.provider_name for i in issues}


def test_missing_feature_inputs_check_name() -> None:
    assert MissingFeatureInputsCheck().check_name == "missing_feature_inputs"


# --- InvalidAnalyticalObjectsCheck ------------------------------------------------


def test_invalid_analytical_objects_flags_empty_symbol() -> None:
    funding = make_funding_analysis(symbol="")
    context = _context(funding=funding)
    issues = InvalidAnalyticalObjectsCheck().run(context)
    assert any("empty symbol" in i.message for i in issues)


def test_invalid_analytical_objects_flags_naive_timestamp() -> None:
    funding = make_funding_analysis()
    funding = FundingAnalysisNaiveHelper(funding)
    context = _context(funding=funding)
    issues = InvalidAnalyticalObjectsCheck().run(context)
    assert any("timezone-aware" in i.message for i in issues)


def test_invalid_analytical_objects_flags_invalid_confidence() -> None:
    funding = make_funding_analysis(confidence_level=float("nan"))
    context = _context(funding=funding)
    issues = InvalidAnalyticalObjectsCheck().run(context)
    assert any("invalid confidence_level" in i.message for i in issues)


def test_invalid_analytical_objects_flags_out_of_range_confidence() -> None:
    funding = make_funding_analysis(confidence_level=1.5)
    context = _context(funding=funding)
    issues = InvalidAnalyticalObjectsCheck().run(context)
    assert any("invalid confidence_level" in i.message for i in issues)


def test_invalid_analytical_objects_no_issues_for_well_formed_analyses() -> None:
    context = _context(
        funding=make_funding_analysis(), open_interest=make_oi_analysis(),
        premium_discount=make_premium_discount_analysis(), liquidity=make_liquidity_analysis(),
    )
    assert InvalidAnalyticalObjectsCheck().run(context) == []


def test_invalid_analytical_objects_skips_absent_analyses() -> None:
    context = _context()
    assert InvalidAnalyticalObjectsCheck().run(context) == []


class FundingAnalysisNaiveHelper:
    """Wraps a FundingAnalysis but exposes a naive timestamp, for testing
    the naive-timestamp branch without needing to bypass the frozen
    dataclass on the real object."""

    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name):
        if name == "as_of":
            return datetime(2024, 1, 1)  # naive
        return getattr(self._wrapped, name)


# --- MissingScoreProvidersCheck --------------------------------------------------


def test_missing_score_providers_flags_unavailable_as_warning() -> None:
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.MISSING, "open_interest": FeatureStatus.AVAILABLE,
            "premium_discount": FeatureStatus.AVAILABLE, "liquidity": FeatureStatus.AVAILABLE,
        }
    )
    context = _context(score=score)
    issues = MissingScoreProvidersCheck().run(context)
    assert len(issues) == 1
    assert issues[0].severity == "WARNING"
    assert issues[0].provider_name == "funding"


def test_missing_score_providers_flags_required_as_error() -> None:
    config = SignalValidationConfig(engine_version="v1", required_providers=("funding",))
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.MISSING, "open_interest": FeatureStatus.AVAILABLE,
            "premium_discount": FeatureStatus.AVAILABLE, "liquidity": FeatureStatus.AVAILABLE,
        }
    )
    context = _context(config, score=score)
    issues = MissingScoreProvidersCheck().run(context)
    assert issues[0].severity == "ERROR"


def test_missing_score_providers_no_issues_when_all_available() -> None:
    context = _context()
    assert MissingScoreProvidersCheck().run(context) == []


# --- ConflictingModuleOutputsCheck ------------------------------------------------


def test_conflicting_module_outputs_flags_symbol_mismatch() -> None:
    funding = make_funding_analysis(symbol="ETHUSDT")
    context = _context(funding=funding)
    issues = ConflictingModuleOutputsCheck().run(context)
    assert any(i.severity == "ERROR" and "does not match" in i.message for i in issues)


def test_conflicting_module_outputs_flags_score_symbol_mismatch() -> None:
    score = make_strategy_score(symbol="ETHUSDT")
    context = _context(score=score)
    issues = ConflictingModuleOutputsCheck().run(context)
    assert any(i.provider_name == "score" for i in issues)


def test_conflicting_module_outputs_no_issues_when_consistent() -> None:
    context = _context(funding=make_funding_analysis())
    assert ConflictingModuleOutputsCheck().run(context) == []


def test_conflicting_module_outputs_skew_not_checked_when_unset() -> None:
    funding = make_funding_analysis(as_of=NOW)
    liquidity = make_liquidity_analysis(as_of=NOW + timedelta(days=1))
    context = _context(funding=funding, liquidity=liquidity)
    issues = ConflictingModuleOutputsCheck().run(context)
    assert not any("skew" in i.message or "span" in i.message for i in issues)


def test_conflicting_module_outputs_flags_timestamp_skew_when_configured() -> None:
    config = SignalValidationConfig(engine_version="v1", max_timestamp_skew=timedelta(minutes=5))
    funding = make_funding_analysis(as_of=NOW)
    liquidity = make_liquidity_analysis(as_of=NOW + timedelta(hours=1))
    context = _context(config, funding=funding, liquidity=liquidity)
    issues = ConflictingModuleOutputsCheck().run(context)
    assert any(i.severity == "WARNING" and "span" in i.message for i in issues)


def test_conflicting_module_outputs_no_skew_flag_within_tolerance() -> None:
    config = SignalValidationConfig(engine_version="v1", max_timestamp_skew=timedelta(hours=1))
    funding = make_funding_analysis(as_of=NOW)
    liquidity = make_liquidity_analysis(as_of=NOW + timedelta(minutes=1))
    context = _context(config, funding=funding, liquidity=liquidity)
    issues = ConflictingModuleOutputsCheck().run(context)
    assert not any("span" in i.message for i in issues)


def test_conflicting_module_outputs_skew_skipped_when_no_analyses_present() -> None:
    config = SignalValidationConfig(engine_version="v1", max_timestamp_skew=timedelta(minutes=5))
    context = _context(config)
    assert ConflictingModuleOutputsCheck().run(context) == []


# --- InvalidConfidenceValuesCheck ------------------------------------------------


def test_invalid_confidence_values_none_confidence_has_no_issues() -> None:
    score = make_strategy_score(confidence=None)
    context = _context(score=score)
    assert InvalidConfidenceValuesCheck().run(context) == []


def test_invalid_confidence_values_flags_nan() -> None:
    score = make_strategy_score(confidence=float("nan"))
    context = _context(score=score)
    issues = InvalidConfidenceValuesCheck().run(context)
    assert issues[0].severity == "ERROR"


def test_invalid_confidence_values_flags_out_of_range() -> None:
    score = make_strategy_score(confidence=2.0)
    context = _context(score=score)
    issues = InvalidConfidenceValuesCheck().run(context)
    assert issues[0].severity == "ERROR"


def test_invalid_confidence_values_flags_low_confidence_when_configured() -> None:
    config = SignalValidationConfig(engine_version="v1", min_confidence=0.5)
    score = make_strategy_score(confidence=0.3)
    context = _context(config, score=score)
    issues = InvalidConfidenceValuesCheck().run(context)
    assert issues[0].severity == "WARNING"


def test_invalid_confidence_values_no_low_flag_without_threshold() -> None:
    score = make_strategy_score(confidence=0.1)
    context = _context(score=score)
    assert InvalidConfidenceValuesCheck().run(context) == []


def test_invalid_confidence_values_valid_confidence_has_no_issues() -> None:
    config = SignalValidationConfig(engine_version="v1", min_confidence=0.5)
    score = make_strategy_score(confidence=0.9)
    context = _context(config, score=score)
    assert InvalidConfidenceValuesCheck().run(context) == []


# --- VersionMismatchCheck ---------------------------------------------------------


def test_version_mismatch_flags_unexpected_score_version() -> None:
    config = SignalValidationConfig(engine_version="v1", expected_score_version="v2")
    score = make_strategy_score(score_version="v1")
    context = _context(config, score=score)
    issues = VersionMismatchCheck().run(context)
    assert any("does not match" in i.message for i in issues)


def test_version_mismatch_not_checked_without_expected_version() -> None:
    score = make_strategy_score(score_version="v1")
    context = _context(score=score)
    assert VersionMismatchCheck().run(context) == []


def test_version_mismatch_flags_disagreeing_component_versions() -> None:
    score = make_strategy_score(
        funding_score=make_score_component("funding", version="v1"),
        liquidity_score=make_score_component("liquidity", version="v2"),
    )
    context = _context(score=score)
    issues = VersionMismatchCheck().run(context)
    assert any("disagree" in i.message for i in issues)


def test_version_mismatch_no_issue_when_component_versions_agree() -> None:
    score = make_strategy_score(
        funding_score=make_score_component("funding", version="v1"),
        liquidity_score=make_score_component("liquidity", version="v1"),
    )
    context = _context(score=score)
    assert VersionMismatchCheck().run(context) == []


def test_version_mismatch_no_issue_with_no_components() -> None:
    context = _context()
    assert VersionMismatchCheck().run(context) == []


# --- DataFreshnessCheck ------------------------------------------------------------


def test_data_freshness_flags_future_timestamp_unconditionally() -> None:
    funding = make_funding_analysis(as_of=NOW + timedelta(hours=1))
    context = _context(funding=funding, reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    assert any("future" in i.message for i in issues)


def test_data_freshness_not_flagged_when_max_staleness_unset() -> None:
    funding = make_funding_analysis(as_of=NOW - timedelta(days=365))
    context = _context(funding=funding, reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    assert not any("stale" in i.message for i in issues)


def test_data_freshness_flags_stale_when_configured() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    funding = make_funding_analysis(as_of=NOW - timedelta(hours=2))
    context = _context(config, funding=funding, reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    assert any("stale" in i.message for i in issues)


def test_data_freshness_not_flagged_within_max_staleness() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    funding = make_funding_analysis(as_of=NOW - timedelta(minutes=30))
    context = _context(config, funding=funding, reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    assert not any("stale" in i.message for i in issues)


def test_data_freshness_checks_the_score_itself() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    score = make_strategy_score(as_of=NOW - timedelta(hours=2))
    context = _context(config, score=score, reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    assert any(i.provider_name is None and "score is stale" in i.message for i in issues)


def test_data_freshness_skips_absent_analyses() -> None:
    context = _context(reference_time=NOW)
    issues = DataFreshnessCheck().run(context)
    # only the always-present score is checked
    assert all(i.provider_name is None for i in issues)


# --- StrategyCompletenessCheck ------------------------------------------------------


def test_strategy_completeness_not_checked_without_threshold() -> None:
    context = _context()
    assert StrategyCompletenessCheck().run(context) == []


def test_strategy_completeness_flags_low_ratio() -> None:
    config = SignalValidationConfig(engine_version="v1", min_completeness_ratio=0.75)
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
        }
    )
    context = _context(config, score=score)
    issues = StrategyCompletenessCheck().run(context)
    assert issues[0].severity == "WARNING"


def test_strategy_completeness_no_flag_when_ratio_meets_threshold() -> None:
    config = SignalValidationConfig(engine_version="v1", min_completeness_ratio=0.5)
    context = _context(config)  # default score = 4/4 available
    assert StrategyCompletenessCheck().run(context) == []


def test_strategy_completeness_no_flag_with_empty_feature_status() -> None:
    config = SignalValidationConfig(engine_version="v1", min_completeness_ratio=0.5)
    score = make_strategy_score(feature_status={})
    context = _context(config, score=score)
    assert StrategyCompletenessCheck().run(context) == []
