"""Run the full ModelMesh test suite."""
import os
import sys
import unittest

if __name__ == "__main__":
    # Ensure the source is importable
    src_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "python"
    )
    sys.path.insert(0, os.path.abspath(src_path))

    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = loader.discover(
        os.path.dirname(__file__), pattern="test_*.py"
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
