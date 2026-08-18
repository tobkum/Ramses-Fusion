# -*- coding: utf-8 -*-
"""Restoring an older version, and what the next save does with it.

The restore path had no test at all: test_pipeline_scenario mocks
``restoreVersion`` out entirely, so nothing here had ever run. Two things were
wrong as a result, and both are asserted below.

These tests use a real temporary folder rather than mocking RamFileManager,
because the whole behaviour under test *is* file naming and placement:
restoreVersion() writes a marked copy beside the working file, getSaveFilePath()
strips the marker back off, and __save() reads the marker to decide whether to
increment. Mock any one of those and the test asserts nothing.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

# --- Environment mocks (Fusion is not importable off a Fusion install) -------
sys.modules.setdefault("bmd", MagicMock())
sys.modules.setdefault("fusionscript", MagicMock())

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
_APP_DIR = os.path.join(_PROJECT_ROOT, "Ramses-Fusion")
_LIB_DIR = os.path.join(_APP_DIR, "lib")
for _p in (_LIB_DIR, _APP_DIR, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ramses  # noqa: E402
import ramses.ramses  # noqa: E402

ramses.ramses.Ramses.connect = MagicMock(return_value=True)

import fusion_host  # noqa: E402
from ramses import RamFileInfo, RamHost, RamItem, RamState, RamStep  # noqa: E402

# NOT ``from fusion_host import FusionHost``. test_ramses_patches reloads the
# module (which is what the launcher does on every Fusion start), rebinding the
# class object, and it sorts before this file under both runners. A name bound
# at import time would then be a *different* class from the one the reloaded
# module body closes over, and every ``super(FusionHost, self)`` inside it
# raises TypeError. Resolve it through the module, which reload mutates in place.

from mocks import MockComp, MockFusion  # noqa: E402

BASE_NAME = "TEST_S_SH010_COMP"


class _SavingComp(MockComp):
    """A comp that actually writes a file, so the SDK's copies have something to copy.

    It also remembers what it was opened with, so a test can prove the *restored*
    content is what ends up in the new version rather than just some file existing.
    """

    def __init__(self):
        super().__init__()
        self.content = ""
        self.save_succeeds = True

    def Save(self, path):
        if not self.save_succeeds:
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.content)
        self.attrs["COMPS_FileName"] = path.replace("\\", "/")
        return True


class _LoadingFusion(MockFusion):
    def __init__(self):
        super().__init__()
        self._comp = _SavingComp()

    def LoadComp(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self._comp.content = f.read()
        self._comp.attrs["COMPS_FileName"] = path.replace("\\", "/")
        return self._comp


class RestoreOnDiskTestCase(unittest.TestCase):
    """A working file with three versions behind it, in a real temp folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ramses_restore_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.wip = os.path.join(self.tmp, "SHOT")
        self.versions = os.path.join(self.wip, "_versions")
        os.makedirs(self.versions)

        self.work = os.path.join(self.wip, BASE_NAME + ".comp")
        self._write(self.work, "v3-content")
        for v in (1, 2, 3):
            self._write(self.version_path(v), "v%d-content" % v)

        self._pin_the_naming_environment()

        self.fusion = _LoadingFusion()
        self.host = fusion_host.FusionHost(self.fusion)
        self.comp.attrs["COMPS_FileName"] = self.work.replace("\\", "/")
        self.comp.content = "v3-content"

        # setupCurrentFile() wants a live project; the restore behaviour does not.
        self._patch(fusion_host.FusionHost, "setupCurrentFile", return_value=True)

        # Identity comes from the daemon and is irrelevant here: the file
        # naming under test is derived from paths, not from the database.
        for name in ("currentItem", "currentStep", "currentStatus"):
            self._patch(fusion_host.FusionHost, name, return_value=None)
        self._patch(RamItem, "fromPath", return_value=None)
        self._patch(RamStep, "fromPath", return_value=None)

    def _patch(self, target, attribute, **kwargs):
        p = patch.object(target, attribute, **kwargs)
        value = p.start()
        self.addCleanup(p.stop)
        return value

    def _pin_the_naming_environment(self):
        """Makes ``wip002`` parse as a version, here and on any machine.

        RamFileInfo builds its filename regex from the *state short names the
        daemon is offering*, and caches it on the class for the process. Two
        consequences, both of which have to be shut down or this file tests
        something different depending on what ran before it:

        - with a Ramses client running on the developer's machine the real
          states come back and "wip002" parses; on a build machine, or under
          the full suite where an earlier module replaces the daemon with a
          MagicMock, only 'v' and 'pub' are known and "wip002" parses as a
          *resource* named "wip002" with no version at all;
        - whichever module first asks for the regex compiles it for everyone,
          so this is order-dependent on top of that.
        """
        wip = RamState(uuid="", data={"shortName": "wip", "name": "Work in progress"})
        self._patch(ramses.ramses.Ramses, "states", return_value=[wip])
        # None forces a rebuild on first use; the real cache is put back on
        # cleanup so this cannot leak into the modules that follow.
        self._patch(RamFileInfo, "_RamFileInfo__nameRe", new=None)

    # --- helpers ------------------------------------------------------------

    @property
    def comp(self):
        return self.fusion._comp

    def _write(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def version_path(self, version):
        return os.path.join(self.versions, "%s_wip%03d.comp" % (BASE_NAME, version))

    def restored_copy_path(self, version=2):
        return os.path.join(self.wip, "%s_+restored-v%d+.comp" % (BASE_NAME, version))

    def restore(self, version=2):
        self.host._restoreVersionUI = MagicMock(
            return_value=self.version_path(version)
        )
        return self.host.restoreVersion()

    def read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


class TestRestoreLeavesTheWorkingFileAlone(RestoreOnDiskTestCase):

    def test_restore_opens_a_marked_copy_beside_the_working_file(self):
        self.assertTrue(self.restore(2))

        copy_path = self.restored_copy_path(2)
        self.assertTrue(os.path.isfile(copy_path), "the restored copy is written")
        self.assertEqual("v2-content", self.read(copy_path))
        self.assertEqual(
            copy_path.replace("\\", "/").lower(),
            self.host.currentFilePath().lower(),
            "the copy is what is now open",
        )

    def test_restore_does_not_touch_the_working_file_or_the_versions(self):
        self.restore(2)

        self.assertEqual(
            "v3-content",
            self.read(self.work),
            "the working file keeps the newer work until the artist saves",
        )
        for v in (1, 2, 3):
            self.assertTrue(os.path.isfile(self.version_path(v)))


class TestRestoredVersionIsReported(RestoreOnDiskTestCase):
    """The header said "now at v-1" after a restore."""

    def test_the_base_implementation_cannot_answer_for_a_restored_copy(self):
        # The control for the override below. RamHost.currentVersion() looks up
        # _versions/ by the *current* file name, and a restored copy's name
        # matches nothing there. If this ever stops returning -1 the override
        # has become dead code and should go.
        self.restore(2)
        self.assertEqual(-1, RamHost.currentVersion(self.host))

    def test_currentVersion_reports_the_restored_version(self):
        self.restore(2)
        self.assertEqual(2, self.host.currentVersion())
        self.assertEqual(2, self.host.currentRestoredVersion())

    def test_currentRestoredVersion_is_minus_one_for_an_ordinary_file(self):
        self.assertEqual(-1, self.host.currentRestoredVersion())
        self.assertEqual(3, self.host.currentVersion())

    def test_currentRestoredVersion_is_minus_one_for_an_unsaved_comp(self):
        self.comp.attrs["COMPS_FileName"] = ""
        self.assertEqual(-1, self.host.currentRestoredVersion())


class TestSavingARestoredComp(RestoreOnDiskTestCase):

    def test_the_save_lands_back_on_the_working_file(self):
        self.restore(2)
        self.assertTrue(self.host.save(setupFile=False))

        self.assertEqual(
            self.work.replace("\\", "/").lower(),
            self.host.currentFilePath().lower(),
        )
        self.assertEqual("v2-content", self.read(self.work))

    def test_the_version_is_incremented_rather_than_overwritten(self):
        self.restore(2)
        self.host.save(setupFile=False)

        self.assertTrue(
            os.path.isfile(self.version_path(4)),
            "restoring must not overwrite v3 with older content",
        )
        self.assertEqual("v2-content", self.read(self.version_path(4)))
        self.assertEqual("v3-content", self.read(self.version_path(3)))
        self.assertEqual(4, self.host.currentVersion())

    def test_the_restored_copy_is_removed(self):
        self.restore(2)
        copy_path = self.restored_copy_path(2)
        self.assertTrue(os.path.isfile(copy_path))

        self.host.save(setupFile=False)

        self.assertFalse(
            os.path.isfile(copy_path),
            "the copy is a duplicate of _versions/...wip002 once its content is saved",
        )

    def test_the_deleted_copy_is_dropped_from_the_metadata_sidecar(self):
        self.restore(2)
        sidecar = os.path.join(self.wip, "_ramses_data.json")
        with open(sidecar, "r", encoding="utf-8") as f:
            self.assertIn(os.path.basename(self.restored_copy_path(2)), json.load(f))

        self.host.save(setupFile=False)

        with open(sidecar, "r", encoding="utf-8") as f:
            self.assertNotIn(
                os.path.basename(self.restored_copy_path(2)), json.load(f)
            )

    def test_a_second_save_behaves_normally(self):
        self.restore(2)
        self.host.save(setupFile=False)
        self.comp.content = "more-work"

        self.host.save(setupFile=False)

        self.assertEqual(
            4,
            self.host.currentVersion(),
            "only the first save after a restore is forced to increment",
        )
        self.assertEqual("more-work", self.read(self.version_path(4)))

    def test_it_also_works_through_the_state_branch_of_save(self):
        # The app's own Save button passes state=..., which takes a different
        # branch of FusionHost.save() than the bare call the tests above make.
        self.restore(2)
        state = MagicMock()
        state.shortName.return_value = "WIP"

        self.assertTrue(self.host.save(setupFile=False, state=state))

        self.assertFalse(os.path.isfile(self.restored_copy_path(2)))
        self.assertTrue(os.path.isfile(self.version_path(4)))


class TestTheRestoredCopyIsKeptWhenDeletingWouldLoseSomething(
    RestoreOnDiskTestCase
):

    def test_a_failed_save_keeps_the_copy(self):
        self.restore(2)
        self.comp.save_succeeds = False

        self.assertFalse(self.host.save(setupFile=False))

        self.assertTrue(
            os.path.isfile(self.restored_copy_path(2)),
            "nothing was written, so the copy is still the only open work",
        )

    def test_the_copy_survives_if_its_source_version_is_gone(self):
        self.restore(2)
        os.remove(self.version_path(2))

        self.host.save(setupFile=False)

        self.assertTrue(
            os.path.isfile(self.restored_copy_path(2)),
            "with _versions/...wip002 gone the copy is no longer a duplicate",
        )

    def test_a_save_that_lands_elsewhere_keeps_the_copy(self):
        # Save As moves the work to another item; the copy still belongs to
        # this one and nothing here supersedes it.
        self.restore(2)
        elsewhere = os.path.join(self.tmp, "OTHER")
        os.makedirs(elsewhere)

        self.host._discardRestoredCopy(self.restored_copy_path(2))
        self.assertTrue(os.path.isfile(self.restored_copy_path(2)))

        self.comp.attrs["COMPS_FileName"] = os.path.join(
            elsewhere, "TEST_S_SH020_COMP.comp"
        ).replace("\\", "/")
        self.host._discardRestoredCopy(self.restored_copy_path(2))

        self.assertTrue(os.path.isfile(self.restored_copy_path(2)))

    def test_a_copy_edited_since_the_restore_is_kept(self):
        # Fusion's own "save before opening?" prompt writes straight into the
        # restored copy, without going through host.save(). Once that has
        # happened the copy holds work that exists nowhere else.
        self.restore(2)
        self._write(self.restored_copy_path(2), "v2-content-plus-an-hour-of-work")

        self.host.save(setupFile=False)

        self.assertTrue(
            os.path.isfile(self.restored_copy_path(2)),
            "the copy no longer matches version 2, so it is not a duplicate",
        )

    def test_an_ordinary_save_deletes_nothing(self):
        self.host.save(setupFile=False)

        self.assertTrue(os.path.isfile(self.work))
        self.assertEqual(
            sorted(os.listdir(self.versions)),
            sorted(
                [
                    "%s_wip%03d.comp" % (BASE_NAME, v)
                    for v in (1, 2, 3)
                ]
                + ["_ramses_data.json"]
            ),
        )


class TestAbandoningARestoredCopy(RestoreOnDiskTestCase):
    """Restore, then move on without saving: the copy must not be left behind."""

    def test_opening_another_file_removes_the_copy(self):
        self.restore(2)
        other = os.path.join(self.wip, "TEST_S_SH010_ANIM.comp")
        self._write(other, "other-content")

        self.assertTrue(self.host._open(other, None, None))

        self.assertFalse(os.path.isfile(self.restored_copy_path(2)))
        self.assertEqual(
            other.replace("\\", "/").lower(), self.host.currentFilePath().lower()
        )

    def test_restoring_twice_leaves_only_the_second_copy(self):
        self.restore(2)
        self.restore(1)

        self.assertFalse(os.path.isfile(self.restored_copy_path(2)))
        self.assertTrue(os.path.isfile(self.restored_copy_path(1)))

    def test_an_edited_copy_survives_being_abandoned(self):
        self.restore(2)
        self._write(self.restored_copy_path(2), "work-fusion-saved-on-the-prompt")
        other = os.path.join(self.wip, "TEST_S_SH010_ANIM.comp")
        self._write(other, "other-content")

        self.host._open(other, None, None)

        self.assertTrue(
            os.path.isfile(self.restored_copy_path(2)),
            "this is the only copy of that work",
        )

    def test_a_failed_open_keeps_the_copy(self):
        self.restore(2)

        self.assertFalse(
            self.host._open(os.path.join(self.wip, "nope.comp"), None, None)
        )

        self.assertTrue(os.path.isfile(self.restored_copy_path(2)))

    def test_opening_from_an_ordinary_file_deletes_nothing(self):
        other = os.path.join(self.wip, "TEST_S_SH010_ANIM.comp")
        self._write(other, "other-content")

        self.host._open(other, None, None)

        self.assertTrue(os.path.isfile(self.work))

    def test_reopening_the_same_restored_copy_keeps_it(self):
        self.restore(2)
        copy_path = self.restored_copy_path(2)

        self.assertTrue(self.host._open(copy_path, None, None))

        self.assertTrue(
            os.path.isfile(copy_path), "it is still the file that is open"
        )


# --- App-facing behaviour ----------------------------------------------------

if "Ramses_Fusion" in sys.modules:
    ram_fusion_mod = sys.modules["Ramses_Fusion"]
else:  # pragma: no cover - depends on module collection order
    import builtins
    import importlib.util

    builtins.fusion = MagicMock()
    builtins.fu = builtins.fusion
    _spec = importlib.util.spec_from_file_location(
        "Ramses_Fusion", os.path.join(_APP_DIR, "Ramses-Fusion.py")
    )
    ram_fusion_mod = importlib.util.module_from_spec(_spec)
    sys.modules["Ramses_Fusion"] = ram_fusion_mod
    _spec.loader.exec_module(ram_fusion_mod)

RamsesFusionApp = ram_fusion_mod.RamsesFusionApp


class TestTheHeaderNamesTheRestoredVersion(unittest.TestCase):
    """A restored copy must not look identical to the working file."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        for attr, value in (
            ("fusion", self.mock_fusion),
            ("fu", self.mock_fusion),
            ("bmd", sys.modules["bmd"]),
        ):
            # create=True: the app reads these as module globals that only
            # exist inside Fusion, so there is nothing here to replace.
            p = patch.object(ram_fusion_mod, attr, value, create=True)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(fusion_host, "bmd", sys.modules["bmd"])
        p.start()
        self.addCleanup(p.stop)

        self.app = RamsesFusionApp()
        self.app.ramses._offline = False
        self.app._outdated_count = 0

        self.item = MagicMock()
        self.item.shortName.return_value = "SH010"
        self.item.uuid.return_value = "item-1"
        self.item.itemType.return_value = ramses.ItemType.SHOT
        self.step = MagicMock()
        self.step.name.return_value = "Compositing"
        self.step.colorName.return_value = "#00ff00"

        for name in ("current_item", "current_step"):
            p = patch.object(
                RamsesFusionApp,
                name,
                new_callable=PropertyMock,
                return_value=self.item if name == "current_item" else self.step,
            )
            p.start()
            self.addCleanup(p.stop)

        p = patch.object(RamsesFusionApp, "_get_project", return_value=None)
        p.start()
        self.addCleanup(p.stop)
        self.item.projectShortName.return_value = "TEST"

    def _context(self, restored):
        with patch.object(
            self.app.ramses.host, "currentRestoredVersion", return_value=restored
        ):
            return self.app._get_context_text()

    def test_the_vertical_header_flags_a_restored_copy(self):
        text = self._context(2)
        self.assertIn("RESTORED v2", text)

    def test_the_horizontal_header_flags_a_restored_copy(self):
        self.app._horizontal = True
        self.assertIn("RESTORED v2", self._context(2))

    def test_an_ordinary_file_gets_no_marker(self):
        self.assertNotIn("RESTORED", self._context(-1))
        self.app._horizontal = True
        self.assertNotIn("RESTORED", self._context(-1))

    def test_the_header_survives_a_host_that_cannot_answer(self):
        with patch.object(
            self.app.ramses.host,
            "currentRestoredVersion",
            side_effect=RuntimeError("no comp"),
        ):
            self.assertIn("SH010", self.app._get_context_text())


class TestTheRestoreMessage(unittest.TestCase):

    def setUp(self):
        self.mock_fusion = MockFusion()
        for attr, value in (
            ("fusion", self.mock_fusion),
            ("fu", self.mock_fusion),
            ("bmd", sys.modules["bmd"]),
        ):
            # create=True: the app reads these as module globals that only
            # exist inside Fusion, so there is nothing here to replace.
            p = patch.object(ram_fusion_mod, attr, value, create=True)
            p.start()
            self.addCleanup(p.stop)
        self.app = RamsesFusionApp()
        self.app.ramses._offline = False

        p = patch.object(RamsesFusionApp, "refresh_header")
        self.refresh = p.start()
        self.addCleanup(p.stop)

        p = patch.object(RamsesFusionApp, "_set_status")
        self.set_status = p.start()
        self.addCleanup(p.stop)

    def test_it_names_the_version_that_was_restored(self):
        # currentVersion() is deliberately given a *different* answer here, so
        # that a message built from it instead fails: the two only agree
        # because FusionHost overrides currentVersion, and this test is meant
        # to hold even if that override goes away.
        with patch.object(
            self.app.ramses.host, "restoreVersion", return_value=True
        ), patch.object(
            self.app.ramses.host, "currentRestoredVersion", return_value=2
        ), patch.object(
            self.app.ramses.host, "currentVersion", return_value=3
        ):
            self.app.on_retrieve(None)

        message = self.set_status.call_args[0][0]
        self.assertIn("v2", message)
        self.assertNotIn("v3", message)
        self.assertNotIn("v-1", message)

    def test_it_forces_a_full_refresh_because_the_current_file_changed(self):
        with patch.object(
            self.app.ramses.host, "restoreVersion", return_value=True
        ), patch.object(
            self.app.ramses.host, "currentRestoredVersion", return_value=2
        ):
            self.app.on_retrieve(None)

        self.refresh.assert_called_once_with(force_full=True)

    def test_a_cancelled_restore_still_reports_nothing_restored(self):
        with patch.object(
            self.app.ramses.host, "restoreVersion", return_value=False
        ):
            self.app.on_retrieve(None)

        self.assertEqual("error", self.set_status.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
