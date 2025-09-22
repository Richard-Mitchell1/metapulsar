"""IPTA Metapulsar Analysis - Multi-PTA pulsar timing data combination framework.

This package provides tools for combining pulsar timing data from multiple PTA 
collaborations (EPTA, PPTA, NANOGrav, MPTA, etc.) into unified "metapulsar" 
objects for gravitational wave detection.
"""

from .metapulsar import MetaPulsar, create_metapulsar

__version__ = "0.1.0"
__author__ = "Rutger van Haasteren, Wangwei Yu"
__email__ = "rutger@vhaasteren.com"
__all__ = ["MetaPulsar", "create_metapulsar"]
