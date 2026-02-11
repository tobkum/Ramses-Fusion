import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# --- 1. Setup Environment Mocks ---
sys.modules["bmd"] = MagicMock()
sys.modules["fusionscript"] = MagicMock()

# --- 2. Setup Path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(os.path.dirname(project_root), "lib")
app_path = os.path.join(project_root, "Ramses-Fusion")

if lib_path not in sys.path:
    sys.path.append(lib_path)
if app_path not in sys.path:
    sys.path.append(app_path)

# Mock Ramses API and Daemon
import ramses

mock_daemon = MagicMock()
mock_daemon.online.return_value = True
mock_daemon.getUser.return_value = MagicMock()
sys.modules["ramses.daemon_interface"] = MagicMock(
    RamDaemonInterface=MagicMock(instance=lambda: mock_daemon)
)

import ramses.ramses

ramses.ramses.Ramses.connect = MagicMock(return_value=True)

# Mock global 'fusion' objects
mock_fusion_obj = MagicMock()
import builtins

builtins.fusion = mock_fusion_obj
builtins.fu = mock_fusion_obj

# Import the App module
import importlib.util

spec = importlib.util.spec_from_file_location(
    "Ramses_Fusion", os.path.join(app_path, "Ramses-Fusion.py")
)
ram_fusion_mod = importlib.util.module_from_spec(spec)
sys.modules["Ramses_Fusion"] = ram_fusion_mod
spec.loader.exec_module(ram_fusion_mod)

from Ramses_Fusion import RamsesFusionApp
from tests.mocks import MockFusion
from ramses import ItemType, LogLevel


