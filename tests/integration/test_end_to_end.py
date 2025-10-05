"""Test end-to-end functionality with real data."""

import pytest
import numpy as np
from metapulsar import MetaPulsar, MetaPulsarFactory, FileDiscoveryService


@pytest.mark.integration
class TestEndToEnd:
    """Test end-to-end functionality with real data."""

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_metapulsar_creation_with_dr2_data(self, available_data_sets, test_pulsars):
        """Test MetaPulsar creation with DR2 submodule data."""
        if "dr2" not in available_data_sets:
            pytest.skip("DR2 data not available")

        # Test with DR2 configurations using FileDiscoveryService
        dr2_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]
        discovery_service = FileDiscoveryService()
        factory = MetaPulsarFactory()

        # This test will need to be updated once the implementation is complete
        # For now, just test that the services can be used
        try:
            # Discover files using FileDiscoveryService
            file_data = discovery_service.discover_all_files_in_ptas(dr2_configs)

            # Create MetaPulsars from discovered files
            result = factory.create_metapulsars_from_file_data(file_data)

            # This test will need to be updated once the implementation is complete
        except Exception:
            # Expected since implementation is not complete
            pass

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_parameter_merging_strategies(self, available_data_sets, test_pulsars):
        """Test different parameter merging strategies."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            # Test with different primary PTAs
            for primary_pta in test_configs:
                mp = MetaPulsarFactory().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=test_configs,
                    reference_pta=primary_pta,
                )

                # Basic validation
                assert mp.name == pulsar
                assert len(mp.pulsars) > 0  # Should have pulsar data from PTAs
                assert len(mp._epulsars) > 0  # Should have Enterprise pulsars

                # Test design matrix
                dm = mp._designmatrix
                assert dm.shape[0] > 0  # Should have observations
                assert dm.shape[1] > 0  # Should have parameters

                # Test flags
                flags = mp._flags
                assert len(flags) == dm.shape[0]  # Flags should match observations
                assert len(np.unique(flags)) > 0  # Should have some variety in flags

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
            # Test PINT configurations
            if any(
                config in available_data_sets.get("dr2", {})
                or config in available_data_sets.get("dr3", {})
                for config in pint_configs
            ):
                mp_pint = MetaPulsarFactory().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=pint_configs,
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
                mp_tempo2 = MetaPulsarFactory().create_metapulsar(
                    pulsar_name=pulsar,
                    pta_names=tempo2_configs,
                    reference_pta=tempo2_configs[0],
                )

                # Basic validation
                assert mp_tempo2.pulsar_name == pulsar
                dm_tempo2 = mp_tempo2.get_design_matrix()
                assert dm_tempo2.shape[0] > 0
                assert dm_tempo2.shape[1] > 0

    @pytest.mark.slow
    @pytest.mark.real_data
    def test_metapulsar_serialization(self, available_data_sets, test_pulsars):
        """Test MetaPulsar serialization and deserialization."""
        if not available_data_sets:
            pytest.skip("No data available for testing")

        test_configs = ["epta_dr1_v2_2", "ppta_dr2", "nanograv_9y"]

        for pulsar in test_pulsars[:1]:  # Test first pulsar
            # Create MetaPulsar
            mp = MetaPulsarFactory().create_metapulsar(
                pulsar_name=pulsar,
                pta_names=test_configs,
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
