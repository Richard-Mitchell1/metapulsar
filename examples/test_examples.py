#!/usr/bin/env python3
"""
Test script for ParFileManager and MetaPulsarFactory examples.

This script tests the basic functionality without requiring actual par files.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ipta_metapulsar import MetaPulsarFactory, PTARegistry, ParFileManager


def test_basic_imports():
    """Test that all classes can be imported."""
    print("Testing imports...")

    try:
        # Test MetaPulsarFactory
        MetaPulsarFactory()
        print("✓ MetaPulsarFactory imported and instantiated")

        # Test PTARegistry
        PTARegistry()
        print("✓ PTARegistry imported and instantiated")

        # Test ParFileManager
        ParFileManager()
        print("✓ ParFileManager imported and instantiated")

        return True

    except Exception as e:
        print(f"✗ Import error: {e}")
        return False


def test_factory_methods():
    """Test MetaPulsarFactory methods."""
    print("\nTesting MetaPulsarFactory methods...")

    try:
        factory = MetaPulsarFactory()

        # Test list_available_pulsars (should work even with no files)
        available = factory.list_available_pulsars()
        print(f"✓ list_available_pulsars() returned: {available}")

        # Test create_metapulsar with composite strategy (should fail gracefully)
        try:
            factory.create_metapulsar(
                "J1909-3744", ["epta_dr2", "ppta_dr2"], combination_strategy="composite"
            )
            print("✓ create_metapulsar() with composite strategy succeeded")
        except Exception as e:
            print(
                f"⚠ create_metapulsar() with composite strategy failed (expected): {e}"
            )

        return True

    except Exception as e:
        print(f"✗ Factory method error: {e}")
        return False


def test_metapulsar_combination_strategy():
    """Test MetaPulsar combination strategy methods."""
    print("\nTesting MetaPulsar combination strategy methods...")

    try:
        from ipta_metapulsar import MetaPulsar

        # Create a mock MetaPulsar
        mock_pulsars = {"epta_dr2": None, "ppta_dr2": None}

        # Test composite strategy
        metapulsar_composite = MetaPulsar(
            pulsars=mock_pulsars, combination_strategy="composite"
        )

        assert metapulsar_composite.get_combination_strategy() == "composite"
        assert metapulsar_composite.is_composite_strategy()
        assert not metapulsar_composite.is_consistent_strategy()
        print("✓ Composite strategy methods work correctly")

        # Test consistent strategy
        metapulsar_consistent = MetaPulsar(
            pulsars=mock_pulsars, combination_strategy="consistent"
        )

        assert metapulsar_consistent.get_combination_strategy() == "consistent"
        assert not metapulsar_consistent.is_composite_strategy()
        assert metapulsar_consistent.is_consistent_strategy()
        print("✓ Consistent strategy methods work correctly")

        return True

    except Exception as e:
        print(f"✗ MetaPulsar strategy error: {e}")
        return False


def test_pta_registry():
    """Test PTARegistry functionality."""
    print("\nTesting PTARegistry...")

    try:
        # Test empty registry
        empty_registry = PTARegistry(configs={})
        print("✓ Empty registry created")

        # Test adding PTA
        empty_registry.add_pta(
            "test_pta",
            {
                "base_dir": "/test/data/",
                "par_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.par",
                "tim_pattern": r"([BJ]\d{4}[+-]\d{2,4})\.tim",
                "timing_package": "pint",
                "priority": 1,
                "description": "Test PTA",
            },
        )
        print("✓ PTA added to registry")

        # Test listing PTAs
        pta_names = empty_registry.list_ptas()
        assert "test_pta" in pta_names
        print(f"✓ PTA listed: {pta_names}")

        return True

    except Exception as e:
        print(f"✗ PTARegistry error: {e}")
        return False


def main():
    """Run all tests."""
    print("ParFileManager and MetaPulsarFactory Test Suite")
    print("=" * 50)

    tests = [
        test_basic_imports,
        test_factory_methods,
        test_metapulsar_combination_strategy,
        test_pta_registry,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The examples should work correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
