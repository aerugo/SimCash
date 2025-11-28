"""Compatibility shim for payment_simulator._core imports.

This module re-exports the Rust bindings from payment_simulator_core_rs
to maintain backward compatibility with code that imports from
payment_simulator._core.
"""

# Re-export everything from the Rust module
from payment_simulator_core_rs import *  # type: ignore[import-untyped]  # noqa: F401, F403

# Preserve module documentation if it exists
try:
    from payment_simulator_core_rs import __doc__ as _rust_doc
    if _rust_doc:
        __doc__ = _rust_doc
except (ImportError, AttributeError):
    pass

# Preserve __all__ if defined in Rust module
try:
    from payment_simulator_core_rs import __all__
except (ImportError, AttributeError):
    pass
