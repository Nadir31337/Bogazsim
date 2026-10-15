"""BoğazSim Analytics & Visualization Package.

This package provides Pandas data processing pipelines for trajectory aggregation
and dark-themed Matplotlib/Seaborn visualization generation.
"""

from __future__ import annotations

from analytics.data_processor import SimulationDataProcessor
from analytics.visualizer import MaritimeVisualizer

__all__ = [
    "MaritimeVisualizer",
    "SimulationDataProcessor",
]

__version__ = "1.0.0"
