"""Structured errors for the Signal Validation Engine."""

from __future__ import annotations


class SignalValidationError(Exception):
    """Base class for every exception raised by :mod:`btengine.signal_validation`."""


class SignalValidationConfigError(SignalValidationError):
    """A :class:`~btengine.signal_validation.config.SignalValidationConfig` failed to load or validate."""
