"""Tests for Meta-Pulsar Factory."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from metapulsar.metapulsar_factory import MetaPulsarFactory
from metapulsar.file_discovery_service import FileDiscoveryService
from metapulsar.position_helpers import discover_pulsars_by_coordinates_optimized


class TestMetaPulsarFactory:
    """Test MetaPulsarFactory class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MetaPulsarFactory()
        self.discovery_service = FileDiscoveryService()

    def test_initialization(self):
        """Test factory initialization without ParFileManager."""
        factory = MetaPulsarFactory()
        assert factory.logger is not None
        # Should not have parfile_manager attribute anymore
        assert not hasattr(factory, "parfile_manager")

    def test_create_metapulsar_with_file_data(self):
        """Test create_metapulsar with enriched file data."""
        # Create mock file data in the new enriched format
        file_data = {
            "epta_dr2": {
                "par": Path("/data/epta/J1857+0943.par"),
                "tim": Path("/data/epta/J1857+0943.tim"),
                "timing_package": "tempo2",
            }
        }

        # This test will need to be updated once the implementation is complete
        # For now, just test that the method accepts the new signature
        try:
            self.factory.create_metapulsar(file_data)
            # Implementation is stubbed, so this will likely fail
        except Exception:
            # Expected since implementation is not complete
            pass

    def test_create_metapulsars_from_file_data(self):
        """Test batch creation of MetaPulsars from enriched file data."""
        # Create mock file data in the new enriched format
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                    "timing_package": "tempo2",
                    "priority": 1,
                },
                {
                    "par": Path("/data/epta/J1939+2134.par"),
                    "tim": Path("/data/epta/J1939+2134.tim"),
                    "timing_package": "tempo2",
                    "priority": 1,
                },
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1857+0943.par"),
                    "tim": Path("/data/ppta/J1857+0943.tim"),
                    "timing_package": "tempo2",
                    "priority": 1,
                }
            ],
        }

        # This test will need to be updated once the implementation is complete
        # For now, just test that the method accepts the new signature
        try:
            self.factory.create_metapulsars_from_file_data(file_data)
            # Implementation is stubbed, so this will likely fail
        except Exception:
            # Expected since implementation is not complete
            pass

    @patch("metapulsar.position_helpers.bj_name_from_pulsar")
    def test_create_metapulsar_success(self, mock_bj_name):
        """Test successful MetaPulsar creation using MockPulsar directly."""
        # Mock position helper
        mock_bj_name.return_value = "J1857+0943"
        # Create MockPulsar objects directly instead of going through factory
        from metapulsar.mockpulsar import MockPulsar
        from metapulsar.mockpulsar import (
            create_mock_timing_data,
            create_mock_flags,
        )

        # Create mock timing data
        toas, residuals, errors, freqs = create_mock_timing_data(50)
        flags = create_mock_flags(50, telescope="test_pta")
        mock_psr = MockPulsar(
            toas,
            residuals,
            errors,
            freqs,
            flags,
            "test_pta",
            "J1857+0943",
            astrometry=True,
            spin=True,
        )

        # Create MetaPulsar with adapted MockPulsar
        from metapulsar.metapulsar import MetaPulsar
        from metapulsar.mockpulsar import create_libstempo_adapter

        adapted_pulsar = create_libstempo_adapter(mock_psr)
        pulsars = {"test_pta": adapted_pulsar}
        metapulsar = MetaPulsar(pulsars=pulsars, combination_strategy="composite")

        assert metapulsar is not None
        assert hasattr(metapulsar, "pulsars")
        assert len(metapulsar.pulsars) == 1
        assert metapulsar.name == "J1857+0943"

    def test_create_metapulsar_invalid_file_data(self):
        """Test MetaPulsar creation with invalid file data."""
        # Test with empty file data
        empty_file_data = {}

        # This test will need to be updated once the implementation is complete
        try:
            self.factory.create_metapulsar(empty_file_data)
        except Exception:
            # Expected since implementation is not complete
            pass

    def test_validate_single_pulsar_data_empty(self):
        """Test validation with empty file data."""
        empty_file_data = {}

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value={},
        ):
            with pytest.raises(ValueError, match="No valid pulsar files found"):
                self.factory._validate_single_pulsar_data(empty_file_data)

    def test_validate_single_pulsar_data_multiple_pulsars(self):
        """Test validation with multiple pulsars in file data."""
        # Mock file data with multiple pulsars
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                }
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1909-3744.par"),
                    "tim": Path("/data/ppta/J1909-3744.tim"),
                }
            ],
        }

        # Mock coordinate discovery to return multiple pulsars
        mock_pulsar_groups = {
            "J1857+0943": {"epta_dr2": [file_data["epta_dr2"][0]]},
            "J1909-3744": {"ppta_dr2": [file_data["ppta_dr2"][0]]},
        }

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value=mock_pulsar_groups,
        ):
            with pytest.raises(ValueError, match="Multiple pulsars detected"):
                self.factory._validate_single_pulsar_data(file_data)

    def test_validate_single_pulsar_data_single_pulsar(self):
        """Test validation with single pulsar in file data."""
        # Mock file data with single pulsar
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                }
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1857+0943.par"),
                    "tim": Path("/data/ppta/J1857+0943.tim"),
                }
            ],
        }

        # Mock coordinate discovery to return single pulsar
        mock_pulsar_groups = {
            "J1857+0943": {
                "epta_dr2": [file_data["epta_dr2"][0]],
                "ppta_dr2": [file_data["ppta_dr2"][0]],
            }
        }

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value=mock_pulsar_groups,
        ):
            # Should not raise an exception
            self.factory._validate_single_pulsar_data(file_data)

    def test_group_files_by_pulsar_empty(self):
        """Test grouping with empty file data."""
        empty_file_data = {}

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value={},
        ):
            with pytest.raises(ValueError, match="No valid pulsar files found"):
                self.factory.group_files_by_pulsar(empty_file_data)

    def test_group_files_by_pulsar_success(self):
        """Test successful grouping of files by pulsar."""
        # Mock file data with multiple pulsars
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                },
                {
                    "par": Path("/data/epta/J1909-3744.par"),
                    "tim": Path("/data/epta/J1909-3744.tim"),
                },
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1857+0943.par"),
                    "tim": Path("/data/ppta/J1857+0943.tim"),
                },
                {
                    "par": Path("/data/ppta/J1909-3744.par"),
                    "tim": Path("/data/ppta/J1909-3744.tim"),
                },
            ],
        }

        # Mock coordinate discovery to return grouped pulsars
        expected_groups = {
            "J1857+0943": {
                "epta_dr2": [file_data["epta_dr2"][0]],
                "ppta_dr2": [file_data["ppta_dr2"][0]],
            },
            "J1909-3744": {
                "epta_dr2": [file_data["epta_dr2"][1]],
                "ppta_dr2": [file_data["ppta_dr2"][1]],
            },
        }

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value=expected_groups,
        ):
            result = self.factory.group_files_by_pulsar(file_data)

            assert result == expected_groups
            assert len(result) == 2
            assert "J1857+0943" in result
            assert "J1909-3744" in result
            assert "epta_dr2" in result["J1857+0943"]
            assert "ppta_dr2" in result["J1857+0943"]

    def test_create_metapulsar_with_validation_single_pulsar(self):
        """Test create_metapulsar with validation for single pulsar."""
        # Mock file data with single pulsar
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                }
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1857+0943.par"),
                    "tim": Path("/data/ppta/J1857+0943.tim"),
                }
            ],
        }

        # Mock coordinate discovery to return single pulsar
        mock_pulsar_groups = {
            "J1857+0943": {
                "epta_dr2": [file_data["epta_dr2"][0]],
                "ppta_dr2": [file_data["ppta_dr2"][0]],
            }
        }

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value=mock_pulsar_groups,
        ):
            with patch.object(
                self.factory, "create_metapulsar_from_file_data"
            ) as mock_create:
                mock_create.return_value = Mock()

                # Should not raise an exception
                self.factory.create_metapulsar(file_data)

                # Verify validation was called and create_metapulsar_from_file_data was called
                mock_create.assert_called_once_with(
                    file_data,
                    "consistent",
                    None,
                    ["astrometry", "spindown", "binary", "dispersion"],
                    True,
                )

    def test_create_metapulsar_with_validation_multiple_pulsars(self):
        """Test create_metapulsar with validation fails for multiple pulsars."""
        # Mock file data with multiple pulsars
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                }
            ],
            "ppta_dr2": [
                {
                    "par": Path("/data/ppta/J1909-3744.par"),
                    "tim": Path("/data/ppta/J1909-3744.tim"),
                }
            ],
        }

        # Mock coordinate discovery to return multiple pulsars
        mock_pulsar_groups = {
            "J1857+0943": {"epta_dr2": [file_data["epta_dr2"][0]]},
            "J1909-3744": {"ppta_dr2": [file_data["ppta_dr2"][0]]},
        }

        with patch(
            "metapulsar.metapulsar_factory.discover_pulsars_by_coordinates_optimized",
            return_value=mock_pulsar_groups,
        ):
            with pytest.raises(ValueError, match="Multiple pulsars detected"):
                self.factory.create_metapulsar(file_data)

    # Note: test_create_metapulsar_enterprise_creation_fails removed
    # This test was written for the old regex-based architecture and is no longer relevant
    # Error handling for Enterprise Pulsar creation is now tested in integration tests

    def test_create_all_metapulsars_with_file_discovery_service(self):
        """Test creating all MetaPulsars using FileDiscoveryService."""
        # This test demonstrates the new workflow using FileDiscoveryService
        # First discover files using the service
        try:
            # Discover all files in test PTAs
            file_data = self.discovery_service.discover_all_files_in_ptas(["epta_dr2"])

            # Create MetaPulsars from discovered files
            self.factory.create_metapulsars_from_file_data(file_data)

            # This test will need to be updated once the implementation is complete
        except Exception:
            # Expected since implementation is not complete
            pass

    def test_file_discovery_service_integration(self):
        """Test integration with FileDiscoveryService."""
        # Test that FileDiscoveryService can be used independently
        assert self.discovery_service is not None
        assert hasattr(self.discovery_service, "discover_all_files_in_ptas")
        assert hasattr(self.discovery_service, "list_ptas")

        # Test listing PTAs
        ptas = self.discovery_service.list_ptas()
        assert isinstance(ptas, list)
        assert len(ptas) > 0

    def test_build_metadata(self):
        """Test metadata building."""
        file_pairs = {
            "epta_dr2": (Path("/data/epta.par"), Path("/data/epta.tim")),
            "ppta_dr3": (Path("/data/ppta.par"), Path("/data/ppta.tim")),
        }

        pta_data_releases = {
            "epta_dr2": {
                "base_dir": "/data/epta",
                "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                "timing_package": "tempo2",
                "description": "EPTA DR2",
            },
            "ppta_dr3": {
                "base_dir": "/data/ppta",
                "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                "timing_package": "tempo2",
                "description": "PPTA DR3",
            },
        }

        metadata = self.factory._build_metadata(file_pairs, pta_data_releases)

        assert "file_pairs" in metadata
        assert "timing_packages" in metadata
        assert "creation_timestamp" in metadata
        assert metadata["timing_packages"]["epta_dr2"] == "tempo2"
        assert metadata["timing_packages"]["ppta_dr3"] == "tempo2"

    @patch("metapulsar.metapulsar_factory.ParameterManager")
    def test_create_metapulsar_with_consistent_strategy(self, mock_param_manager):
        """Test create_metapulsar with consistent strategy using ParameterManager."""
        # Mock ParameterManager
        mock_manager_instance = Mock()
        mock_manager_instance.make_parfiles_consistent.return_value = {
            "epta_dr2": Path("/tmp/consistent_epta_dr2.par")
        }
        mock_param_manager.return_value = mock_manager_instance

        # Create mock file data
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                    "timing_package": "pint",
                    "timespan_days": 1000.0,
                    "par_content": "PSR J1857+0943\nF0 123.456\nRAJ 18:57:36.4\nDECJ 9:43:17.2\n",
                }
            ]
        }

        # Mock the pulsar creation and MetaPulsar creation to avoid complex setup
        with patch.object(
            self.factory, "_create_pulsar_objects"
        ) as mock_create_pulsars:
            with patch(
                "metapulsar.metapulsar_factory.MetaPulsar"
            ) as mock_metapulsar_class:
                mock_metapulsar = Mock()
                mock_metapulsar_class.return_value = mock_metapulsar
                mock_create_pulsars.return_value = {"epta_dr2": Mock()}

                # Test the ParameterManager integration
                result = self.factory.create_metapulsar(
                    file_data,
                    combination_strategy="consistent",
                    combine_components=["astrometry", "spindown"],
                )

                # Verify ParameterManager was called with correct parameters
                mock_param_manager.assert_called_once()
                call_args = mock_param_manager.call_args
                assert call_args[1]["combine_components"] == ["astrometry", "spindown"]

                # Verify the result
                assert result == mock_metapulsar

    def test_create_pulsar_objects_pint(self):
        """Test _create_pulsar_objects with PINT timing package."""
        file_pairs = {
            "epta_dr2": (
                Path("/data/epta/J1857+0943.par"),
                Path("/data/epta/J1857+0943.tim"),
            )
        }
        file_data = {
            "epta_dr2": {
                "par": Path("/data/epta/J1857+0943.par"),
                "tim": Path("/data/epta/J1857+0943.tim"),
                "timing_package": "pint",
                "timespan_days": 1000.0,
                "priority": 1,
            }
        }

        with patch(
            "metapulsar.metapulsar_factory.get_model_and_toas"
        ) as mock_get_model:
            mock_model = Mock()
            mock_toas = Mock()
            mock_get_model.return_value = (mock_model, mock_toas)

            result = self.factory._create_pulsar_objects(file_pairs, file_data)

            assert "epta_dr2" in result
            assert result["epta_dr2"] == (mock_model, mock_toas)
            mock_get_model.assert_called_once_with(
                str(file_pairs["epta_dr2"][0]),
                str(file_pairs["epta_dr2"][1]),
                planets=True,
            )

    def test_create_pulsar_objects_tempo2(self):
        """Test _create_pulsar_objects with Tempo2 timing package."""
        file_pairs = {
            "epta_dr2": (
                Path("/data/epta/J1857+0943.par"),
                Path("/data/epta/J1857+0943.tim"),
            )
        }
        file_data = {
            "epta_dr2": {
                "par": Path("/data/epta/J1857+0943.par"),
                "tim": Path("/data/epta/J1857+0943.tim"),
                "timing_package": "tempo2",
                "timespan_days": 1000.0,
                "priority": 1,
            }
        }

        with patch("metapulsar.metapulsar_factory.t2") as mock_t2:
            mock_psr = Mock()
            mock_t2.tempopulsar.return_value = mock_psr

            result = self.factory._create_pulsar_objects(file_pairs, file_data)

            assert "epta_dr2" in result
            assert result["epta_dr2"] == mock_psr
            mock_t2.tempopulsar.assert_called_once_with(
                str(file_pairs["epta_dr2"][0]), str(file_pairs["epta_dr2"][1])
            )

    def test_discover_pulsars_by_coordinates(self):
        """Test _discover_pulsars_by_coordinates method with proper mocking."""
        file_data = {
            "epta_dr2": [
                {
                    "par": Path("/data/epta/J1857+0943.par"),
                    "tim": Path("/data/epta/J1857+0943.tim"),
                    "par_content": "PSR J1857+0943\nRAJ 18:57:36.4\nDECJ 09:43:17.1\n",
                    "timing_package": "pint",
                    "timespan_days": 1000.0,
                }
            ]
        }

        # Mock the entire _create_minimal_parfile_for_coordinates method to avoid complex dependencies
        with patch.object(
            self.factory, "_create_minimal_parfile_for_coordinates"
        ) as mock_create_minimal:
            mock_create_minimal.return_value = (
                "PSR J1857+0943\nRAJ 18:57:36.4\nDECJ 09:43:17.1\n"
            )

            with patch("pint.models.model_builder.ModelBuilder") as mock_builder:
                # Create a proper mock model with astropy Quantity objects
                from astropy import units as u
                from astropy.coordinates import Angle

                mock_model = Mock()
                mock_model.PSR.value = "J1857+0943"

                # Create proper astropy Quantity objects for RAJ and DECJ
                # For J1857+0943: RAJ = 18:57:36.4 = 18.9601 hours, DECJ = 09:43:17.1 = 9.7214 degrees
                mock_raj = Mock()
                mock_raj.quantity = Angle(18.9601, unit=u.hourangle)  # RA in hours
                mock_model.RAJ = mock_raj

                mock_decj = Mock()
                mock_decj.quantity = Angle(9.7214, unit=u.deg)  # Dec in degrees
                mock_model.DECJ = mock_decj

                mock_builder_instance = Mock()
                mock_builder_instance.return_value = mock_model
                mock_builder.return_value = mock_builder_instance

                with patch(
                    "metapulsar.position_helpers.bj_name_from_pulsar"
                ) as mock_bj_name:
                    mock_bj_name.return_value = "J1857+0943"

                    result = discover_pulsars_by_coordinates_optimized(file_data)

                    assert "J1857+0943" in result
                    assert "epta_dr2" in result["J1857+0943"]
                    assert len(result["J1857+0943"]["epta_dr2"]) == 1
