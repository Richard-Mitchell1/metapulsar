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
    spin : bool, optional
        Whether to include spin parameters (default: True)
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
        spin=True,
    ):
        super().__init__()

        # Set core timing data
        self._toas = np.asarray(toas)
        self._residuals = np.asarray(residuals)
        self._toaerrs = np.asarray(errors)
        self._freqs = np.asarray(freqs)

        # Convert flags to structured numpy array (Enterprise PR specification)
        if flags is None:
            flags = {}

        # Create structured array from dictionary flags
        if flags:
            self._flags = np.zeros(
                len(self._toas), dtype=[(key, val.dtype) for key, val in flags.items()]
            )
            for key, val in flags.items():
                self._flags[key] = val
        else:
            # Empty structured array with no fields
            self._flags = np.zeros(len(self._toas), dtype=[])

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

        # Set up parameters based on requested components
        self.fitpars = []
        self.setpars = []

        if spin:
            self._setup_spin_parameters()

        if astrometry and ASTROPY_AVAILABLE:
            self._setup_astrometry_parameters()
        elif astrometry and not ASTROPY_AVAILABLE:
            logger.warning(
                "Astrometry requested but astropy not available. Skipping astrometry parameters."
            )

        # Create mock design matrix
        self._create_mock_design_matrix()

        # Set up position and other attributes
        self._pdist = self._get_pdist()
        self._pos = self._get_pos()
        self._planetssb = None
        self._sunssb = None
        self._pos_t = np.tile(self._pos, (len(self._toas), 1))

        # Sort data
        self.sort_data()

    def _setup_spin_parameters(self):
        """Set up spin parameters (F0, F1, F2, etc.)."""
        self.fitpars.extend(["F0", "F1", "F2"])
        self.setpars.extend(["F0", "F1", "F2"])

        # Set default spin values
        self._f0 = 100.0  # Hz
        self._f1 = -1e-15  # Hz/s
        self._f2 = 0.0  # Hz/s^2

    def _setup_astrometry_parameters(self):
        """Set up astrometry parameters for the mock pulsar."""
        if not ASTROPY_AVAILABLE:
            return

        # Add astrometry parameters
        self.fitpars.extend(["RAJ", "DECJ", "PMRA", "PMDEC", "PX"])
        self.setpars.extend(["RAJ", "DECJ", "PMRA", "PMDEC", "PX"])

        # Set default astrometry values
        self._raj = np.random.uniform(0, 2 * np.pi)
        self._decj = np.random.uniform(-np.pi / 2, np.pi / 2)
        self._pmra = 0.0  # rad/yr
        self._pmdec = 0.0  # rad/yr
        self._px = 0.0  # arcsec

        # Create SkyCoord object
        self._pos = SkyCoord(ra=self._raj * u.rad, dec=self._decj * u.rad, frame="icrs")

    def _create_mock_design_matrix(self):
        """Create a mock design matrix for testing."""
        n_toas = len(self._toas)
        n_params = len(self.fitpars)

        # Create design matrix with some realistic structure
        self._designmatrix = np.zeros((n_toas, n_params))

        # Add time-dependent terms for spin parameters
        for i, param in enumerate(self.fitpars):
            if param == "F0":
                # F0 contributes to all residuals equally
                self._designmatrix[:, i] = 1.0
            elif param == "F1":
                # F1 contributes linearly with time
                t_ref = np.mean(self._toas)
                self._designmatrix[:, i] = (
                    self._toas - t_ref
                ) / 86400.0  # Convert to days
            elif param == "F2":
                # F2 contributes quadratically with time
                t_ref = np.mean(self._toas)
                self._designmatrix[:, i] = ((self._toas - t_ref) / 86400.0) ** 2
            elif param in ["RAJ", "DECJ"]:
                # Astrometry parameters contribute with frequency-dependent terms
                self._designmatrix[:, i] = np.sin(
                    2 * np.pi * self._freqs / 1000.0
                )  # Simple frequency dependence
            elif param in ["PMRA", "PMDEC"]:
                # Proper motion contributes linearly with time
                t_ref = np.mean(self._toas)
                self._designmatrix[:, i] = (self._toas - t_ref) / (
                    365.25 * 86400.0
                )  # Convert to years
            elif param == "PX":
                # Parallax contributes with annual modulation
                t_ref = np.mean(self._toas)
                self._designmatrix[:, i] = np.sin(
                    2 * np.pi * (self._toas - t_ref) / (365.25 * 86400.0)
                )

    def set_residuals(self, new_residuals):
        """Set new residuals for the mock pulsar."""
        self._residuals = np.asarray(new_residuals)

    def set_position(self, ra, dec):
        """Set new position for the mock pulsar."""
        self._raj = ra
        self._decj = dec
        if ASTROPY_AVAILABLE:
            self._pos = SkyCoord(
                ra=self._raj * u.rad, dec=self._decj * u.rad, frame="icrs"
            )

    def _get_pdist(self):
        """Get pulsar distance (mock implementation)."""
        return 1.0  # 1 kpc default

    def _get_pos(self):
        """Get pulsar position vector (mock implementation)."""
        if ASTROPY_AVAILABLE and hasattr(self, "_pos"):
            return np.array(
                [
                    self._pos.cartesian.x.value,
                    self._pos.cartesian.y.value,
                    self._pos.cartesian.z.value,
                ]
            )
        else:
            # Simple mock position
            return np.array([1.0, 0.0, 0.0])


def create_mock_pulsar(
    toas,
    residuals,
    errors,
    freqs,
    flags,
    telescope,
    name="mock",
    astrometry=False,
    spin=True,
):
    """Convenience function to create a MockPulsar instance."""
    return MockPulsar(
        toas, residuals, errors, freqs, flags or {}, telescope, name, astrometry, spin
    )
