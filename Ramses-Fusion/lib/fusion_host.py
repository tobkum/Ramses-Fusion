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
        """Centralized path normalization for Fusion (forward slashes).

        Args:
            path (str): The file path to normalize.

        Returns:
            str: The normalized path with forward slashes, or empty string if input is None/empty.
        """
        if not path: return ""
        return path.replace("\\", "/")

    @property
    def comp(self):
        """Gets the currently active Fusion composition.

        Returns:
            object: The active Fusion composition object, or None if not available.
        """
        return self.fusion.GetCurrentComp()

    def currentFilePath(self) -> str:
        """Gets the file path of the current composition.

        Returns:
            str: The normalized full path to the current composition file, or empty string if not saved.
        """
        if not self.comp: return ""
        path = self.comp.GetAttrs().get('COMPS_FileName', '')
        return self.normalizePath(path)

    def _isDirty(self) -> bool:
        """Checks if the current composition has unsaved changes.

        Returns:
            bool: True if the composition is modified (dirty), False otherwise.
        """
        if not self.comp: return False
        return self.comp.GetAttrs().get('COMPB_Modified', False)

    def _log(self, message:str, level:int):
        """Logs a message to the Fusion console.

        Args:
            message (str): The message to log.
            level (int): The severity level (from Ramses LogLevel). 
                         Levels below Info are ignored.
        """
        # Silence anything below Info level (0=Debug, -1=DataSent, -2=DataReceived)
        if level < LogLevel.Info:
            return
            
        prefix = self.LOG_PREFIXES.get(level, "LOG")
        print(f"[Ramses][{prefix}] {str(message)}")

    @staticmethod
    def _sanitizeNodeName(name: str) -> str:
        """Ensures a string is a valid Fusion node name.

        Fusion node names must be alphanumeric (underscores allowed) and cannot start with a digit.

        Args:
            name (str): The proposed name.

        Returns:
            str: A sanitized, valid node name.
        """
        if not name:
            return ""
        # Remove invalid chars (keep only alphanumeric and underscore)
        safe_name = "".join([c if c.isalnum() else "_" for c in name])
        # Fusion nodes cannot start with a digit
        if safe_name and safe_name[0].isdigit():
            safe_name = "R_" + safe_name
        return safe_name

    def collectItemSettings(self, item: RamItem) -> dict:
        """Collects resolution and timing settings for the given item.

        Optimized version of base class `__collectItemSettings`.
        Uses API methods to handle overrides correctly while benefiting from DAEMON caching.
        Specifically handles Sequence-level overrides for Shot items.

        Args:
            item (RamItem): The item to collect settings for.

        Returns:
            dict: A dictionary containing 'width', 'height', 'framerate', 'duration', 
                  'pixelAspectRatio', and optionally 'frames'.
        """
        if not item:
            return {}

        # STRICT MODE: Always use the Daemon's active project
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
        """Resolves the official preview file path for the current shot.

        Constructs the path using the project's preview folder and the Ramses naming convention.

        Returns:
            str: The normalized absolute path for the preview file (e.g., .mov), or empty string on failure.
        """
        try:
            # STRICT MODE: Rely on the Daemon's active project to ensure data freshness
            project = RAMSES.project()
            if not project:
                return ""
                
            preview_folder = project.previewPath()
            
            pub_info = self.publishInfo()
            
            preview_info = pub_info.copy()
            preview_info.version = -1
            preview_info.state = ""
            preview_info.resource = ""
            preview_info.extension = "mov"
            
            return self.normalizePath(os.path.join(preview_folder, preview_info.fileName()))
        except Exception:
            return ""

    def resolveFinalPath(self) -> str:
        """Resolves the official master export path for the current shot.

        Attempts to use the project's export path. If not set, falls back to the standard
        publish file path.

        Returns:
            str: The normalized absolute path for the final export file, or empty string on failure.
        """
        try:
            # STRICT MODE: Rely on the Daemon's active project
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
        """Internal implementation to save the composition to a specific path.

        Args:
            filePath (str): The target file path.
            item (RamItem): The item being saved (unused by Fusion implementation).
            step (RamStep): The step context (unused by Fusion implementation).
            version (int): The version number (unused by Fusion implementation).
            comment (str): The comment (unused by Fusion implementation).
            incremented (bool): Whether this is an increment (unused by Fusion implementation).

        Returns:
            bool: True on success, False on failure.
        """
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
        """Internal implementation to open a composition file.

        Args:
            filePath (str): The file path to open.
            item (RamItem): The item context (unused).
            step (RamStep): The step context (unused).

        Returns:
            bool: True if file exists and opened, False otherwise.
        """
        if os.path.exists(filePath):
            # Normalize path for Fusion
            self.fusion.LoadComp(self.normalizePath(filePath))
            return True
        return False
    
    def _setFileName(self, fileName:str ) -> bool:
        """Sets the internal file name of the composition without saving to disk.

        Args:
            fileName (str): The new file name/path.

        Returns:
            bool: True on success, False if no composition is active.
        """
        if not self.comp: return False
        return self.comp.SetAttrs({'COMPS_FileName': self.normalizePath(fileName)})

    def save(self, incremental:bool=False, comment:str=None, setupFile:bool=True) -> bool:
        """Saves the current file, optionally creating a new version or setting up the scene.

        Overridden to bypass the base class implementation of `__collectItemSettings` which
        is less efficient for Fusion. Instead, it calls `_setupCurrentFile` directly with
        optimized settings collection if `setupFile` is True.

        Args:
            incremental (bool, optional): If True, increments the version number. Defaults to False.
            comment (str, optional): A comment describing the version. Defaults to None.
            setupFile (bool, optional): If True, applies project settings (FPS, res) to the comp. Defaults to True.

        Returns:
            bool: True on success, False on failure.
        """
        if setupFile:
            item = self.currentItem()
            if item:
                settings = self.collectItemSettings(item)
                self._setupCurrentFile(item, self.currentStep(), settings)
        
        # Always persist identity metadata before saving
        if not setupFile:
            item = self.currentItem()
            if item:
                self._store_ramses_metadata(item)

        # Calling super().save with setupFile=False avoids the API's __collectItemSettings 
        # while safely calling the private __save method without name-mangling.
        return super(FusionHost, self).save(incremental, comment, setupFile=False)

    # -------------------------------------------------------------------------
    # UI Implementation helpers using UIManager
    # -------------------------------------------------------------------------

    def _request_input(self, title, fields):
        """Shows a custom modal dialog to request user input.

        Uses the Fusion UIManager to create a dynamic form based on the `fields` definition.
        Handles window events and result collection.

        Args:
            title (str): The title of the dialog window.
            fields (list of dict): A list of field definitions. Each dict must contain:
                - 'id' (str): Unique identifier for the field.
                - 'label' (str): Display text for the label.
                - 'type' (str): One of 'text', 'line', 'combo', 'slider', 'checkbox'.
                - 'default' (any): Default value.
                - 'options' (dict, optional): For 'combo' types, mapping index to label.
                - 'lines' (int, optional): For 'text' types, number of lines.

        Returns:
            dict: A dictionary mapping field IDs to their values if the user clicks OK,
                  or None if the user cancels.
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
        """Creates a specific UI control based on the field definition.

        Args:
            ui (UIManager): The Fusion UIManager instance.
            field_def (dict): The field configuration (type, id, default, etc.).

        Returns:
            tuple: (control_object, height_int)
        """
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
        """Imports the specified files as Loader nodes into the current composition.

        Logic:
        1. Determines a grid location below the currently active tool.
        2. Iterates through file paths, creating a Loader node for each.
        3. Staggers nodes horizontally.
        4. Renames nodes based on the Item/Step naming convention (`Item_Step`), sanitizing names to be Fusion-safe.
        5. Sets the Global Start time to match the project start.

        Args:
            filePaths (list): List of absolute file paths to import.
            item (RamItem): The source item associated with the files.
            step (RamStep): The source step associated with the files.
            importOptions (list): (Unused) Import options.
            forceShowImportUI (bool): (Unused) Whether to force UI.

        Returns:
            bool: True on success, False if no composition is open.
        """
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
        """Shows the native Fusion file request dialog for importing.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            dict: {'filePaths': [path]} or None if cancelled.
        """
        path = self.fusion.RequestFile()
        return {'filePaths': [path]} if path else None

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        """Shows the native Fusion file request dialog for opening a composition.

        Args:
            item (RamItem, optional): Context item.
            step (RamStep, optional): Context step.

        Returns:
            dict: {'filePath': path} or None if cancelled.
        """
        path = self.fusion.RequestFile()
        return {'filePath': path} if path else None

    def _preview(
        self,
        previewFolderPath: str,
        previewFileBaseName: str,
        item: RamItem,
        step: RamStep,
    ) -> list:
        """Renders a preview using the `_PREVIEW` Saver anchor.

        Locates the specific `_PREVIEW` node in the flow, sets its output path,
        applies the preview render preset (ProRes 422), triggers the render,
        and verifies the output file.

        Args:
            previewFolderPath (str): Target directory for the preview.
            previewFileBaseName (str): Base filename (without extension usually, but handled here).
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            list: List of generated file paths (usually just one), or empty list on failure.
        """
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
        self.apply_render_preset(preview_node, "preview")
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
        """Returns the publish options, optionally showing a UI.

        Currently just passes through default options.

        Args:
            proposedOptions (dict): Default options from the Step configuration.
            showPublishUI (bool): Whether to force a UI dialog.

        Returns:
            dict: The final publish options.
        """
        # If the UI is forced, we could show a dialog here.
        # For now, we return the options to ensure the process continues.
        return proposedOptions or {}

    def _prePublish(self, publishInfo: RamFileInfo, publishOptions: dict) -> dict:
        """Hook called before the publish process begins.

        Args:
            publishInfo (RamFileInfo): Info about the file to be published.
            publishOptions (dict): Options for the publish process.

        Returns:
            dict: Potentially modified publish options.
        """
        return publishOptions or {}

    def _verify_render_output(self, path: str) -> bool:
        """Verifies that a render output exists and is valid.

        Checks existence and non-zero file size.

        Args:
            path (str): The path to verify.

        Returns:
            bool: True if file exists and size > 0, False otherwise.
        """
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
        """Updates the item status in the database, optionally publishing and creating previews.

        Implements an atomic-like transaction:
        1. Saves and increments the version (on disk).
        2. Tries to publish (if requested).
        3. Updates the database status ONLY if publish succeeds (or wasn't requested).
        4. Generates a preview (optional).

        Args:
            state (RamState, optional): The target state. If None, shows UI.
            comment (str, optional): Comment for the version.
            completionRatio (int, optional): Progress percentage (0-100).
            savePreview (bool, optional): Whether to generate a preview render.
            publish (bool, optional): Whether to publish the file.
            showPublishUI (bool, optional): Whether to force the publish UI.

        Returns:
            bool: True on success, False on failure or cancellation.
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
        """Executes the publish process: Final Render + Comp Backup.

        Implements a "Split Publish":
        1. Render: If `_FINAL` anchor exists, renders it to the Project Export folder.
        2. Backup: Saves a copy of the `.comp` file to the Step Publish folder (`_published`).
        
        If the render fails, the entire process is aborted.

        Args:
            publishInfo (RamFileInfo): Info about the file to be published.
            publishOptions (dict): Options for the publish process.

        Returns:
            list: List of published file paths (rendered file + backup file).
        """
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
        # 0. Sync Render Anchors (Critical for path validity)
        # Note: Handled by caller (RamsesFusionApp) or here?
        # App calls _sync_render_anchors() before save(), so we assume paths are correct.

        # 1. Store Internal Metadata (Project/Item UUID consistency)
        # This ensures we can identify the file's project even if paths are ambiguous.
        item = self.currentItem()
        if item:
            self._store_ramses_metadata(item)

        # 2. File Operation
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
        """Replaces the selected Loader node's clip with the specified file.

        Also updates the node name if it was using a generic name.

        Args:
            filePaths (list): List containing the new file path (only first is used).
            item (RamItem): Context item (for naming).
            step (RamStep): Context step (for naming).
            importOptions (list): (Unused).
            forceShowImportUI (bool): (Unused).

        Returns:
            bool: True on success, False if no valid Loader selected.
        """
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
        """Shows the native Fusion file request dialog for replacing.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            dict: {'filePaths': [path]} or None if cancelled.
        """
        res = self._openUI(item, step)
        if res: return {"filePaths": [res["filePath"]]}
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        """Shows a UI to select a version to restore.

        Args:
            versionFiles (list): List of file paths to previous versions.

        Returns:
            str: The selected file path, or empty string if cancelled.
        """
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
        """Shows the native Fusion file request dialog for 'Save As'.

        Parsing the selected path to reconstruct Ramses Item/Step context.

        Returns:
            dict: Dictionary with 'item', 'step', 'extension', 'resource', or None if cancelled.
        """
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
        """Shows a dialog asking to save changes before closing/opening.

        Returns:
            str: 'save', 'discard', or 'cancel'.
        """
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

    def apply_render_preset(self, node, preset_name: str = "preview") -> None:
        """Applies standard pipeline settings (codec, format) to a Saver node.
        
        Hardcoded to Apple ProRes for now.

        Args:
            node (Tool): The Saver node to modify.
            preset_name (str, optional): 'preview' or 'final'. Defaults to "preview".
        """
        # Future: This will fetch config from self.ramses.settings
        node.SetInput("OutputFormat", "QuickTimeMovies", 0)
        
        if preset_name == "preview":
            node.SetInput("QuickTimeMovies.Compression", "Apple ProRes 422_apcn", 0)
        else:
            # Final / default
            node.SetInput("QuickTimeMovies.Compression", "Apple ProRes 4444_ap4h", 0)

    def _store_ramses_metadata(self, item: RamItem) -> None:
        """Embeds Ramses identity (Project/Item UUIDs) into Fusion composition metadata.

        This ensures the file can be identified even if moved outside the project structure.

        Args:
            item (RamItem): The item whose identity to store.
        """
        if not self.comp or not item:
            return
        
        try:
            # Store Item UUID
            self.comp.SetData("Ramses.ItemUUID", str(item.uuid()))
            
            # Store Project UUID (Resolves cross-project ambiguity)
            project = item.project() or RAMSES.project()
            if project:
                self.comp.SetData("Ramses.ProjectUUID", str(project.uuid()))
                
            self.log(f"Embedded Ramses Metadata: {item.name()}", LogLevel.Debug)
        except Exception as e:
            self.log(f"Failed to embed metadata: {e}", LogLevel.Warning)

    def _setupCurrentFile(self, item: RamItem, step: RamStep, setupOptions: dict) -> bool:
        """Applies Ramses settings (resolution, FPS, ranges) to the current composition.

        Updates Fusion Preferences (FrameFormat) and Attributes (Timeline/Render ranges).
        Persists identity metadata.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.
            setupOptions (dict): Dictionary with 'width', 'height', 'framerate', 'frames', etc.

        Returns:
            bool: True on success.
        """
        if not self.comp:
            return False

        # Get duration from options or fallback to item
        fps = setupOptions.get("framerate", 24.0)
        duration = setupOptions.get("duration", 0.0)

        # If duration is 0, try to get it directly from item if it's a shot
        if duration <= 0 and item and item.itemType() == ItemType.SHOT:
            try:
                duration = float(item.duration())
            except (ValueError, TypeError, AttributeError):
                # Duration may be None or invalid, use default
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

        # Apply Resolution, Rate and Aspect Ratio via Prefs (batched for efficiency)
        new_prefs = {}
        if curr_w != int(width):
            new_prefs["Comp.FrameFormat.Width"] = int(width)
        if curr_h != int(height):
            new_prefs["Comp.FrameFormat.Height"] = int(height)
        if abs(curr_fps - float(fps)) > 0.001:
            new_prefs["Comp.FrameFormat.Rate"] = float(fps)
        if abs(curr_pa_x - float(pa)) > 0.001:
            new_prefs["Comp.FrameFormat.AspectX"] = float(pa)
        if abs(curr_pa_y - 1.0) > 0.001:
            new_prefs["Comp.FrameFormat.AspectY"] = 1.0

        if new_prefs:
            self.comp.SetPrefs(new_prefs)

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

        # Persist Identity Metadata
        self._store_ramses_metadata(item)

        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        """Shows the dialog to update status, comment, and publish settings.

        Args:
            currentStatus (RamStatus, optional): The current status object.

        Returns:
            dict: Dictionary with keys 'comment', 'completionRatio', 'publish', 'state', 'showPublishUI', 'savePreview'.
                  Returns None if cancelled.
        """
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