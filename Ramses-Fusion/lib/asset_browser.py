# -*- coding: utf-8 -*-
import os
import re
from ramses import RamItem, RamStep, RamFileInfo, ItemType, LogLevel

class AssetBrowser:
    def __init__(self, host, fusion_ui, dispatcher):
        self.host = host
        self.ui = fusion_ui
        self.disp = dispatcher
        self.dlg = None
        self.step_map = {}
        self.current_shot = None
        
        # Hardcoded skip states
        self.SKIP_STATES = ["NA", "OMIT", "NO", "WAIT"]

    def show(self):
        """Displays the browser dialog."""
        self.current_shot = self.host.currentItem()
        current_step = self.host.currentStep()
        
        if not self.current_shot:
            self.host._request_input("Error", [{"id": "E", "label": "Error", "type": "label", "default": "No active shot found."}])
            return None

        # Resolve initial source
        initial_step = self.resolve_upstream_source(self.current_shot, current_step)
        if not initial_step:
             # Fallback to current step if no upstream found (e.g. we are at Plate)
             initial_step = current_step
        
        win_id = "AssetBrowser"
        
        # UI Layout
        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": f"Import: {self.current_shot.name()}",
                "ID": win_id,
                "Geometry": [300, 300, 600, 400],
            },
            self.ui.VGroup([
                self.ui.Label({"Text": "Select Source Step:", "Weight": 0}),
                self.ui.ComboBox({"ID": "StepCombo", "Weight": 0}),
                self.ui.VGap(10),
                self.ui.Label({"Text": "Published Versions:", "Weight": 0}),
                self.ui.Tree({"ID": "VersionTree", "Weight": 1, "HeaderHidden": False, "ColumnCount": 2}),
                self.ui.VGap(10),
                self.ui.HGroup({"Weight": 0}, [
                    self.ui.HGap(0, 1),
                    self.ui.Button({"ID": "ImportBtn", "Text": "Import", "Weight": 0, "MinimumSize": [100, 30]}),
                    self.ui.Button({"ID": "CancelBtn", "Text": "Cancel", "Weight": 0, "MinimumSize": [100, 30]}),
                ])
            ])
        )
        
        # Setup Tree Columns
        items = self.dlg.GetItems()
        tree = items["VersionTree"]
        tree.SetHeaderLabels(["Version", "Path"])
        # Hide Path column (index 1) by setting width to 0
        tree.ColumnWidth[1] = 0

        # Populate Steps Combo
        project = self.current_shot.project()
        from ramses import StepType
        # Fetch all shot production steps
        all_steps = project.steps(StepType.SHOT_PRODUCTION)
        
        combo = items["StepCombo"]
        self.step_map = {}
        
        select_idx = 0
        for i, s in enumerate(all_steps):
            combo.AddItem(s.name())
            self.step_map[i] = s
            if initial_step and s.uuid() == initial_step.uuid():
                select_idx = i
                
        combo.CurrentIndex = select_idx
        
        # Initial population of tree
        if initial_step:
            self.populate_versions(initial_step)
        
        # Event Handlers
        results = [None]
        
        def on_step_changed(ev):
            idx = int(combo.CurrentIndex)
            step = self.step_map.get(idx)
            if step:
                self.populate_versions(step)
            
        def on_import(ev):
            # Handle potential PyFunctionCall wrapper
            item_or_func = tree.CurrentItem
            if item_or_func is None:
                return

            if callable(item_or_func):
                item = item_or_func()
            else:
                item = item_or_func

            if item:
                # Column 1 holds the full path
                # Try GetText method first (safer)
                if hasattr(item, "GetText"):
                    path = item.GetText(1)
                else:
                    path = item.Text[1]
                    
                if path and os.path.exists(path):
                    results[0] = path
                    self.disp.ExitLoop()
        
        def on_cancel(ev):
            self.disp.ExitLoop()
            
        self.dlg.On.StepCombo.CurrentIndexChanged = on_step_changed
        self.dlg.On.ImportBtn.Clicked = on_import
        self.dlg.On.CancelBtn.Clicked = on_cancel
        self.dlg.On[win_id].Close = on_cancel
        
        self.dlg.Show()
        self.disp.RunLoop()
        self.dlg.Hide()
        
        return results[0]

    def resolve_upstream_source(self, shot, current_step):
        """Recursively finds the first active upstream step."""
        if not current_step:
            return None

        pipes = current_step.inputPipes()
        if not pipes:
            return None # No upstream inputs

        for pipe in pipes:
            upstream = pipe.outputStep()
            status = shot.currentStatus(upstream)
            
            is_skipped = False
            if status:
                state_short = status.state().shortName().upper()
                if state_short in self.SKIP_STATES:
                    is_skipped = True
            
            if is_skipped:
                # Recurse up
                found = self.resolve_upstream_source(shot, upstream)
                if found:
                    return found
            else:
                # Found a valid active step
                # Optional: Check if it has any published files?
                # For now, just return the step itself as it's the logical source.
                return upstream
                
        return None

    def populate_versions(self, step):
        """Populates the Tree with published versions."""
        tree = self.dlg.GetItems()["VersionTree"]
        tree.Clear()
        
        if not self.current_shot or not step:
            return
            
        # Get published version folders
        folders = self.current_shot.publishedVersionFolderPaths(step)
        
        # Reverse to show newest first
        for folder in reversed(folders):
            v_folder = os.path.basename(folder) 
            
            # Parse from the right: [RESOURCE_]VERSION_STATE
            # VERSION is always the second-to-last block, STATE is the last.
            # RESOURCE may contain underscores (e.g. BG_CITY_001_OK -> resource=BG_CITY).
            blocks = v_folder.split('_')
            if len(blocks) >= 2:
                version_part = blocks[-2]
                resource_parts = blocks[:-2]
                if resource_parts:
                    display_v = f"v{version_part} [{('_'.join(resource_parts))}]"
                else:
                    display_v = f"v{version_part}"
            else:
                display_v = v_folder
            
            # Find main media file
            media_file = self._find_media(folder)
            if media_file:
                # Create Tree Item correctly via tree.NewItem()
                item = tree.NewItem()
                item.Text[0] = f"{display_v}  ({os.path.basename(media_file)})"
                item.Text[1] = media_file
                tree.AddTopLevelItem(item)

    def _find_media(self, folder):
        """Finds the most relevant media file in a folder."""
        try:
            # FILTER: Ignore hidden files, temp files, and metadata sidecars
            IGNORE_EXT = ('.json', '.tmp', '.xml', '.txt', '.log', '.ramses_complete')
            files = [f for f in os.listdir(folder) if not f.startswith(".") and not f.lower().endswith(IGNORE_EXT)]
            files.sort() # Ensure deterministic first-frame selection
        except OSError:
            return None
            
        # Priority 1: Movies
        for f in files:
            if f.lower().endswith(('.mov', '.mp4', '.mxf')):
                return os.path.join(folder, f)
        
        # Priority 2: Sequences (exr, dpx, png)
        # Return the first frame
        for f in files:
            if f.lower().endswith(('.exr', '.dpx', '.png', '.jpg', '.tif', '.tiff')):
                return os.path.join(folder, f)
                
        return None