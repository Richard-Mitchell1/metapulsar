# tests/test_position_helpers_skycoords.py
from io import StringIO
from dataclasses import dataclass
import pytest
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord, ICRS, BarycentricTrueEcliptic

from pint.models.model_builder import ModelBuilder

# Functions under test
from ipta_metapulsar.position_helpers import (
    _skycoord_from_pint_model,
    _skycoord_from_enterprise,
    _skycoord_from_libstempo,
    j_name_from_pulsar,
)

# --- shared fixtures from your earlier setup ---

@pytest.fixture
def mb():
    return ModelBuilder()

def _build_pint_model(mb: ModelBuilder, par_text: str):
    # Accepts both TCB/TDB and tempo2 bits in simplified test pars
    return mb(StringIO(par_text), allow_tcb=True, allow_T2=True)

@pytest.fixture
def model_J(mb, load_parfile_text):
    return _build_pint_model(mb, load_parfile_text("binary.par"))

@pytest.fixture
def model_B(mb, load_parfile_text):
    return _build_pint_model(mb, load_parfile_text("binary-B.par"))

# --- tiny mocks ---

@dataclass
class _LibstempoParam:
    val: float  # libstempo exposes parameter objects with .val (float)

class LibstempoMock:
    """Minimal dict-like interface with .__getitem__ returning .val-bearing objects."""
    def __init__(self, mapping):
        self._m = mapping

    def __getitem__(self, key):
        # Raises KeyError for missing to simulate real behavior
        return self._m[key]

class EnterpriseMock:
    """Minimal Enterprise-like object with radians attributes."""
    def __init__(self, raj_rad: float, decj_rad: float):
        self._raj = raj_rad
        self._decj = decj_rad

# --- helpers to build the mocks from a PINT model ---

def _icrs_from_model(model) -> SkyCoord:
    """Ground-truth ICRS from the PINT model using your extractor."""
    return _skycoord_from_pint_model(model).transform_to(ICRS())

def enterprise_from_model(model) -> EnterpriseMock:
    c = _icrs_from_model(model)
    return EnterpriseMock(c.ra.to(u.rad).value, c.dec.to(u.rad).value)

def libstempo_from_model_equatorial(model) -> LibstempoMock:
    """Mock with RAJ/DECJ (in radians)."""
    c = _icrs_from_model(model)
    mapping = {
        "RAJ": _LibstempoParam(c.ra.to(u.rad).value),
        "DECJ": _LibstempoParam(c.dec.to(u.rad).value),
        # No ecliptic keys so _skycoord_from_libstempo takes equatorial branch
    }
    return LibstempoMock(mapping)

def libstempo_from_model_ecliptic(model) -> LibstempoMock:
    """Mock with ELONG/ELAT only (in radians) to hit the ecliptic branch."""
    c = _icrs_from_model(model).transform_to(BarycentricTrueEcliptic(equinox="J2000"))
    mapping = {
        "ELONG": _LibstempoParam(c.lon.to(u.rad).value),
        "ELAT": _LibstempoParam(c.lat.to(u.rad).value),
        # Intentionally omit RAJ/DECJ so the code must use ecliptic path
    }
    return LibstempoMock(mapping)

# --- utilities for numeric closeness ---

def _assert_coords_close(c1: SkyCoord, c2: SkyCoord, atol_rad=1e-10):
    # Compare on-sphere separation; 1e-10 rad ~ 0.02 mas — very tight
    sep = c1.separation(c2).to(u.rad).value
    assert sep <= atol_rad, f"Coords differ by {sep} rad (> {atol_rad})"

# --- tests for _skycoord_from_enterprise ---

@pytest.mark.parametrize("which", ["J", "B"])
def test_skycoord_from_enterprise_matches_pint(which, model_J, model_B):
    model = model_J if which == "J" else model_B
    truth = _icrs_from_model(model)

    emock = enterprise_from_model(model)
    c_ent = _skycoord_from_enterprise(emock).transform_to(ICRS())

    _assert_coords_close(c_ent, truth)

# --- tests for _skycoord_from_libstempo (RAJ/DECJ branch) ---

@pytest.mark.parametrize("which", ["J", "B"])
def test_skycoord_from_libstempo_equatorial_matches_pint(which, model_J, model_B):
    model = model_J if which == "J" else model_B
    truth = _icrs_from_model(model)

    lmock = libstempo_from_model_equatorial(model)
    c_lt = _skycoord_from_libstempo(lmock).transform_to(ICRS())

    _assert_coords_close(c_lt, truth)

# --- tests for _skycoord_from_libstempo (ELONG/ELAT ecliptic branch) ---

@pytest.mark.parametrize("which", ["J", "B"])
def test_skycoord_from_libstempo_ecliptic_matches_pint(which, model_J, model_B):
    model = model_J if which == "J" else model_B
    truth = _icrs_from_model(model)

    lmock = libstempo_from_model_ecliptic(model)
    c_lt = _skycoord_from_libstempo(lmock).transform_to(ICRS())

    _assert_coords_close(c_lt, truth)

# --- end-to-end label checks via j_name_from_pulsar() using mocks ---

@pytest.mark.parametrize("which", ["J", "B"])
def test_j_label_from_enterprise_mock(which, model_J, model_B):
    model = model_J if which == "J" else model_B
    emock = enterprise_from_model(model)
    assert j_name_from_pulsar(emock) == "J1857+0943"

@pytest.mark.parametrize("which,variant", [("J","eq"),("B","eq"),("J","ecl"),("B","ecl")])
def test_j_label_from_libstempo_mocks(which, variant, model_J, model_B):
    model = model_J if which == "J" else model_B
    if variant == "eq":
        lmock = libstempo_from_model_equatorial(model)
    else:
        lmock = libstempo_from_model_ecliptic(model)
    assert j_name_from_pulsar(lmock) == "J1857+0943"
