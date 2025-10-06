#!/usr/bin/env python3
"""
Enterprise Integration Example

This example demonstrates how to integrate MetaPulsar with
the Enterprise framework for gravitational wave analysis.

Usage:
    python examples/enterprise_integration.py
"""

from metapulsar import (
    FileDiscoveryService,
    MetaPulsarFactory,
    create_staggered_selection,
)


def main():
    """Demonstrate Enterprise integration workflow."""
    print("=== Enterprise Integration Workflow ===")

    # Step 1: Create file discovery service
    print("Step 1: Creating file discovery service...")
    discovery = FileDiscoveryService()

    # Step 2: Discover files
    print("Step 2: Discovering files for epta_dr2 and ppta_dr2...")
    file_data = discovery.discover_all_files_in_ptas(["epta_dr2", "ppta_dr2"])

    if not file_data:
        print("No files found - this is expected in test environment")
        return

    # Filter out PTAs with no files
    file_data_with_files = {pta: files for pta, files in file_data.items() if files}

    if not file_data_with_files:
        print("No PTAs have files - this is expected in test environment")
        return

    print(f"Using PTAs with files: {list(file_data_with_files.keys())}")

    # Step 3: Create MetaPulsar
    print("Step 3: Creating MetaPulsar...")
    factory = MetaPulsarFactory()
    # Use the first PTA with files as reference
    reference_pta = list(file_data_with_files.keys())[0]
    factory.create_metapulsar(
        file_data_with_files,
        combination_strategy="consistent",
        reference_pta=reference_pta,
    )

    # Step 4: Create staggered selection for Enterprise
    print("Step 4: Creating staggered selection for Enterprise...")

    # Create staggered selection function
    selection_func = create_staggered_selection(
        name="telescope_backend_selection",
        flag_criteria={
            "telescope": None,  # Primary flag
            ("backend", "freq_band"): None,  # Fallback flags
        },
        freq_range=(50, 2000),  # Frequency range
    )

    # TODO: Add actual enterprise integration here

    print(f"Staggered selection function created: {selection_func.__name__}")

    # Step 5: Demonstrate Enterprise integration
    print("Step 5: Demonstrating Enterprise integration...")
    print("In a real scenario, you would:")
    print("1. Use the MetaPulsar data with Enterprise models")
    print("2. Apply the staggered selection to your analysis")
    print("3. Run gravitational wave searches")

    print("\n=== Enterprise Integration Complete ===")
    print("This example demonstrates how to integrate MetaPulsar with Enterprise.")


if __name__ == "__main__":
    main()
