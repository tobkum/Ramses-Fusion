# -*- coding: utf-8 -*-
import os
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType, RAMSES, RAM_SETTINGS, RamMetaDataManager, RamState

class FusionHost(RamHost):
    """
    Ramses Host implementation for Blackmagic Fusion.
    """
    LOG_PREFIXES = {
        LogLevel.Info: "INFO",
        LogLevel.Warning: "WARNING",
        LogLevel.Critical: "ERROR",
        LogLevel.Debug: "DEBUG"
    }

    def __init__(self, fusion_obj):
        super(FusionHost, self).__init__()
        self.fusion = fusion_obj
        self.hostName = "Fusion"
        
        try:
            self.hostVersion = str(self.fusion.GetAttrs().get('FUSION_Version', 'Unknown'))
        except Exception:
            self.hostVersion = "Unknown"

    @staticmethod
    def normalizePath(path: str) -> str:
        """Centralized path normalization for Fusion (forward slashes)."""
        if not path: return ""
        return path.replace("\\", "/")

    @property
    def comp(self):
        """Always get the currently active composition."""
        return self.fusion.GetCurrentComp()

    def currentFilePath(self) -> str:
        if not self.comp: return ""
        path = self.comp.GetAttrs().get('COMPS_FileName', '')
        return self.normalizePath(path)

    def _isDirty(self) -> bool:
        if not self.comp: return False
        return self.comp.GetAttrs().get('COMPB_Modified', False)

    def _log(self, message:str, level:int):
        # Silence anything below Info level (0=Debug, -1=DataSent, -2=DataReceived)
        if level < LogLevel.Info:
            return
            
        prefix = self.LOG_PREFIXES.get(level, "LOG")
        print(f"[Ramses][{prefix}] {str(message)}")

    @staticmethod
    def _sanitizeNodeName(name: str) -> str:
        """Ensures a string is a valid Fusion node name (alphanumeric, starts with letter)."""
        if not name:
            return ""
        # Remove invalid chars (keep only alphanumeric and underscore)
        safe_name = "".join([c if c.isalnum() else "_" for c in name])
        # Fusion nodes cannot start with a digit
        if safe_name and safe_name[0].isdigit():
            safe_name = "R_" + safe_name
        return safe_name

    def collectItemSettings(self, item: RamItem) -> dict:
        """
        Optimized version of base class __collectItemSettings.
        Uses API methods to handle overrides correctly while benefiting from DAEMON caching.
        """
        if not item:
            return {}

        # Try to get the project from the item itself to avoid using the Daemon's active project
        project = item.project()
        p_uuid = item.get("project", "")
        if p_uuid:
            if not project or project.uuid() != p_uuid:
                from ramses import RamProject

                project = RamProject(p_uuid)

        if not project:
            project = RAMSES.project()

        if not project:
            return {}

        settings = {
            "width": int(project.width() or 1920),
            "height": int(project.height() or 1080),
            "framerate": float(project.framerate() or 24.0),
            "duration": 0.0,
            "pixelAspectRatio": float(project.pixelAspectRatio() or 1.0),
        }

        if item and item.itemType() == ItemType.SHOT:
            # Use the sequence object to benefit from API override logic
            from ramses import RamShot

            shot = item if isinstance(item, RamShot) else RamShot(item.uuid())

            settings["duration"] = float(shot.duration())
            # Calculate frames manually using Project FPS (currently in settings['framerate'])
            # We use round() to avoid truncation errors present in the API's shot.frames() which uses int()
            settings["frames"] = int(round(settings["duration"] * settings["framerate"]))

            seq = shot.sequence()
            if seq:
                settings["width"] = int(seq.width())
                settings["height"] = int(seq.height())
                settings["framerate"] = float(seq.framerate())
                settings["pixelAspectRatio"] = float(seq.pixelAspectRatio())

        return settings

    def resolvePreviewPath(self) -> str:
        """Resolves the official flat preview path for the current shot."""
        try:
            pub_info = self.publishInfo()
            preview_folder = self.previewPath()
            
            preview_info = pub_info.copy()
            preview_info.version = -1
            preview_info.state = ""
            preview_info.resource = ""
            preview_info.extension = "mov"
            
            return self.normalizePath(os.path.join(preview_folder, preview_info.fileName()))
        except Exception:
            return ""

    def resolveFinalPath(self) -> str:
        """Resolves the official master export path for the current shot."""
        try:
            project = RAMSES.project()
            if not project: return ""
            
            export_folder = project.exportPath()
            if not export_folder:
                return self.normalizePath(self.publishFilePath("mov", ""))
                
            pub_info = self.publishInfo()
            final_info = pub_info.copy()
            final_info.version = -1
            final_info.state = ""
            final_info.resource = ""
            final_info.extension = "mov"
            
            return self.normalizePath(os.path.join(export_folder, final_info.fileName()))
        except Exception:
            return ""

    def _saveAs(self, filePath:str, item:RamItem, step:RamStep, version:int, comment:str, incremented:bool) -> bool:
        if not self.comp: return False
        # Normalize path for Fusion
        filePath = self.normalizePath(filePath)
        try:
            self.comp.Save(filePath)
            return True
        except Exception as e:
            self.log(f"Failed to save: {e}", LogLevel.Critical)
            return False

    def _open(self, filePath:str, item:RamItem, step:RamStep) -> bool:
        if os.path.exists(filePath):
            # Normalize path for Fusion
            self.fusion.LoadComp(self.normalizePath(filePath))
            return True
        return False
    
    def _setFileName(self, fileName:str ) -> bool:
        if not self.comp: return False
        return self.comp.SetAttrs({'COMPS_FileName': self.normalizePath(fileName)})

    def save(self, incremental:bool=False, comment:str=None, setupFile:bool=True) -> bool:
        """
        Overridden to bypass sub-optimal base class implementation of __collectItemSettings.
        """
        if setupFile:
            item = self.currentItem()
            if item:
                settings = self.collectItemSettings(item)
                self._setupCurrentFile(item, self.currentStep(), settings)

        # Calling super().save with setupFile=False avoids the API's __collectItemSettings 
        # while safely calling the private __save method without name-mangling.
        return super(FusionHost, self).save(incremental, comment, setupFile=False)

    # -------------------------------------------------------------------------
    # UI Implementation helpers using UIManager
    # -------------------------------------------------------------------------

    def _request_input(self, title, fields):
        """
        Custom helper to show a dialog using UIManager instead of AskUser.
        """
        ui = self.fusion.UIManager
        disp = bmd.UIDispatcher(ui)
        
        # Use a more unique ID to avoid dispatcher conflicts
        win_id = f"RamsesDlg_{int(os.getpid())}_{id(fields)}"
        
        # Modal behavior: Disable main window if it exists
        main_win = None
        if hasattr(self, "app") and hasattr(self.app, "dlg"):
            main_win = self.app.dlg
            
        if main_win:
            main_win.Enabled = False
        
        rows = []
        total_height = 80 # Buttons + Margins
        
        for f in fields:
            label = ui.Label({"Text": f['label'], "Weight": 0.25})
            ctrl, height = self._create_ui_element(ui, f)
            total_height += height
            rows.append(ui.HGroup([label, ctrl]))

        dlg = disp.AddWindow(
            {"WindowTitle": title, "ID": win_id, "Geometry": [400, 400, 500, total_height]},
            ui.VGroup([
                ui.VGroup({"Spacing": 5}, rows),
                ui.VGap(10),
                ui.HGroup([
                    ui.HGap(200),
                    ui.Button({"ID": "OkBtn", "Text": "OK", "Weight": 0.1}),
                    ui.Button({"ID": "CancelBtn", "Text": "Cancel", "Weight": 0.1})
                ])
            ])
        )
        
        results = {}
        
        def on_ok(ev):
            items = dlg.GetItems()
            for f in fields:
                ctrl = items[f['id']]
                if f['type'] == 'text': results[f['id']] = ctrl.PlainText
                elif f['type'] == 'line': results[f['id']] = ctrl.Text
                elif f['type'] == 'combo': results[f['id']] = int(ctrl.CurrentIndex)
                elif f['type'] == 'slider': results[f['id']] = int(ctrl.Value)
                elif f['type'] == 'checkbox': results[f['id']] = bool(ctrl.Checked)
            
            # Stop the loop
            disp.ExitLoop()
            
        def on_cancel(ev):
            disp.ExitLoop()
            
        # Bind handlers
        dlg.On.OkBtn.Clicked = on_ok
        dlg.On.CancelBtn.Clicked = on_cancel
        dlg.On[win_id].Close = on_cancel
        
        try:
            dlg.Show()
            disp.RunLoop()
        finally:
            # Cleanup handlers safely
            try:
                dlg.On.OkBtn.Clicked = None
                dlg.On.CancelBtn.Clicked = None
                dlg.On[win_id].Close = None
            except Exception:
                pass
                
            dlg.Hide()
            # Re-enable main window
            if main_win:
                main_win.Enabled = True
        
        return results if results else None

    def _create_ui_element(self, ui, field_def):
        """Helper to create UIManager elements from field definitions."""
        f_type = field_def['type']
        f_id = field_def['id']
        default = field_def.get('default', '')
        
        if f_type == 'text':
            h = field_def.get('lines', 1) * 25 + 20
            return ui.TextEdit({"ID": f_id, "Text": str(default), "Weight": 0.75, "MinimumSize": [200, h]}), h
            
        if f_type == 'line':
            return ui.LineEdit({"ID": f_id, "Text": str(default), "Weight": 0.75}), 30
            
        if f_type == 'combo':
            ctrl = ui.ComboBox({"ID": f_id, "Weight": 0.75})
            options = field_def.get('options', {})
            for i in range(len(options)):
                val = options.get(str(i))
                if val: ctrl.AddItem(str(val))
            ctrl.CurrentIndex = int(field_def.get('default', 0))
            return ctrl, 30
            
        if f_type == 'slider':
            return ui.Slider({"ID": f_id, "Value": float(default), "Minimum": 0, "Maximum": 100, "Weight": 0.75}), 30
            
        if f_type == 'checkbox':
            return ui.CheckBox({"ID": f_id, "Checked": bool(default), "Text": "", "Weight": 0.75}), 30
            
        return ui.Label({"Text": "Unknown Field"}), 30

    # -------------------------------------------------------------------------
    # Pipeline Implementation
    # -------------------------------------------------------------------------

    def _import(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        if not self.comp: return False
        self.comp.Lock()
        
        # Get start frame for alignment
        start_frame = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)

        # Determine Reference Position (Grid Units)
        flow = self.comp.CurrentFrame.FlowView
        start_x, start_y = 0, 0

        active = self.comp.ActiveTool
        if active and flow:
            pos = flow.GetPosTable(active)
            # Fusion returns {1.0: x, 2.0: y} in Grid Units
            if pos:
                start_x = pos[1]
                start_y = pos[2] + 1 # Start one unit below active tool

        for i, path in enumerate(filePaths):
            # Stagger horizontally
            target_x = start_x + i
            target_y = start_y
            
            loader = self.comp.AddTool("Loader", target_x, target_y)
            if loader:
                # Explicitly set the clip path with forward slashes for cross-platform safety
                loader.Clip[1] = self.normalizePath(path)
                
                # Smart Naming with safety fallback
                if item:
                    raw_name = f"{item.shortName()}_{step.shortName()}" if step else item.shortName()
                else:
                    # Fallback to sanitized base filename
                    raw_name = os.path.splitext(os.path.basename(path))[0]
                
                name = self._sanitizeNodeName(raw_name)

                if name:
                    # Prevent name collisions by checking if node exists and appending counter
                    final_name = name
                    counter = 1
                    while self.comp.FindTool(final_name):
                        final_name = f"{name}_{counter}"
                        counter += 1
                    loader.SetAttrs({"TOOLS_Name": final_name})
                
                # Automatic Alignment
                loader.GlobalIn[1] = float(start_frame)
                
        self.comp.Unlock()
        return True

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        path = self.fusion.RequestFile()
        return {'filePaths': [path]} if path else None

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        path = self.fusion.RequestFile()
        return {'filePath': path} if path else None

    def _preview(
        self,
        previewFolderPath: str,
        previewFileBaseName: str,
        item: RamItem,
        step: RamStep,
    ) -> list:
        if not self.comp:
            return []

        # 1. Find the Preview Anchor
        preview_node = self.comp.FindTool("_PREVIEW")
        if not preview_node:
            self.log(
                "Preview anchor (_PREVIEW) not found in Flow. Use 'Setup Scene' to add one.",
                LogLevel.Warning,
            )
            return []

        # 2. Construct the final path (Ramses provides the folder and basename)
        # Note: We use .mov as our standard preview format
        filename = (
            previewFileBaseName
            if previewFileBaseName.lower().endswith(".mov")
            else previewFileBaseName + ".mov"
        )
        dst = self.normalizePath(os.path.join(previewFolderPath, filename))

        # 3. Armed for render
        self.log(f"Starting preview render to: {dst}", LogLevel.Info)
        preview_node.Clip[1] = dst
        # Ensure ProRes 422 settings
        preview_node.SetInput("OutputFormat", "QuickTimeMovies", 0)
        preview_node.SetInput("QuickTimeMovies.Compression", "Apple ProRes 422_apcn", 0)
        preview_node.SetAttrs({"TOOLB_PassThrough": False})

        try:
            # 4. Trigger Fusion Render
            if self.comp.Render(True):
                # 5. Verify the output
                if self._verify_render_output(dst):
                    # Disarm immediately after render
                    preview_node.SetAttrs({"TOOLB_PassThrough": True})

                    # Save after render to ensure comp is clean and context is preserved
                    src = self.currentFilePath()
                    if src:
                        self.comp.Save(src)
                    return [dst]
                else:
                    self.log(
                        f"Preview render produced an invalid file: {dst}",
                        LogLevel.Critical,
                    )
            return []
        except Exception as e:
            self.log(f"Preview render failed: {e}", LogLevel.Critical)
            return []
        finally:
            # 6. Always disarm (redundant safety)
            if preview_node:
                preview_node.SetAttrs({"TOOLB_PassThrough": True})

    def _publishOptions(self, proposedOptions: dict, showPublishUI: bool = False) -> dict:
        # If the UI is forced, we could show a dialog here.
        # For now, we return the options to ensure the process continues.
        return proposedOptions or {}

    def _prePublish(self, publishInfo: RamFileInfo, publishOptions: dict) -> dict:
        return publishOptions or {}

    def _verify_render_output(self, path: str) -> bool:
        """Verifies that a render output exists and is not a 0-byte file."""
        if not path:
            return False
        if not os.path.exists(path):
            return False
        # Check for 0-byte files which often indicate a failed or interrupted render
        if os.path.getsize(path) == 0:
            return False
        return True

    def updateStatus(
        self,
        state: RamState = None,
        comment: str = "",
        completionRatio: int = 50,
        savePreview: bool = False,
        publish: bool = False,
        showPublishUI: bool = False,
    ) -> bool:
        """
        Overridden to ensure status update and publish are atomic.
        We rearrange the base class logic so the DB update only happens if the publish succeeds.
        """
        # 1. Basic checks
        if not self.testDaemonConnection():
            return False

        # Ensure we are saved at least once as a Ramses item
        if not self.currentItem() and not self.save():
            return False

        # 2. Collect user input if parameters are missing
        if state is None:
            newStatusDict = self._statusUI(self.currentStatus())
            if not newStatusDict:
                return False

            publish = newStatusDict.get("publish", False)
            savePreview = newStatusDict.get("savePreview", False)
            comment = newStatusDict.get("comment", "")
            completionRatio = newStatusDict.get("completionRatio", 50)
            state = newStatusDict.get("state", RAMSES.defaultState)
            showPublishUI = newStatusDict.get("showPublishUI", False)

        # 3. Step 1 of Transaction: Save and Increment Version
        # This creates the physical version on disk that we will either publish or keep as WIP.
        # We call save(incremental=True) which calls the private __save method.
        if not self.save(incremental=True, comment="Status change"):
            self.log("Failed to save new version for status update.", LogLevel.Critical)
            return False

        # 4. Step 2 of Transaction: Publish (if requested)
        # If publish fails (render fails), we abort the database update.
        if publish:
            # incrementVersion=False because we just incremented it above.
            if not self.publish(showPublishUI, incrementVersion=False):
                self.log(
                    "Publish failed. Status update to database aborted.",
                    LogLevel.Critical,
                )
                return False

        # 5. Step 3 of Transaction: Update the Database
        # Only reached if Publish succeeded OR was not requested.
        status = self.currentStatus()
        if status:
            status.setComment(comment)
            status.setCompletionRatio(completionRatio)
            status.setState(state)
            status.setVersion(self.currentVersion())

        # 6. Preview (Non-critical, doesn't abort the status update if it fails)
        if savePreview:
            try:
                self.savePreview()
            except Exception as e:
                self.log(f"Optional preview generation failed: {e}", LogLevel.Warning)

        return True

    def _publish(self, publishInfo: RamFileInfo, publishOptions: dict) -> list:
        if not self.comp:
            return []

        src = self.currentFilePath()
        if not src:
            self.log(
                "Cannot publish: current composition has no saved path.",
                LogLevel.Critical,
            )
            return []

        # Ensure publishInfo has the correct extension for the comp backup
        ext = os.path.splitext(src)[1].lstrip(".")

        # Use the official API to get the correct publish path
        dst = self.normalizePath(self.publishFilePath(ext, "", publishInfo))

        self.log(f"Publishing SRC: {src}", LogLevel.Info)
        self.log(f"Publishing DST: {dst}", LogLevel.Info)

        published_files = []

        try:
            # 1. Automated Final Render
            # Find the _FINAL anchor node
            final_node = self.comp.FindTool("_FINAL")
            if final_node:
                self.log("Starting final master render...", LogLevel.Info)
                # Enable the node
                final_node.SetAttrs({"TOOLB_PassThrough": False})
                render_success = False
                render_path = ""
                try:
                    # Execute render - comp.Render returns True only on success
                    if self.comp.Render(True):
                        render_path = self.normalizePath(final_node.Clip[1])
                        # Secondary Verification: Check file existence and size
                        if self._verify_render_output(render_path):
                            self.log(
                                f"Final render complete and verified: {render_path}",
                                LogLevel.Info,
                            )
                            render_success = True
                            published_files.append(render_path)
                        else:
                            self.log(
                                f"Final render produced an invalid file: {render_path}",
                                LogLevel.Critical,
                            )
                    else:
                        self.log(
                            "Final render failed or was cancelled by user.",
                            LogLevel.Warning,
                        )
                finally:
                    # Always disarm
                    final_node.SetAttrs({"TOOLB_PassThrough": True})

                # GATEKEEPER: If render was attempted but failed/invalid, abort everything
                if not render_success:
                    self.log(
                        "Publish ABORTED: Render failed. No files will be published.",
                        LogLevel.Critical,
                    )
                    return []
            else:
                self.log(
                    "No _FINAL anchor found. Skipping final render.", LogLevel.Warning
                )

            # 2. Perform Comp File Backup (standard Ramses publish)
            # This only happens if there was no final_node OR if final_node render succeeded.
            if self._saveAs(dst, None, None, -1, "", False):
                self.log(f"Comp backup published to: {dst}", LogLevel.Info)
                published_files.append(dst)

            return published_files
        except Exception as e:
            self.log(f"Publish failed during process: {e}", LogLevel.Critical)
            return []

    def _replace(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        if not self.comp: return False
        active = self.comp.ActiveTool
        if not active or active.GetAttrs()["TOOLS_RegID"] != "Loader":
            self.log("Please select a Loader node to replace.", LogLevel.Warning)
            return False
        
        if filePaths:
            active.Clip[1] = self.normalizePath(filePaths[0])
            # Rename if it was a generic name
            if "Loader" in active.GetAttrs()["TOOLS_Name"]:
                raw_name = f"{item.shortName()}_{step.shortName()}" if step else item.shortName()
                name = self._sanitizeNodeName(raw_name)
                    
                active.SetAttrs({"TOOLS_Name": name})
            return True
        return False

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        res = self._openUI(item, step)
        if res: return {"filePaths": [res["filePath"]]}
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        if not versionFiles: return ""
        
        # Enrich options with comments from metadata
        opts = {}
        for i, f in enumerate(versionFiles):
            comment = RamMetaDataManager.getComment(f)
            basename = os.path.basename(f)
            label = f"{basename} - [{comment}]" if comment else basename
            opts[str(i)] = label
            
        res = self._request_input("Restore Version", [
            {'id': 'Idx', 'label': 'Select Version:', 'type': 'combo', 'options': opts}
        ])
        return versionFiles[res['Idx']] if res else ""

    def _saveAsUI(self) -> dict:
        path = self.fusion.RequestFile()
        if not path:
            return None

        # Use API to parse the selected path and instantiate the correctly typed object
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        nm = RamFileInfo()
        nm.setFilePath(path)

        if not nm.project:
            self.log(
                "The selected path does not seem to belong to a Ramses project. This may cause pipeline issues.",
                LogLevel.Warning,
            )

        if not item:
            item = RamItem(
                data={"name": nm.shortName or "New", "shortName": nm.shortName or "New"},
                create=False,
            )

        step = RamStep.fromPath(path)
        # Ensure we have a valid Ramses step
        if not step:
            step = RamStep(
                data={"name": nm.step or "New", "shortName": nm.step or "New"},
                create=False,
            )

        return {
            "item": item,
            "step": step,
            "extension": os.path.splitext(path)[1].lstrip("."),
            "resource": nm.resource,
        }

    def _saveChangesUI(self) -> str:
        res = self._request_input("Save Changes?", [
            {'id': 'Mode', 'label': 'Current file is modified. Action:', 'type': 'combo', 'options': {
                '0': 'Save and Continue',
                '1': 'Discard and Continue',
                '2': 'Cancel'
            }}
        ])
        if not res: return "cancel"
        modes = {0: "save", 1: "discard", 2: "cancel"}
        return modes.get(res['Mode'], "cancel")

    def _setupCurrentFile(self, item: RamItem, step: RamStep, setupOptions: dict) -> bool:
        if not self.comp:
            return False

        # Get duration from options or fallback to item
        fps = setupOptions.get("framerate", 24.0)
        duration = setupOptions.get("duration", 0.0)

        # If duration is 0, try to get it directly from item if it's a shot
        if duration <= 0 and item and item.itemType() == ItemType.SHOT:
            try:
                duration = float(item.duration())
            except:
                duration = 5.0

        # Fallback to a default if still 0
        if duration <= 0:
            duration = 5.0

        # If we have an explicit frame count from Ramses, use it.
        # Otherwise calculate from duration and (potentially overridden) FPS.
        if setupOptions.get("frames", 0) > 0:
            total_frames = int(setupOptions["frames"])
        else:
            total_frames = int(round(duration * fps))

        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1

        width = setupOptions.get("width", 1920)
        height = setupOptions.get("height", 1080)
        pa = setupOptions.get("pixelAspectRatio", 1.0)

        # Check if changes are actually needed (avoid dirtying the comp)
        curr_prefs = self.comp.GetPrefs("Comp.FrameFormat") or {}
        curr_w = int(curr_prefs.get("Width", 0))
        curr_h = int(curr_prefs.get("Height", 0))
        curr_fps = float(curr_prefs.get("Rate", 24.0))
        curr_pa_x = float(curr_prefs.get("AspectX", 1.0))
        curr_pa_y = float(curr_prefs.get("AspectY", 1.0))

        # Apply Resolution, Rate and Aspect Ratio via Prefs as requested
        if curr_w != int(width):
            self.comp.SetPrefs("Comp.FrameFormat.Width", int(width))
        if curr_h != int(height):
            self.comp.SetPrefs("Comp.FrameFormat.Height", int(height))
        if abs(curr_fps - float(fps)) > 0.001:
            self.comp.SetPrefs("Comp.FrameFormat.Rate", float(fps))
        if abs(curr_pa_x - float(pa)) > 0.001:
            self.comp.SetPrefs("Comp.FrameFormat.AspectX", float(pa))
        if abs(curr_pa_y - 1.0) > 0.001:
            self.comp.SetPrefs("Comp.FrameFormat.AspectY", 1.0)

        # Apply Timeline Ranges via Attrs (Immediate and more reliable)
        attrs = self.comp.GetAttrs()
        new_attrs = {}

        if attrs.get("COMPN_GlobalStart") != float(start):
            new_attrs["COMPN_GlobalStart"] = float(start)
        if attrs.get("COMPN_GlobalEnd") != float(end):
            new_attrs["COMPN_GlobalEnd"] = float(end)
        if attrs.get("COMPN_RenderStart") != float(start):
            new_attrs["COMPN_RenderStart"] = float(start)
        if attrs.get("COMPN_RenderEnd") != float(end):
            new_attrs["COMPN_RenderEnd"] = float(end)

        if new_attrs:
            self.comp.SetAttrs(new_attrs)

        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        states = RAMSES.states()
        if not states: return None
        state_opts = {str(i): s.name() for i, s in enumerate(states)}
        
        cur_comment = currentStatus.comment() if currentStatus else ""
        cur_short = currentStatus.state().shortName() if currentStatus else "WIP"
        def_idx = next((i for i, s in enumerate(states) if s.shortName() == cur_short), 0)

        res = self._request_input("Update Status", [
            {'id': 'Comment', 'label': 'Comment:', 'type': 'text', 'default': cur_comment, 'lines': 6},
            {'id': 'State', 'label': 'State:', 'type': 'combo', 'options': state_opts, 'default': def_idx},
            {'id': 'Publish', 'label': 'Publish:', 'type': 'checkbox', 'default': False}
        ])
        
        if not res: return None
        
        selected_state = states[res['State']]
        
        return {
            "comment": res['Comment'], 
            "completionRatio": int(selected_state.completionRatio()), 
            "publish": res['Publish'], 
            "state": selected_state, 
            "showPublishUI": False, 
            "savePreview": False
        }