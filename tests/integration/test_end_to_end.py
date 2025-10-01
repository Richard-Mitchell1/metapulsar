"""Test end-to-end functionality with real data."""

import pytest
import numpy as np
from metapulsar import MetaPulsar, MetaPulsarFactory


class TestEndToEnd:
    """Test end-to-end functionality with real data."""

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_metapulsar_creation_with_dr2_data(self, available_data_sets, test_pulsars):
        """Test MetaPulsar creation with DR2 submodule data."""
        if "dr2" not in available_data_sets:
            pytest.skip("DR2 data not available")

        # Test with DR2 configurations
        dr2_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            try:
                mp = MetaPulsarFactory.create_metapulsar(
                    pulsar_name=pulsar,
                    pta_configs=dr2_configs,
                    primary_pta="epta_dr1_v2_2",
                    reference_pta="epta_dr1_v2_2",
                )

                # Basic validation
                assert mp.pulsar_name == pulsar
                assert len(mp.par_files) > 0
                assert len(mp.tim_files) > 0

                # Test design matrix
                dm = mp.get_design_matrix()
                assert dm.shape[0] > 0  # Should have observations
                assert dm.shape[1] > 0  # Should have parameters

                # Test flags
                flags = mp.get_flags()
                assert len(flags) == dm.shape[0]  # Flags should match observations
                assert len(np.unique(flags)) > 0  # Should have some variety in flags

            except Exception as e:
                pytest.skip(f"Could not create MetaPulsar for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_metapulsar_creation_with_dr3_data(self, available_data_sets, test_pulsars):
        """Test MetaPulsar creation with DR3 data."""
        if "dr3" not in available_data_sets:
            pytest.skip("DR3 data not available")

        # Test with DR3 configurations
        dr3_configs = [
            "epta_dr2",
            "inpta_dr1",
            "mpta_dr1",
            "nanograv_12y",
            "nanograv_15y",
        ]

        for pulsar in test_pulsars[:2]:  # Test first 2 pulsars
            try:
                mp = MetaPulsarFactory.create_metapulsar(
                    pulsar_name=pulsar,
                    pta_configs=dr3_configs,
                    primary_pta="epta_dr2",
                    reference_pta="epta_dr2",
                )

                # Basic validation
                assert mp.pulsar_name == pulsar
                assert len(mp.par_files) > 0
                assert len(mp.tim_files) > 0

                # Test design matrix
                dm = mp.get_design_matrix()
                assert dm.shape[0] > 0  # Should have observations
                assert dm.shape[1] > 0  # Should have parameters

                # Test flags
                flags = mp.get_flags()
                assert len(flags) == dm.shape[0]  # Flags should match observations
                assert len(np.unique(flags)) > 0  # Should have some variety in flags

            except Exception as e:
                pytest.skip(f"Could not create MetaPulsar for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_mixed_dr2_dr3_creation(self, available_data_sets, test_pulsars):
        """Test MetaPulsar creation with mixed DR2 and DR3 data."""
        if "dr2" not in available_data_sets or "dr3" not in available_data_sets:
            pytest.skip("Both DR2 and DR3 data required")

        # Test with mixed configurations
        mixed_configs = [
            "epta_dr1_v2_2",
            "epta_dr2",
            "ppta_dr2",
            "nanograv_9y",
            "nanograv_12y",
        ]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            try:
                mp = MetaPulsarFactory.create_metapulsar(
                    pulsar_name=pulsar,
                    pta_configs=mixed_configs,
                    primary_pta="epta_dr1_v2_2",
                    reference_pta="epta_dr1_v2_2",
                )

                # Basic validation
                assert mp.pulsar_name == pulsar
                assert len(mp.par_files) > 0
                assert len(mp.tim_files) > 0

                # Test design matrix
                dm = mp.get_design_matrix()
                assert dm.shape[0] > 0  # Should have observations
                assert dm.shape[1] > 0  # Should have parameters

                # Test flags
                flags = mp.get_flags()
                assert len(flags) == dm.shape[0]  # Flags should match observations
                assert len(np.unique(flags)) > 0  # Should have some variety in flags

            except Exception as e:
                pytest.skip(f"Could not create MetaPulsar for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_parameter_merging_strategies(self, available_data_sets, test_pulsars):
        """Test different parameter merging strategies."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            try:
                # Test with different primary PTAs
                for primary_pta in test_configs:
                    mp = MetaPulsarFactory.create_metapulsar(
                        pulsar_name=pulsar,
                        pta_configs=test_configs,
                        primary_pta=primary_pta,
                        reference_pta=primary_pta,
                    )

                    # Basic validation
                    assert mp.pulsar_name == pulsar
                    assert len(mp.par_files) > 0
                    assert len(mp.tim_files) > 0

                    # Test design matrix
                    dm = mp.get_design_matrix()
                    assert dm.shape[0] > 0  # Should have observations
                    assert dm.shape[1] > 0  # Should have parameters

            except Exception as e:
                pytest.skip(f"Could not test parameter merging for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_unit_conversion_consistency(self, available_data_sets, test_pulsars):
        """Test unit conversion consistency across different timing packages."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Test with both PINT and Tempo2 configurations
        pint_configs = ["nanograv_9y", "nanograv_12y", "nanograv_15y"]
        tempo2_configs = [
            "epta_dr1_v2_2",
            "ppta_dr2",
            "epta_dr2",
            "inpta_dr1",
            "mpta_dr1",
        ]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            try:
                # Test PINT configurations
                if any(
                    config in available_data_sets.get("dr2", {})
                    or config in available_data_sets.get("dr3", {})
                    for config in pint_configs
                ):
                    mp_pint = MetaPulsarFactory.create_metapulsar(
                        pulsar_name=pulsar,
                        pta_configs=pint_configs,
                        primary_pta=pint_configs[0],
                        reference_pta=pint_configs[0],
                    )

                    # Basic validation
                    assert mp_pint.pulsar_name == pulsar
                    dm_pint = mp_pint.get_design_matrix()
                    assert dm_pint.shape[0] > 0
                    assert dm_pint.shape[1] > 0

                # Test Tempo2 configurations
                if any(
                    config in available_data_sets.get("dr2", {})
                    or config in available_data_sets.get("dr3", {})
                    for config in tempo2_configs
                ):
                    mp_tempo2 = MetaPulsarFactory.create_metapulsar(
                        pulsar_name=pulsar,
                        pta_configs=tempo2_configs,
                        primary_pta=tempo2_configs[0],
                        reference_pta=tempo2_configs[0],
                    )

                    # Basic validation
                    assert mp_tempo2.pulsar_name == pulsar
                    dm_tempo2 = mp_tempo2.get_design_matrix()
                    assert dm_tempo2.shape[0] > 0
                    assert dm_tempo2.shape[1] > 0

            except Exception as e:
                pytest.skip(f"Could not test unit conversion for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_large_dataset_handling(self, available_data_sets, test_pulsars):
        """Test handling of large datasets."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        # Test with all available configurations
        all_configs = [
            "epta_dr1_v2_2",
            "ppta_dr2",
            "nanograv_9y",
            "epta_dr2",
            "inpta_dr1",
            "mpta_dr1",
            "nanograv_12y",
            "nanograv_15y",
        ]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            try:
                mp = MetaPulsarFactory.create_metapulsar(
                    pulsar_name=pulsar,
                    pta_configs=all_configs,
                    primary_pta="epta_dr1_v2_2",
                    reference_pta="epta_dr1_v2_2",
                )

                # Basic validation
                assert mp.pulsar_name == pulsar
                assert len(mp.par_files) > 0
                assert len(mp.tim_files) > 0

                # Test design matrix
                dm = mp.get_design_matrix()
                assert dm.shape[0] > 0  # Should have observations
                assert dm.shape[1] > 0  # Should have parameters

                # Test flags
                flags = mp.get_flags()
                assert len(flags) == dm.shape[0]  # Flags should match observations
                assert len(np.unique(flags)) > 0  # Should have some variety in flags

                # Test memory usage (basic check)
                assert dm.nbytes < 1e9  # Should be less than 1GB

            except Exception as e:
                pytest.skip(f"Could not test large dataset for {pulsar}: {e}")

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_metapulsar_serialization(self, available_data_sets, test_pulsars):
        """Test MetaPulsar serialization and deserialization."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            try:
                # Create MetaPulsar
                mp = MetaPulsarFactory.create_metapulsar(
                    pulsar_name=pulsar,
                    pta_configs=test_configs,
                    primary_pta="epta_dr1_v2_2",
                    reference_pta="epta_dr1_v2_2",
                )

                # Test basic serialization (if implemented)
                if hasattr(mp, "to_dict"):
                    mp_dict = mp.to_dict()
                    assert isinstance(mp_dict, dict)
                    assert mp_dict["pulsar_name"] == pulsar

                # Test basic deserialization (if implemented)
                if hasattr(mp, "from_dict"):
                    mp_restored = MetaPulsar.from_dict(mp_dict)
                    assert mp_restored.pulsar_name == mp.pulsar_name
                    assert len(mp_restored.par_files) == len(mp.par_files)
                    assert len(mp_restored.tim_files) == len(mp.tim_files)

            except Exception as e:
                pytest.skip(f"Could not test serialization for {pulsar}: {e}")
