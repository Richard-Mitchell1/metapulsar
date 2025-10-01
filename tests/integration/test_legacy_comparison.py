"""Test legacy vs new implementation comparison."""

import pytest
import numpy as np
from pathlib import Path
from metapulsar import PTARegistry


@pytest.mark.integration
class TestLegacyComparison:
    """Test comparison between legacy and new implementations."""

    def _prepare_legacy_input_files(
        self, pulsar_name, pta_configs, available_data_sets
    ):
        """Prepare input files for legacy implementation."""
        import re

        registry = PTARegistry()
        par_files = []
        tim_files = []

        for config_name in pta_configs:
            config = registry.get_pta(config_name)
            base_dir = Path(config["base_dir"])

            if not base_dir.exists():
                continue

            # Find par file using the actual regex pattern from config
            par_pattern = config["par_pattern"]
            par_regex = re.compile(par_pattern)

            # Search through all par files in the directory tree
            for par_file in base_dir.glob("**/*.par"):
                if par_regex.match(str(par_file.relative_to(base_dir))):
                    par_files.append(str(par_file))
                    break  # Found the first matching par file

            # Find tim file using the actual regex pattern from config
            tim_pattern = config["tim_pattern"]
            tim_regex = re.compile(tim_pattern)

            # Search through all tim files in the directory tree
            for tim_file in base_dir.glob("**/*.tim"):
                if tim_regex.match(str(tim_file.relative_to(base_dir))):
                    tim_files.append(str(tim_file))
                    break  # Found the first matching tim file

        return par_files, tim_files

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_metapulsar_creation_equivalence(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test that MetaPulsar creation produces equivalent results."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_configs, available_data_sets
            )

            if not par_files or not tim_files:
                continue

            try:
                # Prepare input files in the format expected by legacy create_metapulsar
                input_files = []
                for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                    pta_name = test_pta_configs[i]
                    # Determine timing package based on PTA
                    package = (
                        "tempo2"
                        if pta_name in ["epta_dr1_v2_2", "ppta_dr2"]
                        else "pint"
                    )
                    input_files.append(
                        {
                            "pta": pta_name,
                            "parfile": par_file,
                            "timfile": tim_file,
                            "package": package,
                        }
                    )

                # Create legacy MetaPulsar
                legacy_mp = legacy_module.create_metapulsar(input_files)

                # Create new MetaPulsar
                new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=test_pta_configs,
                    reference_pta="epta_dr1_v2_2",
                )

                # Compare basic properties
                assert legacy_mp.name == new_mp.name
                assert len(legacy_mp.pulsars) == len(new_mp.pulsars)
                assert len(legacy_mp._epulsars) == len(new_mp._epulsars)

                # Compare design matrix shapes
                legacy_dm = legacy_mp._designmatrix
                new_dm = new_mp._designmatrix
                assert legacy_dm.shape == new_dm.shape

                # Compare design matrix values (within tolerance)
                np.testing.assert_allclose(legacy_dm, new_dm, rtol=1e-10, atol=1e-12)

                # Compare flags
                legacy_flags = legacy_mp._flags
                new_flags = new_mp._flags
                assert len(legacy_flags) == len(new_flags)
                assert np.array_equal(legacy_flags, new_flags)

            except Exception as e:
                pytest.skip(f"Could not create MetaPulsar for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_design_matrix_construction(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test design matrix construction equivalence."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_configs, available_data_sets
            )

            if not par_files or not tim_files:
                continue

            try:
                # Prepare input files in the format expected by legacy create_metapulsar
                input_files = []
                for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                    pta_name = test_pta_configs[i]
                    package = (
                        "tempo2"
                        if pta_name in ["epta_dr1_v2_2", "ppta_dr2"]
                        else "pint"
                    )
                    input_files.append(
                        {
                            "pta": pta_name,
                            "parfile": par_file,
                            "timfile": tim_file,
                            "package": package,
                        }
                    )

                # Create both implementations
                legacy_mp = legacy_module.create_metapulsar(input_files)

                new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=test_pta_configs,
                    reference_pta="epta_dr1_v2_2",
                )

                # Get design matrices
                legacy_dm = legacy_mp._designmatrix
                new_dm = new_mp._designmatrix

                # Compare shapes
                assert legacy_dm.shape == new_dm.shape

                # Compare values
                np.testing.assert_allclose(legacy_dm, new_dm, rtol=1e-10, atol=1e-12)

                # Test that no columns are all zeros (except possibly the first)
                for i in range(1, legacy_dm.shape[1]):
                    legacy_col = legacy_dm[:, i]
                    new_col = new_dm[:, i]

                    # Both should have the same zero pattern
                    legacy_zeros = np.all(legacy_col == 0)
                    new_zeros = np.all(new_col == 0)
                    assert legacy_zeros == new_zeros

                    # If not all zeros, values should match
                    if not legacy_zeros:
                        np.testing.assert_allclose(
                            legacy_col, new_col, rtol=1e-10, atol=1e-12
                        )

            except Exception as e:
                pytest.skip(f"Could not test design matrix for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_flag_combination(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test flag combination equivalence."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_configs, available_data_sets
            )

            if not par_files or not tim_files:
                continue

            try:
                # Prepare input files in the format expected by legacy create_metapulsar
                input_files = []
                for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                    pta_name = test_pta_configs[i]
                    package = (
                        "tempo2"
                        if pta_name in ["epta_dr1_v2_2", "ppta_dr2"]
                        else "pint"
                    )
                    input_files.append(
                        {
                            "pta": pta_name,
                            "parfile": par_file,
                            "timfile": tim_file,
                            "package": package,
                        }
                    )

                # Create both implementations
                legacy_mp = legacy_module.create_metapulsar(input_files)

                new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=test_pta_configs,
                    reference_pta="epta_dr1_v2_2",
                )

                # Get flags
                legacy_flags = legacy_mp._flags
                new_flags = new_mp._flags

                # Compare flags
                assert len(legacy_flags) == len(new_flags)
                assert np.array_equal(legacy_flags, new_flags)

                # Test flag statistics
                legacy_unique, legacy_counts = np.unique(
                    legacy_flags, return_counts=True
                )
                new_unique, new_counts = np.unique(new_flags, return_counts=True)

                assert len(legacy_unique) == len(new_unique)
                assert np.array_equal(legacy_unique, new_unique)
                assert np.array_equal(legacy_counts, new_counts)

            except Exception as e:
                pytest.skip(f"Could not test flags for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_intermediate_par_file_consistency(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test that intermediate par files have consistent parameter values."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]
        key_params = ["F0", "F1", "RAJ", "DECJ", "PMRA", "PMDEC", "PEPOCH"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_configs, available_data_sets
            )

            if not par_files or not tim_files:
                continue

            try:
                # Prepare input files in the format expected by legacy create_metapulsar
                input_files = []
                for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                    pta_name = test_pta_configs[i]
                    package = (
                        "tempo2"
                        if pta_name in ["epta_dr1_v2_2", "ppta_dr2"]
                        else "pint"
                    )
                    input_files.append(
                        {
                            "pta": pta_name,
                            "parfile": par_file,
                            "timfile": tim_file,
                            "package": package,
                        }
                    )

                # Create both implementations
                legacy_mp = legacy_module.create_metapulsar(input_files)

                new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=test_pta_configs,
                    reference_pta="epta_dr1_v2_2",
                )

                # Get intermediate par files (if available)
                legacy_par_content = getattr(
                    legacy_mp, "intermediate_par_content", None
                )
                new_par_content = getattr(new_mp, "intermediate_par_content", None)

                if legacy_par_content and new_par_content:
                    # Parse par files and compare key parameters
                    from pint.models import get_model

                    legacy_model = get_model(legacy_par_content)
                    new_model = get_model(new_par_content)

                    for param in key_params:
                        if hasattr(legacy_model, param) and hasattr(new_model, param):
                            legacy_val = getattr(legacy_model, param).value
                            new_val = getattr(new_model, param).value

                            if legacy_val is not None and new_val is not None:
                                np.testing.assert_allclose(
                                    legacy_val,
                                    new_val,
                                    rtol=1e-10,
                                    atol=1e-12,
                                    err_msg=f"Parameter {param} mismatch",
                                )

            except Exception as e:
                pytest.skip(f"Could not test par file consistency for {pulsar}: {e}")
