#!/usr/bin/env python3
"""
Phase 1: Heuristic-based Pattern Detection for PTA Data Releases

This module provides automatic pattern discovery for PTA data releases
without requiring machine learning or external dependencies.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import re
from collections import defaultdict, Counter
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from loguru import logger


class PatternDiscoveryEngine:
    """Heuristic-based pattern discovery for PTA data releases."""

    def __init__(self):
        self.logger = logger
        # Common PTA patterns we've seen
        self.known_pulsar_patterns = [
            r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)",  # Standard B/J names
            r"([BJ]\d{4}[+-]\d{2,4})",  # Without optional suffix
        ]

        # Common directory structures
        self.common_subdirs = ["par", "tim", "data", "pulsars"]

        # Common file extensions and their purposes
        self.file_types = {
            ".par": "parameter",
            ".tim": "timing",
            ".gls": "glitch",
            ".t2": "tempo2",
        }

    def analyze_directory_structure(self, base_path: Path) -> Dict[str, Any]:
        """Analyze a directory structure and infer PTA patterns."""
        if not base_path.exists():
            raise ValueError(f"Directory {base_path} does not exist")

        self.logger.info(f"Analyzing directory structure: {base_path}")

        # Find all par and tim files, filtering out wideband data
        par_files = [
            f for f in base_path.rglob("*.par") if not self._is_wideband_file(f)
        ]
        tim_files = [
            f for f in base_path.rglob("*.tim") if not self._is_wideband_file(f)
        ]

        if not par_files:
            raise ValueError(f"No .par files found in {base_path}")

        self.logger.info(
            f"Found {len(par_files)} par files and {len(tim_files)} tim files"
        )

        # Analyze structure
        structure = {
            "base_path": str(base_path),
            "par_files": [str(f) for f in par_files],
            "tim_files": [str(f) for f in tim_files],
            "directory_depth": self._analyze_depth(base_path),
            "subdirectory_structure": self._analyze_subdirs(base_path),
            "file_naming_patterns": self._analyze_naming_patterns(par_files, tim_files),
            "pulsar_names": self._extract_pulsar_names(par_files),
        }

        return structure

    def generate_pta_data_release(
        self, structure: Dict, timing_package: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a complete PTA data release from structure analysis."""

        # Use user input if provided, otherwise detect
        if timing_package:
            detected_timing_package = timing_package
        else:
            detected_timing_package = self._detect_timing_package(
                structure["par_files"]
            )

        # Generate patterns
        par_pattern = self._generate_par_pattern(structure)
        tim_pattern = self._generate_tim_pattern(structure)

        # Determine base directory (relative to structure base)
        base_dir = self._determine_base_dir(structure)

        data_release = {
            "base_dir": base_dir,
            "par_pattern": par_pattern,
            "tim_pattern": tim_pattern,
            "timing_package": detected_timing_package,
            "priority": 1,  # Default priority
            "description": f"Auto-discovered PTA from {structure['base_path']}",
            "discovery_confidence": self._calculate_confidence(structure),
        }

        return data_release

    def _analyze_depth(self, base_path: Path) -> int:
        """Analyze maximum directory depth."""
        max_depth = 0
        for path in base_path.rglob("*"):
            if path.is_file():
                depth = len(path.relative_to(base_path).parts) - 1
                max_depth = max(max_depth, depth)
        return max_depth

    def _analyze_subdirs(self, base_path: Path) -> Dict[str, int]:
        """Analyze subdirectory usage patterns."""
        subdir_counts = defaultdict(int)

        for path in base_path.rglob("*"):
            if path.is_dir():
                rel_path = path.relative_to(base_path)
                if len(rel_path.parts) == 1:  # Direct subdirectories
                    subdir_counts[rel_path.name] += 1

        return dict(subdir_counts)

    def _analyze_naming_patterns(
        self, par_files: List[Path], tim_files: List[Path]
    ) -> Dict[str, Any]:
        """Analyze file naming patterns."""
        patterns = {
            "par_naming": self._analyze_file_naming(par_files),
            "tim_naming": self._analyze_file_naming(tim_files),
            "common_prefixes": self._find_common_prefixes(par_files + tim_files),
            "common_suffixes": self._find_common_suffixes(par_files + tim_files),
        }
        return patterns

    def _analyze_file_naming(self, files: List[Path]) -> Dict[str, Any]:
        """Analyze naming patterns in a list of files."""
        if not files:
            return {}

        # Get relative paths from base
        base = files[0].parent
        while not all(f.is_relative_to(base) for f in files):
            base = base.parent

        rel_paths = [f.relative_to(base) for f in files]

        # Analyze patterns
        naming = {
            "has_subdirs": any(len(p.parts) > 1 for p in rel_paths),
            "common_subdirs": self._find_common_subdirs(rel_paths),
            "file_stems": [p.stem for p in rel_paths],
            "extensions": [p.suffix for p in rel_paths],
        }

        return naming

    def _find_common_subdirs(self, paths: List[Path]) -> List[str]:
        """Find common subdirectory patterns."""
        subdirs = []
        for path in paths:
            if len(path.parts) > 1:
                subdirs.extend(path.parts[:-1])  # All parts except filename

        # Count and return most common
        subdir_counts = Counter(subdirs)
        return [subdir for subdir, count in subdir_counts.most_common(3)]

    def _find_common_prefixes(self, files: List[Path]) -> List[str]:
        """Find common prefixes in filenames."""
        stems = [f.stem for f in files]
        if not stems:
            return []

        # Find longest common prefix
        common_prefix = ""
        for i in range(min(len(s) for s in stems)):
            if all(s[i] == stems[0][i] for s in stems):
                common_prefix += stems[0][i]
            else:
                break

        return [common_prefix] if common_prefix else []

    def _find_common_suffixes(self, files: List[Path]) -> List[str]:
        """Find common suffixes in filenames."""
        stems = [f.stem for f in files]
        if not stems:
            return []

        # Find longest common suffix
        common_suffix = ""
        for i in range(1, min(len(s) for s in stems) + 1):
            if all(s[-i:] == stems[0][-i:] for s in stems):
                common_suffix = stems[0][-i:] + common_suffix
            else:
                break

        return [common_suffix] if common_suffix else []

    def _extract_pulsar_names(self, par_files: List[Path]) -> List[str]:
        """Extract pulsar names using existing pattern matching."""
        pulsar_names = []

        for file_path in par_files:
            for pattern in self.known_pulsar_patterns:
                try:
                    match = re.search(pattern, str(file_path))
                    if match:
                        pulsar_names.append(match.group(1))
                        break
                except re.error:
                    continue

        return list(set(pulsar_names))  # Remove duplicates

    def _is_wideband_file(self, file_path: Path) -> bool:
        """
        Check if a file is wideband data that should be ignored.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file is wideband data and should be ignored
        """
        # Convert to string for easier checking
        path_str = str(file_path).lower()

        # Check for wideband indicators in the path
        wideband_indicators = ["wideband", "wb_", "_wb", "wide_band", "wide-band"]

        for indicator in wideband_indicators:
            if indicator in path_str:
                return True

        return False

    def _find_common_path_parts(self, rel_paths: List[Path]) -> List[str]:
        """
        Find common path parts in a list of relative paths.

        Args:
            rel_paths: List of relative paths

        Returns:
            List of common path parts
        """
        if not rel_paths:
            return []

        # Start with the first path
        common_parts = list(rel_paths[0].parts)

        # Find common parts with other paths
        for path in rel_paths[1:]:
            path_parts = list(path.parts)
            # Keep only the parts that match
            common_parts = [
                part
                for i, part in enumerate(common_parts)
                if i < len(path_parts) and path_parts[i] == part
            ]

            if not common_parts:
                break

        return common_parts

    def _detect_timing_package(self, par_files: List[str]) -> str:
        """Detect timing package from par file content."""
        if not par_files:
            return "tempo2"  # Default

        # Check more files for better detection
        sample_files = par_files[:10]  # Check first 10 files

        for par_file_path in sample_files:
            try:
                par_file = Path(par_file_path)
                content = par_file.read_text(encoding="utf-8", errors="ignore")

                # BINARY T2 is definitive for tempo2 - check this first
                if "BINARY" in content and "T2" in content:
                    # Check if BINARY and T2 are on the same line
                    lines = content.split("\n")
                    for line in lines:
                        if "BINARY" in line and "T2" in line:
                            self.logger.info(
                                f"Found BINARY T2 in {par_file.name} - detected tempo2"
                            )
                            return "tempo2"

            except Exception as e:
                self.logger.warning(f"Could not read {par_file_path}: {e}")
                continue

        # Check for PINT comments in par files
        for par_file_path in sample_files:
            try:
                par_file = Path(par_file_path)
                content = par_file.read_text(encoding="utf-8", errors="ignore")

                # Look for PINT comments - lines starting with #
                lines = content.split("\n")
                for line in lines:
                    if line.strip().startswith("#") and "pint" in line.lower():
                        self.logger.info(
                            f"Found PINT comment in {par_file.name} - detected pint"
                        )
                        return "pint"

            except Exception as e:
                self.logger.warning(f"Could not read {par_file_path}: {e}")
                continue

        # Check if this is a NANOGrav PTA (always uses PINT)
        for par_file_path in sample_files:
            if "nanograv" in par_file_path.lower():
                self.logger.info("NANOGrav PTA detected - defaulting to PINT")
                return "pint"

        # If no BINARY T2 found, use other heuristics
        for par_file_path in sample_files:
            try:
                par_file = Path(par_file_path)
                content = par_file.read_text(encoding="utf-8", errors="ignore")

                # Look for PINT-specific indicators
                if any(
                    indicator in content.lower()
                    for indicator in ["pint", "enterprise", "gls", "glitch", "nanograv"]
                ):
                    return "pint"

                # Look for tempo2-specific indicators
                if any(
                    indicator in content.lower()
                    for indicator in ["tempo2", "t2", "jodrell", "epta", "ppta"]
                ):
                    return "tempo2"

            except Exception as e:
                self.logger.warning(f"Could not read {par_file_path}: {e}")
                continue

        return "tempo2"  # Default fallback

    def _generate_par_pattern(self, structure: Dict) -> str:
        """Generate par file pattern from structure analysis."""
        pulsar_names = structure["pulsar_names"]

        if not pulsar_names:
            # Fallback to generic pattern
            return r"([BJ]\d{4}[+-]\d{2,4}[A-Z]?)\.par"

        # Use the most common pulsar name pattern found
        pulsar_pattern = self.known_pulsar_patterns[0]  # Default to standard pattern

        # Analyze the actual file structure
        par_files = [Path(f) for f in structure["par_files"]]
        if not par_files:
            return f"{pulsar_pattern}\\.par"

        # Find the common base directory - start from the structure base path
        structure_base = Path(structure["base_path"])
        base = structure_base

        # Get relative paths from base
        rel_paths = [f.relative_to(base) for f in par_files]

        # Check directory structure patterns
        if all(len(p.parts) > 1 for p in rel_paths):
            # Find common path parts for complex nested structures
            common_parts = self._find_common_path_parts(rel_paths)

            if common_parts:
                # For very deep nested structures, use a more flexible pattern
                if len(common_parts) > 3:
                    # Use wildcard for deep nested structures with flexible suffix
                    return f".*{pulsar_pattern}.*\\.par"
                else:
                    # Build pattern with common path parts
                    path_pattern = "/".join(common_parts)
                    return f"{path_pattern}/{pulsar_pattern}.*\\.par"
            else:
                # Fallback to simple subdirectory analysis
                subdir_names = [p.parts[0] for p in rel_paths]
                subdir_counts = Counter(subdir_names)
                most_common_subdir = subdir_counts.most_common(1)[0][0]

                # Check for common patterns
                if most_common_subdir == "par":
                    return f"par/{pulsar_pattern}\\.par"
                elif most_common_subdir == "tim":
                    return f"tim/{pulsar_pattern}\\.par"
                else:
                    # Check if subdirectory name matches file stem (pulsar-specific dirs)
                    first_path = rel_paths[0]
                    file_stem = first_path.stem
                    if most_common_subdir == file_stem:
                        return f"{pulsar_pattern}/{pulsar_pattern}\\.par"
                    else:
                        # Generic subdirectory pattern
                        return f"{pulsar_pattern}/{pulsar_pattern}\\.par"
        else:
            # Files are in root directory
            return f"{pulsar_pattern}\\.par"

    def _generate_tim_pattern(self, structure: Dict) -> str:
        """Generate tim file pattern from structure analysis."""

        # Start with par pattern and adapt
        par_pattern = self._generate_par_pattern(structure)

        # Replace .par with .tim and make it more flexible
        tim_pattern = par_pattern.replace(".par", ".*\\.tim")

        # Analyze tim file naming patterns more carefully
        tim_files = [Path(f) for f in structure["tim_files"]]
        if tim_files:
            # Find the common base directory - start from the structure base path
            structure_base = Path(structure["base_path"])
            base = structure_base

            # Get relative paths from base
            rel_paths = [f.relative_to(base) for f in tim_files]

            # Check for common suffixes in tim files
            tim_stems = [p.stem for p in rel_paths]
            if tim_stems:
                # Look for common suffixes like "_all", "_dr1dr2", "_NANOGrav_9yv1"
                common_suffixes = []
                for stem in tim_stems:
                    # Extract suffix after pulsar name
                    for pattern in self.known_pulsar_patterns:
                        match = re.search(pattern, stem)
                        if match:
                            # Find the end of the pulsar name in the stem
                            pulsar_end = match.end()
                            suffix = stem[pulsar_end:]
                            if suffix:
                                common_suffixes.append(suffix)
                            break

                if common_suffixes:
                    # Use most common suffix
                    suffix_counts = Counter(common_suffixes)
                    most_common_suffix = suffix_counts.most_common(1)[0][0]
                    # For complex patterns, use flexible matching instead of specific suffix
                    if len(rel_paths) > 0 and len(rel_paths[0].parts) > 3:
                        # Don't add specific suffix for complex nested structures
                        pass
                    else:
                        # Escape special regex characters in the suffix
                        escaped_suffix = re.escape(most_common_suffix)
                        tim_pattern = tim_pattern.replace(
                            ".tim", f"{escaped_suffix}.tim"
                        )

        return tim_pattern

    def _determine_base_dir(self, structure: Dict) -> str:
        """Determine the base directory for the PTA."""
        # For now, just return the analyzed path
        # In practice, this might need to be relative to some data root
        return structure["base_path"]

    def _calculate_confidence(self, structure: Dict) -> float:
        """Calculate confidence score for the discovered patterns."""
        confidence = 0.0

        # Base confidence
        confidence += 0.3

        # Bonus for finding pulsar names
        if structure["pulsar_names"]:
            confidence += 0.3

        # Bonus for consistent naming patterns
        par_naming = structure["file_naming_patterns"]["par_naming"]
        tim_naming = structure["file_naming_patterns"]["tim_naming"]

        if par_naming.get("common_prefixes") or par_naming.get("common_suffixes"):
            confidence += 0.2

        if tim_naming.get("common_prefixes") or tim_naming.get("common_suffixes"):
            confidence += 0.2

        return min(confidence, 1.0)


