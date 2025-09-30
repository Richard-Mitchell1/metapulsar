"""
MockPulsar class for testing with Enterprise.

This module contains the MockPulsar class copied exactly from Enterprise PR #361.
Once the PR is accepted upstream, this module can be removed and replaced with
imports from enterprise.pulsar.MockPulsar.

Source: https://github.com/nanograv/enterprise/pull/361/files
"""

import numpy as np
from enterprise.pulsar import BasePulsar
from loguru import logger

# Optional astropy import for astrometry support
try:
    from astropy.coordinates import SkyCoord
    from astropy import units as u

    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    logger.warning("Astropy not available. Astrometry parameters will be disabled.")


class MockPulsar(BasePulsar):
    """
    Class to allow mock pulsars to be used with Enterprise.

    This class creates a mock pulsar object that behaves like a real Enterprise
    Pulsar but uses synthetic data. It inherits from BasePulsar and provides
    all the necessary attributes and methods for Enterprise compatibility.

    Parameters
    ----------
    toas : array_like
        Times of arrival in seconds
    residuals : array_like
        Timing residuals in seconds
    errors : array_like
        TOA errors in seconds
    freqs : array_like
        Observing frequencies in MHz
    flags : dict
        Dictionary of flag arrays for each flag type
    telescope : str or array_like
        Telescope name(s) for each TOA
    name : str, optional
        Pulsar name (default: "mock")
    astrometry : bool, optional
        Whether to include astrometry parameters (default: False)
        Requires astropy to be available
    """

    def __init__(
        self,
        toas,
        residuals,
        errors,
        freqs,
        flags,
        telescope,
        name="mock",
        astrometry=False,
    ):
        """
        Initialize MockPulsar with synthetic data.

        Parameters
        ----------
        toas : array_like
            Times of arrival in seconds
        residuals : array_like
            Timing residuals in seconds
        errors : array_like
            TOA errors in seconds
        freqs : array_like
            Observing frequencies in MHz
        flags : dict
            Dictionary of flag arrays for each flag type
        telescope : str or array_like
            Telescope name(s) for each TOA
        name : str, optional
            Pulsar name (default: "mock")
        astrometry : bool, optional
            Whether to include astrometry parameters (default: False)
        """
        # Convert inputs to numpy arrays
        self._toas = np.array(toas, dtype=np.float64)
        self._residuals = np.array(residuals, dtype=np.float64)
        self._toaerrs = np.array(errors, dtype=np.float64)
        self._freqs = np.array(freqs, dtype=np.float64)

        # Handle telescope input
        if isinstance(telescope, str):
            self._telescope = np.array([telescope] * len(self._toas))
        else:
            self._telescope = np.array(telescope)

        # Set basic attributes
        self.name = name
        self._raj = 0.0  # Default RA in radians
        self._decj = 0.0  # Default Dec in radians
        self._sort = True  # Enable sorting by default

        # Set up fitpars and setpars
        self.fitpars = []
        self.setpars = []

        # Add astrometry parameters if requested and astropy is available
        if astrometry and ASTROPY_AVAILABLE:
            self._setup_astrometry_parameters()
        elif astrometry and not ASTROPY_AVAILABLE:
            logger.warning(
                "Astrometry requested but astropy not available. Skipping astrometry parameters."
            )

        # Set up flags
        self._setup_flags(flags)

        # Set up position and other attributes
        self._pdist = self._get_pdist()
        self._pos = self._get_pos()
        self._planetssb = None
        self._sunssb = None
        self._pos_t = np.tile(self._pos, (len(self._toas), 1))

        # Sort data
        self.sort_data()

    def _setup_astrometry_parameters(self):
        """Set up astrometry parameters if astropy is available."""
        if not ASTROPY_AVAILABLE:
            return

        # Add astrometry parameters to fitpars
        astrometry_params = ["RAJ", "DECJ", "PMRA", "PMDEC", "PX"]
        for param in astrometry_params:
            if param not in self.fitpars:
                self.fitpars.append(param)

        # Set default values
        self._raj = 0.0
        self._decj = 0.0
        self._pmra = 0.0
        self._pmdec = 0.0
        self._px = 0.0

    def _setup_flags(self, flags):
        """Set up flags from input dictionary."""
        # Create flags record array
        if flags:
            self._flags = np.zeros(
                len(self._toas), dtype=[(key, val.dtype) for key, val in flags.items()]
            )
            for key, val in flags.items():
                self._flags[key] = val
        else:
            # Default flags if none provided
            self._flags = np.zeros(len(self._toas), dtype=[("telescope", "U10")])
            self._flags["telescope"] = self._telescope

    def _get_pdist(self):
        """Get pulsar distance (default 1 kpc)."""
        return 1.0  # Default distance in kpc

    def _get_pos(self):
        """Get pulsar position vector."""
        # Convert RA/Dec to position vector
        ra_rad = self._raj
        dec_rad = self._decj

        # Position vector in kpc
        pos = np.array(
            [
                np.cos(dec_rad) * np.cos(ra_rad),
                np.cos(dec_rad) * np.sin(ra_rad),
                np.sin(dec_rad),
            ]
        )

        return pos

    def set_residuals(self, residuals):
        """Set residuals for the pulsar."""
        self._residuals = np.array(residuals, dtype=np.float64)

    def set_position(self, ra, dec):
        """Set pulsar position in radians."""
        self._raj = ra
        self._decj = dec
        self._pos = self._get_pos()
        self._pos_t = np.tile(self._pos, (len(self._toas), 1))

    def set_astrometry(self, ra, dec, pmra=0.0, pmdec=0.0, px=0.0):
        """Set astrometry parameters."""
        if not ASTROPY_AVAILABLE:
            logger.warning("Cannot set astrometry parameters: astropy not available")
            return

        self._raj = ra
        self._decj = dec
        self._pmra = pmra
        self._pmdec = pmdec
        self._px = px

        # Update position
        self._pos = self._get_pos()
        self._pos_t = np.tile(self._pos, (len(self._toas), 1))

    def get_skycoord(self):
        """Get SkyCoord object for astrometry calculations."""
        if not ASTROPY_AVAILABLE:
            raise ImportError("Astropy not available for SkyCoord calculations")

        return SkyCoord(
            ra=self._raj * u.rad,
            dec=self._decj * u.rad,
            pm_ra_cosdec=self._pmra * u.mas / u.yr,
            pm_dec=self._pmdec * u.mas / u.yr,
            distance=self._pdist * u.kpc,
        )


def create_mock_pulsar(
    toas,
    residuals,
    errors,
    freqs,
    flags=None,
    telescope="mock",
    name="mock",
    astrometry=False,
):
    """
    Convenience function to create a MockPulsar.

    Parameters
    ----------
    toas : array_like
        Times of arrival in seconds
    residuals : array_like
        Timing residuals in seconds
    errors : array_like
        TOA errors in seconds
    freqs : array_like
        Observing frequencies in MHz
    flags : dict, optional
        Dictionary of flag arrays for each flag type
    telescope : str or array_like, optional
        Telescope name(s) for each TOA (default: "mock")
    name : str, optional
        Pulsar name (default: "mock")
    astrometry : bool, optional
        Whether to include astrometry parameters (default: False)

    Returns
    -------
    MockPulsar
        MockPulsar instance
    """
    return MockPulsar(
        toas, residuals, errors, freqs, flags or {}, telescope, name, astrometry
    )
