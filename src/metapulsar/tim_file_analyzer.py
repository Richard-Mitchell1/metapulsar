"""TimFileAnalyzer - Fast TIM file analyzer for timespan calculation.

This module provides a lightweight class to quickly extract TOA MJD values
from TIM files using PINT's parsing logic without creating full TOA objects,
which is much faster for timespan calculations.
"""

from pathlib import Path
from typing import List, Set, Dict, Tuple
from loguru import logger

# Import PINT's parsing functions directly
from pint.toa import _parse_TOA_line


class TimFileAnalyzer:
    """Fast TIM file analyzer for timespan calculation.

    This class efficiently extracts TOA MJD values from TIM files using PINT's
    parsing logic without creating full TOA objects, providing both performance
    and robustness for timespan calculations.

    The analyzer caches results per file to avoid duplicate parsing when both
    timespan and TOA count are needed for the same file.
    """

    def __init__(self):
        """Initialize the TIM file analyzer."""
        self.logger = logger
        self._processed_files: Set[Path] = set()
        # Cache for storing timespan and TOA counts per file (not MJD values to save memory)
        self._file_cache: Dict[Path, Tuple[float, int]] = {}

    def _get_timespan_and_count(self, tim_file_path: Path) -> Tuple[float, int]:
        """Get timespan and TOA count from TIM file, using cache if available.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Tuple of (timespan_in_days, toa_count)
        """
        # Check cache first
        if tim_file_path in self._file_cache:
            self.logger.debug(f"Using cached data for {tim_file_path}")
            return self._file_cache[tim_file_path]

        try:
            self._processed_files.clear()
            mjd_values = self._extract_mjd_values_recursive(tim_file_path)
            toa_count = len(mjd_values)

            if toa_count == 0:
                timespan = 0.0
            else:
                # Calculate timespan as max - min (no need to sort)
                timespan = float(max(mjd_values) - min(mjd_values))

            # Cache only the results we need (timespan and count)
            self._file_cache[tim_file_path] = (timespan, toa_count)

            if toa_count > 0:
                self.logger.debug(
                    f"Cached data for {tim_file_path}: {timespan:.1f} days, {toa_count} TOAs"
                )
            else:
                self.logger.debug(f"Cached data for {tim_file_path}: No TOAs found")
            return timespan, toa_count

        except Exception as e:
            self.logger.warning(f"Parsing failed for {tim_file_path}: {e}")
            self.logger.debug(
                "File may contain non-standard TIM format or malformed data"
            )
            # Cache empty result to avoid repeated failures
            empty_result = (0.0, 0)
            self._file_cache[tim_file_path] = empty_result
            return empty_result

    def calculate_timespan(self, tim_file_path: Path) -> float:
        """Calculate timespan from TIM file using PINT's parsing logic.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Timespan in days (max(mjd) - min(mjd))
        """
        timespan, toa_count = self._get_timespan_and_count(tim_file_path)

        if toa_count == 0:
            self.logger.warning(f"No TOAs found in {tim_file_path}")
            return 0.0

        self.logger.debug(
            f"Timespan for {tim_file_path}: {timespan:.1f} days ({toa_count} TOAs)"
        )
        return timespan

    def count_toas(self, tim_file_path: Path) -> int:
        """Count the number of TOAs in a TIM file.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Number of TOAs found in the file
        """
        _, toa_count = self._get_timespan_and_count(tim_file_path)

        self.logger.debug(f"TOA count for {tim_file_path}: {toa_count} TOAs")
        return toa_count

    def clear_cache(self) -> None:
        """Clear the file cache."""
        self._file_cache.clear()
        self.logger.debug("File cache cleared")

    def get_timespan_and_count(self, tim_file_path: Path) -> Tuple[float, int]:
        """Get both timespan and TOA count efficiently using cached data.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Tuple of (timespan_in_days, toa_count)
        """
        timespan, toa_count = self._get_timespan_and_count(tim_file_path)

        if toa_count == 0:
            self.logger.warning(f"No TOAs found in {tim_file_path}")
            return 0.0, 0

        self.logger.debug(
            f"Timespan and count for {tim_file_path}: {timespan:.1f} days, {toa_count} TOAs"
        )
        return timespan, toa_count

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
