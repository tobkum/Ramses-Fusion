# -*- coding: utf-8 -*-
"""The vendored SDK must not drift, checkable without the studio tree.

`lib/ramses` and `lib/yaml` are copies of `Ramses-Dev/lib`, carried here because
this plugin is installed into Fusion's scripts folder where no parent directory
exists. The rule is that they are never edited: fixes go upstream to Ramses-Py,
or into `lib/ramses_patches.py` as a runtime patch.

Nothing enforced that. On 31 Jul 2026 a bump updated two of three copies and
looked like success, because a missed copy is silent by nature.

This compares against `tests/sdk_manifest.json`, committed alongside, so it
needs nothing outside this repo and runs wherever the tests run. Bumping the SDK
means regenerating the manifest in the same commit, which is the point: the bump
becomes one visible line in review instead of dozens of quietly changed vendored
files.

`Ramses-Dev/tests/test_sdk_copies.py` answers the other half -- whether all the
copies agree with each other -- and can only run where the whole tree is
checked out.
"""

import hashlib
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDORED = REPO_ROOT / "Ramses-Fusion" / "lib"
MANIFEST = Path(__file__).resolve().parent / "sdk_manifest.json"

PACKAGES = ("ramses", "yaml")


def _digest_tree(lib):
    """sha256 per vendored .py, keyed by path relative to lib/."""
    digests = {}
    for package in PACKAGES:
        for path in sorted((lib / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            digests[path.relative_to(lib).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digests


class TestVendoredSDKMatchesManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.recorded = self.manifest["files"]
        self.actual = _digest_tree(VENDORED)

    def test_records_which_upstream_commit_is_vendored(self):
        # Otherwise the manifest says the copy is self-consistent but not what
        # it is a copy of, which is the question during a bump.
        self.assertTrue(self.manifest.get("upstream"))

    def test_the_vendored_sdk_is_present(self):
        for package in PACKAGES:
            with self.subTest(package=package):
                self.assertTrue((VENDORED / package).is_dir())

    def test_no_file_was_added_or_removed(self):
        self.assertEqual(
            sorted(set(self.recorded) - set(self.actual)), [], "missing from the vendored SDK"
        )
        self.assertEqual(
            sorted(set(self.actual) - set(self.recorded)),
            [],
            "present in the vendored SDK but not in the manifest",
        )

    def test_no_vendored_file_was_edited(self):
        differing = sorted(
            name
            for name, digest in self.recorded.items()
            if name in self.actual and self.actual[name] != digest
        )

        self.assertEqual(
            differing,
            [],
            "vendored SDK does not match tests/sdk_manifest.json; if this is an "
            "intentional bump, regenerate the manifest in the same commit",
        )


if __name__ == "__main__":
    unittest.main()
