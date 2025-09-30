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

    TODO: INTEGRATION TESTS REQUIRED
    ================================

    Once the MetaPulsar class is fully implemented, the following integration tests
    MUST be added to ensure proper functionality:

    1. REAL FILE I/O INTEGRATION TESTS
    ----------------------------------
    - test_real_parfile_discovery_with_actual_files()
      * Create real par/tim files with actual coordinates
      * Test coordinate-based discovery with real PINT models
      * Verify file discovery works with actual filesystem
      * Test error handling for missing/corrupted files

    - test_real_pint_model_creation()
      * Test actual PINT model creation from par files
      * Verify coordinate extraction from real models
      * Test B/J name generation with actual coordinates
      * Test error handling for malformed par files

    - test_real_enterprise_pulsar_creation()
      * Test PintPulsar creation with real models and TOAs
      * Test Tempo2Pulsar creation with real data
      * Verify Enterprise Pulsar functionality
      * Test error handling for missing dependencies

    2. META PULSAR FACTORY INTEGRATION TESTS
    ----------------------------------------
    - test_discover_pulsars_by_coordinates_real()
      * Test coordinate discovery with real par files
      * Verify pulsar matching across PTAs works correctly
      * Test canonical name resolution with real data
      * Test error handling for coordinate extraction failures

    - test_create_consistent_metapulsar_real()
      * Test consistent strategy with real par files
      * Verify ParFileManager integration works
      * Test parameter consistency across PTAs
      * Test error handling for par file processing

    - test_create_composite_metapulsar_real()
      * Test composite strategy with real par files
      * Verify raw par files are used without modification
      * Test file discovery and Enterprise Pulsar creation
      * Test error handling for missing files

    - test_get_canonical_name_for_pulsar_real()
      * Test canonical name resolution with real coordinate data
      * Verify B-name preference logic works correctly
      * Test suffix extraction from real filenames
      * Test fallback behavior for unknown pulsars

    3. ERROR HANDLING AND EDGE CASES
    ---------------------------------
    - test_missing_par_files_handling()
      * Test behavior when par files are missing
      * Test error messages and logging
      * Test graceful degradation

    - test_malformed_par_files_handling()
      * Test behavior with corrupted par files
      * Test PINT parsing error handling
      * Test coordinate extraction failures

    - test_invalid_coordinates_handling()
      * Test behavior with invalid coordinate values
      * Test B/J name generation edge cases
      * Test coordinate transformation errors

    - test_file_permission_errors()
      * Test behavior when files cannot be read
      * Test error handling for permission issues
      * Test graceful error reporting

    4. PERFORMANCE AND SCALABILITY TESTS
    -------------------------------------
    - test_multiple_pta_performance()
      * Test with 5+ PTAs and 10+ pulsars
      * Measure discovery time and memory usage
      * Test coordinate matching efficiency

    - test_large_parfile_handling()
      * Test with large par files (1000+ parameters)
      * Test memory usage and processing time
      * Test error handling for oversized files

    5. END-TO-END WORKFLOW TESTS
    -----------------------------
    - test_complete_workflow_with_real_data()
      * Test full pipeline: discovery -> creation -> usage
      * Use actual par files from multiple PTAs
      * Verify MetaPulsar functionality works end-to-end

    - test_coordinate_based_matching_accuracy()
      * Test that same pulsar is correctly identified across PTAs
      * Use real coordinates from different PTAs
      * Verify matching accuracy and false positive rate

    - test_canonical_naming_consistency()
      * Test that canonical names are consistent across runs
      * Test B-name preference works correctly
      * Test suffix handling for binary pulsars

    TEST DATA REQUIREMENTS
    ======================
    - Real par files from multiple PTAs (EPTA, PPTA, NANOGrav, MPTA)
    - Files with actual coordinates for coordinate-based testing
    - Files with different naming conventions (J/B names)
    - Binary pulsar files with suffixes (A, B, etc.)
    - Malformed files for error testing
    - Large files for performance testing

    IMPLEMENTATION NOTES
    ====================
    - These tests should be in tests/test_metapulsar_integration.py
    - Use pytest fixtures for test data setup
    - Mock external dependencies (Enterprise, PINT) only when necessary
    - Test real functionality, not just mocked behavior
    - Include performance benchmarks and memory usage tests
    - Test both success and failure scenarios comprehensively

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
    canonical_name : str, optional
        Canonical name for the pulsar (e.g., "B1857+09A"). Default is None.
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
        canonical_name: str = None,
        sort: bool = True,
        planets: bool = True,
        drop_t2pulsar: bool = True,
        drop_pintpsr: bool = True,
        merge_astrometry: bool = True,
        merge_spin: bool = True,
        merge_binary: bool = True,
        merge_dm: bool = True,
    ):
        """Initialize MetaPulsar with multiple pulsar objects.

        Parameters
        ----------
        pulsars : dict
            Dictionary with PTA names as keys and pulsar objects as values.
        combination_strategy : str, optional
            Strategy used to create this MetaPulsar. Default is "consistent".
        canonical_name : str, optional
            Canonical name for the pulsar (e.g., "B1857+09A"). Default is None.
        sort : bool, optional
            Whether to sort the data by time. Default is True.
        planets : bool, optional
            Whether to model solar system planets. Default is True.
        drop_t2pulsar : bool, optional
            Whether to delete the libstempo pulsar object after processing. Default is True.
        drop_pintpsr : bool, optional
            Whether to delete the PINT objects after processing. Default is True.
        merge_astrometry : bool, optional
            Whether to merge astrometry parameters across PTAs. Default is True.
        merge_spin : bool, optional
            Whether to merge spindown parameters across PTAs. Default is True.
        merge_binary : bool, optional
            Whether to merge binary parameters across PTAs. Default is True.
        merge_dm : bool, optional
            Whether to merge dispersion measure parameters across PTAs. Default is True.
        """

        self.pulsars = pulsars
        self.combination_strategy = combination_strategy
        self.canonical_name = canonical_name
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
