"""
Position helpers for pulsar coordinate conversion and B/J-name generation.

This module provides robust coordinate conversion between different pulsar object
types (PINT TimingModel, libstempo tempopulsar, Enterprise Pulsar) and generates
canonical B-names (BHHMM±DD) or J-names (JHHMM±DDMM) from actual coordinate data.

Functions:
    bj_name_from_pulsar: Generate B-name or J-name from any supported pulsar object
    _skycoord_from_pint_model: Extract coordinates from PINT TimingModel
    _skycoord_from_libstempo: Extract coordinates from libstempo tempopulsar
    _skycoord_from_enterprise: Extract coordinates from Enterprise Pulsar
    _format_j_name_from_icrs: Format ICRS coordinates into J-name string
    _format_b_name_from_icrs: Format ICRS coordinates into B-name string
"""

from typing import Any, Dict, Optional, Tuple, List
import numpy as np
from astropy.coordinates import (
    SkyCoord,
    ICRS,
    FK4,
    Angle,
    GeocentricTrueEcliptic,
    BarycentricTrueEcliptic,
)
from astropy.time import Time
import astropy.units as u
from loguru import logger
from io import StringIO

# Import PINT utilities for robust parfile parsing
from pint.models.model_builder import parse_parfile


def _format_j_name_from_icrs(c: SkyCoord) -> str:
    """Format ICRS coordinates into a JHHMM±DDMM label using TRUNCATION."""
    # RA
    ra_h = c.ra.to(u.hourangle).value
    hh = int(np.floor(ra_h)) % 24
    mm = int((ra_h - hh) * 60.0)  # truncate minutes

    # Dec
    dec_deg = c.dec.to(u.deg).value
    sign = "-" if dec_deg < 0 else "+"
    a = abs(dec_deg)
    DD = int(np.floor(a))
    MM = int((a - DD) * 60.0)  # truncate arcminutes

    return f"J{hh:02d}{mm:02d}{sign}{DD:02d}{MM:02d}"


def _format_b_name_from_icrs(c: SkyCoord) -> str:
    """Format ICRS coordinates into a B1234±56 label using TRUNCATION."""
    # RA
    ra_h = c.ra.to(u.hourangle).value
    hh = int(np.floor(ra_h)) % 24
    mm = int((ra_h - hh) * 60.0)  # truncate minutes

    # Dec
    dec_deg = c.dec.to(u.deg).value
    sign = "-" if dec_deg < 0 else "+"
    a = abs(dec_deg)
    DD = int(np.floor(a))

    return f"B{hh:02d}{mm:02d}{sign}{DD:02d}"


