"""Future seam: an AI/ML model that consumes engineered features.

Not implemented. This ``Protocol`` only fixes the shape a future model
integration must satisfy — given a symbol's currently-known feature values
(e.g. from the Feature Store), return a mapping of named outputs (a
prediction, a confidence score, a signal-adjustment weight, ...). Defining
this now lets the Feature Engineering Layer or a strategy plugin depend on
an abstraction today, before any concrete model exists, without committing
to what that model looks like.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class AIModelProvider(Protocol):
    """Something that turns engineered feature values into model outputs."""

    def predict(self, features: Mapping[str, float]) -> Mapping[str, float]:
        """Return named model outputs for the given named feature values."""
