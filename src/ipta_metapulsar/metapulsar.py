"""Main MetaPulsar class for combining multi-PTA pulsar timing data."""

import os
from itertools import groupby
import numpy as np
from loguru import logger

# Import Enterprise Pulsar classes
import enterprise.pulsar as ep

# Import PINT classes
from pint.models import TimingModel
from pint.toa import TOAs

# Import libstempo
import libstempo as t2

# Import our supporting infrastructure
from .metapulsar_parameter_manager import MetaPulsarParameterManager
from .position_helpers import bj_name_from_pulsar


class MetaPulsar(ep.BasePulsar):
    """Elegant composite pulsar for multi-PTA data combination.

    This class combines pulsar timing data from multiple PTA collaborations
    into a unified object suitable for gravitational wave detection analysis.
    Inherits from enterprise.pulsar.BasePulsar for full Enterprise compatibility.

    Supports two combination strategies:
    - "consistent": Astrophysical consistency (modifies par files for consistency)
    - "composite": Multi-PTA composition (preserves original parameters)
    """

    def __init__(
        self,
        pulsars,
        *,
        combination_strategy="consistent",
        canonical_name=None,
        merge_astrometry=True,
        merge_spin=True,
        merge_binary=True,
        merge_dispersion=True,
        sort=True,
    ):
        """Create MetaPulsar from multiple PTA pulsars.

        Args:
            pulsars: Dict mapping PTA names to pulsar data:
                - PINT: {pta: (pint_model, pint_toas)}
                - Tempo2: {pta: tempo2_psr}
            combination_strategy: Strategy for combining PTAs:
                - "consistent": Astrophysical consistency (modifies par files for consistency)
                - "composite": Multi-PTA composition (preserves original parameters)
            canonical_name: Canonical name for the pulsar (e.g., "B1857+09A"). Default is None.
            merge_astrometry: Whether to make astrometry parameters consistent (consistent strategy only)
            merge_spin: Whether to make spin parameters consistent (consistent strategy only)
            merge_binary: Whether to make binary parameters consistent (consistent strategy only)
            merge_dispersion: Whether to make dispersion parameters consistent (consistent strategy only)
            sort: Whether to sort data by time
        """
        self._pulsars = pulsars
        self.pulsars = pulsars  # Public attribute for compatibility
        self.combination_strategy = combination_strategy
        self.canonical_name = canonical_name
        self._merge_astrometry = merge_astrometry
        self._merge_spin = merge_spin
        self._merge_binary = merge_binary
        self._merge_dispersion = merge_dispersion
        self._sort = sort  # BasePulsar handles sorting

        # Elegant initialization flow
        self._create_enterprise_pulsars()
        self._setup_parameters()
        self._combine_timing_data()
        self._build_design_matrix()
        self._setup_position_and_planets()

        # BasePulsar handles sorting automatically
        self.sort_data()

    @classmethod
    def from_files(
        cls,
        file_configs,
        *,
        combination_strategy="consistent",
        merge_astrometry=True,
        merge_spin=True,
        merge_binary=True,
        merge_dispersion=True,
        sort=True,
        **kwargs,
    ):
        """Create MetaPulsar from par/tim file configurations.

        Args:
            file_configs: List of file configuration dicts
            combination_strategy: Strategy for combining PTAs ("consistent" or "composite")
            merge_astrometry: Whether to make astrometry parameters consistent
            merge_spin: Whether to make spin parameters consistent
            merge_binary: Whether to make binary parameters consistent
            merge_dispersion: Whether to make dispersion parameters consistent
            sort: Whether to sort data by time
            **kwargs: Additional arguments passed to MetaPulsarFactory

        Returns:
            MetaPulsar: New MetaPulsar instance
        """
        # Convert individual merge flags to combine_components list
        combine_components = []
        if merge_astrometry:
            combine_components.append("astrometry")
        if merge_spin:
            combine_components.append("spin")
        if merge_binary:
            combine_components.append("binary")
        if merge_dispersion:
            combine_components.append("dispersion")

        # Use MetaPulsarFactory to create the MetaPulsar
        from .meta_pulsar_factory import MetaPulsarFactory

        factory = MetaPulsarFactory()
        return factory.create_metapulsar(
            file_configs=file_configs,
            combination_strategy=combination_strategy,
            combine_components=combine_components,
            **kwargs,
        )

    def validate_consistency(self):
        """Validate that all PTAs contain the same pulsar.

        Returns:
            str: Pulsar name if consistent, raises ValueError if not
        """
        if not hasattr(self, "_epulsars"):
            raise ValueError("No Enterprise Pulsars created yet")

        # Extract pulsar names from Enterprise Pulsars
        pulsar_names = []
        for pta, psr in self._epulsars.items():
            if hasattr(psr, "name"):
                pulsar_names.append(psr.name)
            else:
                logger.warning(f"PTA {pta} pulsar has no name attribute")

        if not pulsar_names:
            raise ValueError("No pulsar names found")

        if not self._all_equal(pulsar_names):
            raise ValueError(f"Not all the same pulsar: {pulsar_names}")

        return pulsar_names[0]

    def _create_enterprise_pulsars(self):
        """Create Enterprise Pulsar objects from input data."""
        self._epulsars = {}
        pint_models, pint_toas, lt_pulsars = self._unpack_pulsar_data()

        # Handle already-created Enterprise Pulsars (including MockPulsar)
        for pta, psritem in self._pulsars.items():
            if hasattr(psritem, "_toas") and hasattr(psritem, "_residuals"):
                self._epulsars[pta] = psritem

        # Create new Enterprise Pulsars from raw data
        if pint_models or lt_pulsars:
            self.name = self._validate_pulsar_consistency(pint_models, lt_pulsars)

            # Create Enterprise Pulsars from raw PINT objects
            for pta, (pmodel, ptoas) in zip(
                pint_models.keys(), zip(pint_models.values(), pint_toas.values())
            ):
                try:
                    self._epulsars[pta] = ep.PintPulsar(pmodel, ptoas, planets=True)
                except Exception as e:
                    logger.error(f"Failed to create PintPulsar for PTA {pta}: {e}")
                    raise

            # Create Enterprise Pulsars from raw Tempo2 objects
            for pta, lt_psr in lt_pulsars.items():
                try:
                    self._epulsars[pta] = ep.Tempo2Pulsar(lt_psr, planets=True)
                except Exception as e:
                    logger.error(f"Failed to create Tempo2Pulsar for PTA {pta}: {e}")
                    raise
        else:
            # All pulsars are already Enterprise Pulsars, get name from first one
            if self._epulsars:
                self.name = next(iter(self._epulsars.values())).name
            else:
                self.name = "unknown"

    def _unpack_pulsar_data(self):
        """Unpack pulsars dictionary into PINT and libstempo objects."""
        lt_pulsars = {}
        pint_models = {}
        pint_toas = {}

        for pta, psritem in self._pulsars.items():
            # Check if it's already an Enterprise Pulsar (including MockPulsar)
            if hasattr(psritem, "_toas") and hasattr(psritem, "_residuals"):
                # Skip unpacking - already an Enterprise Pulsar
                continue
            # Check if it's a PINT tuple (model, toas)
            elif isinstance(psritem, tuple) and len(psritem) == 2:
                pmodel, ptoas = psritem
                if isinstance(pmodel, TimingModel) and isinstance(ptoas, TOAs):
                    pint_models[pta] = pmodel
                    pint_toas[pta] = ptoas
                else:
                    raise TypeError(
                        f"Invalid PINT objects for {pta}: {type(pmodel)}, {type(ptoas)}"
                    )
            # Check if it's a libstempo pulsar
            elif isinstance(psritem, t2.tempopulsar):
                lt_pulsars[pta] = psritem
            else:
                raise TypeError(
                    f"Unsupported pulsar object type for {pta}: {type(psritem)}"
                )

        return pint_models, pint_toas, lt_pulsars

    def _validate_pulsar_consistency(self, pint_models, lt_pulsars):
        """Validate single pulsar across all PTAs."""
        pulsar_names = []

        # Extract names from PINT models
        for m in pint_models.values():
            pulsar_names.append(os.path.basename(m.name.split(".")[0]))

        # Extract names from libstempo pulsars
        for psr in lt_pulsars.values():
            pulsar_names.append(psr.name)

        if not pulsar_names:
            raise ValueError("No valid pulsars found for validation")

        if not self._all_equal(pulsar_names):
            raise ValueError(f"Not all the same pulsar: {pulsar_names}")

        return pulsar_names[0]

    def _all_equal(self, iterable):
        """Check if all items in iterable are equal."""
        g = groupby(iterable)
        return next(g, True) and not next(g, False)

    def _setup_parameters(self):
        """Setup parameter management using existing infrastructure."""
        if self.combination_strategy == "composite":
            # For composite strategy, preserve original parameters from each PTA
            self._setup_composite_parameters()
        elif self.combination_strategy == "consistent":
            # For consistent strategy, use consistent parameters (already handled by ParFileManager)
            self._setup_consistent_parameters()

    def _setup_composite_parameters(self):
        """Setup parameters for composite strategy (preserve original PTA parameters)."""
        # Get PINT models directly from the unpacked data
        pint_models, _, _ = self._unpack_pulsar_data()

        if not pint_models:
            # No PINT models available, create empty parameter lists
            self._fitparameters = {}
            self._setparameters = {}
            self.fitpars = []
            self.setpars = []
            return

        manager = MetaPulsarParameterManager(pint_models)
        mapping = manager.build_parameter_mappings(
            merge_astrometry=False,  # Don't merge for composite
            merge_spin=False,
            merge_binary=False,
            merge_dm=False,
        )

        self._fitparameters = mapping.fitparameters
        self._setparameters = mapping.setparameters
        self.fitpars = list(self._fitparameters.keys())
        self.setpars = list(self._setparameters.keys())

    def _setup_consistent_parameters(self):
        """Setup parameters for consistent strategy (use consistent parameters)."""
        # Get PINT models directly from the unpacked data
        pint_models, _, _ = self._unpack_pulsar_data()

        if not pint_models:
            # No PINT models available, create empty parameter lists
            self._fitparameters = {}
            self._setparameters = {}
            self.fitpars = []
            self.setpars = []
            return

        manager = MetaPulsarParameterManager(pint_models)
        mapping = manager.build_parameter_mappings(
            merge_astrometry=self._merge_astrometry,
            merge_spin=self._merge_spin,
            merge_binary=self._merge_binary,
            merge_dm=self._merge_dispersion,
        )

        self._fitparameters = mapping.fitparameters
        self._setparameters = mapping.setparameters
        self.fitpars = list(self._fitparameters.keys())
        self.setpars = list(self._setparameters.keys())

    def _combine_timing_data(self):
        """Combine timing data from all PTAs."""

        def concat(attribute):
            """Concatenate attribute across all PTAs."""
            values = []
            for pta, psr in self._epulsars.items():
                if hasattr(psr, attribute):
                    values.append(getattr(psr, attribute))
            return np.concatenate(values) if values else np.array([])

        # Combine core timing data
        self._toas = concat("_toas")
        self._stoas = concat("_stoas")
        self._residuals = concat("_residuals")
        self._toaerrs = concat("_toaerrs")
        self._ssbfreqs = concat("_ssbfreqs")
        self._telescope = concat("_telescope")

        # Combine flags
        self._flags = self._combine_flags()

    def _combine_flags(self):
        """Combine flags from all PTAs."""
        all_flags = {}

        for pta, psr in self._epulsars.items():
            if hasattr(psr, "_flags"):
                # Handle both dictionary and array formats
                if isinstance(psr._flags, dict):
                    # Dictionary format (real Enterprise Pulsars)
                    for flag_name, flag_values in psr._flags.items():
                        if flag_name not in all_flags:
                            all_flags[flag_name] = []
                        all_flags[flag_name].append(flag_values)
                elif hasattr(psr._flags, "dtype") and hasattr(psr._flags, "items"):
                    # Structured array format
                    for flag_name in psr._flags.dtype.names:
                        if flag_name not in all_flags:
                            all_flags[flag_name] = []
                        all_flags[flag_name].append(psr._flags[flag_name])

        # Concatenate flag arrays
        combined_flags = {}
        for flag_name, flag_arrays in all_flags.items():
            combined_flags[flag_name] = np.concatenate(flag_arrays)

        return combined_flags

    def _get_pta_slices(self):
        """Get slice objects for each PTA in the combined data."""
        slices = {}
        start_idx = 0

        for pta, psr in self._epulsars.items():
            if hasattr(psr, "_toas"):
                end_idx = start_idx + len(psr._toas)
                slices[pta] = slice(start_idx, end_idx)
                start_idx = end_idx

        return slices

    def _get_timing_package(self, psr):
        """Determine timing package used by pulsar."""
        if hasattr(psr, "_pint_model"):
            return "pint"
        elif hasattr(psr, "_lt_pulsar"):
            return "tempo2"
        else:
            return "unknown"

    def _build_design_matrix(self):
        """Build combined design matrix with unit conversion."""
        n_toas = len(self._toas)
        n_params = len(self.fitpars)

        self._designmatrix = np.zeros((n_toas, n_params))

        for i, parname in enumerate(self.fitpars):
            self._designmatrix[:, i] = self._build_design_matrix_column(parname)

    def _build_design_matrix_column(self, full_parname):
        """Build design matrix column for a single parameter."""
        pta_slices = self._get_pta_slices()
        n_toas = len(self._toas)
        column = np.zeros(n_toas)

        for pta, psr in self._epulsars.items():
            if pta not in pta_slices:
                continue

            slice_obj = pta_slices[pta]
            timing_package = self._get_timing_package(psr)

            # Get design matrix from Enterprise Pulsar
            if hasattr(psr, "designmatrix"):
                dm = psr.designmatrix
                if full_parname in psr.fitpars:
                    par_idx = psr.fitpars.index(full_parname)
                    column[slice_obj] = dm[:, par_idx]

            # Apply unit conversion if needed
            column[slice_obj] = self._convert_design_matrix_units(
                column[slice_obj], full_parname, timing_package
            )

        return column

    def _convert_design_matrix_units(self, column, param_name, timing_package):
        """Convert design matrix units between PINT and libstempo."""
        # Only convert coordinate parameters that actually need it
        coordinate_conversions = {
            ("raj", "pint"): 1.0,  # PINT uses degrees
            ("raj", "tempo2"): np.pi / 180.0,  # libstempo uses radians
            ("decj", "pint"): 1.0,  # PINT uses degrees
            ("decj", "tempo2"): np.pi / 180.0,  # libstempo uses radians
            ("elong", "pint"): 1.0,  # PINT uses degrees
            ("elong", "tempo2"): np.pi / 180.0,  # libstempo uses radians
            ("elat", "pint"): 1.0,  # PINT uses degrees
            ("elat", "tempo2"): np.pi / 180.0,  # libstempo uses radians
            ("lambda", "pint"): 1.0,  # PINT uses degrees
            ("lambda", "tempo2"): np.pi / 180.0,  # libstempo uses radians
            ("beta", "pint"): 1.0,  # PINT uses degrees
            ("beta", "tempo2"): np.pi / 180.0,  # libstempo uses radians
        }

        if param_name.lower() in ["raj", "decj", "elong", "elat", "lambda", "beta"]:
            key = (param_name.lower(), timing_package.lower())
            factor = coordinate_conversions.get(key, 1.0)
            return column * factor

        return column

    def _setup_position_and_planets(self):
        """Setup position and planetary data using PositionHelpers."""
        # Get reference pulsar for position

        ref_psr = next(iter(self._epulsars.values()))

        # Set basic position attributes
        self._raj = ref_psr._raj
        self._decj = ref_psr._decj

        # Generate B/J name using position_helpers
        bj_name_from_pulsar(ref_psr)

        # Set position vector and time array
        pta_slice = self._get_pta_slices()
        self._pos = np.zeros((len(self._toas), 3))
        self._pos_t = np.zeros((len(self._toas), 3))
        for pta, psr in self._epulsars.items():
            self._pos[pta_slice[pta], :] = psr._pos
            self._pos_t[pta_slice[pta], :] = psr._pos_t

        # Set planetary data
        self._planetssb = ref_psr._planetssb
        self._sunssb = ref_psr._sunssb
        self._pdist = ref_psr._pdist


# Note: Sorting is handled by BasePulsar.sort_data() method
# We don't need to implement custom sorting since we inherit from BasePulsar
