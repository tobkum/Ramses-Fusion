"""Unit tests for AssetBrowser._list_deliverables (per-deliverable rows).

Pure logic over a real temp dir, so no Fusion/daemon needed. Mirrors the
path-setup of test_ramses_fusion_app.py.
"""
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock

# `_list_deliverables` is pure (os.listdir + regex), so this file needs no
# daemon/fusion mocks. Crucially it does NOT import `asset_browser` at module
# (collection) level: this file sorts first alphabetically, and importing the
# `ramses` chain early would perturb the other suites' import-order-sensitive
# mock setup. Instead setUp imports it lazily at run time, by which point
# fusion_host's own `from asset_browser import AssetBrowser` (line 27) has
# already cached the module during collection - so we just reuse it.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(project_root, "Ramses-Fusion", "lib")
if lib_path not in sys.path:
    sys.path.append(lib_path)
sys.modules.setdefault("bmd", MagicMock())


class TestListDeliverables(unittest.TestCase):
    def setUp(self):
        from asset_browser import AssetBrowser  # lazy — reuse cached module
        # __init__ only stores refs; no dialog is built until show().
        self.browser = AssetBrowser(MagicMock(), MagicMock(), MagicMock())
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, *names):
        for n in names:
            open(os.path.join(self.tmp, n), "w").close()

    def _kinds(self, extra=(".comp",)):
        return [d["kind"] for d in self.browser._list_deliverables(self.tmp, extra)]

    def _by_kind(self, extra=(".comp",)):
        out = {}
        for d in self.browser._list_deliverables(self.tmp, extra):
            out.setdefault(d["kind"], []).append(d)
        return out

    def test_comp_only_folder_yields_one_comp_row(self):
        self._touch("DNX_0163_camera.comp", "_ramses_data.json", ".ramses_complete")
        res = self.browser._list_deliverables(self.tmp, {".comp"})
        self.assertEqual([d["kind"] for d in res], ["comp"])
        self.assertTrue(res[0]["path"].endswith("DNX_0163_camera.comp"))

    def test_footage_and_comp_yield_two_rows(self):
        self._touch("preview.mov", "camera.comp", "_ramses_data.json")
        by = self._by_kind()
        self.assertIn("movie", by)
        self.assertIn("comp", by)
        self.assertEqual(len(by["movie"]), 1)
        self.assertEqual(len(by["comp"]), 1)

    def test_exr_sequence_collapses_to_one_row_at_first_frame(self):
        frames = [f"PLATE.{1599116 + i:08d}.exr" for i in range(43)]
        self._touch(*frames)
        res = self.browser._list_deliverables(self.tmp, {".comp"})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["kind"], "sequence")
        # First frame (lowest number) is the representative path.
        self.assertTrue(res[0]["path"].endswith("PLATE.01599116.exr"))
        self.assertEqual(res[0]["label"], "PLATE.[####].exr")

    def test_sidecars_and_hidden_files_dropped(self):
        self._touch("_ramses_data.json", ".ramses_complete", "notes.txt")
        self.assertEqual(self.browser._list_deliverables(self.tmp, {".comp"}), [])

    def test_two_sequences_yield_two_rows(self):
        self._touch(
            "beauty.0001.exr", "beauty.0002.exr", "beauty.0003.exr",
            "matte.0001.exr", "matte.0002.exr",
        )
        res = self.browser._list_deliverables(self.tmp, {".comp"})
        self.assertEqual(len(res), 2)
        self.assertTrue(all(d["kind"] == "sequence" for d in res))
        labels = sorted(d["label"] for d in res)
        self.assertEqual(labels, ["beauty.[####].exr", "matte.[####].exr"])

    def test_empty_folder_yields_no_rows(self):
        self.assertEqual(self.browser._list_deliverables(self.tmp, {".comp"}), [])

    def test_unknown_extension_skipped(self):
        self._touch("readme.pdf", "data.abc")
        self.assertEqual(self.browser._list_deliverables(self.tmp, {".comp"}), [])

    def test_without_extra_exts_comp_is_not_surfaced(self):
        """If the app config yields no formats, a .comp isn't shown (footage
        still is) - the caller always passes the {'.comp'} fallback, but guard
        the empty case."""
        self._touch("camera.comp", "preview.mov")
        kinds = [d["kind"] for d in self.browser._list_deliverables(self.tmp, ())]
        self.assertEqual(kinds, ["movie"])

    def test_ordering_movies_then_sequences_then_comp(self):
        self._touch("beauty.0001.exr", "beauty.0002.exr", "preview.mov", "camera.comp")
        kinds = [d["kind"] for d in self.browser._list_deliverables(self.tmp, {".comp"})]
        self.assertEqual(kinds, ["movie", "sequence", "comp"])


if __name__ == "__main__":
    unittest.main()
