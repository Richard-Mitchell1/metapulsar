#!/usr/bin/env python3
"""
Compare MetaPulsars created with new code against feather files from legacy implementation.

This script loads feather files created with the legacy code and compares them
against MetaPulsars created with the new implementation. It follows the same
pattern as the legacy comparison tests but works with the actual feather files.

Usage:
    python examples/compare_feather_metapulsars.py [pulsar_name]
    
If no pulsar name is provided, it will run on a single test pulsar.
"""

import sys
import os
from pathlib import Path
import numpy as np
from typing import List, Optional
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metapulsar.file_discovery_service import FileDiscoveryService
from metapulsar.metapulsar_factory import MetaPulsarFactory
from metapulsar.position_helpers import discover_pulsars_by_coordinates_optimized

# Import Enterprise FeatherPulsar for loading feather files
try:
    from enterprise.pulsar import FeatherPulsar
except ImportError:
    print("ERROR: Enterprise not available. Cannot load feather files.")
    sys.exit(1)


class FeatherMetaPulsarComparison:
    """Compare MetaPulsars against feather files from legacy implementation."""

    def __init__(
        self,
        feather_dir: str = "/workspaces/metapulsar/data/legacy-binary/hdf5-feather",
    ):
        """Initialize the comparison.

        Args:
            feather_dir: Directory containing feather files
        """
        self.feather_dir = Path(feather_dir)
        self.working_dir = Path("/workspaces/metapulsar/data/ipta-dr2")

        # Initialize services
        self.file_discovery_service = FileDiscoveryService(
            working_dir=str(self.working_dir)
        )
        self.metapulsar_factory = MetaPulsarFactory()

        print(f"Feather directory: {self.feather_dir}")
        print(f"Working directory: {self.working_dir}")

    def get_available_feather_pulsars(self) -> List[str]:
        """Get list of available pulsar names from feather files."""
        feather_files = list(self.feather_dir.glob("*.feather"))
        pulsar_names = [f.stem for f in feather_files]
        return sorted(pulsar_names)

    def load_feather_pulsar(self, pulsar_name: str):
        """Load a pulsar from feather file."""
        feather_path = self.feather_dir / f"{pulsar_name}.feather"
        if not feather_path.exists():
            raise FileNotFoundError(f"Feather file not found: {feather_path}")

        print(f"Loading feather pulsar: {pulsar_name}")
        feather_pulsar = FeatherPulsar.read_feather(str(feather_path))
        return feather_pulsar

    def create_new_metapulsar(self, pulsar_name: str):
        """Create a new MetaPulsar using the current implementation."""
        print(f"Creating new MetaPulsar for: {pulsar_name}")

        # Discover files for all PTAs
        file_data = self.file_discovery_service.discover_files()

        # Find pulsar data using coordinate-based discovery
        pulsar_groups = discover_pulsars_by_coordinates_optimized(file_data)

        if pulsar_name not in pulsar_groups:
            raise ValueError(f"No data found for pulsar {pulsar_name}")

        pulsar_data = pulsar_groups[pulsar_name]

        # Create MetaPulsar
        metapulsar = self.metapulsar_factory.create_metapulsar(
            pulsar_data, combination_strategy="consistent"
        )

        return metapulsar

    def compare_pulsars(self, feather_pulsar, new_metapulsar, pulsar_name: str):
        """Compare feather pulsar with new MetaPulsar."""
        print(f"\n=== Comparing {pulsar_name} ===")

        # Debug: Print available attributes to understand the data structure
        print(
            f"FeatherPulsar attributes: {[attr for attr in dir(feather_pulsar) if not attr.startswith('_')]}"
        )
        print(
            f"MetaPulsar attributes: {[attr for attr in dir(new_metapulsar) if not attr.startswith('_')]}"
        )

        # Check for unsorted data attributes
        print(f"FeatherPulsar has _toas: {hasattr(feather_pulsar, '_toas')}")
        print(f"FeatherPulsar has _residuals: {hasattr(feather_pulsar, '_residuals')}")
        print(f"FeatherPulsar has _ssbfreqs: {hasattr(feather_pulsar, '_ssbfreqs')}")
        print(f"MetaPulsar has _toas: {hasattr(new_metapulsar, '_toas')}")
        print(f"MetaPulsar has _residuals: {hasattr(new_metapulsar, '_residuals')}")
        print(f"MetaPulsar has _ssbfreqs: {hasattr(new_metapulsar, '_ssbfreqs')}")

        # Check for sorting information
        print(f"FeatherPulsar has isort: {hasattr(feather_pulsar, 'isort')}")
        print(f"MetaPulsar has isort: {hasattr(new_metapulsar, 'isort')}")

        # Check if we can access the original unsorted data
        if hasattr(feather_pulsar, "stoas"):
            print(
                f"FeatherPulsar stoas shape: {feather_pulsar.stoas.shape if hasattr(feather_pulsar.stoas, 'shape') else 'No shape'}"
            )
        if hasattr(new_metapulsar, "stoas"):
            print(
                f"MetaPulsar stoas shape: {new_metapulsar.stoas.shape if hasattr(new_metapulsar.stoas, 'shape') else 'No shape'}"
            )

        # Check if this pulsar has NANOGrav data (reference PTA for feather files)
        print(
            f"MetaPulsar PTAs: {list(new_metapulsar._epulsars.keys()) if hasattr(new_metapulsar, '_epulsars') else 'Unknown'}"
        )
        has_nanograv = "nanograv_9y" in (
            new_metapulsar._epulsars.keys()
            if hasattr(new_metapulsar, "_epulsars")
            else []
        )
        print(f"Has NANOGrav data: {has_nanograv}")
        if not has_nanograv:
            print(
                "WARNING: No NANOGrav data found - reference PTA unknown for feather files"
            )

        # Debug: Check isort and data shapes
        print(
            f"MetaPulsar isort shape: {new_metapulsar.isort.shape if hasattr(new_metapulsar, 'isort') else 'No isort'}"
        )
        print(
            f"MetaPulsar toas shape: {new_metapulsar.toas.shape if hasattr(new_metapulsar, 'toas') else 'No toas'}"
        )
        print(
            f"FeatherPulsar toas shape: {feather_pulsar.toas.shape if hasattr(feather_pulsar, 'toas') else 'No toas'}"
        )
        print(
            f"MetaPulsar toas range: {new_metapulsar.toas.min():.2f} to {new_metapulsar.toas.max():.2f}"
        )
        print(
            f"FeatherPulsar toas range: {feather_pulsar.toas.min():.2f} to {feather_pulsar.toas.max():.2f}"
        )

        # Test the specific comparison you suggested
        if len(feather_pulsar.residuals) == len(new_metapulsar.residuals):
            legacy_isort = np.argsort(feather_pulsar.toas)

            # Check if the sorting indices are the same
            print(f"Legacy isort range: {legacy_isort.min()} to {legacy_isort.max()}")
            print(
                f"New isort range: {new_metapulsar.isort.min()} to {new_metapulsar.isort.max()}"
            )
            print(
                f"Are isort arrays identical: {np.array_equal(legacy_isort, new_metapulsar.isort)}"
            )

            # Check actual differences
            toas_diff = np.abs(
                feather_pulsar.toas[legacy_isort]
                - new_metapulsar.toas[new_metapulsar.isort]
            )
            residuals_diff = np.abs(
                feather_pulsar.residuals[legacy_isort]
                - new_metapulsar.residuals[new_metapulsar.isort]
            )
            freqs_diff = np.abs(
                feather_pulsar.freqs[legacy_isort]
                - new_metapulsar.freqs[new_metapulsar.isort]
            )

            print(f"TOAs max diff: {toas_diff.max():.2e}")
            print(f"Residuals max diff: {residuals_diff.max():.2e}")
            print(f"Frequencies max diff: {freqs_diff.max():.2e}")

            residuals_match = np.allclose(
                feather_pulsar.residuals[legacy_isort],
                new_metapulsar.residuals[new_metapulsar.isort],
            )
            print(f"Residuals allclose test: {residuals_match}")

            toas_match = np.allclose(
                feather_pulsar.toas[legacy_isort],
                new_metapulsar.toas[new_metapulsar.isort],
            )
            print(f"TOAs allclose test: {toas_match}")

            freqs_match = np.allclose(
                feather_pulsar.freqs[legacy_isort],
                new_metapulsar.freqs[new_metapulsar.isort],
            )
            print(f"Frequencies allclose test: {freqs_match}")

        comparisons = {}

        # Basic properties
        comparisons["name"] = {
            "feather": feather_pulsar.name,
            "new": new_metapulsar.name,
            "match": feather_pulsar.name == new_metapulsar.name,
        }

        # Data sizes
        comparisons["n_toas"] = {
            "feather": len(feather_pulsar.toas),
            "new": len(new_metapulsar.toas),
            "match": len(feather_pulsar.toas) == len(new_metapulsar.toas),
        }

        # Check if fitpars exists (FeatherPulsar might not have it)
        feather_fitpars = getattr(feather_pulsar, "fitpars", [])
        comparisons["n_params"] = {
            "feather": len(feather_fitpars),
            "new": len(new_metapulsar.fitpars),
            "match": len(feather_fitpars) == len(new_metapulsar.fitpars),
        }

        # Design matrix shape
        feather_dm_shape = feather_pulsar.Mmat.shape
        new_dm_shape = new_metapulsar.Mmat.shape
        comparisons["design_matrix_shape"] = {
            "feather": feather_dm_shape,
            "new": new_dm_shape,
            "match": feather_dm_shape == new_dm_shape,
        }

        # Position
        feather_pos = feather_pulsar.pos
        new_pos = new_metapulsar.pos
        pos_diff = np.linalg.norm(feather_pos - new_pos)
        comparisons["position"] = {
            "feather": feather_pos,
            "new": new_pos,
            "difference": pos_diff,
            "match": pos_diff < 1e-10,
        }

        # Distance
        feather_dist = feather_pulsar.pdist
        new_dist = new_metapulsar.pdist
        dist_diff = abs(feather_dist[0] - new_dist[0])
        comparisons["distance"] = {
            "feather": feather_dist,
            "new": new_dist,
            "difference": dist_diff,
            "match": dist_diff < 1e-6,
        }

        # TOAs comparison (if same length)
        if len(feather_pulsar.toas) == len(new_metapulsar.toas):
            # Both datasets need to be sorted consistently
            # Get sorting indices for both datasets
            legacy_isort = np.argsort(feather_pulsar.toas)
            new_isort = new_metapulsar.isort

            # Compare both datasets in their sorted order
            toa_diff = np.max(
                np.abs(
                    feather_pulsar.toas[legacy_isort] - new_metapulsar.toas[new_isort]
                )
            )

            comparisons["toas"] = {"max_difference": toa_diff, "match": toa_diff < 1e-6}

        # Residuals comparison (if same length)
        if len(feather_pulsar.residuals) == len(new_metapulsar.residuals):
            # Both datasets need to be sorted consistently
            # Get sorting indices for both datasets
            legacy_isort = np.argsort(feather_pulsar.toas)
            new_isort = new_metapulsar.isort

            # Compare residuals in sorted order
            res_diff = np.max(
                np.abs(
                    feather_pulsar.residuals[legacy_isort]
                    - new_metapulsar.residuals[new_isort]
                )
            )

            comparisons["residuals"] = {
                "max_difference": res_diff,
                "match": res_diff < 1e-6,
            }

        # Frequencies comparison (if same length)
        if len(feather_pulsar.freqs) == len(new_metapulsar.freqs):
            # Both datasets need to be sorted consistently
            # Get sorting indices for both datasets
            legacy_isort = np.argsort(feather_pulsar.toas)
            new_isort = new_metapulsar.isort

            # Compare frequencies in sorted order
            freq_diff = np.max(
                np.abs(
                    feather_pulsar.freqs[legacy_isort] - new_metapulsar.freqs[new_isort]
                )
            )

            comparisons["frequencies"] = {
                "max_difference": freq_diff,
                "match": freq_diff < 1e-6,
            }

        # Print results
        print(
            f"Name: {comparisons['name']['feather']} vs {comparisons['name']['new']} - {'✓' if comparisons['name']['match'] else '✗'}"
        )
        print(
            f"TOAs: {comparisons['n_toas']['feather']} vs {comparisons['n_toas']['new']} - {'✓' if comparisons['n_toas']['match'] else '✗'}"
        )
        print(
            f"Parameters: {comparisons['n_params']['feather']} vs {comparisons['n_params']['new']} - {'✓' if comparisons['n_params']['match'] else '✗'}"
        )
        print(
            f"Design Matrix: {comparisons['design_matrix_shape']['feather']} vs {comparisons['design_matrix_shape']['new']} - {'✓' if comparisons['design_matrix_shape']['match'] else '✗'}"
        )
        print(
            f"Position diff: {comparisons['position']['difference']:.2e} - {'✓' if comparisons['position']['match'] else '✗'}"
        )
        print(
            f"Distance diff: {comparisons['distance']['difference']:.2e} - {'✓' if comparisons['distance']['match'] else '✗'}"
        )

        if "toas" in comparisons:
            print(
                f"TOAs max diff: {comparisons['toas']['max_difference']:.2e} - {'✓' if comparisons['toas']['match'] else '✗'}"
            )
        if "residuals" in comparisons:
            print(
                f"Residuals max diff: {comparisons['residuals']['max_difference']:.2e} - {'✓' if comparisons['residuals']['match'] else '✗'}"
            )
        if "frequencies" in comparisons:
            print(
                f"Frequencies max diff: {comparisons['frequencies']['max_difference']:.2e} - {'✓' if comparisons['frequencies']['match'] else '✗'}"
            )

        return comparisons

    def run_comparison(self, pulsar_name: Optional[str] = None):
        """Run comparison for a specific pulsar or all available pulsars."""
        available_pulsars = self.get_available_feather_pulsars()

        if pulsar_name:
            if pulsar_name not in available_pulsars:
                print(f"ERROR: Pulsar {pulsar_name} not found in feather files.")
                print(f"Available pulsars: {available_pulsars[:10]}...")
                return
            pulsars_to_test = [pulsar_name]
        else:
            # Default to first pulsar for testing
            pulsars_to_test = [available_pulsars[0]]
            print(f"No pulsar specified, testing with: {pulsars_to_test[0]}")

        print(f"Available feather pulsars: {len(available_pulsars)}")
        print(f"Testing pulsars: {pulsars_to_test}")

        results = {}

        for pulsar_name in pulsars_to_test:
            try:
                print(f"\n{'='*60}")
                print(f"Processing {pulsar_name}")
                print(f"{'='*60}")

                start_time = time.time()

                # Load feather pulsar
                feather_pulsar = self.load_feather_pulsar(pulsar_name)

                # Create new MetaPulsar
                new_metapulsar = self.create_new_metapulsar(pulsar_name)

                # Compare
                comparison_results = self.compare_pulsars(
                    feather_pulsar, new_metapulsar, pulsar_name
                )

                elapsed_time = time.time() - start_time
                print(f"\nCompleted in {elapsed_time:.2f} seconds")

                results[pulsar_name] = {
                    "success": True,
                    "comparison": comparison_results,
                    "elapsed_time": elapsed_time,
                }

            except Exception as e:
                print(f"ERROR processing {pulsar_name}: {e}")
                results[pulsar_name] = {
                    "success": False,
                    "error": str(e),
                    "elapsed_time": 0,
                }

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        successful = sum(1 for r in results.values() if r["success"])
        total = len(results)

        print(f"Processed: {total} pulsars")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")

        if successful > 0:
            avg_time = np.mean(
                [r["elapsed_time"] for r in results.values() if r["success"]]
            )
            print(f"Average time per pulsar: {avg_time:.2f} seconds")

        return results


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare MetaPulsars with feather files"
    )
    parser.add_argument("pulsar", nargs="?", help="Pulsar name to test (optional)")
    parser.add_argument(
        "--feather-dir",
        default="/workspaces/metapulsar/data/legacy-binary/hdf5-feather",
        help="Directory containing feather files",
    )

    args = parser.parse_args()

    # Create comparison instance
    comparison = FeatherMetaPulsarComparison(feather_dir=args.feather_dir)

    # Run comparison
    results = comparison.run_comparison(pulsar_name=args.pulsar)

    return results


if __name__ == "__main__":
    main()