def _skycoord_from_pint_model(model: Any) -> SkyCoord:
    """
    Build a SkyCoord from a PINT TimingModel.

    Tries multiple coordinate systems in order of preference:
    1. Direct equatorial (RAJ/DECJ) - preferred
    2. Ecliptic coordinates (LAMBDA/BETA or ELONG/ELAT)
    3. FK4/B1950 coordinates (RA/DEC) - legacy fallback

    Args:
        model: PINT TimingModel object

    Returns:
        SkyCoord object in ICRS frame

    Raises:
        ValueError: If no valid coordinates found
    """
    # Direct equatorial coordinates (preferred method)
    if (
        hasattr(model, "RAJ")
        and hasattr(model, "DECJ")
        and model.RAJ.value is not None
        and model.DECJ.value is not None
    ):
        ra = Angle(model.RAJ.quantity).to(u.hourangle)
        dec = Angle(model.DECJ.quantity).to(u.deg)
        return SkyCoord(ra=ra, dec=dec, frame=ICRS())

    # Ecliptic coordinates (LAMBDA/BETA or ELONG/ELAT)
    # Try BarycentricTrueEcliptic first; fall back to GeocentricTrueEcliptic
    for ecl_frame in (BarycentricTrueEcliptic, GeocentricTrueEcliptic):
        if (
            hasattr(model, "LAMBDA")
            and hasattr(model, "BETA")
            and model.LAMBDA.value is not None
            and model.BETA.value is not None
        ):
            lam = Angle(model.LAMBDA.quantity).to(u.deg)
            bet = Angle(model.BETA.quantity).to(u.deg)
            c = SkyCoord(
                lon=lam,
                lat=bet,
                distance=1 * u.pc,
                frame=ecl_frame(equinox=Time("J2000")),
            )
            return c.transform_to(ICRS())

        if (
            hasattr(model, "ELONG")
            and hasattr(model, "ELAT")
            and model.ELONG.value is not None
            and model.ELAT.value is not None
        ):
            lam = Angle(model.ELONG.quantity).to(u.deg)
            bet = Angle(model.ELAT.quantity).to(u.deg)
            c = SkyCoord(
                lon=lam,
                lat=bet,
                distance=1 * u.pc,
                frame=ecl_frame(equinox=Time("J2000")),
            )
            return c.transform_to(ICRS())

    # Legacy FK4/B1950 coordinates (rare fallback)
    if (
        hasattr(model, "RA")
        and hasattr(model, "DEC")
        and model.RA.value is not None
        and model.DEC.value is not None
    ):
        ra = Angle(model.RA.quantity).to(u.hourangle)
        dec = Angle(model.DEC.quantity).to(u.deg)
        c_fk4 = SkyCoord(ra=ra, dec=dec, frame=FK4(equinox=Time("B1950")))
        return c_fk4.transform_to(ICRS())

    raise ValueError("Could not derive coordinates from PINT TimingModel.")


def _skycoord_from_libstempo(psr: Any) -> SkyCoord:
    """
    Build a SkyCoord from a libstempo tempopulsar.

    Tries multiple coordinate systems in order of preference:
    1. Direct equatorial (RAJ/DECJ) - preferred
    2. Ecliptic coordinates (LAMBDA/BETA or ELONG/ELAT)
    3. FK4/B1950 coordinates (RA/DEC) - legacy fallback

    Args:
        psr: libstempo tempopulsar object with parameter access

    Returns:
        SkyCoord object in ICRS frame

    Raises:
        ValueError: If no valid coordinates found
    """

    # Helper to fetch parameter safely
    def _val(name):
        # libstempo exposes parameters via dict-like access; .val gives float
        try:
            return psr[name].val
        except Exception:
            return None

    raj = _val("RAJ")
    decj = _val("DECJ")
    if raj is not None and decj is not None:
        return SkyCoord(ra=raj * u.rad, dec=decj * u.rad, frame=ICRS())

    # Ecliptic variants (in radians)
    lam = _val("LAMBDA") or _val("ELONG")
    bet = _val("BETA") or _val("ELAT")
    if lam is not None and bet is not None:
        c = SkyCoord(
            lon=lam * u.rad,
            lat=bet * u.rad,
            distance=1 * u.pc,
            frame=BarycentricTrueEcliptic(equinox=Time("J2000")),
        )
        return c.transform_to(ICRS())

    # FK4 B1950 fallback (rare)
    ra_b = _val("RA")
    dec_b = _val("DEC")
    if ra_b is not None and dec_b is not None:
        c_fk4 = SkyCoord(
            ra=ra_b * u.rad, dec=dec_b * u.rad, frame=FK4(equinox=Time("B1950"))
        )
        return c_fk4.transform_to(ICRS())

    raise ValueError("Could not derive coordinates from libstempo tempopulsar.")


def _skycoord_from_enterprise(psr: Any) -> SkyCoord:
    """
    Build a SkyCoord from an Enterprise Pulsar (PintPulsar or Tempo2Pulsar).

    Uses internal _raj/_decj attributes stored in radians (ICRS-equivalent).

    Args:
        psr: Enterprise Pulsar object with _raj/_decj attributes

    Returns:
        SkyCoord object in ICRS frame

    Raises:
        ValueError: If _raj/_decj attributes not found
    """
    if hasattr(psr, "_raj") and hasattr(psr, "_decj"):
        return SkyCoord(ra=psr._raj * u.rad, dec=psr._decj * u.rad, frame=ICRS())
    raise ValueError("Enterprise pulsar lacks _raj/_decj.")


