"""Test legacy vs new implementation comparison."""

import pytest
import numpy as np
from metapulsar import (
    FileDiscoveryService,
    get_pulsar_names_from_file_data,
    filter_file_data_by_pulsars,
)
from metapulsar.legacy.metapulsar import get_timing_package


@pytest.mark.integration
class TestLegacyComparison:
    """Test comparison between legacy and new implementations."""

    def _prepare_legacy_input_files(
        self, pulsar_name, pta_data_releases, available_data_sets
    ):
        """Prepare input files for legacy implementation using the same discovery as new system."""
        discovery_service = FileDiscoveryService()

        # Discover files for all PTAs
        file_data = discovery_service.discover_files(pta_data_releases)

        # Use proper pulsar selection methods like using_metapulsar.py
        # First get all pulsar names from the file data
        all_pulsar_names = get_pulsar_names_from_file_data(file_data)

        # Check if our target pulsar is in the discovered pulsars
        if pulsar_name not in all_pulsar_names:
            return [], []  # Return empty lists if pulsar not found

        # Filter file data to only include files for this specific pulsar
        filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar_name])

        # Convert to the format expected by legacy implementation
        par_files = []
        tim_files = []

        for data_release_name in pta_data_releases:
            if (
                data_release_name in filtered_file_data
                and filtered_file_data[data_release_name]
            ):
                # Get the first matching file for this PTA
                file_info = filtered_file_data[data_release_name][0]
                par_file = file_info.get("par")
                tim_file = file_info.get("tim")
                par_files.append(str(par_file) if par_file else None)
                tim_files.append(str(tim_file) if tim_file else None)
            else:
                # Add None for missing PTAs to maintain order
                par_files.append(None)
                tim_files.append(None)

        return par_files, tim_files

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_metapulsar_creation_equivalence(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test that MetaPulsar creation produces equivalent results."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_data_releases = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        # Get available pulsars and use the first 2 that have data
        discovery_service = FileDiscoveryService()
        file_data = discovery_service.discover_files(test_pta_data_releases)
        all_pulsar_names = get_pulsar_names_from_file_data(file_data)

        # Test first 2 available pulsars
        test_pulsars_to_use = all_pulsar_names[:2]

        for pulsar in test_pulsars_to_use:
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_data_releases, available_data_sets
            )

            # Filter out None values and check if we have any valid files
            valid_files = [
                (p, t)
                for p, t in zip(par_files, tim_files)
                if p is not None and t is not None
            ]
            if not valid_files:
                continue

            # Prepare input files in the format expected by legacy create_metapulsar
            input_files = []
            for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                if par_file is None or tim_file is None:
                    continue  # Skip missing files

                pta_name = test_pta_data_releases[i]
                # Determine timing package based on PTA
                package = (
                    "tempo2" if pta_name in ["epta_dr1_v2_2", "ppta_dr2"] else "pint"
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

            discovery_service = FileDiscoveryService()
            file_data = discovery_service.discover_files(test_pta_data_releases)

            # Use proper pulsar selection methods like using_metapulsar.py
            all_pulsar_names = get_pulsar_names_from_file_data(file_data)

            # Check if our target pulsar is in the discovered pulsars
            if pulsar not in all_pulsar_names:
                continue  # Skip if pulsar not found

            # Filter file data to only include files for this specific pulsar
            filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar])

            if not filtered_file_data:
                continue  # Skip if no files found for this pulsar

            new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                file_data=filtered_file_data
            )

            # Compare basic properties
            assert legacy_mp.name == new_mp.name
            assert len(legacy_mp._epulsars) == len(new_mp._epulsars)

            # Compare design matrix shapes
            legacy_dm = legacy_mp._designmatrix
            new_dm = new_mp._designmatrix

            # Debug: Print detailed information about the data being compared
            print(f"\n=== Debugging Design Matrix Shapes for {pulsar} ===")
            print(f"Legacy design matrix shape: {legacy_dm.shape}")
            print(f"New design matrix shape: {new_dm.shape}")
            print(f"Legacy TOAs count: {len(legacy_mp._toas)}")
            print(f"New TOAs count: {len(new_mp._toas)}")
            print(f"Legacy fitpars count: {len(legacy_mp.fitpars)}")
            print(f"New fitpars count: {len(new_mp.fitpars)}")
            print(f"Legacy fitpars: {sorted(legacy_mp.fitpars)}")
            print(f"New fitpars: {sorted(new_mp.fitpars)}")

            # Check if different PTAs are being used
            print(f"Legacy PTAs: {list(legacy_mp._epulsars.keys())}")
            print(f"New PTAs: {list(new_mp._epulsars.keys())}")

            # Check units being used
            print(
                f"Legacy timing packages: {[get_timing_package(psr) for psr in legacy_mp._epulsars.values()]}"
            )
            print(
                f"New timing packages: {[get_timing_package(psr) for psr in new_mp._epulsars.values()]}"
            )

            # Check if we can access units information
            for pta, psr in legacy_mp._epulsars.items():
                if hasattr(psr, "model") and hasattr(psr.model, "UNITS"):
                    print(f"Legacy {pta} units: {psr.model.UNITS}")
                elif hasattr(psr, "_lt_pulsar") and hasattr(psr._lt_pulsar, "units"):
                    print(f"Legacy {pta} units: {psr._lt_pulsar.units}")

            for pta, psr in new_mp._epulsars.items():
                if hasattr(psr, "model") and hasattr(psr.model, "UNITS"):
                    print(f"New {pta} units: {psr.model.UNITS}")
                elif hasattr(psr, "_lt_pulsar") and hasattr(psr._lt_pulsar, "units"):
                    print(f"New {pta} units: {psr._lt_pulsar.units}")

            # Check TOA ranges
            if len(legacy_mp._toas) > 0 and len(new_mp._toas) > 0:
                print(
                    f"Legacy TOA range: {legacy_mp._toas.min():.2f} to {legacy_mp._toas.max():.2f}"
                )
                print(
                    f"New TOA range: {new_mp._toas.min():.2f} to {new_mp._toas.max():.2f}"
                )

                # Check if TOAs are identical
                toa_diff = np.abs(legacy_mp._toas - new_mp._toas)
                print(f"Max TOA difference: {toa_diff.max():.2f}")
                print(f"Mean TOA difference: {toa_diff.mean():.2f}")
                print(f"Number of different TOAs: {np.sum(toa_diff > 1e-6)}")

                # Check first few TOAs
                print(f"First 5 legacy TOAs: {legacy_mp._toas[:5]}")
                print(f"First 5 new TOAs: {new_mp._toas[:5]}")

                # Check if it's a systematic offset
                if len(legacy_mp._toas) == len(new_mp._toas):
                    offset = np.mean(new_mp._toas - legacy_mp._toas)
                    print(f"Systematic TOA offset (new - legacy): {offset:.2f}")

            assert legacy_dm.shape == new_dm.shape

            # Reorder new design matrix to match legacy parameter order
            # Both implementations have the same fitpars, so we can use legacy order
            legacy_fitpars = legacy_mp.fitpars
            new_fitpars = new_mp.fitpars

            # Create mapping from new parameter order to legacy parameter order
            new_to_legacy_indices = [
                new_fitpars.index(param) for param in legacy_fitpars
            ]

            # Reorder new design matrix columns to match legacy order
            new_dm_reordered = new_dm[:, new_to_legacy_indices]

            # Compare design matrix values (within tolerance)
            np.testing.assert_allclose(
                legacy_dm, new_dm_reordered, rtol=1e-10, atol=1e-12
            )

            # Compare flags
            legacy_flags = legacy_mp._flags
            new_flags = new_mp._flags
            assert len(legacy_flags) == len(new_flags)

            # Normalize timing_package field to handle case sensitivity differences
            legacy_flags_normalized = legacy_flags.copy()
            new_flags_normalized = new_flags.copy()

            # Convert timing_package to lowercase for comparison
            legacy_flags_normalized["timing_package"] = np.char.lower(
                legacy_flags["timing_package"]
            )
            new_flags_normalized["timing_package"] = np.char.lower(
                new_flags["timing_package"]
            )

            assert np.array_equal(legacy_flags_normalized, new_flags_normalized)

            # Compare timing residuals
            legacy_residuals = legacy_mp._residuals
            new_residuals = new_mp._residuals
            assert len(legacy_residuals) == len(new_residuals)
            np.testing.assert_allclose(
                legacy_residuals,
                new_residuals,
                rtol=1e-10,
                atol=1e-12,
                err_msg="Timing residuals do not match between legacy and new implementations",
            )

            # Compare TOAs (Times of Arrival)
            legacy_toas = legacy_mp._toas
            new_toas = new_mp._toas
            assert len(legacy_toas) == len(new_toas)
            np.testing.assert_allclose(
                legacy_toas,
                new_toas,
                rtol=1e-10,
                atol=1e-12,
                err_msg="TOAs do not match between legacy and new implementations",
            )

            # Compare TOA errors
            legacy_toaerrs = legacy_mp._toaerrs
            new_toaerrs = new_mp._toaerrs
            assert len(legacy_toaerrs) == len(new_toaerrs)
            np.testing.assert_allclose(
                legacy_toaerrs,
                new_toaerrs,
                rtol=1e-10,
                atol=1e-12,
                err_msg="TOA errors do not match between legacy and new implementations",
            )

            # Compare frequencies
            legacy_freqs = legacy_mp.freqs
            new_freqs = new_mp.freqs
            assert len(legacy_freqs) == len(new_freqs)
            np.testing.assert_allclose(
                legacy_freqs,
                new_freqs,
                rtol=1e-10,
                atol=1e-12,
                err_msg="Frequencies do not match between legacy and new implementations",
            )

            # Compare individual Enterprise pulsar properties for each PTA
            for pta_name in legacy_mp._epulsars.keys():
                if pta_name in new_mp._epulsars:
                    legacy_epulsar = legacy_mp._epulsars[pta_name]
                    new_epulsar = new_mp._epulsars[pta_name]

                    # Compare Enterprise pulsar residuals
                    legacy_ep_residuals = legacy_epulsar.residuals
                    new_ep_residuals = new_epulsar.residuals
                    assert len(legacy_ep_residuals) == len(new_ep_residuals)
                    np.testing.assert_allclose(
                        legacy_ep_residuals,
                        new_ep_residuals,
                        rtol=1e-10,
                        atol=1e-12,
                        err_msg=f"Enterprise pulsar residuals for {pta_name} do not match",
                    )

                    # Compare Enterprise pulsar TOAs
                    legacy_ep_toas = legacy_epulsar.toas
                    new_ep_toas = new_epulsar.toas
                    assert len(legacy_ep_toas) == len(new_ep_toas)
                    np.testing.assert_allclose(
                        legacy_ep_toas,
                        new_ep_toas,
                        rtol=1e-10,
                        atol=1e-12,
                        err_msg=f"Enterprise pulsar TOAs for {pta_name} do not match",
                    )

                    # Compare Enterprise pulsar TOA errors
                    legacy_ep_toaerrs = legacy_epulsar.toaerrs
                    new_ep_toaerrs = new_epulsar.toaerrs
                    assert len(legacy_ep_toaerrs) == len(new_ep_toaerrs)
                    np.testing.assert_allclose(
                        legacy_ep_toaerrs,
                        new_ep_toaerrs,
                        rtol=1e-10,
                        atol=1e-12,
                        err_msg=f"Enterprise pulsar TOA errors for {pta_name} do not match",
                    )

                    # Compare Enterprise pulsar frequencies
                    legacy_ep_freqs = legacy_epulsar.freqs
                    new_ep_freqs = new_epulsar.freqs
                    assert len(legacy_ep_freqs) == len(new_ep_freqs)
                    np.testing.assert_allclose(
                        legacy_ep_freqs,
                        new_ep_freqs,
                        rtol=1e-10,
                        atol=1e-12,
                        err_msg=f"Enterprise pulsar frequencies for {pta_name} do not match",
                    )

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_design_matrix_construction(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test design matrix construction equivalence."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_data_releases = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_data_releases, available_data_sets
            )

            # Filter out None values and check if we have any valid files
            valid_files = [
                (p, t)
                for p, t in zip(par_files, tim_files)
                if p is not None and t is not None
            ]
            if not valid_files:
                continue

            # Prepare input files in the format expected by legacy create_metapulsar
            input_files = []
            for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                if par_file is None or tim_file is None:
                    continue  # Skip missing files

                pta_name = test_pta_data_releases[i]
                package = (
                    "tempo2" if pta_name in ["epta_dr1_v2_2", "ppta_dr2"] else "pint"
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

            discovery_service = FileDiscoveryService()
            file_data = discovery_service.discover_files(test_pta_data_releases)

            # Use proper pulsar selection methods like using_metapulsar.py
            all_pulsar_names = get_pulsar_names_from_file_data(file_data)

            # Check if our target pulsar is in the discovered pulsars
            if pulsar not in all_pulsar_names:
                continue  # Skip if pulsar not found

            # Filter file data to only include files for this specific pulsar
            filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar])

            if not filtered_file_data:
                continue  # Skip if no files found for this pulsar

            new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                file_data=filtered_file_data
            )

            # Get design matrices
            legacy_dm = legacy_mp._designmatrix
            new_dm = new_mp._designmatrix

            # Debug: Print detailed information about the data being compared
            print(f"\n=== Debugging Design Matrix Construction for {pulsar} ===")
            print(f"Legacy design matrix shape: {legacy_dm.shape}")
            print(f"New design matrix shape: {new_dm.shape}")
            print(f"Legacy TOAs count: {len(legacy_mp._toas)}")
            print(f"New TOAs count: {len(new_mp._toas)}")
            print(f"Legacy fitpars count: {len(legacy_mp.fitpars)}")
            print(f"New fitpars count: {len(new_mp.fitpars)}")
            print(f"Legacy PTAs: {list(legacy_mp._epulsars.keys())}")
            print(f"New PTAs: {list(new_mp._epulsars.keys())}")

            # Compare shapes
            assert legacy_dm.shape == new_dm.shape

            # Reorder new design matrix to match legacy parameter order
            # Both implementations have the same fitpars, so we can use legacy order
            legacy_fitpars = legacy_mp.fitpars
            new_fitpars = new_mp.fitpars

            # Create mapping from new parameter order to legacy parameter order
            new_to_legacy_indices = [
                new_fitpars.index(param) for param in legacy_fitpars
            ]

            # Reorder new design matrix columns to match legacy order
            new_dm_reordered = new_dm[:, new_to_legacy_indices]

            # Compare values
            np.testing.assert_allclose(
                legacy_dm, new_dm_reordered, rtol=1e-10, atol=1e-12
            )

            # Test that no columns are all zeros (except possibly the first)
            for i in range(1, legacy_dm.shape[1]):
                legacy_col = legacy_dm[:, i]
                new_col = new_dm_reordered[:, i]

                # Both should have the same zero pattern
                legacy_zeros = np.all(legacy_col == 0)
                new_zeros = np.all(new_col == 0)
                assert legacy_zeros == new_zeros

                # If not all zeros, values should match
                if not legacy_zeros:
                    np.testing.assert_allclose(
                        legacy_col, new_col, rtol=1e-10, atol=1e-12
                    )

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_flag_combination(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test flag combination equivalence."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_data_releases = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_data_releases, available_data_sets
            )

            if not par_files or not tim_files:
                continue

            # Prepare input files in the format expected by legacy create_metapulsar
            input_files = []
            for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                if par_file is None or tim_file is None:
                    continue  # Skip missing files

                pta_name = test_pta_data_releases[i]
                package = (
                    "tempo2" if pta_name in ["epta_dr1_v2_2", "ppta_dr2"] else "pint"
                )
                input_files.append(
                    {
                        "pta": pta_name,
                        "parfile": par_file,
                        "timfile": tim_file,
                        "package": package,
                    }
                )

            # Skip if no valid input files found
            if not input_files:
                continue

            # Create both implementations
            legacy_mp = legacy_module.create_metapulsar(input_files)

            discovery_service = FileDiscoveryService()
            file_data = discovery_service.discover_files(test_pta_data_releases)

            # Use proper pulsar selection methods like using_metapulsar.py
            all_pulsar_names = get_pulsar_names_from_file_data(file_data)

            # Check if our target pulsar is in the discovered pulsars
            if pulsar not in all_pulsar_names:
                continue  # Skip if pulsar not found

            # Filter file data to only include files for this specific pulsar
            filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar])

            if not filtered_file_data:
                continue  # Skip if no files found for this pulsar

            new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                file_data=filtered_file_data
            )

            # Get flags
            legacy_flags = legacy_mp._flags
            new_flags = new_mp._flags

            # Compare flags
            assert len(legacy_flags) == len(new_flags)

            # Normalize timing_package field to handle case sensitivity differences
            legacy_flags_normalized = legacy_flags.copy()
            new_flags_normalized = new_flags.copy()

            # Convert timing_package to lowercase for comparison
            legacy_flags_normalized["timing_package"] = np.char.lower(
                legacy_flags["timing_package"]
            )
            new_flags_normalized["timing_package"] = np.char.lower(
                new_flags["timing_package"]
            )

            assert np.array_equal(legacy_flags_normalized, new_flags_normalized)

            # Test flag statistics
            legacy_unique, legacy_counts = np.unique(
                legacy_flags_normalized, return_counts=True
            )
            new_unique, new_counts = np.unique(new_flags_normalized, return_counts=True)

            assert len(legacy_unique) == len(new_unique)
            assert np.array_equal(legacy_unique, new_unique)
            assert np.array_equal(legacy_counts, new_counts)

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_intermediate_par_file_consistency(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test that intermediate par files have consistent parameter values."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_data_releases = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]
        key_params = ["F0", "F1", "RAJ", "DECJ", "PMRA", "PMDEC", "PEPOCH"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_data_releases, available_data_sets
            )

            # Filter out None values and check if we have any valid files
            valid_files = [
                (p, t)
                for p, t in zip(par_files, tim_files)
                if p is not None and t is not None
            ]
            if not valid_files:
                continue

            # Prepare input files in the format expected by legacy create_metapulsar
            input_files = []
            for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                if par_file is None or tim_file is None:
                    continue  # Skip missing files

                pta_name = test_pta_data_releases[i]
                package = (
                    "tempo2" if pta_name in ["epta_dr1_v2_2", "ppta_dr2"] else "pint"
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

            discovery_service = FileDiscoveryService()
            file_data = discovery_service.discover_files(test_pta_data_releases)

            # Use proper pulsar selection methods like using_metapulsar.py
            all_pulsar_names = get_pulsar_names_from_file_data(file_data)

            # Check if our target pulsar is in the discovered pulsars
            if pulsar not in all_pulsar_names:
                continue  # Skip if pulsar not found

            # Filter file data to only include files for this specific pulsar
            filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar])

            if not filtered_file_data:
                continue  # Skip if no files found for this pulsar

            new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                file_data=filtered_file_data
            )

            # Get intermediate par files (if available)
            legacy_par_content = getattr(legacy_mp, "intermediate_par_content", None)
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

    @pytest.mark.slow
    @pytest.mark.legacy_comparison
    def test_fitpars_equivalence(
        self, legacy_module, new_module, available_data_sets, test_pulsars
    ):
        """Test that fitpars (fit parameters) are equivalent between legacy and new implementations.

        This is a critical test to ensure parameter merging logic works correctly.
        """
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_pta_data_releases = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            par_files, tim_files = self._prepare_legacy_input_files(
                pulsar, test_pta_data_releases, available_data_sets
            )

            # Filter out None values and check if we have any valid files
            valid_files = [
                (p, t)
                for p, t in zip(par_files, tim_files)
                if p is not None and t is not None
            ]
            if not valid_files:
                continue

            # Prepare input files in the format expected by legacy create_metapulsar
            input_files = []
            for i, (par_file, tim_file) in enumerate(zip(par_files, tim_files)):
                if par_file is None or tim_file is None:
                    continue  # Skip missing files

                pta_name = test_pta_data_releases[i]
                package = (
                    "tempo2" if pta_name in ["epta_dr1_v2_2", "ppta_dr2"] else "pint"
                )
                input_files.append(
                    {
                        "pta": pta_name,
                        "parfile": par_file,
                        "timfile": tim_file,
                        "package": package,
                    }
                )

            # Skip if no valid input files found
            if not input_files:
                continue

            # Create both implementations
            legacy_mp = legacy_module.create_metapulsar(input_files)

            discovery_service = FileDiscoveryService()
            file_data = discovery_service.discover_files(test_pta_data_releases)

            # Use proper pulsar selection methods like using_metapulsar.py
            all_pulsar_names = get_pulsar_names_from_file_data(file_data)

            # Check if our target pulsar is in the discovered pulsars
            if pulsar not in all_pulsar_names:
                continue  # Skip if pulsar not found

            # Filter file data to only include files for this specific pulsar
            filtered_file_data = filter_file_data_by_pulsars(file_data, [pulsar])

            if not filtered_file_data:
                continue  # Skip if no files found for this pulsar

            new_mp = new_module["MetaPulsarFactory"]().create_metapulsar(
                file_data=filtered_file_data
            )

            # Get fitpars from both implementations
            legacy_fitpars = set(legacy_mp.fitpars)
            new_fitpars = set(new_mp.fitpars)

            # Compare the sets of fit parameters
            assert legacy_fitpars == new_fitpars, (
                f"Fit parameters do not match between legacy and new implementations for pulsar {pulsar}:\n"
                f"Legacy fitpars ({len(legacy_fitpars)}): {sorted(legacy_fitpars)}\n"
                f"New fitpars ({len(new_fitpars)}): {sorted(new_fitpars)}\n"
                f"Missing in new: {legacy_fitpars - new_fitpars}\n"
                f"Extra in new: {new_fitpars - legacy_fitpars}"
            )

            # Additional detailed analysis for debugging
            print(f"\n=== Fitpars Analysis for {pulsar} ===")
            print(f"Legacy fitpars count: {len(legacy_fitpars)}")
            print(f"New fitpars count: {len(new_fitpars)}")

            # Analyze parameter types
            legacy_merged = {
                p
                for p in legacy_fitpars
                if not any(
                    suffix in p
                    for suffix in ["_epta_dr1_v2_2", "_ppta_dr2", "_nanograv_9y"]
                )
            }
            new_merged = {
                p
                for p in new_fitpars
                if not any(
                    suffix in p
                    for suffix in ["_epta_dr1_v2_2", "_ppta_dr2", "_nanograv_9y"]
                )
            }

            legacy_pta_specific = legacy_fitpars - legacy_merged
            new_pta_specific = new_fitpars - new_merged

            print(
                f"Legacy merged parameters: {len(legacy_merged)} - {sorted(legacy_merged)}"
            )
            print(f"New merged parameters: {len(new_merged)} - {sorted(new_merged)}")
            print(
                f"Legacy PTA-specific parameters: {len(legacy_pta_specific)} - {sorted(legacy_pta_specific)}"
            )
            print(
                f"New PTA-specific parameters: {len(new_pta_specific)} - {sorted(new_pta_specific)}"
            )

            # Test that the number of parameters is reasonable (not too small)
            assert len(new_fitpars) > 10, (
                f"New implementation has suspiciously few fit parameters ({len(new_fitpars)}). "
                f"This suggests parameter merging logic may be broken."
            )

            # Test that we have both merged and PTA-specific parameters
            assert (
                len(new_merged) > 0
            ), "No merged parameters found - parameter merging may be broken"
            assert (
                len(new_pta_specific) > 0
            ), "No PTA-specific parameters found - parameter merging may be broken"
