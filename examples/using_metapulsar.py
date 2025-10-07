#!/usr/bin/env python3
"""
MetaPulsar Usage Example

This script demonstrates how to use MetaPulsar to combine pulsar timing data
from multiple PTA collaborations into unified Enterprise pulsar objects.

The workflow covers:
1. Manual single-pulsar data preparation
2. MetaPulsar creation with consistent parameter merging
3. Automated discovery and processing of multiple pulsars
4. Reference PTA selection strategies
"""

import logging
from metapulsar import (
    MetaPulsarFactory,
    discover_files,
    discover_layout,
    combine_layouts,
)

# Suppress debug output for cleaner example
logging.getLogger("metapulsar").setLevel(logging.WARNING)

# =============================================================================
# PART 1: Manual Single-Pulsar Data Preparation
# =============================================================================

print("=" * 80)
print("PART 1: Manual Single-Pulsar Data Preparation")
print("=" * 80)

# Manually create a single-pulsar dictionary with three PTAs
# The reference PTA (first in the dictionary) will be used for parameter
# inheritance where appropriate
pulsar_data = {
    # Reference PTA - parameters from this PTA will be inherited by the MetaPulsar
    # for model components that are merged (astrometry, spindown, binary, dispersion)
    "nanograv_9y": [
        {
            "par": "../data/ipta-dr2/NANOGrav_9y/par/J0613-0200_NANOGrav_9yv1.gls.par",
            "tim": "../data/ipta-dr2/NANOGrav_9y/tim/J0613-0200_NANOGrav_9yv1.tim",
            "timespan_days": 3285.0,  # 9 years
            "timing_package": "pint",
        }
    ],
    "epta_dr2": [
        {
            "par": "../data/ipta-dr2/EPTA_v2.2/J0613-0200/J0613-0200.par",
            "tim": "../data/ipta-dr2/EPTA_v2.2/J0613-0200/J0613-0200_all.tim",
            "timespan_days": 3650.0,  # Data span in days
            "timing_package": "tempo2",  # Timing package used
        }
    ],
    # Additional PTAs - parameters from these will be merged where requested
    "ppta_dr2": [
        {
            "par": "../data/ipta-dr2/PPTA_dr1dr2/par/J0613-0200_dr1dr2.par",
            "tim": "../data/ipta-dr2/PPTA_dr1dr2/tim/J0613-0200_dr1dr2.tim",
            "timespan_days": 4200.0,
            "timing_package": "tempo2",
        }
    ],
}

print("Single-pulsar data structure:")
print("  Pulsar: J0613-0200")
print(f"  PTAs: {list(pulsar_data.keys())}")
print(f"  Reference PTA: {list(pulsar_data.keys())[0]} (first in dictionary)")
print("  Data structure fields:")
print("    - par: Path to .par file (pulsar parameters)")
print("    - tim: Path to .tim file (timing observations)")
print("    - timespan_days: Data span in days")
print("    - timing_package: Software used (tempo2/pint)")

# =============================================================================
# PART 2: MetaPulsar Creation with Consistent Strategy
# =============================================================================

print("\n" + "=" * 80)
print("PART 2: MetaPulsar Creation with Consistent Strategy")
print("=" * 80)

# Create MetaPulsarFactory instance
factory = MetaPulsarFactory()

# Create MetaPulsar using the 'consistent' strategy
# This merges parameters from different PTAs where possible
metapulsar = factory.create_metapulsar(
    file_data=pulsar_data,
    combination_strategy="consistent",  # Merge compatible parameters
    combine_components=[
        "astrometry",
        "spindown",
        "binary",
        "dispersion",
    ],  # Components to merge
    add_dm_derivatives=True,  # Ensure DM1, DM2 are present
)

print(f"Created MetaPulsar: {metapulsar.name}")
print(f"Reference PTA: {list(pulsar_data.keys())[0]}")
print("Combination strategy: consistent")
print("Components merged: astrometry, spindown, binary, dispersion")

# =============================================================================
# PART 3: MetaPulsar as Enterprise Pulsar
# =============================================================================

print("\n" + "=" * 80)
print("PART 3: MetaPulsar as Enterprise Pulsar")
print("=" * 80)

# The resulting MetaPulsar is an Enterprise pulsar with all standard attributes
print("MetaPulsar Enterprise attributes:")
print(f"  Name: {metapulsar.name}")
print(f"  Number of pulsars: {len(metapulsar.pulsars)}")
print(f"  PTA names: {list(metapulsar.pulsars.keys())}")
print(f"  Combination strategy: {metapulsar.combination_strategy}")
print(f"  Components merged: {metapulsar.combine_components}")

# Show some basic Enterprise pulsar attributes
print("\nEnterprise pulsar attributes:")
print(f"  Number of TOAs: {len(metapulsar.toas)}")
print(
    f"  Frequency range: {metapulsar.freqs.min():.2f} - {metapulsar.freqs.max():.2f} MHz"
)
print(f"  Time span: {metapulsar.toas.max() - metapulsar.toas.min():.1f} days")

print(
    "\nThe MetaPulsar combines data from multiple PTAs into a single Enterprise pulsar."
)
print(
    f"Merged parameters inherit values from the reference PTA ({list(pulsar_data.keys())[0]})."
)
print("PTA-specific parameters retain their original PTA-specific values.")

# Demonstrate parameter naming conventions
print("\nParameter naming conventions:")
print("Merged parameters (no suffix):")
fitparams = metapulsar.fitpars
# Get PTA names from our data structure
pta_names = list(pulsar_data.keys())
pta_suffixes = [f"_{pta}" for pta in pta_names]