def bj_name_from_pulsar(psr_obj: Any, name_type: str = "J") -> str:
    """
    Generate canonical B-name or J-name from pulsar object coordinates.

    Supports multiple pulsar object types:
    - PINT TimingModel
    - PINT tuple (model, toas) - uses the model
    - libstempo tempopulsar
    - Enterprise Pulsar (PintPulsar or Tempo2Pulsar)

    Args:
        psr_obj: Pulsar object with coordinate information
        name_type: "J" for J-name (JHHMM±DDMM) or "B" for B-name (BHHMM±DD)

    Returns:
        Canonical name string (e.g., "J1857+0943" or "B1857+09")

    Raises:
        ValueError: If coordinates cannot be extracted from object or invalid name_type
    """
    # Validate name_type
    if name_type.upper() not in ["J", "B"]:
        raise ValueError(f"Invalid name_type '{name_type}'. Must be 'J' or 'B'")

    # Handle PINT tuple (model, toas) - extract the model
    if isinstance(psr_obj, tuple) and len(psr_obj) == 2:
        psr_obj = psr_obj[0]  # Use the model from the tuple

    # Try enterprise first (common in your MetaPulsar flow)
    try:
        c = _skycoord_from_enterprise(psr_obj)
    except Exception:
        # Try PINT TimingModel
        try:
            c = _skycoord_from_pint_model(psr_obj)
        except Exception:
            # Try libstempo tempopulsar
            c = _skycoord_from_libstempo(psr_obj)

    # Ensure we're in ICRS (if any upstream gave a different frame)
    c_icrs = c.transform_to(ICRS())

    if name_type.upper() == "B":
        # B-names should be based on FK4 B1950 coordinates, not ICRS
        c_fk4 = c_icrs.transform_to(FK4(equinox=Time("B1950")))
        return _format_b_name_from_icrs(c_fk4)
    else:
        return _format_j_name_from_icrs(c_icrs)


# ============================================================================
# OPTIMIZED COORDINATE EXTRACTION FUNCTIONS
# ============================================================================


def _parse_parfile_optimized(parfile_content: str) -> Dict[str, str]:
    """Parse parfile content using PINT's robust parser."""
    parfile_dict = parse_parfile(StringIO(parfile_content))
    # Convert defaultdict(list) to dict with first values for compatibility
    # Also split on whitespace to get only the first value (before uncertainty columns)
    result = {}
    for k, v in parfile_dict.items():
        if v:
            # Take first value and split to get only the parameter value (not uncertainty)
            first_value = v[0].split()[0] if v[0].split() else ""
            result[k] = first_value
        else:
            result[k] = ""
    return result


def _parse_ra_string_optimized(ra_str: str) -> Optional[float]:
    """Parse RA string using Astropy's Angle parsing."""
    try:
        angle = Angle(ra_str, unit=u.hourangle)
        return angle.to(u.hourangle).value
    except Exception:
        return None


def _parse_dec_string_optimized(dec_str: str) -> Optional[float]:
    """Parse DEC string using Astropy's Angle parsing."""
    try:
        angle = Angle(dec_str, unit=u.deg)
        return angle.to(u.deg).value
    except Exception:
        return None


def _parse_angle_string_optimized(angle_str: str) -> Optional[float]:
    """Parse angle string using Astropy's Angle parsing."""
    try:
        angle = Angle(angle_str, unit=u.deg)
        return angle.to(u.deg).value
    except Exception:
        return None


def _extract_equatorial_coordinates_optimized(
    parfile_dict: Dict[str, str],
) -> Tuple[Optional[float], Optional[float]]:
    """Extract RAJ/DECJ coordinates (optimized version)."""
    try:
        # Try RAJ/DECJ first, then RA/DEC aliases
        raj = parfile_dict.get("RAJ") or parfile_dict.get("RA")
        decj = parfile_dict.get("DECJ") or parfile_dict.get("DEC")

        if not raj or not decj:
            return None, None

        # Parse RA (format: HH:MM:SS.SSSS or HH:MM:SS)
        ra_hours = _parse_ra_string_optimized(raj)
        if ra_hours is None:
            return None, None

        # Parse DEC (format: ±DD:MM:SS.SSSS or ±DD:MM:SS)
        dec_deg = _parse_dec_string_optimized(decj)
        if dec_deg is None:
            return None, None

        return ra_hours, dec_deg

    except Exception:
        return None, None


