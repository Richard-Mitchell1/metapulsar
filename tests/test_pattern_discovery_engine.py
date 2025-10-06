#!/usr/bin/env python3
"""
Tests for the Pattern Discovery Engine.

This module tests the heuristic-based pattern detection for PTA data releases.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile

from metapulsar.pattern_discovery_engine import PatternDiscoveryEngine


class TestPatternDiscoveryEngine:
    """Test cases for PatternDiscoveryEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = PatternDiscoveryEngine()

    def test_init(self):
        """Test engine initialization."""
        assert self.engine.logger is not None
        assert len(self.engine.known_pulsar_patterns) > 0
        assert len(self.engine.common_subdirs) > 0
        assert len(self.engine.file_types) > 0

    def test_analyze_directory_structure_nonexistent(self):
        """Test analysis of non-existent directory."""
        with pytest.raises(ValueError, match="Directory .* does not exist"):
            self.engine.analyze_directory_structure(Path("/nonexistent/path"))

    def test_analyze_directory_structure_no_par_files(self):
        """Test analysis of directory with no par files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a directory with no par files
            (temp_path / "empty").mkdir()

            with pytest.raises(ValueError, match="No .par files found"):
                self.engine.analyze_directory_structure(temp_path)

    def test_analyze_directory_structure_with_files(self):
        """Test analysis of directory with par and tim files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "par").mkdir()
            (temp_path / "tim").mkdir()

            # Create par files
            (temp_path / "par" / "J1909-3744.par").write_text("test par content")
            (temp_path / "par" / "J1713+0747.par").write_text("test par content")

            # Create tim files
            (temp_path / "tim" / "J1909-3744.tim").write_text("test tim content")
            (temp_path / "tim" / "J1713+0747.tim").write_text("test tim content")

            structure = self.engine.analyze_directory_structure(temp_path)

            assert structure["base_path"] == str(temp_path)
            assert len(structure["par_files"]) == 2
            assert len(structure["tim_files"]) == 2
            assert structure["directory_depth"] >= 1
            assert "subdirectory_structure" in structure
            assert "file_naming_patterns" in structure
            assert "pulsar_names" in structure

    def test_is_wideband_file(self):
        """Test wideband file detection."""
        # Test wideband indicators
        wideband_paths = [
            "path/to/wideband/file.par",
            "path/to/wb_file.par",
            "path/to/file_wb.par",
            "path/to/wide_band/file.par",
            "path/to/wide-band/file.par",
        ]

        for path_str in wideband_paths:
            assert self.engine._is_wideband_file(Path(path_str))

        # Test non-wideband files
        normal_paths = [
            "path/to/normal/file.par",
            "path/to/regular_file.par",
            "path/to/standard/file.par",
        ]

        for path_str in normal_paths:
            assert not self.engine._is_wideband_file(Path(path_str))

    def test_extract_pulsar_names(self):
        """Test pulsar name extraction."""
        # Create test par files with different naming patterns
        test_files = [
            Path("J1909-3744.par"),
            Path("B1919+21.par"),
            Path("J1713+0747A.par"),
            Path("invalid_name.par"),
        ]

        pulsar_names = self.engine._extract_pulsar_names(test_files)

        # Should extract valid pulsar names
        assert "J1909-3744" in pulsar_names
        assert "B1919+21" in pulsar_names
        assert "J1713+0747A" in pulsar_names
        # Should not extract invalid names
        assert "invalid_name" not in pulsar_names

    def test_detect_timing_package_tempo2(self):
        """Test tempo2 package detection."""
        # Mock par file content with BINARY T2
        mock_content = """
        PSRJ J1909-3744
        BINARY T2
        F0 339.317
        """

        with patch("pathlib.Path.read_text", return_value=mock_content):
            result = self.engine._detect_timing_package(["test.par"])
            assert result == "tempo2"

    def test_detect_timing_package_pint(self):
        """Test PINT package detection."""
        # Mock par file content with PINT comment
        mock_content = """
        PSRJ J1909-3744
        # PINT comment
        F0 339.317
        """

        with patch("pathlib.Path.read_text", return_value=mock_content):
            result = self.engine._detect_timing_package(["test.par"])
            assert result == "pint"

    def test_detect_timing_package_nanograv(self):
        """Test NANOGrav PTA detection (defaults to PINT)."""
        result = self.engine._detect_timing_package(["nanograv/test.par"])
        assert result == "pint"

    def test_detect_timing_package_default(self):
        """Test default timing package fallback."""
        # Mock empty content
        with patch("pathlib.Path.read_text", return_value=""):
            result = self.engine._detect_timing_package(["test.par"])
            assert result == "tempo2"

    def test_generate_par_pattern_simple(self):
        """Test par pattern generation for simple structure."""
        structure = {
            "base_path": "/test/path",
            "pulsar_names": ["J1909-3744", "J1713+0747"],
            "par_files": ["/test/path/J1909-3744.par", "/test/path/J1713+0747.par"],
        }

        pattern = self.engine._generate_par_pattern(structure)
        # Pattern should be a regex that matches pulsar names
        assert pattern.endswith(".par")
        assert "\\d{4}" in pattern  # Should contain regex for 4 digits
        assert "[BJ]" in pattern  # Should contain regex for B or J

    def test_generate_tim_pattern(self):
        """Test tim pattern generation."""
        structure = {
            "base_path": "/test/path",
            "pulsar_names": ["J1909-3744"],
            "par_files": ["/test/path/J1909-3744.par"],
            "tim_files": ["/test/path/J1909-3744.tim"],
        }

        pattern = self.engine._generate_tim_pattern(structure)
        assert pattern.endswith(".tim")

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        # Test with minimal structure
        minimal_structure = {
            "pulsar_names": [],
            "file_naming_patterns": {
                "par_naming": {},
                "tim_naming": {},
            },
        }

        confidence = self.engine._calculate_confidence(minimal_structure)
        assert 0.0 <= confidence <= 1.0
        assert confidence == 0.3  # Base confidence

        # Test with pulsar names
        structure_with_pulsars = {
            "pulsar_names": ["J1909-3744"],
            "file_naming_patterns": {
                "par_naming": {},
                "tim_naming": {},
            },
        }

        confidence = self.engine._calculate_confidence(structure_with_pulsars)
        assert confidence > 0.3  # Should be higher with pulsars

    def test_generate_pta_data_release(self):
        """Test complete PTA data release generation."""
        structure = {
            "base_path": "/test/path",
            "pulsar_names": ["J1909-3744"],
            "par_files": ["/test/path/J1909-3744.par"],
            "tim_files": ["/test/path/J1909-3744.tim"],
            "file_naming_patterns": {
                "par_naming": {},
                "tim_naming": {},
            },
        }

        with patch.object(self.engine, "_detect_timing_package", return_value="tempo2"):
            data_release = self.engine.generate_pta_data_release(structure)

            assert "base_dir" in data_release
            assert "par_pattern" in data_release
            assert "tim_pattern" in data_release
            assert "timing_package" in data_release
            assert "priority" in data_release
            assert "description" in data_release
            assert "discovery_confidence" in data_release
            assert data_release["timing_package"] == "tempo2"

    def test_generate_pta_data_release_with_timing_package(self):
        """Test PTA data release generation with specified timing package."""
        structure = {
            "base_path": "/test/path",
            "pulsar_names": ["J1909-3744"],
            "par_files": ["/test/path/J1909-3744.par"],
            "tim_files": ["/test/path/J1909-3744.tim"],
            "file_naming_patterns": {
                "par_naming": {},
                "tim_naming": {},
            },
        }

        data_release = self.engine.generate_pta_data_release(
            structure, timing_package="pint"
        )
        assert data_release["timing_package"] == "pint"