merged_params = [
    p for p in fitparams if not any(suffix in p for suffix in pta_suffixes)
]
for param in merged_params[:5]:  # Show first 5 merged parameters
    print(f"  {param}")

print("\nPTA-specific parameters (retain PTA suffix):")
pta_specific_params = [
    p for p in fitparams if any(suffix in p for suffix in pta_suffixes)
]
for param in pta_specific_params[:5]:  # Show first 5 PTA-specific parameters
    print(f"  {param}")

print("\nThis naming convention allows you to distinguish between:")
print("  - Merged parameters: Inherit reference PTA values, no suffix")
print("  - PTA-specific parameters: Retain original values, keep PTA suffix")

# Demonstrate the effect of NOT merging astrometry parameters
print("\n" + "-" * 60)
print("Example: NOT merging astrometry parameters")
print("-" * 60)

# Create another MetaPulsar without merging astrometry
metapulsar_no_astrometry = factory.create_metapulsar(
    file_data=pulsar_data,
    combination_strategy="consistent",
    combine_components=["spindown", "binary", "dispersion"],  # Exclude astrometry
    add_dm_derivatives=True,
)

print("When astrometry is NOT merged, astrometry parameters get PTA suffixes:")
fitparams_no_astrometry = metapulsar_no_astrometry.fitpars
astrometry_params = [
    p
    for p in fitparams_no_astrometry
    if any(
        term in p.lower()
        for term in [
            "ra",
            "dec",
            "pmra",
            "pmdec",
            "px",
            "elong",
            "elat",
            "pmelong",
            "pmelat",
            "beta",
            "lambda",
            "pmbeta",
            "pmlambda",
        ]
    )
]
for param in astrometry_params[:3]:  # Show first 3 astrometry parameters
    print(f"  {param}")

print("\nCompare with merged astrometry (from first example):")
astrometry_merged = [
    p
    for p in fitparams
    if any(
        term in p.lower()
        for term in [
            "ra",
            "dec",
            "pmra",
            "pmdec",
            "px",
            "elong",
            "elat",
            "pmelong",
            "pmelat",
            "beta",
            "lambda",
            "pmbeta",
            "pmlambda",
        ]
    )
]
for param in astrometry_merged[:3]:  # Show first 3 astrometry parameters
    print(f"  {param} (no suffix - merged)")

print(f"\nNote: PTA suffixes used are: {', '.join(pta_suffixes)}")

print(
    "\nThis shows how combine_components controls which parameters are merged vs. kept PTA-specific."
)

# =============================================================================
# PART 4: Automated Multi-Pulsar Processing
# =============================================================================

print("\n" + "=" * 80)
print("PART 4: Automated Multi-Pulsar Processing")
print("=" * 80)

print("Manually creating data structures for all pulsars in an array is cumbersome.")
print("We provide utility functions based on regex pattern matching for automation.")

# Discover data release layouts
print("\n1. Discovering data release layouts...")
layout1 = discover_layout("../data/ipta-dr2/EPTA_v2.2")
layout2 = discover_layout("../data/ipta-dr2/PPTA_dr1dr2")

# Combine layouts (only use available ones)
combined_layout = combine_layouts(layout1, layout2, include_defaults=True)
print(f"   Discovered {len(combined_layout)} data releases")

# Discover files using the combined layout
print("\n2. Discovering files...")
file_data = discover_files(
    working_dir=".",  # Current directory
    pta_data_releases=combined_layout,
    # data_release_names=["epta_dr2", "ppta_dr2"],  # Specific PTAs
    verbose=True,
)

print(f"   Found files for {len(file_data)} data releases")

# Create MetaPulsars for all discovered pulsars
print("\n3. Creating MetaPulsars for all pulsars...")

# Option 1: Auto-select reference PTA by timespan for each pulsar
print("   Option 1: Auto-select reference PTA by timespan (per pulsar)")
metapulsars_auto = factory.create_all_metapulsars(
    file_data=file_data,
    combination_strategy="consistent",
    reference_pta=None,  # Auto-select by longest timespan
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True,
)

print(
    f"   Created {len(metapulsars_auto)} MetaPulsars with auto-selected reference PTAs"
)

# Option 2: Use specific reference PTA for all pulsars
print("\n   Option 2: Use specific reference PTA for all pulsars")
metapulsars_epta = factory.create_all_metapulsars(
    file_data=file_data,
    combination_strategy="consistent",
    # reference_pta="epta_dr2",  # EPTA as reference for all pulsars
    combine_components=["astrometry", "spindown", "binary", "dispersion"],
    add_dm_derivatives=True,
)

print(f"   Created {len(metapulsars_epta)} MetaPulsars with EPTA as reference PTA")

# Show results (limited to 3 pulsars for demonstration)
print("\nResults (showing first 3 pulsars):")
all_pulsars = list(metapulsars_auto.keys())
print(f"  Total pulsars found: {len(all_pulsars)}")
for pulsar_name in all_pulsars[:3]:  # Show first 3
    auto_ref = list(metapulsars_auto[pulsar_name].pulsars.keys())[0]
    epta_ref = list(metapulsars_epta[pulsar_name].pulsars.keys())[0]
    print(f"    {pulsar_name}: auto={auto_ref}, epta={epta_ref}")

print("\nReference PTA selection:")
print("  - reference_pta=None: Auto-select by longest timespan per pulsar")
print("  - reference_pta='epta_dr2': Use EPTA as reference for all pulsars")
print("  - Manual: Use reorder_ptas_for_pulsar() for specific pulsars")

print("\n" + "=" * 80)
print("Example completed successfully!")
print("=" * 80)
