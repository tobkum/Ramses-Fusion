# -*- coding: utf-8 -*-
import os
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType, RAMSES, RAM_SETTINGS, RamMetaDataManager

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

    def collectItemSettings(self, item: RamItem) -> dict:
        """
        Optimized version of base class __collectItemSettings.
        Fetches sequence data in bulk if the item is a shot.
        """
        project = RAMSES.project()
        if not project:
            return {}

        settings = {
            "width": int(project.width() or 1920),
            "height": int(project.height() or 1080),
            "framerate": float(project.framerate() or 24.0),
            "duration": 0.0,
            "pixelAspectRatio": float(project.pixelAspectRatio() or 1.0),
            "aspectRatio": float(project.aspectRatio() or 1.0)
        }

        if item and item.itemType() == ItemType.SHOT:
            settings['duration'] = float(item.duration())
            seq_uuid = item.get("sequence", "")
            if seq_uuid:
                # Optimized bulk fetch
                seq_data = RAMSES.daemonInterface().getData(seq_uuid, "RamSequence")
                if seq_data:
                    settings['width'] = int(seq_data.get("width", settings['width']))
                    settings['height'] = int(seq_data.get("height", settings['height']))
                    settings['framerate'] = float(seq_data.get("framerate", settings['framerate']))
                    pa = float(seq_data.get("pixelAspectRatio", settings['pixelAspectRatio']))
                    settings['pixelAspectRatio'] = pa
                    if settings['height'] > 0:
                        settings['aspectRatio'] = (settings['width'] / settings['height']) * pa

        return settings

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
        
        for path in filePaths:
            loader = self.comp.AddTool("Loader", -32768, -32768)
            if loader:
                # Explicitly set the clip path with forward slashes for cross-platform safety
                loader.Clip[1] = self.normalizePath(path)
                
                # Smart Naming with safety fallback
                if item:
                    name = f"{item.shortName()}_{step.shortName()}" if step else item.shortName()
                else:
                    # Fallback to sanitized base filename
                    base = os.path.splitext(os.path.basename(path))[0]
                    # Sanitize: Fusion node names can't have spaces or dots
                    name = "".join([c if c.isalnum() else "_" for c in base])
                
                # Pipeline Safety: Ensure node name starts with a letter to avoid expression bugs
                if name and name[0].isdigit():
                    name = "R_" + name

                if name:
                    loader.SetAttrs({"TOOLS_Name": name})
                
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

    def _preview(self, previewFolderPath:str, previewFileBaseName:str, item:RamItem, step:RamStep) -> list:
        if not self.comp: return []
        
        # 1. Find the Preview Anchor
        preview_node = self.comp.FindTool("_PREVIEW")
        if not preview_node:
            self.log("Preview anchor (_PREVIEW) not found in Flow. Use 'Setup Scene' to add one.", LogLevel.Warning)
            return []

        # 2. Construct the final path (Ramses provides the folder and basename)
        # Note: We use .mov as our standard preview format
        filename = previewFileBaseName if previewFileBaseName.lower().endswith(".mov") else previewFileBaseName + ".mov"
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
                # Save after render to ensure disarming state is captured and comp is clean
                src = self.currentFilePath()
                if src:
                    self.comp.Save(src)
                return [dst]
            return []
        except Exception as e:
            self.log(f"Preview render failed: {e}", LogLevel.Critical)
            return []
        finally:
            # 5. Always disarm
            preview_node.SetAttrs({"TOOLB_PassThrough": True})

    def _publishOptions(self, proposedOptions:dict, showPublishUI:bool=False) -> dict:
        # If the UI is forced, we could show a dialog here. 
        # For now, we return the options to ensure the process continues.
        return proposedOptions or {}

    def _prePublish(self, publishInfo:RamFileInfo, publishOptions:dict) -> dict:
        return publishOptions or {}

    def _publish(self, publishInfo:RamFileInfo, publishOptions:dict) -> list:
        if not self.comp: return []
        
        src = self.currentFilePath()
        if not src:
            self.log("Cannot publish: current composition has no saved path.", LogLevel.Critical)
            return []
            
        # Ensure publishInfo has the correct extension for the comp backup
        ext = os.path.splitext(src)[1].lstrip('.')
        
        # Use the official API to get the correct publish path
        dst = self.normalizePath(self.publishFilePath(ext, "", publishInfo))
        
        self.log(f"Publishing SRC: {src}", LogLevel.Info)
        self.log(f"Publishing DST: {dst}", LogLevel.Info)
        
        try:
            # 1. Automated Final Render
            # Find the _FINAL anchor node
            final_node = self.comp.FindTool("_FINAL")
            if final_node:
                self.log("Starting final master render...", LogLevel.Info)
                # Enable the node
                final_node.SetAttrs({"TOOLB_PassThrough": False})
                try:
                    # Execute render
                    if self.comp.Render(True):
                        self.log(f"Final render complete: {final_node.Clip[1]}", LogLevel.Info)
                    else:
                        self.log("Final render failed or was cancelled.", LogLevel.Warning)
                finally:
                    # Always disarm
                    final_node.SetAttrs({"TOOLB_PassThrough": True})
            else:
                self.log("No _FINAL anchor found. Skipping final render.", LogLevel.Warning)

            # 2. Perform Comp File Backup (standard Ramses publish)
            # The base class publish() already saves the working file (src) before and after.
            # We only need to save the backup copy (dst) here.
            # Using _saveAs ensures consistent path handling.
            if self._saveAs(dst, None, None, -1, "", False):
                self.log(f"Comp backup published to: {dst}", LogLevel.Info)
                return [dst]
            
            return []
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
                name = f"{item.shortName()}_{step.shortName()}" if step else item.shortName()
                
                # Pipeline Safety: Ensure node name starts with a letter
                if name and name[0].isdigit():
                    name = "R_" + name
                    
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
        if not path: return None
        
        # Use API to parse the selected path and instantiate the correctly typed object
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        nm = RamFileInfo()
        nm.setFilePath(path)
        
        if not item: 
            item = RamItem(data={'name': nm.shortName or 'New', 'shortName': nm.shortName or 'New'}, create=False)
            
        step = RamStep.fromPath(path)
        # Ensure we have a valid Ramses step
        if not step: 
            step = RamStep(data={'name': nm.step or 'New', 'shortName': nm.step or 'New'}, create=False)
        
        return {
            'item': item, 
            'step': step, 
            'extension': os.path.splitext(path)[1].lstrip('.'), 
            'resource': nm.resource
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

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        if not self.comp: return False
        
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
            
        total_frames = int(round(duration * fps))
        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1
        
        width = setupOptions.get("width", 1920)
        height = setupOptions.get("height", 1080)
        pa = setupOptions.get("pixelAspectRatio", 1.0)
        
        # Apply Frame Format Rate via Prefs (required for FPS)
        self.comp.SetPrefs("Comp.FrameFormat.Rate", float(fps))
        
        # Apply Resolution and Aspect Ratio via Attrs (Immediate and more reliable)
        self.comp.SetAttrs({
            "COMPN_Width": int(width),
            "COMPN_Height": int(height),
            "COMPN_AspectX": float(pa),
            "COMPN_AspectY": 1.0,
            "COMPN_PixelAspectX": float(pa),
            "COMPN_PixelAspectY": 1.0,
            "COMPN_GlobalStart": float(start), 
            "COMPN_GlobalEnd": float(end), 
            "COMPN_RenderStart": float(start), 
            "COMPN_RenderEnd": float(end)
        })
        
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