def test_pattern_discovery():
    """Test the pattern discovery engine on IPTA data."""
    print("=== Pattern Discovery Engine Test ===\n")

    engine = PatternDiscoveryEngine()
    data_root = Path("/workspaces/metapulsar/data/ipta-dr2")

    if not data_root.exists():
        print(f"❌ Data directory {data_root} does not exist")
        return

    # Test on each PTA directory
    pta_dirs = [
        d
        for d in data_root.iterdir()
        if d.is_dir()
        and d.name
        not in [".git", "utils", "working", "release", "finalize_timing_summary"]
    ]

    print(f"Found {len(pta_dirs)} potential PTA directories:")
    for pta_dir in pta_dirs:
        print(f"  - {pta_dir.name}")
    print()

    results = []

    for pta_dir in pta_dirs:
        print(f"🔍 Analyzing {pta_dir.name}...")
        try:
            # Analyze structure
            structure = engine.analyze_directory_structure(pta_dir)

            # Generate config
            data_release = engine.generate_pta_data_release(structure)

            results.append(
                {
                    "name": pta_dir.name,
                    "structure": structure,
                    "data_release": data_release,
                }
            )

            print(
                f"  ✅ Success! Confidence: {data_release['discovery_confidence']:.2f}"
            )
            print(f"     Par pattern: {data_release['par_pattern']}")
            print(f"     Tim pattern: {data_release['tim_pattern']}")
            print(f"     Timing package: {data_release['timing_package']}")
            print(f"     Pulsars found: {len(structure['pulsar_names'])}")
            if structure["pulsar_names"]:
                print(f"     Example pulsars: {structure['pulsar_names'][:3]}")
            print()

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            print()

    # Summary
    print("=== Summary ===")
    successful = [r for r in results if r]
    print(f"Successfully analyzed: {len(successful)}/{len(pta_dirs)} PTAs")

    if successful:
        avg_confidence = sum(
            r["config"]["discovery_confidence"] for r in successful
        ) / len(successful)
        print(f"Average confidence: {avg_confidence:.2f}")

        print("\nGenerated configurations:")
        for result in successful:
            print(f"\n{result['name']}:")
            print(f"  base_dir: {result['config']['base_dir']}")
            print(f"  par_pattern: {result['config']['par_pattern']}")
            print(f"  tim_pattern: {result['config']['tim_pattern']}")
            print(f"  timing_package: {result['config']['timing_package']}")
            print(f"  confidence: {result['config']['discovery_confidence']:.2f}")


if __name__ == "__main__":
    test_pattern_discovery()
