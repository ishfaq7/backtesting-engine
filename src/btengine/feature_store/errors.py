"""Structured errors for the Feature Store, kept independent from
``btengine.data.errors`` since this is a separate bounded context (engineered
features, not raw market data) even though the storage mechanics rhyme.
"""

from __future__ import annotations


class FeatureStoreError(Exception):
    """Reading from or writing to a feature store failed."""
