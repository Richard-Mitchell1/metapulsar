from typing import Any
import numpy as np
from astropy.coordinates import SkyCoord, ICRS, FK4, FK5, Angle
from astropy.coordinates import GeocentricTrueEcliptic, BarycentricTrueEcliptic
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
    sign = '-' if dec_deg < 0 else '+'
    a = abs(dec_deg)
    DD = int(np.floor(a))
    MM = int((a - DD) * 60.0)  # truncate arcminutes

    return f"J{hh:02d}{mm:02d}{sign}{DD:02d}{MM:02d}"

def _skycoord_from_pint_model(model: Any) -> SkyCoord:
    """
    Build a SkyCoord from a PINT TimingModel.
    Prefers RAJ/DECJ; falls back to ELONG/ELAT or LAMBDA/BETA if needed.
    Assumes RAJ/DECJ are J2000-like; if only FK4/B1950 components are present, converts.
    """
    # Direct equatorial (preferred)
    if hasattr(model, "RAJ") and hasattr(model, "DECJ") and model.RAJ.value is not None and model.DECJ.value is not None:
        ra = Angle(model.RAJ.quantity).to(u.hourangle)
        dec = Angle(model.DECJ.quantity).to(u.deg)
        return SkyCoord(ra=ra, dec=dec, frame=ICRS())

    # Ecliptic (True ecliptic in many parfiles: LAMBDA/BETA)
    # Try BarycentricTrueEcliptic first; fall back to GeocentricTrueEcliptic
    for ecl_frame in (BarycentricTrueEcliptic, GeocentricTrueEcliptic):
        if hasattr(model, "LAMBDA") and hasattr(model, "BETA") and model.LAMBDA.value is not None and model.BETA.value is not None:
            lam = Angle(model.LAMBDA.quantity).to(u.deg)
            bet = Angle(model.BETA.quantity).to(u.deg)
            c = SkyCoord(lon=lam, lat=bet, distance=1*u.pc, frame=ecl_frame(equinox=Time('J2000')))
            return c.transform_to(ICRS())

        if hasattr(model, "ELONG") and hasattr(model, "ELAT") and model.ELONG.value is not None and model.ELAT.value is not None:
            lam = Angle(model.ELONG.quantity).to(u.deg)
            bet = Angle(model.ELAT.quantity).to(u.deg)
            c = SkyCoord(lon=lam, lat=bet, distance=1*u.pc, frame=ecl_frame(equinox=Time('J2000')))
            return c.transform_to(ICRS())

    # Very old B1950-style RA/DEC: rarely present as FK4 in models; handle if encountered
    if hasattr(model, "RA") and hasattr(model, "DEC") and model.RA.value is not None and model.DEC.value is not None:
        ra = Angle(model.RA.quantity).to(u.hourangle)
        dec = Angle(model.DEC.quantity).to(u.deg)
        c_fk4 = SkyCoord(ra=ra, dec=dec, frame=FK4(equinox=Time('B1950')))
        return c_fk4.transform_to(ICRS())

    raise ValueError("Could not derive coordinates from PINT TimingModel.")

def _skycoord_from_libstempo(psr: Any) -> SkyCoord:
    """
    Build a SkyCoord from a libstempo tempopulsar.
    Expects RAJ/DECJ in radians (libstempo stores parameters in SI/radians).
    Falls back to ELONG/ELAT or LAMBDA/BETA if present.
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
        return SkyCoord(ra=raj*u.rad, dec=decj*u.rad, frame=ICRS())

    # Ecliptic variants (in radians)
    lam = _val("LAMBDA") or _val("ELONG")
    bet = _val("BETA")   or _val("ELAT")
    if lam is not None and bet is not None:
        c = SkyCoord(lon=lam*u.rad, lat=bet*u.rad, distance=1*u.pc,
                     frame=BarycentricTrueEcliptic(equinox=Time('J2000')))
        return c.transform_to(ICRS())

    # FK4 B1950 fallback (rare)
    ra_b = _val("RA")
    dec_b = _val("DEC")
    if ra_b is not None and dec_b is not None:
        c_fk4 = SkyCoord(ra=ra_b*u.rad, dec=dec_b*u.rad, frame=FK4(equinox=Time('B1950')))
        return c_fk4.transform_to(ICRS())

    raise ValueError("Could not derive coordinates from libstempo tempopulsar.")

def _skycoord_from_enterprise(psr: Any) -> SkyCoord:
    """
    Build a SkyCoord from an Enterprise Pulsar (PintPulsar or Tempo2Pulsar).
    Uses internal _raj/_decj stored in radians (ICRS-equivalent).
    """
    if hasattr(psr, "_raj") and hasattr(psr, "_decj"):
        return SkyCoord(ra=psr._raj * u.rad, dec=psr._decj * u.rad, frame=ICRS())
    raise ValueError("Enterprise pulsar lacks _raj/_decj.")

def j_name_from_pulsar(psr_obj: Any) -> str:
    """
    Given a PINT TimingModel, libstempo tempopulsar, or Enterprise Pulsar,
    return the canonical J-name (JHHMM±DDMM) computed from the object's coordinates.
    """
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

    # Ensure we’re in ICRS (if any upstream gave a different frame)
    c_icrs = c.transform_to(ICRS())
    return _format_j_name_from_icrs(c_icrs)
