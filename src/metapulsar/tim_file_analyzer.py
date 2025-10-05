"""TimFileAnalyzer - Fast TIM file analyzer for timespan calculation.

This module provides a lightweight class to quickly extract TOA MJD values
from TIM files without loading the full PINT TOAs object, which is much faster
for timespan calculations. Much of the logic is borrowed from PINT for format
detection and command handling.
"""

from pathlib import Path
from typing import List, Set
import re
from loguru import logger


class TimFileAnalyzer:
    """Fast TIM file analyzer for timespan calculation.

    This class efficiently parses TIM files to extract TOA MJD values
    without loading the full PINT TOAs object, making it much faster
    for timespan calculations. Enhanced with PINT's format detection
    and command handling logic.
    """

    def __init__(self):
        """Initialize the TIM file analyzer."""
        self.logger = logger
        self._processed_files: Set[Path] = (
            set()
        )  # Track processed files to avoid infinite recursion

    def calculate_timespan(self, tim_file_path: Path) -> float:
        """Calculate timespan from TIM file.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Timespan in days (max(mjd) - min(mjd))
        """
        try:
            mjd_values = self._extract_mjd_values(tim_file_path)

            if len(mjd_values) == 0:
                self.logger.warning(f"No TOAs found in {tim_file_path}")
                return 0.0

            # Sort MJD values for better debugging
            mjd_values.sort()
            timespan = float(mjd_values[-1] - mjd_values[0])

            self.logger.debug(
                f"Timespan for {tim_file_path}: {timespan:.1f} days "
                f"({len(mjd_values)} TOAs, range: {mjd_values[0]:.1f} to {mjd_values[-1]:.1f} MJD)"
            )
            return timespan

        except Exception as e:
            self.logger.error(f"Could not calculate timespan for {tim_file_path}: {e}")
            return 0.0

    def _extract_mjd_values(self, tim_file_path: Path) -> List[float]:
        """Extract MJD values from TIM file, handling INCLUDE statements.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            List of MJD values from all TOA lines
        """
        # Reset processed files for each new calculation
        self._processed_files.clear()
        return self._extract_mjd_values_recursive(tim_file_path)

    def _toa_format(self, line: str) -> str:
        """Determine the type of a TOA line (borrowed from PINT).

        Args:
            line: Line from TIM file

        Returns:
            Format type: 'Princeton', 'Tempo2', 'Parkes', 'Comment', 'Command', 'Blank', 'Unknown'
        """
        if re.match(r"[0-9a-z@] ", line):
            return "Princeton"
        elif (
            line.startswith("C ")
            or line.startswith("c ")  # This matches Princeton format too!
            or line.startswith("#")
            or line.startswith("CC ")
        ):
            return "Comment"
        elif (
            line.upper()
            .lstrip()
            .startswith(
                (
                    "FORMAT",
                    "JUMP",
                    "TIME",
                    "PHASE",
                    "INCLUDE",
                    "SKIP",
                    "NOSKIP",
                    "END",
                    "INFO",
                    "EMIN",
                    "EMAX",
                    "EQUAD",
                    "FMIN",
                    "FMAX",
                    "EFAC",
                    "PHA1",
                    "PHA2",
                    "MODE",
                )
            )
        ):
            return "Command"
        elif re.match(r"^\s*$", line):
            return "Blank"
        elif re.match(r"^ ", line) and len(line) > 41 and line[41] == ".":
            return "Parkes"
        elif len(line) > 80:
            return "Tempo2"
        else:
            return "Unknown"

    def _extract_mjd_values_recursive(self, tim_file_path: Path) -> List[float]:
        """Recursively extract MJD values from TIM file and included files.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            List of MJD values from all TOA lines
        """
        mjd_values = []

        # Avoid infinite recursion
        if tim_file_path in self._processed_files:
            self.logger.warning(f"Circular INCLUDE detected: {tim_file_path}")
            return mjd_values

        self._processed_files.add(tim_file_path)

        try:
            with open(tim_file_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines
                    if not line:
                        continue

                    # Determine line type using improved format detection
                    fmt = self._toa_format(line)

                    if fmt == "Comment":
                        continue
                    elif fmt == "Blank":
                        continue
                    elif fmt == "Command":
                        # Handle commands (borrowed from PINT)
                        self._handle_command(line, tim_file_path, mjd_values)
                        continue
                    else:
                        # Parse TOA line
                        toa_mjd = self._parse_toa_line(line)
                        if toa_mjd is not None:
                            mjd_values.append(toa_mjd)

        except Exception as e:
            self.logger.error(f"Error reading TIM file {tim_file_path}: {e}")

        return mjd_values

    def _handle_command(
        self, line: str, current_file: Path, mjd_values: List[float]
    ) -> None:
        """Handle TIM file commands (borrowed from PINT).

        Args:
            line: Command line from TIM file
            current_file: Current TIM file being processed
            mjd_values: List to extend with MJD values from included files
        """
        fields = line.split()
        if not fields:
            return

        cmd = fields[0].upper()

        if cmd == "FORMAT":
            # FORMAT 1 means Tempo2 format - no action needed for timespan calculation
            pass
        elif cmd == "JUMP":
            # JUMP commands - just skip for timespan calculation
            pass
        elif cmd == "TIME":
            # TIME commands - just skip for timespan calculation
            pass
        elif cmd == "PHASE":
            # PHASE commands - just skip for timespan calculation
            pass
        elif cmd == "INCLUDE":
            if len(fields) < 2:
                self.logger.warning(f"INCLUDE command without filename: {line}")
                return

            include_file = fields[1]
            include_path = current_file.parent / include_file

            if include_path.exists():
                self.logger.debug(f"Processing included TOA file {include_path}")
                included_mjds = self._extract_mjd_values_recursive(include_path)
                mjd_values.extend(included_mjds)
            else:
                self.logger.warning(f"INCLUDE file not found: {include_path}")
        elif cmd in (
            "SKIP",
            "NOSKIP",
            "END",
            "INFO",
            "EMIN",
            "EMAX",
            "EQUAD",
            "FMIN",
            "FMAX",
            "EFAC",
            "PHA1",
            "PHA2",
            "MODE",
        ):
            # These commands don't affect timespan calculation
            pass
        else:
            self.logger.debug(f"Unknown command: {cmd} in line: {line}")

    def _parse_toa_line(self, line: str) -> float:
        """Parse a TOA line to extract MJD value (improved with PINT logic).

        Args:
            line: TOA line from TIM file

        Returns:
            MJD value as float, or None if parsing fails
        """
        try:
            # Determine format first
            fmt = self._toa_format(line)

            if fmt in ["Comment", "Command", "Blank", "Unknown"]:
                return None

            # Parse based on format
            if fmt == "Tempo2":
                fields = line.split()
                if len(fields) < 4:
                    return None

                # Third field should be the MJD value
                mjd_str = fields[2]
                if "." in mjd_str:
                    ii, ff = mjd_str.split(".")
                    mjd_value = int(ii) + float(f"0.{ff}")
                else:
                    mjd_value = float(mjd_str)

            elif fmt == "Princeton":
                # Princeton format: columns 25-44 contain TOA
                if len(line) < 44:
                    return None
                toa_str = line[24:44].strip()
                if "." not in toa_str:
                    return None
                ii, ff = toa_str.split(".")
                ii = int(ii)
                # Handle old TOAs (before 40000)
                if ii < 40000:
                    ii += 39126
                mjd_value = ii + float(f"0.{ff}")

            elif fmt == "Parkes":
                # Parkes format: columns 35-55 contain TOA
                if len(line) < 55:
                    return None
                ii = line[34:41]
                ff = line[42:55]
                mjd_value = int(ii) + float(f"0.{ff}")

            else:
                return None

            # Basic validation - MJD should be reasonable (after 1950)
            if mjd_value < 30000 or mjd_value > 100000:
                return None

            return mjd_value

        except (ValueError, IndexError) as e:
            self.logger.debug(f"Could not parse TOA line: {line} - {e}")
            return None
