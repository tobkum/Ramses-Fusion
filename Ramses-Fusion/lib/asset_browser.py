# -*- coding: utf-8 -*-
import os
import re
from ramses import RamItem, RamStep, RamFileInfo, ItemType, LogLevel
from ramses_patches import DisableMakedirs

# A trailing frame token, e.g. "...PLATE.01599116.exr" -> group(1) == "01599116".
# Used to collapse an image sequence to a single deliverable (mirrors the same
# pattern in fusion_host._FRAME_TOKEN_RE).
_FRAME_TOKEN_RE = re.compile(r"[._](\d+)\.[A-Za-z0-9]{1,5}$")

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
                    self.ui.Button({"ID": "ImportBtn", "Text": "Import", "Weight": 0, "MinimumSize": [100, 30], "Default": True}),
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

        # Block the main panel behind the browser, like every other dialog
        # (_request_input, the Switch Shot wizard). Without this the panel
        # stayed live and the browser could be opened a second time on top
        # of itself.
        main_win = getattr(getattr(self.host, "app", None), "dlg", None)
        if main_win:
            main_win.Enabled = False
        try:
            self.dlg.Show()
            self.disp.RunLoop()
        finally:
            self.dlg.Hide()
            if main_win:
                main_win.Enabled = True

        return results[0]

    def resolve_upstream_source(self, shot, current_step, _visited=None):
        """Recursively finds the first active upstream step.

        _visited is a set of step UUIDs already on the current search path,
        used to break cycles in pipeline graphs.
        """
        if not current_step:
            return None

        if _visited is None:
            _visited = set()
        step_uuid = current_step.uuid()
        if step_uuid in _visited:
            return None  # cycle detected — stop recursion
        _visited.add(step_uuid)

        pipes = current_step.inputPipes()
        if not pipes:
            return None  # No upstream inputs

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
                found = self.resolve_upstream_source(shot, upstream, _visited)
                if found:
                    return found
            else:
                # Only return this step if it actually has published versions;
                # a step can be "OK" or "WIP" without any files (e.g. a
                # management step), which would leave the browser empty.
                if self._published_version_folders(shot, upstream):
                    return upstream
                # No files — keep looking further upstream
                found = self.resolve_upstream_source(shot, upstream, _visited)
                if found:
                    return found

        return None

    def _published_version_folders(self, shot, step):
        """Lists published version folders for shot/step without creating any.

        RamItem.publishedVersionFolderPaths() -> publishFolderPath() creates
        the step's _published folder as a side effect if it doesn't exist
        yet - fine for an actual import, but this browser calls it just to
        probe candidate steps (resolve_upstream_source() walks the whole
        upstream pipe chain) and to populate the tree, neither of which
        should litter the project with empty folders. DisableMakedirs stops
        the folder from being created, which means it may genuinely not
        exist on disk - os.listdir() inside publishedVersionFolderPaths()
        would then raise, so treat that the same as "nothing published".
        """
        with DisableMakedirs():
            try:
                return shot.publishedVersionFolderPaths(step)
            except OSError:
                return []

    def populate_versions(self, step):
        """Populates the Tree with published versions."""
        tree = self.dlg.GetItems()["VersionTree"]
        tree.Clear()
        
        if not self.current_shot or not step:
            return
            
        # Get published version folders
        folders = self._published_version_folders(self.current_shot, step)

        # Extensions the current Fusion tool can ingest beyond footage (e.g.
        # {".comp"}), read from the Ramses app config - not the upstream `step`
        # (which often has no app linked), so no argument = current step.
        extra_exts = self.host.fusionFileFormats()

        rows_added = 0
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

            # One row per logical deliverable in the version (footage AND a
            # .comp, if both were published), instead of collapsing to one file.
            for d in self._list_deliverables(folder, extra_exts):
                item = tree.NewItem()
                item.Text[0] = f"{display_v} · {d['label']}"
                item.Text[1] = d["path"]
                tree.AddTopLevelItem(item)
                rows_added += 1

        # Explain an empty tree rather than leaving it blank.
        if rows_added == 0:
            step_name = step.name() if hasattr(step, "name") else "this step"
            placeholder = tree.NewItem()
            placeholder.Text[0] = f"Nothing published in {step_name} yet."
            placeholder.Text[1] = ""  # no path -> on_import's os.path.exists guard ignores it
            tree.AddTopLevelItem(placeholder)

    # Media the browser can surface. Movies and image sequences are always
    # loadable (Loaders); app formats (e.g. .comp) come from the Fusion app
    # config and get merged instead. Sidecars are dropped.
    _MOVIE_EXTS = (".mov", ".mp4", ".mxf")
    _SEQUENCE_EXTS = (".exr", ".dpx", ".png", ".jpg", ".jpeg", ".tif", ".tiff")
    _IGNORE_EXT = (".json", ".tmp", ".xml", ".txt", ".log", ".ramses_complete")

    def _list_deliverables(self, folder, extra_exts=()):
        """Lists the logical deliverables in a published version folder.

        One entry per distinct movie, image sequence (frames collapsed to the
        first one) and app-format file (e.g. ``.comp``). Hidden files and
        metadata sidecars (``_ramses_data.json``, ``.ramses_complete``) are
        dropped. Replaces the old single-file ``_find_media`` so a version that
        publishes several outputs (e.g. a tracked ``.comp`` AND a preview
        render) offers each as its own selectable row.

        Args:
            folder: The published version folder to scan.
            extra_exts: Dotted, lowercased extensions to treat as mergeable
                deliverables (from ``host.fusionFileFormats()``), e.g.
                ``{".comp"}``.

        Returns:
            list of dicts ``{"path", "label", "kind"}`` where kind is one of
            "movie", "sequence", "comp".
        """
        try:
            names = [
                f for f in os.listdir(folder)
                if not f.startswith(".")
                and not f.lower().endswith(self._IGNORE_EXT)
            ]
        except OSError:
            return []
        names.sort()  # deterministic first-frame (and stable row) order

        extra = tuple(e.lower() for e in extra_exts)
        deliverables = []
        seen_sequences = set()

        for name in names:
            lower = name.lower()
            path = os.path.join(folder, name)

            # Movies: one entry each, no frame grouping.
            if lower.endswith(self._MOVIE_EXTS):
                deliverables.append({"path": path, "label": name, "kind": "movie"})
                continue

            # App formats (e.g. .comp): one entry each, merged on import.
            if extra and lower.endswith(extra):
                deliverables.append({"path": path, "label": name, "kind": "comp"})
                continue

            # Image sequences: collapse frames to a single entry at frame 1.
            if lower.endswith(self._SEQUENCE_EXTS):
                m = _FRAME_TOKEN_RE.search(name)
                if m:
                    ext = os.path.splitext(name)[1]
                    stem = name[:m.start()]  # name without ".<frame>.<ext>"
                    key = (stem, ext.lower())
                    if key in seen_sequences:
                        continue  # already recorded this sequence's first frame
                    seen_sequences.add(key)
                    deliverables.append(
                        {"path": path, "label": f"{stem}.[####]{ext}", "kind": "sequence"}
                    )
                else:
                    # A single still with no frame token: its own row.
                    deliverables.append({"path": path, "label": name, "kind": "sequence"})
                continue

            # Unknown / non-importable types: skipped.

        # Stable presentation order: movies, then sequences, then app formats.
        order = {"movie": 0, "sequence": 1, "comp": 2}
        deliverables.sort(key=lambda d: (order.get(d["kind"], 9), d["label"].lower()))
        return deliverables