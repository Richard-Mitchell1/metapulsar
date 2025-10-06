"""MetaPulsar - Multi-PTA pulsar timing data combination framework.

This package provides tools for combining pulsar timing data from multiple PTA 
collaborations (EPTA, PPTA, NANOGrav, MPTA, etc.) into unified "metapulsar" 
objects for gravitational wave detection.
"""

# Core classes
from .metapulsar import MetaPulsar
from .metapulsar_factory import MetaPulsarFactory
from .file_discovery_service import FileDiscoveryService, PTA_DATA_RELEASES
from .pattern_discovery_engine import PatternDiscoveryEngine
from .parameter_manager import (
    ParameterManager,
    ParameterMapping,
    ParameterInconsistencyError,
)
from .mockpulsar import MockPulsar
from .tim_file_analyzer import TimFileAnalyzer
from .selection_utils import create_staggered_selection

# Exceptions
from .pint_helpers import PINTDiscoveryError

__version__ = "0.1.0"
__author__ = "Rutger van Haasteren, Wangwei Yu"
__email__ = "rutger@vhaasteren.com"

__all__ = [
    # Core classes
    "MetaPulsar",
    "MetaPulsarFactory",
    "FileDiscoveryService",
    "PTA_DATA_RELEASES",
    "PatternDiscoveryEngine",
    "ParameterManager",
    "ParameterMapping",
    "ParameterInconsistencyError",
    "MockPulsar",
    "TimFileAnalyzer",
    "create_staggered_selection",
    # Exceptions
    "PINTDiscoveryError",
]
