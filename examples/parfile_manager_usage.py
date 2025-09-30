#!/usr/bin/env python3
"""
Usage examples for ParFileManager and MetaPulsarFactory.

This script demonstrates how to use the ParFileManager and MetaPulsarFactory
classes for multi-PTA pulsar timing data combination.

Author: IPTA Metapulsar Analysis Team
Date: 2025-09-30
"""

from pathlib import Path
from ipta_metapulsar import MetaPulsarFactory, PTARegistry, ParFileManager


def basic_usage_example():
    """Demonstrate basic usage of MetaPulsarFactory."""
    print("=== Basic Usage Example ===")

    # Create factory with default PTARegistry
    factory = MetaPulsarFactory()

    # List available pulsars
    available_pulsars = factory.list_available_pulsars()
    print(f"Available pulsars: {available_pulsars}")

    # Create MetaPulsar with composite approach (default, Borg/FrankenStat methods)
    print("\nCreating MetaPulsar with composite strategy...")
    metapulsar = factory.create_metapulsar(
        "J1909-3744", ["epta_dr2", "ppta_dr2", "nanograv_15y"]
    )
    print(f"MetaPulsar combination strategy: {metapulsar.get_combination_strategy()}")
    print(f"Is composite strategy: {metapulsar.combination_strategy == 'composite'}")

    # Create MetaPulsar with astrophysical consistency approach
    print("\nCreating MetaPulsar with consistent strategy...")
    metapulsar_consistent = factory.create_metapulsar(
        "J1909-3744",
        ["epta_dr2", "ppta_dr2", "nanograv_15y"],
        combination_strategy="consistent",
        reference_pta="epta_dr2",
    )
    print(
        f"MetaPulsar combination strategy: {metapulsar_consistent.get_combination_strategy()}"
    )
    print(
        f"Is consistent strategy: {metapulsar_consistent.combination_strategy == 'consistent'}"
    )


def custom_pta_registry_example():
    """Demonstrate custom PTA registry usage."""
    print("\n=== Custom PTA Registry Example ===")

    # Example 1: Create custom PTA registry with default PTAs + custom PTAs
    print("Creating custom PTA registry...")
    custom_registry = PTARegistry()

    # Add new PTA with custom regex patterns to existing registry
    custom_registry.add_pta(
        "custom_pta",
        {
            "base_dir": "/data/custom_pta/",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Custom PTA with specific naming convention",
        },
    )

    # Example 2: Create empty registry and add only custom PTAs
    print("Creating empty registry with custom PTAs...")
    empty_registry = PTARegistry(configs={})  # Start with empty configs

    # Add custom PTAs one by one
    empty_registry.add_pta(
        "custom_pta",
        {
            "base_dir": "/data/custom_pta/",
            "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
            "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
            "timing_package": "pint",
            "priority": 1,
            "description": "Custom PTA with specific naming convention",
        },
    )

    empty_registry.add_pta(
        "another_pta",
        {
            "base_dir": "/data/another_pta/",
            "par_pattern": r"pulsar_([BJ]\d{4}[+-]\d{2,4})\.par",
            "tim_pattern": r"pulsar_([BJ]\d{4}[+-]\d{2,4})\.tim",
            "timing_package": "tempo2",
            "priority": 2,
            "description": "Another PTA with different file structure",
        },
    )

    # Create factory with custom registry
    factory = MetaPulsarFactory(registry=custom_registry)

    # List available pulsars in custom PTAs
    available_pulsars = factory.list_available_pulsars(["custom_pta", "another_pta"])
    print(f"Available pulsars in custom PTAs: {available_pulsars}")

    # Create MetaPulsar using custom PTAs
    print("Creating MetaPulsar with custom PTAs...")
    metapulsar = factory.create_metapulsar(
        "J1909-3744", ["custom_pta", "another_pta"], combination_strategy="composite"
    )
    print(f"MetaPulsar created with strategy: {metapulsar.combination_strategy}")


