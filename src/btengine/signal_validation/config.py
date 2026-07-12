"""Configuration for the Signal Validation Engine.

Every threshold-shaped field defaults to ``None`` — an explicit, unset
placeholder — exactly like every upstream analysis/scoring config
before it. "How stale is too stale," "how much timestamp drift between
modules is acceptable," "what confidence counts as low," and "what
completeness ratio is sufficient" are all strategy-owner judgment calls,
not something this framework may guess. ``history_window`` is the one
generic, technical parameter (a buffer size, like an SMA period
elsewhere in this codebase) with a sensible default.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import yaml

from btengine.signal_validation.errors import SignalValidationConfigError

_PROVIDER_NAMES = ("funding", "open_interest", "premium_discount", "liquidity")


@dataclass(frozen=True)
class SignalValidationConfig:
    """Tunable parameters for :class:`~btengine.signal_validation.engine.SignalValidationEngine`."""

    engine_version: str

    # TODO(owner): set to enable the "version mismatch" check against
    # StrategyScore.score_version. None = not checked.
    expected_score_version: str | None = None

    # TODO(owner): set to enable "data freshness" staleness detection.
    # None = staleness is never flagged (a future/past timestamp is still
    # checked unconditionally - see checks.builtin.DataFreshnessCheck).
    max_staleness: timedelta | None = None

    # TODO(owner): set to enable the "conflicting module outputs" timestamp
    # divergence check. None = timestamp skew is never flagged.
    max_timestamp_skew: timedelta | None = None

    # TODO(owner): set to enable ConfidenceStatus.LOW classification and
    # the corresponding "invalid confidence values" warning.
    min_confidence: float | None = None

    # TODO(owner): set to enable FeatureCompleteness.is_sufficient and the
    # "strategy completeness" ratio warning.
    min_completeness_ratio: float | None = None

    # None = no provider is required; a missing/unavailable one is only a
    # WARNING (see checks.builtin.MissingScoreProvidersCheck), not a
    # validation-failing ERROR.
    required_providers: tuple[str, ...] | None = None

    # Bounded per-symbol history size used by the engine's own
    # "historical consistency" (monotonic as_of) check.
    history_window: int = 20

    def __post_init__(self) -> None:
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")
        if self.max_staleness is not None and self.max_staleness <= timedelta(0):
            raise ValueError(f"max_staleness must be positive, got {self.max_staleness}")
        if self.max_timestamp_skew is not None and self.max_timestamp_skew < timedelta(0):
            raise ValueError(f"max_timestamp_skew must be >= 0, got {self.max_timestamp_skew}")
        if self.min_confidence is not None and not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be between 0 and 1, got {self.min_confidence}")
        if self.min_completeness_ratio is not None and not 0.0 <= self.min_completeness_ratio <= 1.0:
            raise ValueError(
                f"min_completeness_ratio must be between 0 and 1, got {self.min_completeness_ratio}"
            )
        if self.required_providers is not None:
            unknown = set(self.required_providers) - set(_PROVIDER_NAMES)
            if unknown:
                raise ValueError(
                    f"unknown provider name(s) in required_providers: {sorted(unknown)}"
                )
        if self.history_window < 1:
            raise ValueError(f"history_window must be >= 1, got {self.history_window}")


def load_signal_validation_config(path: Path | str) -> SignalValidationConfig:
    """Load a :class:`SignalValidationConfig` from a YAML file.

    Follows the same "missing value is a placeholder, not an error"
    convention as :func:`btengine.strategy.spec_loader.load_strategy_spec`
    and :func:`btengine.scoring.config.load_scoring_engine_config`.
    """
    path = Path(path)
    try:
        raw = path.read_text()
    except OSError as exc:
        raise SignalValidationConfigError(f"Could not read signal validation config {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SignalValidationConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SignalValidationConfigError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )

    engine_version = data.get("engine_version")
    if not engine_version:
        raise SignalValidationConfigError(f"{path}: engine_version is required")

    required_providers = data.get("required_providers")
    if required_providers is not None:
        required_providers = tuple(required_providers)

    def _optional_seconds(key: str) -> timedelta | None:
        value = data.get(key)
        return None if value is None else timedelta(seconds=value)

    try:
        return SignalValidationConfig(
            engine_version=engine_version,
            expected_score_version=data.get("expected_score_version"),
            max_staleness=_optional_seconds("max_staleness_seconds"),
            max_timestamp_skew=_optional_seconds("max_timestamp_skew_seconds"),
            min_confidence=data.get("min_confidence"),
            min_completeness_ratio=data.get("min_completeness_ratio"),
            required_providers=required_providers,
            history_window=data.get("history_window", 20),
        )
    except (ValueError, TypeError) as exc:
        raise SignalValidationConfigError(f"{path}: invalid signal validation config: {exc}") from exc
