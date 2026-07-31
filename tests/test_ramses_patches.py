# -*- coding: utf-8 -*-
"""Runtime SDK patches: the data-loss guards and their re-entrancy.

This module had no tests at all, despite its own docstring describing the
metadata corruption it exists to prevent.
"""

import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import ramses_patches
from ramses.metadata_manager import RamMetaDataManager


class TestPatchIdempotence(unittest.TestCase):
    """apply() must be safe to run repeatedly.

    Ramses-Fusion.py reloads fusion_host on every launch, which re-runs
    apply(). The patches it used to install wrapped whatever was currently
    installed, so without a guard each launch added another wrapper layer.
    """

    def test_apply_is_a_no_op_and_stays_callable(self):
        """apply() no longer patches anything, but both hosts still call it.

        The metadata fixes are in the vendored SDK as of Ramses-Py 30582ce,
        the daemon one as of d19ce44. Removing the function would break the
        call sites, so it stays as the hook for the next one.
        """
        for _ in range(5):
            ramses_patches.apply()
        self.assertFalse(
            getattr(RamMetaDataManager, "_ramses_patched", False),
            "no patch installs a sentinel any more",
        )


class TestGetMetaDataOwnership(unittest.TestCase):
    """The reader in use must be the SDK's, in tests and in production alike."""

    def test_patched_reader_survives_a_fusion_host_reload(self):
        import fusion_host

        # Exactly what Ramses-Fusion.py's __main__ does on every launch.
        importlib.reload(fusion_host)
        self.assertEqual(
            RamMetaDataManager.getMetaData.__module__, "ramses.metadata_manager",
            "getMetaData must come from the vendored SDK: the fix is upstream "
            "now, so nothing should be reinstalling its own reader. fusion_host "
            "used to install a competing one, and which won depended on whether "
            "the module had been reloaded, so the tests and the shipped add-on "
            "ran different code",
        )


class TestNoPruneOnRead(unittest.TestCase):
    """getMetaData must not delete entries for files it cannot see.

    A version backup may still be in flight on a copy thread; pruning it on
    read and persisting that on the next write destroyed real history.
    """

    def test_entry_for_a_missing_file_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            sidecar = os.path.join(folder, "_ramses_data.json")
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump({"not_on_disk_yet.comp": {"comment": "keep me"}}, f)

            data = RamMetaDataManager.getMetaData(folder)

        self.assertIn("not_on_disk_yet.comp", data)
        self.assertEqual(data["not_on_disk_yet.comp"]["comment"], "keep me")


class TestSidecarClobberGuard(unittest.TestCase):
    """setFileMetaData must never rewrite a sidecar it failed to read."""

    def test_unreadable_sidecar_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            sidecar = os.path.join(folder, "_ramses_data.json")
            original = '{"a.comp": {"comment": "months of history"}}'
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write(original)

            target = os.path.join(folder, "b.comp")
            # Simulate the sidecar being unreadable at this instant (the
            # Ramses client rewriting it non-atomically).
            with patch.object(
                RamMetaDataManager, "getMetaData", staticmethod(lambda _p: {})
            ):
                RamMetaDataManager.setFileMetaData(target, {"comment": "new"})

            with open(sidecar, encoding="utf-8") as f:
                after = f.read()

        self.assertEqual(
            json.loads(after), json.loads(original),
            "a transient unreadable read must not wipe the folder's metadata",
        )

    def test_readable_sidecar_still_accepts_writes(self):
        """The guard must not block the normal path."""
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "b.comp")
            open(target, "w").close()
            RamMetaDataManager.setFileMetaData(target, {"comment": "new"})

            data = RamMetaDataManager.getMetaData(folder)

        self.assertEqual(data["b.comp"]["comment"], "new")


class TestFalsyPathGuards(unittest.TestCase):
    """copyToVersion()/restoreVersionFile() can return None."""

    def test_getValue_returns_none_instead_of_raising(self):
        self.assertIsNone(RamMetaDataManager.getValue(None, "comment"))

    def test_setValue_is_a_noop_instead_of_raising(self):
        RamMetaDataManager.setValue(None, "comment", "x")  # must not raise
        RamMetaDataManager.setValue("", "comment", "x")


class TestDaemonOnlineNeverRaises(unittest.TestCase):
    """online() is a connectivity probe; callers expect a bool, not a raise.

    This asserts the vendored SDK now, not a runtime patch: the guard moved
    upstream in Ramses-Py d19ce44 (PR #16) and the patch was deleted.
    """

    def test_online_returns_false_when_the_daemon_misbehaves(self):
        from unittest.mock import MagicMock

        from ramses.daemon_interface import RamDaemonInterface

        if isinstance(RamDaemonInterface, MagicMock):
            # Another test module replaced ramses.daemon_interface in
            # sys.modules at import time, so there is no real class left to
            # patch. This assertion is still exercised when this file runs on
            # its own.
            self.skipTest("ramses.daemon_interface is mocked by another module")

        daemon = RamDaemonInterface.instance()
        for boom in (KeyError("content"), ConnectionResetError(), ValueError()):
            with self.subTest(error=type(boom).__name__):
                with patch.object(
                    RamDaemonInterface, "_RamDaemonInterface__testConnection",
                    side_effect=boom,
                ):
                    self.assertFalse(daemon.online())


class TestDisableMakedirs(unittest.TestCase):
    """Read-only SDK probes must not create folders."""

    def test_suppresses_and_restores(self):
        with tempfile.TemporaryDirectory() as base:
            target = os.path.join(base, "should_not_exist")
            with ramses_patches.DisableMakedirs():
                os.makedirs(target, exist_ok=True)
            self.assertFalse(os.path.isdir(target))

            os.makedirs(target, exist_ok=True)
            self.assertTrue(os.path.isdir(target), "suppression must not leak")

    def test_nesting_restores_the_outer_state(self):
        with tempfile.TemporaryDirectory() as base:
            with ramses_patches.DisableMakedirs():
                with ramses_patches.DisableMakedirs():
                    pass
                # Still suppressed: the inner block must not re-enable.
                inner = os.path.join(base, "inner")
                os.makedirs(inner, exist_ok=True)
                self.assertFalse(os.path.isdir(inner))

    def test_suppression_is_per_thread(self):
        with tempfile.TemporaryDirectory() as base:
            other_thread_created = []

            def worker():
                target = os.path.join(base, "from_other_thread")
                os.makedirs(target, exist_ok=True)
                other_thread_created.append(os.path.isdir(target))

            with ramses_patches.DisableMakedirs():
                t = threading.Thread(target=worker)
                t.start()
                t.join()

        self.assertEqual(
            other_thread_created, [True],
            "one thread's DisableMakedirs must not suppress another's",
        )


if __name__ == "__main__":
    unittest.main()
