#!/usr/bin/env python3
"""
Meta-Pulsar Factory Usage Example

This example demonstrates how to use the new dictionary-based PTA Registry
and MetaPulsar Factory to create MetaPulsars from multiple PTA datasets.

Usage:
    python examples/factory_usage_example.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ipta_metapulsar import PTARegistry, MetaPulsarFactory


def main():
    """Demonstrate MetaPulsar Factory usage."""

    print("=== Meta-Pulsar Factory Usage Example ===\n")

    # 1. Create PTA Registry
    print("1. Creating PTA Registry...")
    registry = PTARegistry()
    print(f"   Loaded {len(registry.configs)} PTA configurations")
    print(f"   Available PTAs: {', '.join(registry.list_ptas())}\n")

    # 2. Create MetaPulsar Factory
    print("2. Creating MetaPulsar Factory...")
    factory = MetaPulsarFactory(registry)
    print("   Factory created successfully\n")

    # 3. Demonstrate PTA Registry operations
    print("3. PTA Registry Operations:")

    # List PTAs by timing package
    pint_ptas = registry.get_ptas_by_timing_package("pint")
    tempo2_ptas = registry.get_ptas_by_timing_package("tempo2")
    print(f"   PINT PTAs: {pint_ptas}")
    print(f"   Tempo2 PTAs: {tempo2_ptas}")

    # List PTAs by coordinate system
    equatorial_ptas = registry.get_ptas_by_coordinates("equatorial")
    ecliptical_ptas = registry.get_ptas_by_coordinates("ecliptical")
    print(f"   Equatorial PTAs: {equatorial_ptas}")
    print(f"   Ecliptical PTAs: {ecliptical_ptas}\n")

    # 4. Add a custom PTA configuration
    print("4. Adding Custom PTA Configuration:")
    custom_config = {
        "base_dir": "/data/custom_pta",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
        "coordinates": "equatorial",
        "timing_package": "pint",
        "priority": 1,
        "description": "Custom PTA for demonstration",
    }

    try:
        registry.add_pta("custom_pta", custom_config)
        print("   ✅ Custom PTA added successfully")
        print(f"   Total PTAs now: {len(registry.configs)}")
    except ValueError as e:
        print(f"   ❌ Error adding custom PTA: {e}")

    print()

    # 5. Demonstrate file discovery (mock)
    print("5. File Discovery (Mock):")
    print(
        "   Note: This is a demonstration - actual file discovery requires real data files"
    )

    # Mock file discovery for demonstration
    try:
        # This would normally discover real files
        available_pulsars = factory.discover_available_pulsars(["epta_dr2", "ppta_dr3"])
        print(f"   Discovered {len(available_pulsars)} pulsars across specified PTAs")
        if available_pulsars:
            print(f"   Example pulsars: {available_pulsars[:3]}...")
    except Exception as e:
        print(f"   File discovery requires real data files: {e}")

    print()

    # 6. Demonstrate PTA configuration access
    print("6. PTA Configuration Access:")

    # Get specific PTA configuration
    epta_config = registry.get_pta("epta_dr2")
    print("   EPTA DR2 Configuration:")
    print(f"     Base Directory: {epta_config['base_dir']}")
    print(f"     Coordinates: {epta_config['coordinates']}")
    print(f"     Timing Package: {epta_config['timing_package']}")
    print(f"     Priority: {epta_config['priority']}")

    # Get subset of PTAs
    subset = registry.get_pta_subset(["epta_dr2", "ppta_dr3"])
    print(f"   Subset of 2 PTAs: {list(subset.keys())}")

    print()

    # 7. Demonstrate error handling
    print("7. Error Handling:")

    # Try to get non-existent PTA
    try:
        registry.get_pta("nonexistent_pta")
    except KeyError as e:
        print(f"   ✅ Caught expected error: {e}")

    # Try to add invalid configuration
    try:
        registry.add_pta(
            "invalid_pta", {"base_dir": "/data"}
        )  # Missing required fields
    except ValueError as e:
        print(f"   ✅ Caught validation error: {e}")

    print()

    # 8. Show registry statistics
    print("8. Registry Statistics:")
    print(f"   Total PTAs: {len(registry)}")
    print(f"   PINT PTAs: {len(registry.get_ptas_by_timing_package('pint'))}")
    print(f"   Tempo2 PTAs: {len(registry.get_ptas_by_timing_package('tempo2'))}")
    print(
        f"   PTAs that use equatorial coordinates: {len(registry.get_ptas_by_coordinates('equatorial'))}"
    )
    print(
        f"   PTAs that use ecliptical coordinates: {len(registry.get_ptas_by_coordinates('ecliptical'))}"
    )

    print()
    print("=== Example Complete ===")
    print("\nNext steps:")
    print("- Use factory.create_metapulsar() with real data files")
    print("- Use factory.create_all_metapulsars() to process all available pulsars")
    print("- Add more custom PTA configurations as needed")


if __name__ == "__main__":
    main()
