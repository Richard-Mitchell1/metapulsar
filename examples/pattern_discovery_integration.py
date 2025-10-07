#!/usr/bin/env python3
"""
Example: Integrating Pattern Discovery Engine with FileDiscoveryService

This example demonstrates how to use the LayoutDiscoveryService to automatically
discover patterns for new PTA data releases and integrate them with the existing
FileDiscoveryService.
"""

from pathlib import Path
from metapulsar import (
    LayoutDiscoveryService,
    FileDiscoveryService,
    PTA_DATA_RELEASES,
)


def discover_and_integrate_new_pta(
    data_dir: Path, pta_name: str, description: str = None
):
    """
    Discover patterns for a new PTA and integrate with FileDiscoveryService.

    Args:
        data_dir: Path to the PTA data directory
        pta_name: Name for the new PTA configuration
        description: Optional description for the PTA
    """
    print(f"🔍 Discovering patterns for {pta_name}...")

    # Initialize layout discovery service
    layout_service = LayoutDiscoveryService()

    # Step 1: Discover layout using new API
    print("  📁 Discovering layout...")
    discovered_layouts = layout_service.discover_layout(
        working_dir=str(data_dir), verbose=False
    )

    # Extract the configuration from the discovered layout
    discovered_data_release = list(discovered_layouts.values())[0]

    print("✅ Discovered data release:")
    print(f"   Par pattern: {discovered_data_release['par_pattern']}")
    print(f"   Tim pattern: {discovered_data_release['tim_pattern']}")
    print(f"   Timing package: {discovered_data_release['timing_package']}")
    print(f"   Confidence: {discovered_data_release['discovery_confidence']:.2f}")

    # Step 2: Create PTA data release for FileDiscoveryService
    pta_data_release = {
        "base_dir": str(data_dir),
        "par_pattern": discovered_data_release["par_pattern"],
        "tim_pattern": discovered_data_release["tim_pattern"],
        "timing_package": discovered_data_release["timing_package"],
        "description": description or f"Auto-discovered {pta_name}",
        "priority": 1,
    }

    # Step 3: Add to PTA_DATA_RELEASES
    PTA_DATA_RELEASES[pta_name] = pta_data_release
    print(f"✅ Added {pta_name} to PTA_DATA_RELEASES")

    return pta_data_release


def test_file_discovery_with_new_pta(pta_name: str):
    """
    Test FileDiscoveryService with the newly added PTA.

    Args:
        pta_name: Name of the PTA to test
    """
    print(f"\n🧪 Testing FileDiscoveryService with {pta_name}...")

    # IMPORTANT: Create a NEW FileDiscoveryService instance after modifying PTA_DATA_RELEASES
    # because FileDiscoveryService uses .copy() of PTA_DATA_RELEASES in its constructor
    file_service = FileDiscoveryService()

    try:
        # Discover patterns
        patterns = file_service.discover_patterns_in_data_release(pta_name)
        print(f"✅ Found {len(patterns)} patterns")

        # Discover file pairs
        file_pairs = file_service.discover_files([pta_name])
        print(f"✅ Found {len(file_pairs)} file pairs")

        # Show some examples
        if file_pairs:
            print("\n📁 Sample file pairs:")
            for i, pair in enumerate(file_pairs[:3]):
                par_file = pair.get("par_file", "N/A")
                tim_file = pair.get("tim_file", "N/A")
                if par_file != "N/A":
                    print(
                        f"   {i+1}. {Path(par_file).name} + {Path(tim_file).name if tim_file != 'N/A' else 'N/A'}"
                    )

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def compare_pta_patterns(pta_names: list):
    """
    Compare patterns across different PTAs.

    Args:
        pta_names: List of PTA names to compare
    """
    print("\n📊 Comparing PTA patterns:")
    print("=" * 60)

    for pta_name in pta_names:
        if pta_name in PTA_DATA_RELEASES:
            config = PTA_DATA_RELEASES[pta_name]
            print(f"\n{pta_name.upper()}:")
            print(f"  Par: {config['par_pattern']}")
            print(f"  Tim: {config['tim_pattern']}")
            print(f"  Timing: {config['timing_package']}")
        else:
            print(f"\n{pta_name.upper()}: Not found in configuration")


def main():
    """Main example function."""
    print("🚀 Pattern Discovery Engine + FileDiscoveryService Integration Example")
    print("=" * 80)

    # Example 1: Discover patterns for NANOGrav 15yr release
    print("\n1. DISCOVERING PATTERNS FOR NANOGRAV 15YR RELEASE")
    print("-" * 50)

    data_dir = Path("/workspaces/metapulsar/data-check/nanograv-15yr-release")
    if data_dir.exists():
        discover_and_integrate_new_pta(
            data_dir, "nanograv_15yr_zenodo", "NANOGrav 15-year Data Release (Zenodo)"
        )

        # Test the integration
        success = test_file_discovery_with_new_pta("nanograv_15yr_zenodo")

        if success:
            print("✅ Integration successful!")
        else:
            print("❌ Integration failed!")
    else:
        print(f"❌ Data directory not found: {data_dir}")

    # Example 2: Compare with existing PTAs
    print("\n2. COMPARING WITH EXISTING PTAs")
    print("-" * 50)

    existing_ptas = ["nanograv_9y", "nanograv_12y", "ppta_dr2", "nanograv_15yr_zenodo"]
    compare_pta_patterns(existing_ptas)

    # Example 3: Show workflow summary
    print("\n3. WORKFLOW SUMMARY")
    print("-" * 50)
    print(
        """
    The integration workflow is:
    
    1. 🔍 LayoutDiscoveryService analyzes new PTA data structure
    2. 🎯 Generates appropriate regex patterns automatically  
    3. 🔧 Detects timing package (PINT vs tempo2)
    4. 🚫 Filters out unwanted data (wideband, temp files)
    5. ➕ Adds discovered config to PTA_DATA_RELEASES
    6. 🧪 FileDiscoveryService uses new patterns to find files
    7. ✅ Both services work together seamlessly!
    
    Benefits:
    • No manual regex writing required
    • Handles complex directory structures automatically
    • Reduces human error in pattern creation
    • Scales to any PTA data release format
    """
    )


if __name__ == "__main__":
    main()