def advanced_usage_example():
    """Demonstrate advanced usage with custom parameters."""
    print("\n=== Advanced Usage Example ===")

    factory = MetaPulsarFactory()

    # Custom astrophysical consistency
    print("Creating MetaPulsar with custom astrophysical consistency...")
    factory.create_metapulsar(
        "J1909-3744",
        ["epta_dr2", "ppta_dr2", "nanograv_15y"],
        combination_strategy="consistent",
        reference_pta="epta_dr2",
        combine_components=[
            "spin",
            "astrometry",
        ],  # Only make these astrophysically consistent
        add_dm_derivatives=True,  # Ensure DM1, DM2 are present in all par files
    )
    print("MetaPulsar created with consistent strategy")
    print(f"Components combined: {['spin', 'astrometry']}")
    print("DM derivatives added: True")

    # For custom covariance matrix modeling (no DM derivatives)
    print("\nCreating MetaPulsar without DM derivatives...")
    factory.create_metapulsar(
        "J1909-3744",
        ["epta_dr2", "ppta_dr2", "nanograv_15y"],
        combination_strategy="consistent",
        reference_pta="epta_dr2",
        combine_components=["spin", "astrometry", "binary", "dispersion"],
        add_dm_derivatives=False,  # Do not add DM parameters, but align existing DM1, DM2 to reference
    )
    print("MetaPulsar created without DM derivatives")
    print(f"Components combined: {['spin', 'astrometry', 'binary', 'dispersion']}")
    print("DM derivatives added: False")

    # Example where add_dm_derivatives=True is ignored (warning issued)
    print("\nCreating MetaPulsar with ignored DM derivatives (warning expected)...")
    factory.create_metapulsar(
        "J1909-3744",
        ["epta_dr2", "ppta_dr2", "nanograv_15y"],
        combination_strategy="consistent",
        reference_pta="epta_dr2",
        combine_components=[
            "spin",
            "astrometry",
        ],  # No 'dispersion' in combine_components
        add_dm_derivatives=True,  # This will be ignored with a warning
    )
    print(
        "MetaPulsar created (DM derivatives ignored due to missing 'dispersion' component)"
    )


def direct_parfile_manager_example():
    """Demonstrate direct ParFileManager usage."""
    print("\n=== Direct ParFileManager Usage Example ===")

    # Create ParFileManager
    parfile_manager = ParFileManager()

    # Create consistent par files
    print("Creating consistent par files...")
    output_dir = Path("/tmp/consistent_parfiles/")
    output_dir.mkdir(exist_ok=True)

    try:
        consistent_files = parfile_manager.write_consistent_parfiles(
            "J1909-3744",
            ["epta_dr2", "ppta_dr2"],
            reference_pta="epta_dr2",
            combine_components=["spin", "astrometry", "binary", "dispersion"],
            add_dm_derivatives=True,
            output_dir=output_dir,
        )
        print(f"Consistent par files created: {consistent_files}")

        # List the created files
        for pta_name, file_path in consistent_files.items():
            print(f"  {pta_name}: {file_path}")

    except Exception as e:
        print(f"Error creating consistent par files: {e}")
        print(
            "This is expected if the actual par files are not available in the test environment"
        )


def combination_strategy_comparison():
    """Demonstrate the difference between combination strategies."""
    print("\n=== Combination Strategy Comparison ===")

    factory = MetaPulsarFactory()

    # Composite strategy (Borg/FrankenStat method)
    print("Creating MetaPulsar with composite strategy...")
    metapulsar_composite = factory.create_metapulsar(
        "J1909-3744", ["epta_dr2", "ppta_dr2"], combination_strategy="composite"
    )
    print(f"Composite strategy: {metapulsar_composite.combination_strategy}")
    print("  - Uses raw par files without modification")
    print("  - Preserves PTA-specific parameter differences")
    print("  - Suitable for 'Borg' or 'FrankenStat' analysis methods")

    # Consistent strategy (Astrophysical consistency)
    print("\nCreating MetaPulsar with consistent strategy...")
    metapulsar_consistent = factory.create_metapulsar(
        "J1909-3744",
        ["epta_dr2", "ppta_dr2"],
        combination_strategy="consistent",
        reference_pta="epta_dr2",
        combine_components=["spin", "astrometry", "binary", "dispersion"],
    )
    print(f"Consistent strategy: {metapulsar_consistent.combination_strategy}")
    print("  - Uses astrophysically consistent par files")
    print("  - Aligns parameters to reference PTA values")
    print("  - Suitable for unified gravitational wave analysis")


def main():
    """Run all usage examples."""
    print("ParFileManager and MetaPulsarFactory Usage Examples")
    print("=" * 60)

    try:
        basic_usage_example()
        custom_pta_registry_example()
        advanced_usage_example()
        direct_parfile_manager_example()
        combination_strategy_comparison()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Basic MetaPulsarFactory usage")
        print("✓ Custom PTA registry configuration")
        print("✓ Advanced parameter control")
        print("✓ Direct ParFileManager usage")
        print("✓ Combination strategy comparison")
        print("✓ Combination strategy tracking in MetaPulsar")

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Note: Some examples may fail if actual par files are not available")
        print("in the test environment. This is expected behavior.")


if __name__ == "__main__":
    main()
