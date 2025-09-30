"""IPTA Metapulsar Analysis - Multi-PTA pulsar timing data combination framework.

This package provides tools for combining pulsar timing data from multiple PTA 
collaborations (EPTA, PPTA, NANOGrav, MPTA, etc.) into unified "metapulsar" 
objects for gravitational wave detection.
"""

from .metapulsar import MetaPulsar

# New factory architecture imports
from .pta_registry import PTARegistry
from .meta_pulsar_factory import MetaPulsarFactory

__version__ = "0.1.0"
__author__ = "Rutger van Haasteren, Wangwei Yu"
__email__ = "rutger@vhaasteren.com"

# Selection utilities
from .selection_utils import create_staggered_selection

# Export both legacy and new classes for backward compatibility
__all__ = [
    "MetaPulsar",
    "PTARegistry",
    "MetaPulsarFactory",
    "create_staggered_selection",
]
