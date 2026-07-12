"""Tests for release and diagnostics metadata consistency."""

import json
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).parents[1]


class MetadataConsistencyTests(unittest.TestCase):
    """Keep every exported integration version synchronized."""

    def test_integration_versions_match(self) -> None:
        """Use one release version in manifest, package and diagnostics constants."""
        manifest = json.loads(
            (ROOT / "custom_components" / "adaptive_cover" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        const_source = (
            ROOT / "custom_components" / "adaptive_cover" / "const.py"
        ).read_text(encoding="utf-8")
        match = re.search(
            r'^INTEGRATION_VERSION = "([^"]+)"$',
            const_source,
            re.MULTILINE,
        )
        self.assertIsNotNone(match)
        self.assertEqual(manifest["version"], pyproject["tool"]["poetry"]["version"])
        self.assertEqual(manifest["version"], match.group(1))


if __name__ == "__main__":
    unittest.main()