def test_pattern_discovery_integration():
    """Integration test for pattern discovery engine on IPTA data."""
    print("=== Pattern Discovery Engine Integration Test ===\n")

    engine = PatternDiscoveryEngine()
    data_root = Path("/workspaces/metapulsar/data/ipta-dr2")

    if not data_root.exists():
        pytest.skip(f"Data directory {data_root} does not exist")

    # Test on each PTA directory
    pta_dirs = [
        d
        for d in data_root.iterdir()
        if d.is_dir()
        and d.name
        not in [".git", "utils", "working", "release", "finalize_timing_summary"]
    ]

    print(f"Found {len(pta_dirs)} potential PTA directories:")
    for pta_dir in pta_dirs:
        print(f"  - {pta_dir.name}")
    print()

    results = []

    for pta_dir in pta_dirs:
        print(f"🔍 Analyzing {pta_dir.name}...")
        try:
            # Analyze structure
            structure = engine.analyze_directory_structure(pta_dir)

            # Generate config
            data_release = engine.generate_pta_data_release(structure)

            results.append(
                {
                    "name": pta_dir.name,
                    "structure": structure,
                    "data_release": data_release,
                }
            )

            print(
                f"  ✅ Success! Confidence: {data_release['discovery_confidence']:.2f}"
            )
            print(f"     Par pattern: {data_release['par_pattern']}")
            print(f"     Tim pattern: {data_release['tim_pattern']}")
            print(f"     Timing package: {data_release['timing_package']}")
            print(f"     Pulsars found: {len(structure['pulsar_names'])}")
            if structure["pulsar_names"]:
                print(f"     Example pulsars: {structure['pulsar_names'][:3]}")
            print()

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            print()

    # Summary
    print("=== Summary ===")
    successful = [r for r in results if r]
    print(f"Successfully analyzed: {len(successful)}/{len(pta_dirs)} PTAs")

    if successful:
        avg_confidence = sum(
            r["data_release"]["discovery_confidence"] for r in successful
        ) / len(successful)
        print(f"Average confidence: {avg_confidence:.2f}")

        print("\nGenerated configurations:")
        for result in successful:
            print(f"\n{result['name']}:")
            print(f"  base_dir: {result['data_release']['base_dir']}")
            print(f"  par_pattern: {result['data_release']['par_pattern']}")
            print(f"  tim_pattern: {result['data_release']['tim_pattern']}")
            print(f"  timing_package: {result['data_release']['timing_package']}")
            print(f"  confidence: {result['data_release']['discovery_confidence']:.2f}")


if __name__ == "__main__":
    # Run the integration test if called directly
    test_pattern_discovery_integration()
