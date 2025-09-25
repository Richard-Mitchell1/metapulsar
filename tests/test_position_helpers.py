from io import StringIO
import pytest
from pint.models.model_builder import ModelBuilder

# Import the helper under test. Adjust the import path to wherever you put it.
# For example, if you placed it in ipta_metapulsar/pint_helpers.py:
from ipta_metapulsar.position_helpers import j_name_from_pulsar


@pytest.fixture(scope="module")
def mb():
    return ModelBuilder()


def build_pint_model(mb, par_text: str):
    # PINT ModelBuilder accepts a file-like object; give it StringIO
    sio = StringIO(par_text)
    model = mb(sio, allow_tcb=True, allow_T2=True)
    return model

def _build_pint_model(mb: ModelBuilder, par_text: str):
    # ModelBuilder can take a file-like; StringIO keeps tests hermetic
    return mb(StringIO(par_text), allow_tcb=True, allow_T2=True)

@pytest.mark.parametrize("parfile_name", ["binary.par", "binary-B.par"])
def test_j_label_is_consistent_across_parfiles(mb, load_parfile_text, parfile_name):
    par_text = load_parfile_text(parfile_name)
    model = _build_pint_model(mb, par_text)

    jlabel = j_name_from_pulsar(model)

    # Canonical expected J-label for this source
    assert jlabel == "J1857+0943"

def test_idempotent_between_the_two_parfiles(mb, load_parfile_text):
    par_j = load_parfile_text("binary.par")
    par_b = load_parfile_text("binary-B.par")

    mdl_j = _build_pint_model(mb, par_j)
    mdl_b = _build_pint_model(mb, par_b)

    jl_j = j_name_from_pulsar(mdl_j)
    jl_b = j_name_from_pulsar(mdl_b)

    assert jl_j == jl_b == "J1857+0943"