def _extract_ecliptic_coordinates_optimized(
    parfile_dict: Dict[str, str],
) -> Tuple[Optional[float], Optional[float]]:
    """Extract ecliptic coordinates and convert to equatorial (optimized version)."""
    try:
        # Try LAMBDA/BETA first, then ELONG/ELAT aliases
        lam = parfile_dict.get("LAMBDA") or parfile_dict.get("ELONG")
        bet = parfile_dict.get("BETA") or parfile_dict.get("ELAT")

        if not lam or not bet:
            return None, None

        # Parse ecliptic coordinates
        lam_deg = _parse_angle_string_optimized(lam)
        bet_deg = _parse_angle_string_optimized(bet)

        if lam_deg is None or bet_deg is None:
            return None, None

        # Convert ecliptic to equatorial
        c_ecl = SkyCoord(
            lon=lam_deg * u.deg,
            lat=bet_deg * u.deg,
            distance=1 * u.pc,
            frame=BarycentricTrueEcliptic(equinox=Time("J2000")),
        )
        c_icrs = c_ecl.transform_to(ICRS())

        return c_icrs.ra.to(u.hourangle).value, c_icrs.dec.to(u.deg).value

    except Exception:
        return None, None


def _extract_fk4_coordinates_optimized(
    parfile_dict: Dict[str, str],
) -> Tuple[Optional[float], Optional[float]]:
    """Extract FK4/B1950 coordinates and convert to equatorial (optimized version)."""
    try:
        ra = parfile_dict.get("RA")
        dec = parfile_dict.get("DEC")

        if not ra or not dec:
            return None, None

        # Parse coordinates
        ra_hours = _parse_ra_string_optimized(ra)
        dec_deg = _parse_dec_string_optimized(dec)

        if ra_hours is None or dec_deg is None:
            return None, None

        # Convert FK4 to ICRS
        c_fk4 = SkyCoord(
            ra=ra_hours * u.hourangle,
            dec=dec_deg * u.deg,
            frame=FK4(equinox=Time("B1950")),
        )
        c_icrs = c_fk4.transform_to(ICRS())

        return c_icrs.ra.to(u.hourangle).value, c_icrs.dec.to(u.deg).value

    except Exception:
        return None, None


def extract_coordinates_from_parfile_optimized(
    parfile_content: str,
) -> Optional[Tuple[float, float]]:
    """
    Extract RA/DEC coordinates directly from parfile content (optimized version).

    This function bypasses PINT model creation and extracts coordinates using
    lightweight parsing for significant performance improvements.

    Args:
        parfile_content: Raw parfile content as string

    Returns:
        Tuple of (RA_hours, DEC_degrees) or None if extraction fails
    """
    try:
        # Parse parfile into simple dictionary
        parfile_dict = _parse_parfile_optimized(parfile_content)

        # Try direct equatorial coordinates first (most common)
        ra_hours, dec_deg = _extract_equatorial_coordinates_optimized(parfile_dict)
        if ra_hours is not None and dec_deg is not None:
            return ra_hours, dec_deg

        # Try ecliptic coordinates as fallback
        ra_hours, dec_deg = _extract_ecliptic_coordinates_optimized(parfile_dict)
        if ra_hours is not None and dec_deg is not None:
            return ra_hours, dec_deg

        # Try FK4/B1950 coordinates as last resort
        ra_hours, dec_deg = _extract_fk4_coordinates_optimized(parfile_dict)
        if ra_hours is not None and dec_deg is not None:
            return ra_hours, dec_deg

        return None

    except Exception as e:
        logger.debug(f"Failed to extract coordinates: {e}")
        return None


