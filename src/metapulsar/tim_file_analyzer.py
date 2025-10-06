"""TimFileAnalyzer - Fast TIM file analyzer for timespan calculation.

This module provides a lightweight class to quickly extract TOA MJD values
from TIM files using PINT's parsing logic without creating full TOA objects,
which is much faster for timespan calculations.
"""

from pathlib import Path
from typing import List, Set
from loguru import logger

# Import PINT's parsing functions directly
from pint.toa import _parse_TOA_line


class TimFileAnalyzer:
    """Fast TIM file analyzer for timespan calculation.

    This class efficiently extracts TOA MJD values from TIM files using PINT's
    parsing logic without creating full TOA objects, providing both performance
    and robustness for timespan calculations.
    """

    def __init__(self):
        """Initialize the TIM file analyzer."""
        self.logger = logger
        self._processed_files: Set[Path] = set()

    def calculate_timespan(self, tim_file_path: Path) -> float:
        """Calculate timespan from TIM file using PINT's parsing logic.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Timespan in days (max(mjd) - min(mjd))
        """
        try:
            # Reset processed files for each new calculation
            self._processed_files.clear()
            mjd_values = self._extract_mjd_values_recursive(tim_file_path)

            if len(mjd_values) == 0:
                self.logger.warning(f"No TOAs found in {tim_file_path}")
                return 0.0

            # Calculate timespan as max - min (no need to sort)
            timespan = float(max(mjd_values) - min(mjd_values))

            self.logger.debug(
                f"Timespan for {tim_file_path}: {timespan:.1f} days "
                f"({len(mjd_values)} TOAs, range: {min(mjd_values):.1f} to {max(mjd_values):.1f} MJD)"
            )
            return timespan

        except Exception as e:
            self.logger.warning(f"Parsing failed for {tim_file_path}: {e}")
            self.logger.debug(
                "File may contain non-standard TIM format or malformed data"
            )
            return 0.0

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

                    # Use PINT's parsing for both TOA lines and commands
                    try:
                        mjd_tuple, d = _parse_TOA_line(line)
                    except Exception as e:
                        # PINT may fail on malformed lines - skip them gracefully
                        self.logger.debug(
                            f"Skipping malformed line in {tim_file_path}: {line.strip()} - {e}"
                        )
                        continue

                    # Handle commands (especially INCLUDE)
                    if d["format"] == "Command":
                        self._handle_command(d, tim_file_path, mjd_values)
                        continue

                    # Skip non-TOA lines
                    if d["format"] in ("Comment", "Blank", "Unknown"):
                        continue

                    # Extract MJD from TOA line
                    if mjd_tuple is not None:
                        # Convert PINT's (int, float) tuple to float MJD
                        mjd_value = float(mjd_tuple[0]) + float(mjd_tuple[1])
                        mjd_values.append(mjd_value)

        except Exception as e:
            self.logger.error(f"Error reading TIM file {tim_file_path}: {e}")

        return mjd_values

    def _handle_command(
        self, d: dict, current_file: Path, mjd_values: List[float]
    ) -> None:
        """Handle TIM file commands using PINT's parsed command data.

        Args:
            d: Parsed command dictionary from PINT
            current_file: Current TIM file being processed
            mjd_values: List to extend with MJD values from included files
        """
        if d["format"] != "Command":
            return

        cmd = d["Command"][0].upper()

        if cmd == "INCLUDE":
            if len(d["Command"]) < 2:
                self.logger.warning(f"INCLUDE command without filename: {d['Command']}")
                return

            include_file = d["Command"][1]
            include_path = current_file.parent / include_file

            if include_path.exists():
                self.logger.debug(f"Processing included TOA file {include_path}")
                included_mjds = self._extract_mjd_values_recursive(include_path)
                mjd_values.extend(included_mjds)
            else:
                self.logger.warning(f"INCLUDE file not found: {include_path}")
        # Other commands don't affect timespan calculation
