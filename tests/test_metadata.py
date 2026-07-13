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

    def test_hacs_metadata_identifies_this_fork(self) -> None:
        """Keep user-facing HACS ownership and support links on the maintained fork."""
        manifest = json.loads(
            (ROOT / "custom_components" / "adaptive_cover" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["domain"], "adaptive_cover")
        self.assertEqual(manifest["name"], "Adaptive Cover rako Edition")
        self.assertEqual(manifest["codeowners"], ["@rako79"])
        self.assertEqual(
            manifest["documentation"], "https://github.com/rako79/adaptive-cover"
        )
        self.assertEqual(
            manifest["issue_tracker"],
            "https://github.com/rako79/adaptive-cover/issues",
        )
        self.assertEqual(hacs["name"], manifest["name"])
        self.assertTrue((ROOT / "NOTICE.md").is_file())
        self.assertTrue((ROOT / "brand" / "icon.png").is_file())


if __name__ == "__main__":
    unittest.main()
