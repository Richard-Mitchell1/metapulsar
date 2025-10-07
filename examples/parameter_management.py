#!/usr/bin/env python3
"""
Parameter Management Example

This example demonstrates how to use ParameterManager for
astrophysical consistency across multiple PTAs.

Usage:
    python examples/parameter_management.py
"""

from metapulsar import FileDiscoveryService, ParameterManager


def main():
    """Demonstrate parameter management workflow."""
    print("=== Parameter Management Workflow ===")

    # Step 1: Create file discovery service
    print("Step 1: Creating file discovery service...")
    discovery = FileDiscoveryService()

    # Step 2: Discover files
    print("Step 2: Discovering files for epta_dr2 and ppta_dr2...")
    file_data = discovery.discover_files(["epta_dr2", "ppta_dr2"])

    if not file_data:
        print("No files found - this is expected in test environment")
        return

    # Step 3: Convert to single file per PTA format for ParameterManager
    print("Step 3: Preparing file data for ParameterManager...")
    single_file_data = {}
    for pta_name, file_list in file_data.items():
        if file_list:
            single_file_data[pta_name] = file_list[0]  # Take first file

    # Step 4: Create ParameterManager
    print("Step 4: Creating ParameterManager...")
    param_manager = ParameterManager(
        file_data=single_file_data,
        reference_pta="epta_dr2",
        combine_components=["astrometry", "spindown", "binary", "dispersion"],
        add_dm_derivatives=True,
    )

    # Step 5: Build parameter mappings
    print("Step 5: Building parameter mappings...")
    try:
        mapping = param_manager.build_parameter_mappings()
        print("Parameter mapping created successfully")
        print(f"Merged parameters: {len(mapping.merged_parameters)}")
        print(f"PTA-specific parameters: {len(mapping.pta_specific_parameters)}")
    except Exception as e:
        print(f"Parameter mapping failed (expected with mock data): {e}")

    print("\n=== Parameter Management Complete ===")
    print("This example demonstrates how to manage parameters across multiple PTAs.")


if __name__ == "__main__":
    main()
