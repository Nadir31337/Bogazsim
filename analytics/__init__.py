"""BoğazSim Analytics & Visualization Package.

This package provides Pandas data processing pipelines for trajectory aggregation
and dark-themed Matplotlib/Seaborn visualization generation.
"""

from __future__ import annotations

from analytics.data_processor import SimulationDataProcessor

__all__ = [
    "MaritimeVisualizer",
    "SimulationDataProcessor",
]

__version__ = "1.0.0"


def __getattr__(name: str) -> Any:
    if name == "MaritimeVisualizer":
        from analytics.visualizer import MaritimeVisualizer
        return MaritimeVisualizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