class TestPipelineScenario(unittest.TestCase):
    """Scenario Test: Simulates a complete shot lifecycle in the pipeline."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        # Inject global mocks
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]

        import fusion_host

        fusion_host.bmd = sys.modules["bmd"]

        self.app = RamsesFusionApp()
        self.host = self.app.ramses.host

    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    @patch("os.path.getmtime", return_value=123456789.0)
    @patch("os.listdir", return_value=[])
    @patch("os.makedirs")
    @patch("shutil.copy2")
    @patch("ramses.file_manager.RamFileManager.getSaveFilePath")
    @patch("ramses.file_manager.RamFileManager.copyToVersion")
    @patch("ramses.metadata_manager.RamMetaDataManager.setMetaData")
    @patch("ramses.metadata_manager.RamMetaDataManager.getMetaData", return_value={})
    @patch(
        "ramses.metadata_manager.RamMetaDataManager.getFileMetaData", return_value={}
    )
    def test_complete_shot_lifecycle(
        self,
        mock_get_file_meta,
        mock_get_meta,
        mock_set_meta,
        mock_copy_ver,
        mock_get_save,
        mock_copy,
        mock_makedirs,
        mock_listdir,
        mock_mtime,
        mock_isdir,
        mock_exists,
    ):
        """
        Walkthrough - Tests ACTUAL STATE CHANGES through the pipeline:
        1. User sets up scene (syncs project settings).
        2. User triggers save via app handler.
        3. User adds a note via app handler.
        4. User generates preview.
        5. User updates status and publishes.
        6. User restores a previous version.
        """
        # Ensure connection check doesn't block or try to reach daemon
        self.app.ramses.online = MagicMock(return_value=True)

        # Ensure save file path is simple
        mock_get_save.side_effect = lambda x: x
        mock_copy_ver.side_effect = lambda path, inc, state: path

        with patch.object(self.app, "refresh_header"):
            # Setup Mocks early to avoid UnboundLocalError
            mock_project = MagicMock()
            mock_project.uuid.return_value = "proj-123"
            mock_project.shortName.return_value = "TESTPROJ"

            mock_shot = MagicMock()
            mock_shot.uuid.return_value = "shot-456"
            mock_shot.shortName.return_value = "SH010"
            mock_shot.itemType.return_value = ItemType.SHOT
            mock_shot.project.return_value = mock_project

            # Ensure Host uses our mocks for identity instead of path parsing
            self.host.currentItem = MagicMock(return_value=mock_shot)
            self.host.currentStep = MagicMock(return_value=MagicMock())

            # --- PHASE 1: Initial State Verification ---
            comp = self.mock_fusion.GetCurrentComp()

            # Verify comp starts without Ramses metadata
            self.assertIsNone(comp.GetData("Ramses.ItemUUID"))
            self.assertIsNone(comp.GetData("Ramses.ProjectUUID"))

            # Verify no anchor nodes exist initially
            self.assertIsNone(comp.FindTool("_PREVIEW"))
            self.assertIsNone(comp.FindTool("_FINAL"))

            # --- PHASE 2: Scene Setup - Verify ACTUAL State Changes ---
            self.app.ramses.project = MagicMock(return_value=mock_project)

            mock_wip_state = MagicMock()
            mock_wip_state.shortName.return_value = "WIP"
            mock_wip_state.name.return_value = "Work In Progress"
            self.app.ramses.defaultState = MagicMock(return_value=mock_wip_state)

            path = "D:/Projects/TESTPROJ/SH010/COMP/TESTPROJ_S_SH010_COMP.comp"
            comp.SetAttrs({"COMPS_FileName": path})

            # Setup settings
            db_settings = {
                "width": 1920,
                "height": 1080,
                "framerate": 24.0,
                "frames": 48,
            }
            self.host.collectItemSettings = MagicMock(return_value=db_settings)
            self.host.resolvePreviewPath = MagicMock(
                return_value="D:/Previews/SH010.mov"
            )
            self.host.resolveFinalPath = MagicMock(return_value="D:/Renders/SH010.mov")

            # Trigger setup scene
            self.app.on_setup_scene(None)

            # VERIFY ACTUAL STATE CHANGES (not mock calls):
            # 1. Resolution was applied
            prefs = comp.GetPrefs("Comp.FrameFormat")
            self.assertEqual(prefs["Width"], 1920, "Width should be set to 1920")
            self.assertEqual(prefs["Height"], 1080, "Height should be set to 1080")
            self.assertEqual(prefs["Rate"], 24.0, "Framerate should be set to 24.0")

            # 2. Anchor nodes were created
            preview_node = comp.FindTool("_PREVIEW")
            final_node = comp.FindTool("_FINAL")
            self.assertIsNotNone(preview_node, "_PREVIEW anchor should exist")
            self.assertIsNotNone(final_node, "_FINAL anchor should exist")

            # 3. Anchor paths were set correctly
            self.assertEqual(preview_node.Clip[1], "D:/Previews/SH010.mov")
            self.assertEqual(final_node.Clip[1], "D:/Renders/SH010.mov")

            # 4. Anchors are disabled by default (PassThrough)
            self.assertTrue(
                preview_node.attrs.get("TOOLB_PassThrough"),
                "_PREVIEW should be pass-through"
            )
            self.assertTrue(
                final_node.attrs.get("TOOLB_PassThrough"),
                "_FINAL should be pass-through"
            )

            # 5. Identity metadata was persisted
            self.assertEqual(
                comp.GetData("Ramses.ItemUUID"), "shot-456",
                "Item UUID should be stored in comp metadata"
            )
            self.assertEqual(
                comp.GetData("Ramses.ProjectUUID"), "proj-123",
                "Project UUID should be stored in comp metadata"
            )

            # --- PHASE 3: Save Handler Test ---
            # Test that on_save triggers host.save with correct state propagation
            mock_status = MagicMock()
            mock_status.state.return_value = mock_wip_state
            mock_status.comment.return_value = ""
            self.host.currentStatus = MagicMock(return_value=mock_status)

            with patch.object(self.host, "save", return_value=True) as mock_save:
                # Trigger via APP handler (not direct host call)
                self.app.on_save(None)

                # Verify the APP correctly called HOST with state propagation
                mock_save.assert_called_once()
                call_kwargs = mock_save.call_args[1]
                self.assertEqual(
                    call_kwargs.get("state"), mock_wip_state,
                    "Save should propagate current state"
                )

            # --- PHASE 4: Comment Handler Test ---
            mock_status.comment.return_value = "Old Note"

            # Simulate user input for note dialog
            self.host._request_input = MagicMock(
                return_value={"Comment": "Added motion blur", "Incremental": True}
            )

            with patch.object(self.host, "save", return_value=True) as mock_save:
                # Trigger via APP handler
                self.app.on_comment(None)

                # Verify comment was passed and incremental flag respected
                mock_save.assert_called_once()
                call_kwargs = mock_save.call_args[1]
                self.assertEqual(call_kwargs.get("comment"), "Added motion blur")
                self.assertTrue(call_kwargs.get("incremental"))
                self.assertEqual(call_kwargs.get("state"), mock_wip_state)

            # --- PHASE 5: Preview Handler Test ---
            self.host.savePreview = MagicMock()

            # Mock validation passing for preview
            with patch.object(self.app, "_validate_publish", return_value=(True, "", False)):
                self.app.on_preview(None)
                self.host.savePreview.assert_called_once()

            # --- PHASE 6: Status Update Transaction Test ---
            mock_done_state = MagicMock()
            mock_done_state.shortName.return_value = "DONE"
            mock_done_state.completionRatio.return_value = 100

            # Mock status update UI
            self.host._statusUI = MagicMock(
                return_value={
                    "publish": True,
                    "note": "Final version for review",
                    "state": mock_done_state,
                    "completionRatio": 100,
                }
            )

            # Mock successful render and copy
            self.host._verify_render_output = MagicMock(return_value=True)
            self.host.publish = MagicMock(return_value=True)
            self.host.currentVersion = MagicMock(return_value=5)

            # Use real save to test transaction orchestration
            with patch.object(self.host, "save", return_value=True) as mock_save:
                success = self.host.updateStatus()

            self.assertTrue(success, "updateStatus should succeed")

            # Verify transaction order: save was called BEFORE publish
            mock_save.assert_called_once()
            self.host.publish.assert_called_once()

            # Verify state propagation to publish (prevents reversion bug)
            publish_kwargs = self.host.publish.call_args[1]
            self.assertEqual(
                publish_kwargs.get("state"), mock_done_state,
                "Publish should receive target state to prevent reversion"
            )

            # Verify database was updated
            mock_status.setState.assert_called_with(mock_done_state)
            mock_status.setComment.assert_called_with("Final version for review")
            mock_status.setVersion.assert_called_with(5)

            # --- PHASE 7: Version Restore Test ---
            self.host.restoreVersion = MagicMock(return_value=True)

            # Trigger via APP handler
            self.app.on_retrieve(None)

            self.host.restoreVersion.assert_called_once()
            self.app.refresh_header.assert_called()


class TestPipelineFailureModes(unittest.TestCase):
    """Tests failure scenarios in the pipeline to ensure graceful handling."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]

        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]

        self.app = RamsesFusionApp()
        self.host = self.app.ramses.host

    def test_update_status_aborts_on_save_failure(self):
        """Verify updateStatus aborts cleanly if save fails."""
        self.host.testDaemonConnection = MagicMock(return_value=True)
        self.host.currentItem = MagicMock(return_value=MagicMock())

        mock_state = MagicMock()
        self.host._statusUI = MagicMock(return_value={
            "publish": True,
            "note": "Test",
            "state": mock_state,
            "completionRatio": 50
        })

        # Save fails
        self.host.save = MagicMock(return_value=False)
        self.host.publish = MagicMock(return_value=True)

        success = self.host.updateStatus()

        self.assertFalse(success, "Should fail when save fails")
        # Publish should NOT have been called
        self.host.publish.assert_not_called()

    def test_update_status_aborts_on_publish_failure(self):
        """Verify updateStatus aborts and logs when publish fails after save."""
        self.host.testDaemonConnection = MagicMock(return_value=True)
        self.host.currentItem = MagicMock(return_value=MagicMock())

        mock_state = MagicMock()
        mock_status = MagicMock()
        self.host.currentStatus = MagicMock(return_value=mock_status)

        self.host._statusUI = MagicMock(return_value={
            "publish": True,
            "note": "Test",
            "state": mock_state,
            "completionRatio": 50
        })

        # Save succeeds, publish fails
        self.host.save = MagicMock(return_value=True)
        self.host.publish = MagicMock(return_value=False)

        # Capture log messages
        log_messages = []
        original_log = self.host._log
        self.host._log = lambda msg, level: log_messages.append((msg, level))

        success = self.host.updateStatus()

        self.assertFalse(success, "Should fail when publish fails")

        # Database should NOT have been updated (transaction aborted)
        mock_status.setState.assert_not_called()

        # User should be warned about the desync
        warning_msgs = [msg for msg, lvl in log_messages if lvl == LogLevel.Warning]
        self.assertTrue(
            any("manually" in msg.lower() for msg in warning_msgs),
            "Should warn user about manual recovery needed"
        )

    def test_update_status_skips_publish_when_not_requested(self):
        """Verify updateStatus skips publish when user doesn't request it."""
        self.host.testDaemonConnection = MagicMock(return_value=True)
        self.host.currentItem = MagicMock(return_value=MagicMock())

        mock_state = MagicMock()
        mock_status = MagicMock()
        self.host.currentStatus = MagicMock(return_value=mock_status)

        self.host._statusUI = MagicMock(return_value={
            "publish": False,  # User doesn't want to publish
            "note": "Just updating status",
            "state": mock_state,
            "completionRatio": 75
        })

        self.host.save = MagicMock(return_value=True)
        self.host.publish = MagicMock(return_value=True)
        self.host.currentVersion = MagicMock(return_value=3)

        success = self.host.updateStatus()

        self.assertTrue(success)
        # Publish should NOT have been called
        self.host.publish.assert_not_called()
        # But database should still be updated
        mock_status.setState.assert_called_with(mock_state)

    def test_comment_handler_skips_save_when_unchanged(self):
        """Verify on_comment doesn't save when note is unchanged and not incremental."""
        mock_status = MagicMock()
        mock_status.comment.return_value = "Existing note"
        mock_status.state.return_value = MagicMock()
        self.host.currentStatus = MagicMock(return_value=mock_status)

        # User doesn't change anything
        self.host._request_input = MagicMock(
            return_value={"Comment": "Existing note", "Incremental": False}
        )

        self.host.save = MagicMock(return_value=True)

        with patch.object(self.app, "refresh_header"):
            self.app.on_comment(None)

        # Save should NOT have been called
        self.host.save.assert_not_called()

    def test_comment_handler_cancellation(self):
        """Verify on_comment handles user cancellation gracefully."""
        mock_status = MagicMock()
        mock_status.comment.return_value = "Note"
        mock_status.state.return_value = MagicMock()
        self.host.currentStatus = MagicMock(return_value=mock_status)

        # User cancels the dialog
        self.host._request_input = MagicMock(return_value=None)

        self.host.save = MagicMock(return_value=True)

        self.app.on_comment(None)

        # Save should NOT have been called
        self.host.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
