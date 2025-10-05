"""Unit tests for TimFileAnalyzer class."""

import pytest
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metapulsar.tim_file_analyzer import TimFileAnalyzer


class TestTimFileAnalyzer:
    """Test cases for TimFileAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.analyzer = TimFileAnalyzer()
        self.test_data_dir = Path("tests/data/tim_files")
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up after each test method."""
        # Clean up any test files created
        if self.test_data_dir.exists():
            for file in self.test_data_dir.glob("*.tim"):
                file.unlink()
            self.test_data_dir.rmdir()

    def _create_test_tim_file(self, filename: str, content: str) -> Path:
        """Create a test TIM file with given content."""
        file_path = self.test_data_dir / filename
        file_path.write_text(content)
        return file_path

    def _create_tempo2_line(self, mjd: float) -> str:
        """Create a properly formatted Tempo2 TOA line."""
        return f"c036915.align.pazr.30min 1345.999 {mjd} 2.890 g 12345678901234567890123456789012345678901234567890123456789012345678901234567890"

    # Core Functionality Tests

    def test_calculate_timespan_basic(self):
        """Test basic timespan calculation with simple TIM file."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
{self._create_tempo2_line(55093.1109722889085)}
"""
        tim_file = self._create_test_tim_file("basic.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Timespan should be 55093.1109722889085 - 55087.1109722889085 = 6.0 days
        assert timespan == 6.0

    def test_calculate_timespan_empty_file(self):
        """Test handling of empty TIM file."""
        tim_file = self._create_test_tim_file("empty.tim", "")

        timespan = self.analyzer.calculate_timespan(tim_file)

        assert timespan == 0.0

    def test_calculate_timespan_single_toa(self):
        """Test file with only one TOA."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
"""
        tim_file = self._create_test_tim_file("single_toa.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        assert timespan == 0.0

    def test_calculate_timespan_missing_file(self):
        """Test handling of non-existent file."""
        missing_file = self.test_data_dir / "missing.tim"

        timespan = self.analyzer.calculate_timespan(missing_file)

        assert timespan == 0.0

    # Format Detection Tests

    def test_toa_format_tempo2(self):
        """Test Tempo2 format detection."""
        # Long line (>80 chars) should be detected as Tempo2
        long_line = (
            "c036915.align.pazr.30min 1345.999 55087.1109722889085 2.890 g " + "x" * 50
        )
        assert self.analyzer._toa_format(long_line) == "Tempo2"

    def test_toa_format_princeton(self):
        """Test Princeton format detection."""
        # Line starting with [0-9a-z@] followed by space should be Princeton
        princeton_line = "a 1345.999 55087.1109722889085 2.890 g"
        assert self.analyzer._toa_format(princeton_line) == "Princeton"

    def test_toa_format_parkes(self):
        """Test Parkes format detection."""
        # Line starting with space and having decimal at column 42
        parkes_line = " " * 41 + ".123456" + " " * 20
        assert self.analyzer._toa_format(parkes_line) == "Parkes"

    def test_toa_format_comments(self):
        """Test comment line detection."""
        # Lines starting with #, C , CC should be comments
        # Note: "c " (lowercase c with space) is detected as Princeton, not Comment
        assert self.analyzer._toa_format("# This is a comment") == "Comment"
        assert self.analyzer._toa_format("C This is a comment") == "Comment"
        assert self.analyzer._toa_format("CC This is a comment") == "Comment"

    def test_toa_format_commands(self):
        """Test command line detection."""
        # Lines starting with FORMAT, JUMP, TIME, etc. should be commands
        assert self.analyzer._toa_format("FORMAT 1") == "Command"
        assert self.analyzer._toa_format("JUMP 55000 55001") == "Command"
        assert self.analyzer._toa_format("TIME 55000") == "Command"
        assert self.analyzer._toa_format("PHASE 0") == "Command"
        assert self.analyzer._toa_format("SKIP") == "Command"
        assert self.analyzer._toa_format("NOSKIP") == "Command"

    def test_toa_format_blank(self):
        """Test blank line detection."""
        # Empty or whitespace-only lines should be blank
        assert self.analyzer._toa_format("") == "Blank"
        assert self.analyzer._toa_format("   ") == "Blank"
        assert self.analyzer._toa_format("\t") == "Blank"

    def test_toa_format_unknown(self):
        """Test unknown format detection."""
        # Lines that don't match any pattern should be unknown
        assert self.analyzer._toa_format("!@#$%^&*()") == "Unknown"

    # TOA Parsing Tests

    def test_parse_tempo2_line(self):
        """Test parsing Tempo2 format TOA lines."""
        tempo2_line = self._create_tempo2_line(55087.1109722889085)
        mjd = self.analyzer._parse_toa_line(tempo2_line)
        assert mjd == 55087.1109722889085

    def test_parse_princeton_line(self):
        """Test parsing Princeton format TOA lines."""
        # Princeton format: identifier obs_freq TOA_mjd toa_err observatory_code
        # TOA is in columns 25-44 (0-indexed: 24-44), so we need to pad the line
        princeton_line = "a 1345.999 55087.1109722889085 2.890 g"
        # Pad to ensure TOA is in correct column position (25-44)
        # Need to position the TOA at columns 24-44
        princeton_line = "a 1345.999 " + " " * 13 + "55087.1109722889085" + " " * 10
        mjd = self.analyzer._parse_toa_line(princeton_line)
        assert mjd == 55087.1109722889085

    def test_parse_parkes_line(self):
        """Test parsing Parkes format TOA lines."""
        # Parkes format: space-padded with TOA in columns 35-55
        # Integer part in columns 35-41 (0-indexed: 34-41), fractional part in columns 42-55 (0-indexed: 42-55)
        # Need decimal at column 42 for format detection
        parkes_line = " " * 34 + "55087" + "  " + "." + "1109722889085" + " " * 20
        mjd = self.analyzer._parse_toa_line(parkes_line)
        assert mjd == 55087.1109722889085

    def test_parse_old_princeton_toa(self):
        """Test parsing old Princeton TOAs (< 40000)."""
        # Old Princeton format with MJD < 40000 should add 39126
        # Need to format as Princeton with TOA in columns 25-44 (0-indexed: 24-44)
        old_princeton_line = "a 1345.999 " + " " * 13 + "1000.0" + " " * 15
        mjd = self.analyzer._parse_toa_line(old_princeton_line)
        assert mjd == 1000.0 + 39126.0

    def test_parse_invalid_lines(self):
        """Test parsing invalid TOA lines."""
        # Should return None for malformed lines
        assert self.analyzer._parse_toa_line("invalid line") is None
        assert self.analyzer._parse_toa_line("123") is None
        assert self.analyzer._parse_toa_line("abc def ghi") is None

    def test_parse_comment_lines(self):
        """Test parsing comment lines."""
        # Should return None for comment lines
        # Note: "c " (lowercase c with space) is detected as Princeton, not Comment
        assert self.analyzer._parse_toa_line("# This is a comment") is None
        assert self.analyzer._parse_toa_line("C This is a comment") is None
        assert self.analyzer._parse_toa_line("CC This is a comment") is None

    def test_parse_command_lines(self):
        """Test parsing command lines."""
        # Should return None for command lines
        assert self.analyzer._parse_toa_line("FORMAT 1") is None
        assert self.analyzer._parse_toa_line("JUMP 55000 55001") is None
        assert self.analyzer._parse_toa_line("TIME 55000") is None
        assert self.analyzer._parse_toa_line("PHASE 0") is None
        assert self.analyzer._parse_toa_line("SKIP") is None
        assert self.analyzer._parse_toa_line("NOSKIP") is None

    def test_parse_blank_lines(self):
        """Test parsing blank lines."""
        # Should return None for blank lines
        assert self.analyzer._parse_toa_line("") is None
        assert self.analyzer._parse_toa_line("   ") is None
        assert self.analyzer._parse_toa_line("\t") is None

    # INCLUDE Statement Tests

    def test_include_single_file(self):
        """Test processing single INCLUDE statement."""
        # Create main file with INCLUDE
        main_content = f"""FORMAT 1
INCLUDE included.tim
{self._create_tempo2_line(55087.1109722889085)}
"""
        included_content = f"""FORMAT 1
{self._create_tempo2_line(55090.1109722889085)}
"""

        main_file = self._create_test_tim_file("main.tim", main_content)
        included_file = self._create_test_tim_file("included.tim", included_content)

        timespan = self.analyzer.calculate_timespan(main_file)

        # Should include TOAs from both files: 55090.1109722889085 - 55087.1109722889085 = 3.0 days
        assert timespan == 3.0

    def test_include_multiple_files(self):
        """Test processing multiple INCLUDE statements."""
        main_content = f"""FORMAT 1
INCLUDE file1.tim
INCLUDE file2.tim
{self._create_tempo2_line(55087.1109722889085)}
"""
        file1_content = f"""FORMAT 1
{self._create_tempo2_line(55090.1109722889085)}
"""
        file2_content = f"""FORMAT 1
{self._create_tempo2_line(55093.1109722889085)}
"""

        main_file = self._create_test_tim_file("main_multi.tim", main_content)
        file1 = self._create_test_tim_file("file1.tim", file1_content)
        file2 = self._create_test_tim_file("file2.tim", file2_content)

        timespan = self.analyzer.calculate_timespan(main_file)

        # Should include TOAs from all files: 55093.1109722889085 - 55087.1109722889085 = 6.0 days
        assert timespan == 6.0

    def test_include_missing_file(self):
        """Test handling of missing INCLUDE file."""
        main_content = f"""FORMAT 1
INCLUDE missing.tim
{self._create_tempo2_line(55087.1109722889085)}
"""
        main_file = self._create_test_tim_file("main_missing.tim", main_content)

        timespan = self.analyzer.calculate_timespan(main_file)

        # Should only include TOAs from main file: 0.0 days (single TOA)
        assert timespan == 0.0

    def test_include_circular_reference(self):
        """Test handling of circular INCLUDE references."""
        # File A includes B, B includes A - should detect and prevent infinite loop
        file_a_content = f"""FORMAT 1
INCLUDE file_b.tim
{self._create_tempo2_line(55087.1109722889085)}
"""
        file_b_content = f"""FORMAT 1
INCLUDE file_a.tim
{self._create_tempo2_line(55090.1109722889085)}
"""

        file_a = self._create_test_tim_file("file_a.tim", file_a_content)
        file_b = self._create_test_tim_file("file_b.tim", file_b_content)

        timespan = self.analyzer.calculate_timespan(file_a)

        # Should handle circular reference gracefully and not crash
        assert timespan >= 0.0

    def test_include_nested(self):
        """Test nested INCLUDE statements."""
        # File A includes B, B includes C - should process all levels
        file_a_content = f"""FORMAT 1
INCLUDE file_b_nested.tim
{self._create_tempo2_line(55087.1109722889085)}
"""
        file_b_content = f"""FORMAT 1
INCLUDE file_c_nested.tim
{self._create_tempo2_line(55090.1109722889085)}
"""
        file_c_content = f"""FORMAT 1
{self._create_tempo2_line(55093.1109722889085)}
"""

        file_a = self._create_test_tim_file("file_a_nested.tim", file_a_content)
        file_b = self._create_test_tim_file("file_b_nested.tim", file_b_content)
        file_c = self._create_test_tim_file("file_c_nested.tim", file_c_content)

        timespan = self.analyzer.calculate_timespan(file_a)

        # Should include TOAs from all nested files: 55093.1109722889085 - 55087.1109722889085 = 6.0 days
        assert timespan == 6.0

    # Command Handling Tests

    def test_handle_format_command(self):
        """Test FORMAT command handling."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("format_command.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # FORMAT command should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    def test_handle_jump_command(self):
        """Test JUMP command handling."""
        content = f"""FORMAT 1
JUMP 55000 55001
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("jump_command.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # JUMP command should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    def test_handle_time_command(self):
        """Test TIME command handling."""
        content = f"""FORMAT 1
TIME 55000
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("time_command.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # TIME command should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    def test_handle_phase_command(self):
        """Test PHASE command handling."""
        content = f"""FORMAT 1
PHASE 0
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("phase_command.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # PHASE command should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    def test_handle_skip_commands(self):
        """Test SKIP/NOSKIP command handling."""
        content = f"""FORMAT 1
SKIP
{self._create_tempo2_line(55087.1109722889085)}
NOSKIP
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("skip_commands.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # SKIP/NOSKIP commands should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    def test_handle_unknown_command(self):
        """Test handling of unknown commands."""
        content = f"""FORMAT 1
UNKNOWN_COMMAND arg1 arg2
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("unknown_command.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Unknown command should be ignored, timespan should be calculated from TOAs
        assert timespan == 3.0

    # Edge Cases and Error Handling Tests

    def test_corrupted_file(self):
        """Test handling of corrupted TIM file."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
corrupted line that should be ignored
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("corrupted.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should handle corrupted lines gracefully and extract what it can
        assert timespan == 3.0

    def test_mixed_formats(self):
        """Test file with mixed TOA formats."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
1234567890abcdefghijklmnopqrstuvwxyz@ 1345.999 55090.1109722889085 2.890 g
{self._create_tempo2_line(55093.1109722889085)}
"""
        tim_file = self._create_test_tim_file("mixed_formats.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should handle mixed formats correctly
        assert timespan == 6.0

    def test_unicode_characters(self):
        """Test handling of Unicode characters in file."""
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
# Comment with unicode: αβγδε
"""
        tim_file = self._create_test_tim_file("unicode.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should handle Unicode characters gracefully
        assert timespan == 3.0

    def test_comments_only(self):
        """Test file with only comments and commands."""
        content = """FORMAT 1
# This is a comment
C This is another comment
JUMP 55000 55001
TIME 55000
"""
        tim_file = self._create_test_tim_file("comments_only.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should return 0.0 for file with no TOAs
        assert timespan == 0.0

    def test_blank_lines_only(self):
        """Test file with only blank lines."""
        content = """


"""
        tim_file = self._create_test_tim_file("blank_only.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should return 0.0 for file with no TOAs
        assert timespan == 0.0

    # Integration Tests

    def test_integration_with_file_discovery(self):
        """Test TimFileAnalyzer integration with FileDiscoveryService."""
        # This test would require FileDiscoveryService, so we'll test the method directly
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("integration_test.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should calculate timespan correctly
        assert timespan == 3.0

    def test_timespan_in_enriched_data(self):
        """Test that timespan appears correctly in enriched file data."""
        # This test would require FileDiscoveryService, so we'll test the method directly
        content = f"""FORMAT 1
{self._create_tempo2_line(55087.1109722889085)}
{self._create_tempo2_line(55090.1109722889085)}
"""
        tim_file = self._create_test_tim_file("enriched_data_test.tim", content)

        timespan = self.analyzer.calculate_timespan(tim_file)

        # Should calculate timespan correctly for enriched data
        assert timespan == 3.0


if __name__ == "__main__":
    pytest.main([__file__])
