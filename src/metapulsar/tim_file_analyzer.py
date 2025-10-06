"""TimFileAnalyzer - Fast TIM file analyzer for timespan calculation.

This module provides a lightweight class to quickly extract TOA MJD values
from TIM files without loading the full PINT TOAs object, which is much faster
for timespan calculations.
"""

from pathlib import Path
from loguru import logger

from pint.toa import read_toa_file


class TimFileAnalyzer:
    """Fast TIM file analyzer for timespan calculation.

    This class efficiently extracts TOA MJD values from TIM files using PINT's
    robust parsing infrastructure while avoiding the performance overhead of
    creating full TOAs objects.
    """

    def __init__(self):
        """Initialize the TIM file analyzer."""
        self.logger = logger

    def calculate_timespan(self, tim_file_path: Path) -> float:
        """Calculate timespan from TIM file using PINT's parsing infrastructure.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Timespan in days (max(mjd) - min(mjd))
        """
        try:
            # Use PINT's read_toa_file to handle all complexity (INCLUDE, commands, etc.)
            toas, _ = read_toa_file(str(tim_file_path), process_includes=True)

            if len(toas) == 0:
                self.logger.warning(f"No TOAs found in {tim_file_path}")
                return 0.0

            # Extract MJD values from TOA objects (much faster than creating TOAs object)
            mjd_values = [float(toa.mjd.mjd) for toa in toas]

            # Calculate timespan as max - min (no need to sort)
            timespan = float(max(mjd_values) - min(mjd_values))

            self.logger.debug(
                f"Timespan for {tim_file_path}: {timespan:.1f} days "
                f"({len(mjd_values)} TOAs, range: {min(mjd_values):.1f} to {max(mjd_values):.1f} MJD)"
            )
            return timespan

        except Exception as e:
            # PINT may fail on malformed TIM files (e.g., non-standard comment lines)
            # Log the error but don't crash - return 0.0 to indicate parsing failure
            self.logger.warning(f"PINT parsing failed for {tim_file_path}: {e}")
            self.logger.debug(
                "File may contain non-standard TIM format or malformed data"
            )
            return 0.0
