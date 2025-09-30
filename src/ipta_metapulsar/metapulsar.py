"""Main MetaPulsar class for combining multi-PTA pulsar timing data."""

from typing import Dict, Tuple, Union
import logging


# PINT parameter discovery functions will be implemented

# Import will be handled when we implement the full functionality
# from h5pulsar import BasePulsar
# import enterprise.pulsar as ep

logger = logging.getLogger(__name__)


class MetaPulsar:
    """Composite pulsar class for multiple PINT and Tempo2 objects.

    This class combines pulsar timing data from multiple PTA collaborations
    into a unified object suitable for gravitational wave detection analysis.

    Parameters
    ----------
    pulsars : dict
        Dictionary with PTA names as keys and pulsar objects as values.
        Format: {'pta1': (pint_model, pint_toas), 'pta2': t2_psr, ...}
    combination_strategy : str, optional
        Strategy used to create this MetaPulsar. Options are:
        - "composite": Use raw par files without modification (Borg/FrankenStat method)
        - "consistent": Use astrophysically consistent par files
        Default is "consistent".
    sort : bool, optional
        Whether to sort the data by time. Default is True.
    planets : bool, optional
        Whether to model solar system planets. Default is True.
    drop_t2pulsar : bool, optional
        Whether to delete the libstempo pulsar object after processing.
        Default is True.
    drop_pintpsr : bool, optional
        Whether to delete the PINT objects after processing.
        Default is True.
    merge_astrometry : bool, optional
        Whether to merge astrometry parameters across PTAs. Default is True.
    merge_spin : bool, optional
        Whether to merge spindown parameters across PTAs. Default is True.
    merge_binary : bool, optional
        Whether to merge binary parameters across PTAs. Default is True.
    merge_dm : bool, optional
        Whether to merge dispersion measure parameters across PTAs. Default is True.
    """

    def __init__(
        self,
        pulsars: Dict[str, Union[Tuple, object]],
        combination_strategy: str = "consistent",
        sort: bool = True,
        planets: bool = True,
        drop_t2pulsar: bool = True,
        drop_pintpsr: bool = True,
        merge_astrometry: bool = True,
        merge_spin: bool = True,
        merge_binary: bool = True,
        merge_dm: bool = True,
    ):
        """Initialize MetaPulsar with multiple pulsar objects."""

        self.pulsars = pulsars
        self.combination_strategy = combination_strategy
        self.sort = sort
        self.planets = planets
        self.drop_t2pulsar = drop_t2pulsar
        self.drop_pintpsr = drop_pintpsr

        # Parameter merging configuration
        self._merge_astrometry = merge_astrometry
        self._merge_spin = merge_spin
        self._merge_binary = merge_binary
        self._merge_dm = merge_dm

        # Initialize attributes
        self._pint_models = {}
        self._pint_toas = {}
        self._fitparameters = {}
        self._setparameters = {}
        self.fitpars = []
        self.setpars = []

        # Process the pulsars
        self._process_pulsars()

    def _process_pulsars(self):
        """Process the input pulsars and extract pulsar objects."""
        # NOTE: this is wrong, obviously this also needs to parse libstempo pulsars
        for pta_name, pulsar_obj in self.pulsars.items():
            if isinstance(pulsar_obj, tuple) and len(pulsar_obj) == 2:
                # PINT model and TOAs tuple
                model, toas = pulsar_obj
                self._pint_models[pta_name] = model
                self._pint_toas[pta_name] = toas
            else:
                # Handle other pulsar object types (e.g., libstempo)
                logger.warning(
                    f"Unsupported pulsar object type for {pta_name}: {type(pulsar_obj)}"
                )

    # PINT parameter discovery methods will be implemented

    def get_combination_strategy(self) -> str:
        """Get the combination strategy used for this MetaPulsar.

        Returns
        -------
        str
            The combination strategy: "composite" or "consistent"
        """
        return self.combination_strategy

    def drop_pulsars(self, drop_t2pulsar=True, drop_pintpsr=True):
        """Drop the original pulsar objects if required"""
        if drop_t2pulsar and hasattr(self, "_lt_pulsars"):
            del self._lt_pulsars
        if drop_pintpsr:
            if hasattr(self, "_pint_models"):
                del self._pint_models
            if hasattr(self, "_pint_toas"):
                del self._pint_toas
