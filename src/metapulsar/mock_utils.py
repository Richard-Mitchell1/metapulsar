"""
Utility functions for MockPulsar support.

This module contains utility functions copied exactly from Enterprise PR #361.
Once the PR is accepted upstream, this module can be removed and replaced with
imports from enterprise.signals.utils.

Source: https://github.com/nanograv/enterprise/pull/361/files
"""

import numpy as np
from loguru import logger

# Optional astropy import for astrometry support
try:
    from astropy.coordinates import SkyCoord
    from astropy import units as u

    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False


def create_astrometry_model(ra, dec, pmra=0.0, pmdec=0.0, px=0.0):
    """
    Create a simple astrometry model for MockPulsar.

    Parameters
    ----------
    ra : float
        Right ascension in radians
    dec : float
        Declination in radians
    pmra : float, optional
        Proper motion in RA (mas/yr) (default: 0.0)
    pmdec : float, optional
        Proper motion in Dec (mas/yr) (default: 0.0)
    px : float, optional
        Parallax (mas) (default: 0.0)

    Returns
    -------
    dict
        Dictionary containing astrometry parameters
    """
    if not ASTROPY_AVAILABLE:
        logger.warning("Astropy not available for astrometry model creation")
        return {}

    # Convert to SkyCoord for validation
    try:
        skycoord = SkyCoord(
            ra=ra * u.rad,
            dec=dec * u.rad,
            pm_ra_cosdec=pmra * u.mas / u.yr,
            pm_dec=pmdec * u.mas / u.yr,
            distance=1.0 * u.kpc,
        )  # Default distance

        return {
            "RAJ": ra,
            "DECJ": dec,
            "PMRA": pmra,
            "PMDEC": pmdec,
            "PX": px,
            "skycoord": skycoord,
        }
    except Exception as e:
        logger.error(f"Failed to create astrometry model: {e}")
        return {}


def convert_astrometry_units(params, from_units="rad", to_units="deg"):
    """
    Convert astrometry parameters between units.

    Parameters
    ----------
    params : dict
        Dictionary containing astrometry parameters
    from_units : str, optional
        Input units ('rad' or 'deg') (default: 'rad')
    to_units : str, optional
        Output units ('rad' or 'deg') (default: 'deg')

    Returns
    -------
    dict
        Dictionary with converted parameters
    """
    if from_units == to_units:
        return params.copy()

    converted = params.copy()

    # Conversion factors
    if from_units == "rad" and to_units == "deg":
        factor = 180.0 / np.pi
    elif from_units == "deg" and to_units == "rad":
        factor = np.pi / 180.0
    else:
        logger.warning(f"Unknown unit conversion: {from_units} to {to_units}")
        return params

    # Convert RA and Dec
    if "RAJ" in converted:
        converted["RAJ"] *= factor
    if "DECJ" in converted:
        converted["DECJ"] *= factor

    return converted


def create_mock_flags(n_toas, telescope="mock", backend="mock", **kwargs):
    """
    Create mock flags for MockPulsar.

    Parameters
    ----------
    n_toas : int
        Number of TOAs
    telescope : str, optional
        Telescope name (default: "mock")
    backend : str, optional
        Backend name (default: "mock")
    **kwargs
        Additional flag arrays

    Returns
    -------
    dict
        Dictionary of flag arrays
    """
    flags = {
        "telescope": np.array([telescope] * n_toas),
        "backend": np.array([backend] * n_toas),
    }

    # Add any additional flags
    for key, value in kwargs.items():
        if isinstance(value, (list, np.ndarray)):
            if len(value) == n_toas:
                flags[key] = np.array(value)
            else:
                logger.warning(
                    f"Flag {key} length {len(value)} doesn't match n_toas {n_toas}"
                )
        else:
            flags[key] = np.array([value] * n_toas)

    return flags


def create_mock_timing_data(
    n_toas,
    toa_range=(50000, 60000),
    residual_std=1e-6,
    error_std=1e-7,
    freq_range=(100, 2000),
):
    """
    Create mock timing data for testing.

    Parameters
    ----------
    n_toas : int
        Number of TOAs to generate
    toa_range : tuple, optional
        TOA range in MJD (default: (50000, 60000))
    residual_std : float, optional
        Standard deviation for residuals in seconds (default: 1e-6)
    error_std : float, optional
        Standard deviation for errors in seconds (default: 1e-7)
    freq_range : tuple, optional
        Frequency range in MHz (default: (100, 2000))

    Returns
    -------
    tuple
        (toas, residuals, errors, freqs) arrays
    """
    # Generate random TOAs
    toas = np.random.uniform(toa_range[0], toa_range[1], n_toas)
    toas = np.sort(toas)  # Sort by time

    # Convert to seconds (MJD to seconds since epoch)
    toas = (toas - 50000) * 86400  # Approximate conversion

    # Generate residuals (white noise)
    residuals = np.random.normal(0, residual_std, n_toas)

    # Generate errors (white noise)
    errors = np.abs(np.random.normal(error_std, error_std * 0.1, n_toas))

    # Generate frequencies
    freqs = np.random.uniform(freq_range[0], freq_range[1], n_toas)

    return toas, residuals, errors, freqs


def validate_mock_pulsar_data(toas, residuals, errors, freqs, flags=None):
    """
    Validate mock pulsar data for consistency.

    Parameters
    ----------
    toas : array_like
        Times of arrival
    residuals : array_like
        Timing residuals
    errors : array_like
        TOA errors
    freqs : array_like
        Observing frequencies
    flags : dict, optional
        Flag arrays

    Returns
    -------
    bool
        True if data is valid
    """
    n_toas = len(toas)

    # Check array lengths
    if len(residuals) != n_toas:
        logger.error(f"Residuals length {len(residuals)} != TOAs length {n_toas}")
        return False

    if len(errors) != n_toas:
        logger.error(f"Errors length {len(errors)} != TOAs length {n_toas}")
        return False

    if len(freqs) != n_toas:
        logger.error(f"Frequencies length {len(freqs)} != TOAs length {n_toas}")
        return False

    # Check flags if provided
    if flags:
        for key, value in flags.items():
            if len(value) != n_toas:
                logger.error(f"Flag {key} length {len(value)} != TOAs length {n_toas}")
                return False

    # Check for valid values
    if np.any(np.isnan(toas)) or np.any(np.isinf(toas)):
        logger.error("Invalid TOAs (NaN or Inf)")
        return False

    if np.any(np.isnan(residuals)) or np.any(np.isinf(residuals)):
        logger.error("Invalid residuals (NaN or Inf)")
        return False

    if np.any(errors <= 0):
        logger.error("Non-positive errors found")
        return False

    if np.any(freqs <= 0):
        logger.error("Non-positive frequencies found")
        return False

    return True
