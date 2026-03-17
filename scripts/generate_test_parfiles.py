#!/usr/bin/env python3
"""
Generate test parfiles for proper motion J2000 normalization tests.

This script generates all parfiles needed for TestProperMotionJ2000Normalization
using libstempo to ensure consistency.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import libstempo as T  # noqa: E402
import libstempo.toasim as LT  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
import astropy.units as u  # noqa: E402

# Output directory
OUTPUT_DIR = project_root / "tests" / "fixtures" / "sample_parfiles"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Input files
BASE_PAR = project_root / "parfiledata" / "base_template.par"
BASE_TIM = project_root / "parfiledata" / "random_data.tim"

J2000_MJD = 51544.5


def generate_same_pulsar_different_posepoch():
    """Generate 2 parfiles: same pulsar at POSEPOCH 54500 and 56000.

    These have correct positions at each epoch (reflecting proper motion),
    so they normalize to the same J2000 position.

    Changes POSEPOCH incrementally with refits to maintain timing solution coherence.
    """
    print(
        "Generating test_same_pulsar_epoch1_54500.par and test_same_pulsar_epoch2_56000.par..."
    )

    # Load and prepare
    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1234)

    # Use a realistic but clearly non-zero PM: large enough to produce a visible
    # coordinate difference between the two epochs, small enough that J2000
    # propagation keeps the RA well inside the 57m bin (~3 arcmin headroom).
    pmra_val = 3000.0  # mas/yr
    pmdec_val = -25.0  # mas/yr
    psr["PMRA"].val = pmra_val
    psr["PMDEC"].val = pmdec_val
    psr["PMRA"].fit = False
    psr["PMDEC"].fit = False

    # Save epoch 1 (54500)
    psr["POSEPOCH"].val = 54500.0
    psr["PEPOCH"].val = 54500.0
    psr.fit()

    psr.savepar(str(OUTPUT_DIR / "test_same_pulsar_epoch1_54500.par"))

    # For epoch 2, incrementally change POSEPOCH from 54500 to 56000
    # with refits at each step to maintain timing solution coherence
    # Step size: 100 days (small enough to maintain coherence)
    step_size_days = 100.0
    start_epoch = 54500.0
    end_epoch = 56000.0
    current_epoch = start_epoch

    # Incrementally change POSEPOCH and refit
    while current_epoch < end_epoch:
        next_epoch = min(current_epoch + step_size_days, end_epoch)
        psr["POSEPOCH"].val = next_epoch
        psr["PEPOCH"].val = next_epoch
        psr.fit()  # Refit at each step to maintain coherence
        current_epoch = next_epoch

    # Final epoch should be 56000.0
    assert (
        abs(psr["POSEPOCH"].val - 56000.0) < 0.1
    ), f"Final POSEPOCH should be 56000.0, got {psr['POSEPOCH'].val}"

    psr.savepar(str(OUTPUT_DIR / "test_same_pulsar_epoch2_56000.par"))

    print("  ✓ Generated")


def generate_equatorial_pm():
    """Generate parfile with equatorial PM (for test_proper_motion_propagation_equatorial)."""
    print("Generating test_equatorial_pm.par...")

    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1235)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 100000.0  # Very large PMRA for testing - more stable than PMDEC
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr["PEPOCH"].val = 54500.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_equatorial_pm.par"))

    print("  ✓ Generated")


def generate_ecliptic_pmelong():
    """Generate parfile with ELONG/ELAT and PMELONG/PMELAT."""
    print("Generating test_ecliptic_pmelong.par...")

    # Start with equatorial parfile
    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1236)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 100000.0  # Very large PMRA for testing - more stable than PMDEC
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr["PEPOCH"].val = 54500.0
    psr.fit()

    # Get equatorial coordinates
    ra_rad = psr["RAJ"].val
    dec_rad = psr["DECJ"].val
    c_icrs = SkyCoord(ra=ra_rad * u.rad, dec=dec_rad * u.rad, frame="icrs")
    c_ecl = c_icrs.transform_to("barycentrictrueecliptic")

    # Convert to ecliptic frame (simplified - for test purposes we'll use approximate values)
    # In reality, proper motion transformation between frames is complex
    # For testing, we'll use values that give similar magnitude
    elong_deg = c_ecl.lon.to(u.deg).value
    elat_deg = c_ecl.lat.to(u.deg).value

    # Approximate PM conversion (for testing - not physically accurate but sufficient for tests)
    pmelong = 100000.0  # Very large PM for testing (consistent) - more stable
    pmelat = -100.0  # Use same magnitude

    # Save a temporary parfile first
    temp_par = OUTPUT_DIR / "temp_equatorial.par"
    psr.savepar(str(temp_par))

    # Read the equatorial parfile and convert to ecliptic
    with open(temp_par, "r") as f:
        content = f.read()

    # Replace RAJ/DECJ with ELONG/ELAT
    # Find RAJ and DECJ lines and replace
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("RAJ"):
            # Extract the fit flag if present
            parts = stripped.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            new_lines.append(f"ELONG {elong_deg:.4f}    {fit_flag}")
        elif stripped.startswith("DECJ"):
            parts = stripped.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            new_lines.append(f"ELAT {elat_deg:.4f}    {fit_flag}")
        elif stripped.startswith("PMRA"):
            parts = stripped.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            new_lines.append(f"PMELONG {pmelong:.1f}            {fit_flag}")
        elif stripped.startswith("PMDEC"):
            parts = stripped.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            new_lines.append(f"PMELAT {pmelat:.1f}            {fit_flag}")
        else:
            new_lines.append(line)

    with open(OUTPUT_DIR / "test_ecliptic_pmelong.par", "w") as f:
        f.write("\n".join(new_lines))

    # Clean up temp file
    temp_par.unlink()

    print("  ✓ Generated")


def generate_ecliptic_pmlambda():
    """Generate parfile with ELONG/ELAT and PMLAMBDA/PMBETA (aliases)."""
    print("Generating test_ecliptic_pmlambda.par...")

    # Read the PMELONG parfile and replace parameter names in the text
    # This ensures the parfile text contains PMLAMBDA/PMBETA (not normalized to PMELONG/PMELAT)
    with open(OUTPUT_DIR / "test_ecliptic_pmelong.par", "r") as f:
        content = f.read()

    # Replace PMELONG/PMELAT with PMLAMBDA/PMBETA in the parfile text
    content = content.replace("PMELONG", "PMLAMBDA")
    content = content.replace("PMELAT", "PMBETA")

    # Write new parfile
    with open(OUTPUT_DIR / "test_ecliptic_pmlambda.par", "w") as f:
        f.write(content)

    print("  ✓ Generated")


def generate_ecliptic_lambda_beta():
    """Generate parfile with LAMBDA/BETA coordinates and PMLAMBDA/PMBETA."""
    print("Generating test_ecliptic_lambda_beta.par...")

    # Read the PMELONG parfile and replace parameter names in the text
    # This ensures the parfile text contains LAMBDA/BETA/PMLAMBDA/PMBETA (not normalized)
    with open(OUTPUT_DIR / "test_ecliptic_pmelong.par", "r") as f:
        content = f.read()

    # Replace coordinate and PM parameter names
    content = content.replace("ELONG", "LAMBDA")
    content = content.replace("ELAT", "BETA")
    content = content.replace("PMELONG", "PMLAMBDA")
    content = content.replace("PMELAT", "PMBETA")

    # Write new parfile
    with open(OUTPUT_DIR / "test_ecliptic_lambda_beta.par", "w") as f:
        f.write(content)

    print("  ✓ Generated")


def generate_partial_pm_no_pmdec():
    """Generate parfile with PMRA but no PMDEC."""
    print("Generating test_partial_pm_no_pmdec.par...")

    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1237)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 5000.0  # Large PMRA for testing (15000/3) - will be removed later
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_partial_pm_no_pmdec.par"))

    # Remove PMDEC and F1 lines from parfile
    with open(OUTPUT_DIR / "test_partial_pm_no_pmdec.par", "r") as f:
        lines = f.readlines()

    with open(OUTPUT_DIR / "test_partial_pm_no_pmdec.par", "w") as f:
        for line in lines:
            stripped = line.strip()
            if not (
                stripped.startswith("PMDEC")
                or stripped.startswith("F1")
                or stripped.startswith("PEPOCH")
            ):
                f.write(line)

    print("  ✓ Generated")


def generate_partial_pm_no_pmra():
    """Generate parfile with PMDEC but no PMRA."""
    print("Generating test_partial_pm_no_pmra.par...")

    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1238)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 5000.0  # Large PMRA for testing (15000/3) - will be removed later
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_partial_pm_no_pmra.par"))

    # Remove PMRA, F1, and PEPOCH lines from parfile
    with open(OUTPUT_DIR / "test_partial_pm_no_pmra.par", "r") as f:
        lines = f.readlines()

    with open(OUTPUT_DIR / "test_partial_pm_no_pmra.par", "w") as f:
        for line in lines:
            stripped = line.strip()
            if not (
                stripped.startswith("PMRA")
                or stripped.startswith("F1")
                or stripped.startswith("PEPOCH")
            ):
                f.write(line)

    print("  ✓ Generated")


def generate_partial_pm_no_posepoch():
    """Generate parfile with PM but no POSEPOCH."""
    print("Generating test_partial_pm_no_posepoch.par...")

    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1239)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 100000.0  # Very large PMRA for testing - more stable than PMDEC
    psr["PMDEC"].val = -100.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_partial_pm_no_posepoch.par"))

    # Remove POSEPOCH, F1, and PEPOCH lines from parfile
    with open(OUTPUT_DIR / "test_partial_pm_no_posepoch.par", "r") as f:
        lines = f.readlines()

    with open(OUTPUT_DIR / "test_partial_pm_no_posepoch.par", "w") as f:
        for line in lines:
            stripped = line.strip()
            if not (
                stripped.startswith("POSEPOCH")
                or stripped.startswith("F1")
                or stripped.startswith("PEPOCH")
            ):
                f.write(line)

    print("  ✓ Generated")


def generate_no_pm():
    """Generate parfile with no PM and no POSEPOCH."""
    print("Generating test_no_pm.par...")

    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1240)

    psr["PEPOCH"].val = 54500.0  # Keep PEPOCH for F1
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_no_pm.par"))

    # Remove PM and POSEPOCH lines from parfile
    with open(OUTPUT_DIR / "test_no_pm.par", "r") as f:
        lines = f.readlines()

    with open(OUTPUT_DIR / "test_no_pm.par", "w") as f:
        for line in lines:
            if not any(
                line.strip().startswith(p) for p in ["PMRA", "PMDEC", "POSEPOCH"]
            ):
                f.write(line)

    print("  ✓ Generated")


def generate_b_name_propagation():
    """Generate parfile for B-name generation test (same as equatorial_pm)."""
    print("Generating test_b_name_propagation.par...")

    # Same as equatorial_pm
    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1241)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 100000.0  # Very large PMRA for testing - more stable than PMDEC
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr["PEPOCH"].val = 54500.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_b_name_propagation.par"))

    print("  ✓ Generated")


def generate_pint_model_normalization():
    """Generate parfile for PINT model normalization test (same as equatorial_pm)."""
    print("Generating test_pint_model_normalization.par...")

    # Same as equatorial_pm
    psr = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr)
    LT.add_efac(psr, efac=1.0, seed=1242)

    # Set large PM values for testing (consistent across all parfiles)
    psr["PMRA"].val = 100000.0  # Very large PMRA for testing - more stable than PMDEC
    psr["PMDEC"].val = -100.0
    psr["POSEPOCH"].val = 54500.0
    psr["PEPOCH"].val = 54500.0
    psr.fit()
    psr.savepar(str(OUTPUT_DIR / "test_pint_model_normalization.par"))

    print("  ✓ Generated")


def generate_same_position_large_pm_different_posepoch():
    """Generate 2 parfiles: same position at different POSEPOCH with large PM.

    This simulates an error case where someone incorrectly provides the same position
    at different epochs when proper motion exists. After normalization to J2000,
    these should produce different coordinates (and different J-names with large PM).

    Loads the same pulsar twice, changes ONLY POSEPOCH in the second one (no refitting).
    """
    print(
        "Generating test_same_position_large_pm_epoch1_54500.par and test_same_position_large_pm_epoch2_56000.par..."
    )

    # Load and prepare psr_a (epoch 1)
    psr_a = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr_a)
    LT.add_efac(psr_a, efac=1.0, seed=1243)

    # Set large PM values for testing
    # Use very large PMRA to ensure error case test produces different J-names
    # Need >15 arcmin difference to cross minute boundary in J-name generation
    pmra_val = 100000.0  # Very large PMRA for testing - ensures RA diff > 15 arcmin to cross minute boundary
    pmdec_val = -100.0
    psr_a["PMRA"].val = pmra_val
    psr_a["PMDEC"].val = pmdec_val

    # Set epoch 1
    psr_a["POSEPOCH"].val = 54500.0
    psr_a["PEPOCH"].val = 54500.0
    psr_a.fit()

    # Adjust RAJ to be very close to the minute boundary so PMRA difference will push it over
    # Target: 18h 57m 59.5s = 18.99986h (very close to 58m boundary)
    # With PMRA=30000 mas/yr, the difference in propagation between epochs is ~2 arcmin
    # Starting very close to boundary ensures the difference pushes one into the next minute
    import math

    target_ra_h = (
        18 + 57 / 60 + 59.5 / 3600
    )  # 18h 57m 59.5s (very close to 58m boundary)
    target_ra_rad = math.radians(target_ra_h * 15)

    # Save epoch 1 parfile first
    psr_a.savepar(str(OUTPUT_DIR / "test_same_position_large_pm_epoch1_54500.par"))

    # Manually edit RAJ in the parfile to ensure it's set to target value
    # Read parfile, replace RAJ line, write back
    with open(OUTPUT_DIR / "test_same_position_large_pm_epoch1_54500.par", "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith("RAJ"):
            # Replace with target RAJ value
            # Format: RAJ HH:MM:SS.sssssss [fit_flag] [uncertainty]
            parts = line.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            h = int(target_ra_h)
            m = int((target_ra_h - h) * 60)
            s = ((target_ra_h - h) * 60 - m) * 60
            new_lines.append(
                f"RAJ             {h:02d}:{m:02d}:{s:06.3f}            {fit_flag}\n"
            )
        else:
            new_lines.append(line)

    with open(OUTPUT_DIR / "test_same_position_large_pm_epoch1_54500.par", "w") as f:
        f.writelines(new_lines)

    # Load the same pulsar again as psr_b
    psr_b = T.tempopulsar(str(BASE_PAR), str(BASE_TIM))
    LT.make_ideal(psr_b)
    LT.add_efac(psr_b, efac=1.0, seed=1243)  # Same seed for consistency

    # Set the same PM values
    psr_b["PMRA"].val = pmra_val
    psr_b["PMDEC"].val = pmdec_val

    # Set epoch 1 and fit, then adjust to same RAJ as psr_a
    psr_b["POSEPOCH"].val = 54500.0
    psr_b["PEPOCH"].val = 54500.0
    psr_b.fit()

    # Set to the same RAJ and DECJ as psr_a (near minute boundary)
    psr_b["RAJ"].val = target_ra_rad
    psr_b["DECJ"].val = psr_a["DECJ"].val  # Use same DECJ
    psr_b["RAJ"].fit = False  # Fix RAJ
    psr_b["DECJ"].fit = False  # Fix DECJ
    psr_b.fit()  # Refit with fixed RAJ and DECJ

    # Verify positions match
    assert abs(psr_b["RAJ"].val - target_ra_rad) < 1e-6, "RAJ should match target"
    assert abs(psr_b["DECJ"].val - psr_a["DECJ"].val) < 1e-8, "DECJ should match"

    # Change ONLY POSEPOCH (no refitting, nothing else)
    psr_b["POSEPOCH"].val = 56000.0
    psr_b["PEPOCH"].val = 56000.0

    # Save epoch 2 parfile (same position, different POSEPOCH - error case)
    psr_b.savepar(str(OUTPUT_DIR / "test_same_position_large_pm_epoch2_56000.par"))

    # Manually edit RAJ and DECJ in epoch 2 parfile to match epoch 1 (ensure exact same position)
    with open(OUTPUT_DIR / "test_same_position_large_pm_epoch1_54500.par", "r") as f:
        epoch1_lines = f.readlines()

    # Extract DECJ from epoch1
    decj_epoch1 = None
    for line in epoch1_lines:
        if line.strip().startswith("DECJ"):
            decj_epoch1 = line
            break

    with open(OUTPUT_DIR / "test_same_position_large_pm_epoch2_56000.par", "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith("RAJ"):
            # Replace with target RAJ value (same as epoch1)
            parts = line.split()
            fit_flag = parts[-1] if len(parts) > 1 and parts[-1] in ["0", "1"] else "1"
            h = int(target_ra_h)
            m = int((target_ra_h - h) * 60)
            s = ((target_ra_h - h) * 60 - m) * 60
            new_lines.append(
                f"RAJ             {h:02d}:{m:02d}:{s:06.3f}            {fit_flag}\n"
            )
        elif line.strip().startswith("DECJ") and decj_epoch1:
            # Replace with same DECJ as epoch1
            new_lines.append(decj_epoch1)
        else:
            new_lines.append(line)

    with open(OUTPUT_DIR / "test_same_position_large_pm_epoch2_56000.par", "w") as f:
        f.writelines(new_lines)

    print("  ✓ Generated")


def main():
    """Generate all test parfiles."""
    print("=" * 60)
    print("Generating test parfiles for proper motion J2000 normalization")
    print("=" * 60)
    print()

    try:
        generate_same_pulsar_different_posepoch()
        generate_equatorial_pm()
        generate_ecliptic_pmelong()
        generate_ecliptic_pmlambda()
        generate_ecliptic_lambda_beta()
        generate_partial_pm_no_pmdec()
        generate_partial_pm_no_pmra()
        generate_partial_pm_no_posepoch()
        generate_no_pm()
        generate_b_name_propagation()
        generate_pint_model_normalization()
        generate_same_position_large_pm_different_posepoch()

        print()
        print("=" * 60)
        print("✓ All parfiles generated successfully!")
        print(f"Output directory: {OUTPUT_DIR}")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error generating parfiles: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
