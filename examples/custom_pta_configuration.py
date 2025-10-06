#!/usr/bin/env python3
"""
Custom PTA Configuration Example

This example demonstrates how to add custom PTA configurations
and use them in the MetaPulsar workflow.

Usage:
    python examples/custom_pta_configuration.py
"""

from metapulsar import FileDiscoveryService, MetaPulsarFactory


def main():
    """Demonstrate custom PTA configuration workflow."""
    print("=== Custom PTA Configuration Workflow ===")

    # Step 1: Create file discovery service
    print("Step 1: Creating file discovery service...")
    discovery = FileDiscoveryService()

    # Step 2: Add custom PTA configuration
    print("Step 2: Adding custom PTA configuration...")
    custom_config = {
        "base_dir": "/data/custom_pta/",
        "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.par",
        "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})_custom\.tim",
        "timing_package": "pint",
        "priority": 1,
        "description": "Custom PTA for demonstration",
    }

    discovery.add_pta("custom_pta", custom_config)
    print("Custom PTA added successfully")

    # Step 3: List all PTAs (including custom one)
    print("Step 3: Listing all PTAs...")
    all_ptas = discovery.list_ptas()
    print(f"All PTAs: {all_ptas}")

    # Step 4: Discover files for custom PTA
    print("Step 4: Discovering files for custom PTA...")
    file_data = discovery.discover_all_files_in_ptas(["custom_pta"])

    # Check if any PTAs have files
    file_data_with_files = {pta: files for pta, files in file_data.items() if files}

    if file_data_with_files:
        print("Files found for custom PTA")
        # Step 5: Create MetaPulsar with custom PTA
        print("Step 5: Creating MetaPulsar with custom PTA...")
        factory = MetaPulsarFactory()
        metapulsar = factory.create_metapulsar(
            file_data_with_files, combination_strategy="composite"
        )
        print(f"MetaPulsar created with custom PTA: {metapulsar.combination_strategy}")
    else:
        print("No files found for custom PTA - this is expected in test environment")
        print(
            "In a real environment, you would place par/tim files in the custom PTA directory"
        )
        print(
            "The custom PTA configuration has been successfully added to the discovery service"
        )

    print("\n=== Custom PTA Configuration Complete ===")
    print("This example demonstrates how to add and use custom PTA configurations.")


if __name__ == "__main__":
    main()
