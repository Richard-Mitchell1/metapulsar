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

from typing import Any
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
