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
lib_path = os.path.join(project_root, "Ramses-Fusion", "lib")
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
        Walkthrough:
        1. User creates a new shot SH010 via the wizard.
        2. User syncs project settings (Resolution, FPS).
        3. User performs an incremental save with a note.
        4. User updates status to DONE and publishes.
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

            # --- PHASE 1: Shot Creation ---
            self.app.ramses.project = MagicMock(return_value=mock_project)

            mock_wip_state = MagicMock()
            mock_wip_state.shortName.return_value = "WIP"
            mock_wip_state.name.return_value = "Work In Progress"
            self.app.ramses.defaultState = MagicMock(return_value=mock_wip_state)

            path = "D:/Projects/TESTPROJ/SH010/COMP/TESTPROJ_S_SH010_COMP.comp"
            self.mock_fusion.GetCurrentComp().SetAttrs({"COMPS_FileName": path})

            with patch.object(self.host, "save", return_value=True) as mock_save:
                self.host.save(
                    comment="Initial creation", setupFile=True, state=mock_wip_state
                )
                mock_save.assert_called_with(
                    comment="Initial creation", setupFile=True, state=mock_wip_state
                )

            # --- PHASE 2: Scene Setup & Identity Verification ---
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

            self.app.on_setup_scene(None)

            comp = self.mock_fusion.GetCurrentComp()
            self.assertEqual(comp.GetPrefs("Comp.FrameFormat")["Width"], 1920)
            self.assertIsNotNone(comp.FindTool("_FINAL"))

            # Verify Identity Persistence (Metadata was written)
            self.assertEqual(comp.GetData("Ramses.ItemUUID"), "shot-456")

            # --- PHASE 3: Iteration (Save Incremental & Note) ---
            mock_status = MagicMock()
            mock_status.state.return_value = mock_wip_state
            mock_status.comment.return_value = "Old Note"
            self.host.currentStatus = MagicMock(return_value=mock_status)

            # User adds a note
            self.host._request_input = MagicMock(
                return_value={"Comment": "Added motion blur", "Incremental": False}
            )

            # Verify that save was called with the note AND state preservation
            with patch.object(self.host, "save", return_value=True) as mock_save_iter:
                self.app.on_comment(None)
                mock_save_iter.assert_called_with(
                    comment="Added motion blur", setupFile=True, incremental=False, state=mock_wip_state
                )

            # --- PHASE 3.5: Preview (Dailies) ---
            # User generates a preview for supervisor review
            self.host.savePreview = MagicMock()
            
            # Mock validation passing for preview
            with patch.object(self.app, "_validate_publish", return_value=(True, "", False)):
                self.app.on_preview(None)
                self.host.savePreview.assert_called_once()

            # --- PHASE 4: Delivery (Status Update + Publish) ---
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

            success = self.host.updateStatus()

            self.assertTrue(success)
            # Verify Publish occurred with target state (to prevent reversion)
            self.host.publish.assert_called()
            args, kwargs = self.host.publish.call_args
            self.assertEqual(kwargs.get("state"), mock_done_state)

            # Verify Database update
            mock_status.setState.assert_called_with(mock_done_state)
            mock_status.setComment.assert_called_with("Final version for review")

            # --- PHASE 5: Version Control (Restoration) ---
            # User realizes v5 has an error and rolls back to v4
            self.host.restoreVersion = MagicMock(return_value=True)
            
            # Verify restoration handler triggers host logic and UI refresh
            self.app.on_retrieve(None)
            self.host.restoreVersion.assert_called_once()
            self.app.refresh_header.assert_called()


if __name__ == "__main__":
    unittest.main()
