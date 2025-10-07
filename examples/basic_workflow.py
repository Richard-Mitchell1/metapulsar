#!/usr/bin/env python3
"""
Basic MetaPulsar Workflow Example

This example demonstrates the complete workflow from file discovery
to MetaPulsar creation using the correct API.

Usage:
    python examples/basic_workflow.py
"""

from metapulsar import MetaPulsarFactory, FileDiscoveryService, discover_files


def main():
    """Demonstrate basic MetaPulsar workflow."""
    print("=== Basic MetaPulsar Workflow ===")

    # Step 1: Create file discovery service
    print("Step 1: Creating file discovery service...")
    discovery = FileDiscoveryService()

    # Step 2: List available PTAs
    print("Step 2: Listing available PTAs...")
    available_ptas = discovery.list_data_releases()
    print(f"Available PTAs: {available_ptas}")

    # Step 3: Discover files for specific PTAs
    print("Step 3: Discovering files for epta_dr2 and ppta_dr2...")
    file_data = discovery.discover_files(["epta_dr2", "ppta_dr2"])

    if not file_data:
        print("No files found - this is expected in test environment")
        print("In a real environment, this would discover actual par/tim files")
        print("Skipping MetaPulsar creation for demonstration purposes")
        return

    print(f"Found files for PTAs: {list(file_data.keys())}")
    for pta_name, files in file_data.items():
        print(f"  {pta_name}: {len(files)} file pairs")

    # Filter out PTAs with no files
    file_data_with_files = {pta: files for pta, files in file_data.items() if files}

    if not file_data_with_files:
        print("No PTAs have files - this is expected in test environment")
        print("In a real environment, this would discover actual par/tim files")
        print("Skipping MetaPulsar creation for demonstration purposes")
        return

    print(f"Using PTAs with files: {list(file_data_with_files.keys())}")

    # Step 4: Create MetaPulsar factory
    print("Step 4: Creating MetaPulsar factory...")
    factory = MetaPulsarFactory()

    # Step 5: Create MetaPulsar with composite strategy
    print("Step 5: Creating MetaPulsar with composite strategy...")
    metapulsar = factory.create_metapulsar(
        file_data_with_files, combination_strategy="composite"
    )
    print(f"MetaPulsar created with strategy: {metapulsar.combination_strategy}")

    # Step 6: Create MetaPulsar with consistent strategy
    print("Step 6: Creating MetaPulsar with consistent strategy...")
    # Use the first PTA with files as reference
    reference_pta = list(file_data_with_files.keys())[0]
    metapulsar_consistent = factory.create_metapulsar(
        file_data_with_files,
        combination_strategy="consistent",
        reference_pta=reference_pta,
    )
    print(
        f"MetaPulsar created with strategy: {metapulsar_consistent.combination_strategy}"
    )

    # Alternative: Using convenience functions
    print("\n=== Alternative: Using Convenience Functions ===")
    print("You can also use the convenience functions directly:")
    print("file_data = discover_files(data_release_names=['epta_dr2', 'ppta_dr2'])")

    # Demonstrate convenience function
    print("Demonstrating convenience function...")
    file_data_convenience = discover_files(data_release_names=["epta_dr2", "ppta_dr2"])
    print(f"Convenience function found files for: {list(file_data_convenience.keys())}")

    print("\n=== Workflow Complete ===")
    print(
        "This example demonstrates the complete workflow from file discovery to MetaPulsar creation."
    )


if __name__ == "__main__":
    main()
