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

        # Enterprise compatibility attributes
        self._stoas = self._toas  # Enterprise expects _stoas
        self._isort = np.arange(len(self._toas))  # Default sort order

        # Set up parameters based on requested components
        self.fitpars = []
        self.setpars = []

        # Add Offset parameter (Enterprise standard - always first)
        self.fitpars.append("Offset")
        self.setpars.append("Offset")

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

        # Set default astrometry values (fixed coordinates)
        self._raj = np.pi / 4  # 45 degrees in radians
        self._decj = np.pi / 4  # 45 degrees in radians
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

        # Add time-dependent terms for parameters
        for i, param in enumerate(self.fitpars):
            if param == "Offset":
                # Offset contributes to all residuals equally (all 1s)
                self._designmatrix[:, i] = 1.0
            elif param == "F0":
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

    @property
    def toas(self):
        """Return TOAs in MJD (Enterprise compatibility)."""
        return self._toas

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


class MockParameter:
    """Mock parameter object with .val and .err attributes for libstempo compatibility."""

    def __init__(self, value, error=0.0):
        """Initialize mock parameter.

        Args:
            value: Parameter value
            error: Parameter error (default: 0.0)
        """
        self.val = value
        self.err = error


class LibstempoMockPulsarAdapter:
    """Adapter to make MockPulsar look like libstempo.tempopulsar.

    This class provides the libstempo.tempopulsar interface that Tempo2Pulsar
    expects, allowing MockPulsar to be used as a raw timing object in tests.

    Parameters
    ----------
    mock_pulsar : MockPulsar
        The MockPulsar instance to wrap
    """

    def __init__(self, mock_pulsar: MockPulsar):
        """Initialize the adapter.

        Args:
            mock_pulsar: MockPulsar instance to wrap
        """
        self._mock = mock_pulsar

    # Core data methods (libstempo interface)
    def toas(self):
        """Return TOAs in MJD (converted from seconds)."""
        # Convert seconds to days using astropy units
        toas_days = (self._mock._toas * u.s).to(u.day).value
        return toas_days

    @property
    def stoas(self):
        """Return station TOAs in MJD (same as toas for mock data)."""
        # Convert seconds to days using astropy units
        stoas_days = (self._mock._toas * u.s).to(u.day).value
        return stoas_days

    def residuals(self):
        """Return timing residuals in seconds."""
        return self._mock._residuals

    @property
    def toaerrs(self):
        """Return TOA errors in microseconds."""
        # Convert seconds to microseconds using astropy units
        toaerrs_us = (self._mock._toaerrs * u.s).to(u.us).value
        return toaerrs_us

    def designmatrix(self):
        """Return design matrix for parameter fitting (libstempo includes Offset column)."""
        # MockPulsar now has Offset as first column, but libstempo quirk:
        # - designmatrix() includes Offset column (first column)
        # - pars() does NOT include Offset in parameter list
        # So we need to return the design matrix as-is (with Offset column)
        return self._mock._designmatrix

    def ssbfreqs(self):
        """Return SSB frequencies in Hz."""
        # Convert MHz to Hz using astropy units
        freqs_hz = (self._mock._freqs * u.MHz).to(u.Hz).value
        return freqs_hz

    def telescope(self):
        """Return telescope names as bytes."""
        return self._mock._telescope.astype("S")

    # Parameter management (libstempo interface)
    def pars(self, which="fit"):
        """Return parameter names as libstempo would (libstempo does NOT include Offset)."""
        if which == "fit":
            # libstempo pars() does NOT include Offset, so exclude it
            return tuple([p for p in self._mock.fitpars if p != "Offset"])
        else:  # set
            return tuple([p for p in self._mock.setpars if p != "Offset"])

    def __getitem__(self, param_name):
        """Get parameter value (dict-like access).

        Args:
            param_name: Parameter name

        Returns:
            MockParameter object with .val and .err attributes
        """
        # Map common parameter names to MockPulsar attributes
        param_mapping = {
            "RAJ": "_raj",
            "DECJ": "_decj",
            "F0": "_f0",
            "F1": "_f1",
            "F2": "_f2",
            "PMRA": "_pmra",
            "PMDEC": "_pmdec",
            "PX": "_px",
            "DM": "_dm",
        }

        attr_name = param_mapping.get(param_name, f"_{param_name.lower()}")
        value = getattr(self._mock, attr_name, 0.0)
        error = 0.0  # Mock data has no errors

        return MockParameter(value, error)

    # Flag system (libstempo interface)
    def flags(self):
        """Return list of flag names."""
        if self._mock._flags.dtype.names:
            return list(self._mock._flags.dtype.names)
        return []

    def flagvals(self, key):
        """Return flag values for specific key.

        Args:
            key: Flag name

        Returns:
            Array of flag values
        """
        return self._mock._flags[key]

    # Position and astrometry (libstempo interface)
    @property
    def psrPos(self):
        """Return pulsar position vectors over time."""
        return self._mock._pos_t

    @property
    def name(self):
        """Return pulsar name."""
        return getattr(self._mock, "name", None)

    # Planetary data (mock implementations)
    def formbats(self):
        """Form barycentric arrival times (no-op for mock)."""
        pass

    @property
    def mercury_ssb(self):
        """Return Mercury position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def venus_ssb(self):
        """Return Venus position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def earth_ssb(self):
        """Return Earth position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def mars_ssb(self):
        """Return Mars position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def jupiter_ssb(self):
        """Return Jupiter position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def saturn_ssb(self):
        """Return Saturn position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def uranus_ssb(self):
        """Return Uranus position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def neptune_ssb(self):
        """Return Neptune position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def pluto_ssb(self):
        """Return Pluto position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))

    @property
    def sun_ssb(self):
        """Return Sun position vectors (mock data)."""
        return np.zeros((len(self._mock._toas), 6))


def create_libstempo_adapter(mock_pulsar: MockPulsar) -> LibstempoMockPulsarAdapter:
    """Create a libstempo adapter for MockPulsar.

    Args:
        mock_pulsar: MockPulsar instance to wrap

    Returns:
        LibstempoMockPulsarAdapter instance
    """
    return LibstempoMockPulsarAdapter(mock_pulsar)