def bj_name_from_coordinates_optimized(
    ra_hours: float, dec_deg: float, name_type: str = "J"
) -> str:
    """
    Generate B-name or J-name from coordinates without PINT model creation (optimized version).

    Args:
        ra_hours: Right ascension in hours
        dec_deg: Declination in degrees
        name_type: "J" for J-name (JHHMM±DDMM) or "B" for B-name (BHHMM±DD)

    Returns:
        Canonical name string (e.g., "J1857+0943" or "B1857+09")
    """
    # Create SkyCoord for coordinate transformations
    c_icrs = SkyCoord(ra=ra_hours * u.hourangle, dec=dec_deg * u.deg, frame=ICRS())

    if name_type.upper() == "B":
        # B-names should be based on FK4 B1950 coordinates
        c_fk4 = c_icrs.transform_to(FK4(equinox=Time("B1950")))
        return _format_b_name_from_coordinates_optimized(
            c_fk4.ra.to(u.hourangle).value, c_fk4.dec.to(u.deg).value
        )
    else:
        return _format_j_name_from_coordinates_optimized(ra_hours, dec_deg)


def _format_j_name_from_coordinates_optimized(ra_hours: float, dec_deg: float) -> str:
    """Format ICRS coordinates into a JHHMM±DDMM label using TRUNCATION (optimized version)."""
    # RA
    hh = int(np.floor(ra_hours)) % 24
    mm = int((ra_hours - hh) * 60.0)  # truncate minutes

    # Dec
    sign = "-" if dec_deg < 0 else "+"
    a = abs(dec_deg)
    DD = int(np.floor(a))
    MM = int((a - DD) * 60.0)  # truncate arcminutes

    return f"J{hh:02d}{mm:02d}{sign}{DD:02d}{MM:02d}"


def _format_b_name_from_coordinates_optimized(ra_hours: float, dec_deg: float) -> str:
    """Format FK4 coordinates into a B1234±56 label using TRUNCATION (optimized version)."""
    # RA
    hh = int(np.floor(ra_hours)) % 24
    mm = int((ra_hours - hh) * 60.0)  # truncate minutes

    # Dec
    sign = "-" if dec_deg < 0 else "+"
    a = abs(dec_deg)
    DD = int(np.floor(a))

    return f"B{hh:02d}{mm:02d}{sign}{DD:02d}"


def discover_pulsars_by_coordinates_optimized(
    file_data: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Discover pulsars by extracting coordinates directly from parfiles (optimized version).

    This optimized version bypasses PINT model creation and extracts
    coordinates using lightweight parsing for significant performance improvements.

    Args:
        file_data: Dictionary mapping PTA names to file lists

    Returns:
        Dictionary mapping J-names to PTA file data
    """
    coordinate_map = {}

    for pta_name, file_list in file_data.items():
        logger.debug(f"Processing {len(file_list)} files for PTA {pta_name}")

        for file_dict in file_list:
            try:
                # Extract coordinates directly from parfile content
                coords = extract_coordinates_from_parfile_optimized(
                    file_dict["par_content"]
                )

                if coords is None:
                    logger.warning(
                        f"Could not extract coordinates from {file_dict.get('par', 'unknown')}"
                    )
                    continue

                ra_hours, dec_deg = coords

                # Generate J-name directly from coordinates
                j_name = bj_name_from_coordinates_optimized(ra_hours, dec_deg, "J")

                # Add to coordinate map
                if j_name not in coordinate_map:
                    coordinate_map[j_name] = {}
                if pta_name not in coordinate_map[j_name]:
                    coordinate_map[j_name][pta_name] = []

                coordinate_map[j_name][pta_name].append(file_dict)

                logger.debug(
                    f"Found pulsar {j_name} at RA={ra_hours:.4f}h, DEC={dec_deg:.4f}°"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to process {file_dict.get('par', 'unknown')}: {e}"
                )
                continue

    logger.info(f"Discovered {len(coordinate_map)} unique pulsars across all PTAs")
    return coordinate_map
