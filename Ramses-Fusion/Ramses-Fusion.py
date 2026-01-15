import sys
import os
import re
import concurrent.futures

# Add the 'lib' directory to Python's search path
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
except NameError:
    # Fallback for environments where __file__ is not defined
    script_dir = os.path.dirname(
        os.path.realpath(fu.MapPath("Scripts:/Comp/Ramses-Fusion/Ramses-Fusion.py"))
    )

lib_path = os.path.join(script_dir, "lib")
if lib_path not in sys.path:
    sys.path.append(lib_path)

import ramses as ram
import fusion_host


class RamsesFusionApp:
    def __init__(self):
        self.ramses = ram.Ramses.instance()
        self.settings = ram.RamSettings.instance()

        # Initialize Host with global fusion object
        self.ramses.host = fusion_host.FusionHost(fusion)
        self.ramses.host.app = self

        self.ui = fu.UIManager
        self.disp = bmd.UIDispatcher(self.ui)
        self.script_dir = script_dir
        self.icon_dir = os.path.join(self.script_dir, "icons")
        self._icon_cache = {}
        self.dlg = None
        self._project_cache = None
        self._user_name_cache = None

        # Context Caching
        self._item_cache = None
        self._item_path = ""
        self._step_cache = None
        self._step_path = ""
        self._last_synced_path = None

    def _get_icon(self, icon_name):
        """Lazy-loading icon cache."""
        if icon_name not in self._icon_cache:
            icon_path = os.path.join(self.icon_dir, icon_name)
            self._icon_cache[icon_name] = self.ui.Icon({"File": icon_path})
        return self._icon_cache[icon_name]

    @property
    def current_item(self):
        self._update_context()
        return self._item_cache

    @property
    def current_step(self):
        self._update_context()
        return self._step_cache

    def _update_context(self):
        """Internal helper to sync item and step from the host once per access cycle."""
        path = self.ramses.host.currentFilePath()
        if path != self._item_path or not self._item_cache or not self._step_cache:
            self._item_path = path
            self._item_cache = self.ramses.host.currentItem()
            self._step_path = path
            self._step_cache = self.ramses.host.currentStep()
        return path

    def _get_project(self):
        """Cached access to the current project."""
        if not self._project_cache:
            self._project_cache = self.ramses.project()
        return self._project_cache

    def _get_user_name(self):
        """Cached access to the user name."""
        if not self._user_name_cache:
            user = self.ramses.user()
            self._user_name_cache = user.name() if user else "Not Logged In"
        return self._user_name_cache

    def _require_step(self):
        """Validates that a step is active before proceeding."""
        step = self.current_step
        if not step:
            self.ramses.host._request_input(
                "Ramses Warning",
                [
                    {
                        "id": "W",
                        "label": "",
                        "type": "text",
                        "default": "Save as valid Step first.",
                        "lines": 1,
                    }
                ],
            )
            return None
        return step

    def _update_ui_state(self, is_online):
        """Updates the UI elements (Header, Buttons) based on connection status."""
        if not self.dlg:
            return

        try:
            items = self.dlg.GetItems()
            
            # 1. Update Context Header
            if "ContextLabel" in items:
                if is_online:
                    items["ContextLabel"].Text = self._get_context_text()
                else:
                    items["ContextLabel"].Text = "<font color='#ff4444'><b>CONNECTION ERROR</b></font><br><font color='#999'>Ramses Client is offline</font>"
            
            if "RamsesVersion" in items:
                items["RamsesVersion"].Text = self._get_footer_text()

            # 2. Toggle Buttons
            # We need to re-fetch the item ONLY if online to determine pipeline status
            # If offline, item is None, so pipeline buttons are disabled anyway.
            item = self.current_item if is_online else None
            is_pipeline = item is not None and bool(item.uuid())

            # Group 1: Pipeline Buttons (Require Connection AND valid Ramses Item)
            pipeline_buttons = [
                "SetupSceneButton",
                "ImportButton",
                "ReplaceButton",
                "TemplateButton",
                "IncrementalSaveButton",
                "SaveButton",
                "RetrieveButton",
                "CommentButton",
                "PreviewButton",
                "UpdateStatusButton",
                "PubSettingsButton",
            ]
            for btn_id in pipeline_buttons:
                if btn_id in items:
                    items[btn_id].Enabled = is_online and is_pipeline

            # Group 2: DB Buttons (Require Connection, but not necessarily an Item)
            db_buttons = ["SwitchShotButton", "OpenButton"]
            for btn_id in db_buttons:
                if btn_id in items:
                    items[btn_id].Enabled = is_online
        except Exception:
            pass

    def _check_connection(self, silent=False):
        """Checks if Ramses Daemon is online and shows a dialog if not."""
        # Force a real ping to check status (bypass cached flag)
        if not self.ramses.daemonInterface().online():
            self.ramses.disconnect()
            self.ramses.connect()

        if not self.ramses.online():
            # Force UI update to offline state immediately
            self._update_ui_state(False)

            if not silent:
                self.ramses.host._request_input(
                    "Ramses Connection Error",
                    [
                        {
                            "id": "E",
                            "label": "",
                            "type": "text",
                            "default": "Could not reach the Ramses Client. \n\nPlease make sure Ramses is running and you are logged in.",
                            "lines": 3,
                        }
                    ],
                )
            return False
        return True

    def _get_context_text(self):
        item = self.current_item
        step = self.current_step

        if not item or not item.uuid():
            path = self.ramses.host.currentFilePath()
            if path:
                return "<font color='#cc9900'>External Composition</font><br><font color='#777'>Not in a Ramses Project</font>"
            return "<font color='#cc9900'>No Active Ramses Item</font>"

        project = self._get_project()
        project_name = project.name() if project else item.projectShortName()
        item_name = item.shortName()
        step_name = step.name() if step else "No Step"
        return f"<font color='#555'>{project_name} / </font><b><font color='#BBB'>{item_name}</font></b><br><font color='#999'>{step_name}</font>"

    def log(self, message, level=ram.LogLevel.Info):
        """Directly logs to the Fusion console bypassing API filtering."""
        self.ramses.host._log(message, level)

    def _get_footer_text(self):
        return f"<font color='#555'>User: {self._get_user_name()} | Ramses API {self.settings.version}</font>"

    def _create_render_anchors(self):
        """Creates _PREVIEW and _FINAL Saver nodes at calculated grid coordinates."""
        comp = self.ramses.host.comp
        if not comp:
            return

        comp.Lock()
        try:
            # 1. Determine Reference Position (Grid Units)
            flow = comp.CurrentFrame.FlowView
            start_x, start_y = 0, 0

            active = comp.ActiveTool
            if active and flow:
                pos = flow.GetPosTable(active)
                # Fusion returns {1.0: x, 2.0: y} in Grid Units
                if pos:
                    start_x = pos[1]
                    start_y = pos[2]

            # 2. Configuration: Exact Grid Offsets
            # Place side-by-side BELOW the selection
            anchors_config = {
                "_PREVIEW": {
                    "color": {"R": 0.3, "G": 0.7, "B": 0.3},
                    "target_x": int(start_x + 0),
                    "target_y": int(start_y + 2),
                },
                "_FINAL": {
                    "color": {"R": 0.7, "G": 0.3, "B": 0.3},
                    "target_x": int(start_x + 1),
                    "target_y": int(start_y + 2),
                },
            }

            # Pre-calculate paths via Host
            preview_path = self.ramses.host.resolvePreviewPath()
            publish_path = self.ramses.host.resolveFinalPath()

            for name, cfg in anchors_config.items():
                node = comp.FindTool(name)

                # Create if missing, using calculated coordinates directly
                if not node:
                    node = comp.AddTool("Saver", cfg["target_x"], cfg["target_y"])
                    if node:
                        node.SetAttrs({"TOOLS_Name": name, "TOOLB_PassThrough": True})

                        if name == "_PREVIEW":
                            if preview_path:
                                node.Clip[1] = preview_path
                            node.SetInput("OutputFormat", "QuickTimeMovies", 0)
                            node.SetInput(
                                "QuickTimeMovies.Compression",
                                "Apple ProRes 422_apcn",
                                0,
                            )
                            node.Comments[1] = (
                                "Preview renders will be saved here. Connect your output."
                            )
                        else:
                            if publish_path:
                                node.Clip[1] = publish_path
                            node.SetInput("OutputFormat", "QuickTimeMovies", 0)
                            node.SetInput(
                                "QuickTimeMovies.Compression",
                                "Apple ProRes 4444_ap4h",
                                0,
                            )
                            node.Comments[1] = (
                                "Final renders will be saved here. Connect your output."
                            )

                # Ensure color is correct (even if existing)
                if node:
                    node.TileColor = cfg["color"]
        finally:
            comp.Unlock()

    def _validate_publish(self, check_preview=True, check_final=True):
        """Validates comp settings against Ramses database before publishing."""
        item = self.current_item
        project = self._get_project()
        if not item or not project:
            return True, ""

        errors = []
        comp = self.ramses.host.comp

        # 1. Check Frame Range
        if item.itemType() == ram.ItemType.SHOT:
            framerate = project.framerate() if project else 24.0
            expected_frames = int(round(item.duration() * framerate))

            # Check Render Range
            attrs = comp.GetAttrs()
            comp_start = attrs.get("COMPN_RenderStart", 0)
            comp_end = attrs.get("COMPN_RenderEnd", 0)
            actual_frames = int(comp_end - comp_start + 1)

            if expected_frames > 0 and actual_frames != expected_frames:
                errors.append(
                    f"• Frame Range Mismatch: DB expects {expected_frames} frames, Comp is set to render {actual_frames}."
                )

        # 2. Check Resolution (Project Master)
        db_w = int(project.width() or 1920)
        db_h = int(project.height() or 1080)

        prefs = comp.GetPrefs()
        frame_format = prefs.get("Comp", {}).get("FrameFormat", {})

        comp_w = int(frame_format.get("Width", 0))
        comp_h = int(frame_format.get("Height", 0))

        if db_w != comp_w or db_h != comp_h:
            errors.append(
                f"• Resolution Mismatch: DB expects {db_w}x{db_h}, Comp is {comp_w}x{comp_h}."
            )

        # 3. Check Framerate
        db_fps = float(project.framerate() or 24.0)
        comp_fps = float(frame_format.get("Rate", 24.0))

        if abs(db_fps - comp_fps) > 0.001:
            errors.append(
                f"• Framerate Mismatch: DB expects {db_fps} fps, Comp is set to {comp_fps} fps."
            )

        # 4. Check Saver Connections
        def check_anchor(tool_name):
            node = comp.FindTool(tool_name)
            if not node:
                return f"• Missing Anchor: '{tool_name}' node not found. Run 'Setup Scene' to create it."

            inp = node.FindMainInput(1)
            if not inp or inp.GetConnectedOutput() is None:
                return f"• Disconnected Anchor: '{tool_name}' node has no input connection."
            return None

        if check_preview:
            err_preview = check_anchor("_PREVIEW")
            if err_preview:
                errors.append(err_preview)

        if check_final:
            err_final = check_anchor("_FINAL")
            if err_final:
                errors.append(err_final)

        if errors:
            return False, "\n".join(errors)
        return True, ""

    def _sync_render_anchors(self):
        """Syncs existing _PREVIEW and _FINAL Saver paths with current project specs."""
        comp = self.ramses.host.comp
        if not comp:
            return

        # Performance Gate: Only sync if context changed
        current_path = self.ramses.host.currentFilePath()
        if self._last_synced_path == current_path:
            return

        try:
            preview_path = self.ramses.host.resolvePreviewPath()
            final_path = self.ramses.host.resolveFinalPath()
            if not preview_path and not final_path:
                return

            comp.Lock()
            try:
                preview_node = comp.FindTool("_PREVIEW")
                if preview_node:
                    if preview_node.Clip[1] != preview_path:
                        preview_node.Clip[1] = preview_path
                    preview_node.SetInput("OutputFormat", "QuickTimeMovies", 0)
                    preview_node.SetInput(
                        "QuickTimeMovies.Compression", "Apple ProRes 422_apcn", 0
                    )

                final_node = comp.FindTool("_FINAL")
                if final_node:
                    if final_node.Clip[1] != final_path:
                        final_node.Clip[1] = final_path
                    final_node.SetInput("OutputFormat", "QuickTimeMovies", 0)
                    final_node.SetInput(
                        "QuickTimeMovies.Compression", "Apple ProRes 4444_ap4h", 0
                    )

                self._last_synced_path = current_path
            finally:
                comp.Unlock()
        except Exception:
            pass

    def refresh_header(self, force_full=False):
        """Updates the context label and footer with current info."""
        is_online = self._check_connection(silent=True)

        if is_online:
            try:
                # Force cache refresh for project and user only if requested
                if force_full:
                    self._project_cache = None
                    self._user_name_cache = None

                # Clear item/step caches and path trackers to force re-fetch from host
                self._item_cache = None
                self._item_path = ""
                self._step_cache = None
                self._step_path = ""

                # Reset sync gate to force Saver anchor updates on manual refresh
                self._last_synced_path = None

                # Sync Savers before updating UI (Optimized with path gating)
                self._sync_render_anchors()
            except Exception:
                pass

        # Update UI based on the determined status
        self._update_ui_state(is_online)

    def show_main_window(self):
        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses-Fusion",
                "ID": "MainWin",
                "Geometry": [200, 200, 280, 825],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 0, "Weight": 1},
                    [
                        self.ui.VGap(15),
                        self.ui.HGroup(
                            {"Weight": 1},
                            [
                                self.ui.HGap(15),
                                self.ui.VGroup(
                                    {"Spacing": 4, "Weight": 1},
                                    [
                                        # Context Header
                                        self.ui.HGroup(
                                            {"Weight": 0},
                                            [
                                                self.ui.Label(
                                                    {
                                                        "ID": "ContextLabel",
                                                        "Text": self._get_context_text(),
                                                        "Alignment": {
                                                            "AlignHCenter": True,
                                                            "AlignTop": True,
                                                        },
                                                        "WordWrap": True,
                                                        "Weight": 1,
                                                    }
                                                ),
                                                self.ui.Button(
                                                    {
                                                        "ID": "RefreshButton",
                                                        "Text": "",
                                                        "Weight": 0,
                                                        "MinimumSize": [48, 48],
                                                        "MaximumSize": [48, 48],
                                                        "IconSize": [32, 32],
                                                        "Flat": True,
                                                        "ToolTip": "Manually refresh the context header.",
                                                        "Icon": self._get_icon(
                                                            "ramupdate.png"
                                                        ),
                                                    }
                                                ),
                                            ],
                                        ),
                                        self.ui.VGap(10),
                                        # Groups
                                        self._build_project_group(),
                                        self.ui.VGap(8),
                                        self._build_pipeline_group(),
                                        self.ui.VGap(8),
                                        self._build_working_group(),
                                        self.ui.VGap(8),
                                        self._build_publish_group(),
                                        self.ui.VGap(8),
                                        self._build_settings_group(),
                                        # Spacer to push everything up
                                        self.ui.VGap(0, 1),
                                        # Footer Version
                                        self.ui.Label(
                                            {
                                                "ID": "RamsesVersion",
                                                "Text": self._get_footer_text(),
                                                "Alignment": {"AlignHCenter": True},
                                                "Weight": 0,
                                            }
                                        ),
                                    ],
                                ),
                                self.ui.HGap(15),
                            ],
                        ),
                        self.ui.VGap(15),
                    ],
                )
            ],
        )

        # Bind Events
        self.dlg.On.RefreshButton.Clicked = lambda ev: self.refresh_header(force_full=True)
        self.dlg.On.RamsesButton.Clicked = self.on_run_ramses
        self.dlg.On.SwitchShotButton.Clicked = self.on_switch_shot
        self.dlg.On.ImportButton.Clicked = self.on_import
        self.dlg.On.ReplaceButton.Clicked = self.on_replace
        self.dlg.On.SaveButton.Clicked = self.on_save
        self.dlg.On.CommentButton.Clicked = self.on_comment
        self.dlg.On.IncrementalSaveButton.Clicked = self.on_incremental_save
        self.dlg.On.UpdateStatusButton.Clicked = self.on_update_status
        self.dlg.On.PreviewButton.Clicked = self.on_preview
        self.dlg.On.TemplateButton.Clicked = self.on_save_template
        self.dlg.On.SetupSceneButton.Clicked = self.on_setup_scene
        self.dlg.On.OpenButton.Clicked = self.on_open
        self.dlg.On.RetrieveButton.Clicked = self.on_retrieve
        self.dlg.On.PubSettingsButton.Clicked = self.on_publish_settings
        self.dlg.On.SettingsButton.Clicked = self.show_settings_window
        self.dlg.On.AboutButton.Clicked = self.show_about_window
        self.dlg.On.MainWin.Close = self.on_close

        self.refresh_header()
        self.dlg.Show()
        self.disp.RunLoop()
        self.dlg.Hide()

    def _build_project_group(self):
        bg_color = "#2a3442"  # Very Dark Desaturated Blue
        return self.ui.VGroup(
            [
                self.ui.Label(
                    {
                        "Text": "PROJECT & SCENE",
                        "Weight": 0,
                        "Font": self.ui.Font({"PixelSize": 11, "Bold": True}),
                    }
                ),
                self.create_button(
                    "SwitchShotButton",
                    "Switch Shot",
                    "ramshot.png",
                    tooltip="Quickly jump to another shot in this project or create a new one from a template.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "SetupSceneButton",
                    "Setup Scene",
                    "ramsetupscene.png",
                    tooltip="Automatically set the resolution, FPS, and frame range based on Ramses project settings.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "OpenButton",
                    "Open Composition",
                    "ramopen.png",
                    tooltip="Browse and open an existing Ramses composition.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "RamsesButton",
                    "Open Ramses Client",
                    "ramses.png",
                    tooltip="Launch the main Ramses Client application.",
                    accent_color=bg_color,
                ),
            ]
        )

    def _build_pipeline_group(self):
        bg_color = "#342a42"  # Very Dark Desaturated Purple
        return self.ui.VGroup(
            [
                self.ui.Label(
                    {
                        "Text": "ASSETS & TOOLS",
                        "Weight": 0,
                        "Font": self.ui.Font({"PixelSize": 11, "Bold": True}),
                    }
                ),
                self.create_button(
                    "ImportButton",
                    "Import Asset",
                    "ramimport.png",
                    tooltip="Import a published asset or render into the current composition.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "ReplaceButton",
                    "Replace Loader",
                    "ramreplace.png",
                    tooltip="Replace the selected Loader node with a different version or asset.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "TemplateButton",
                    "Save as Template",
                    "ramtemplate.png",
                    tooltip="Save the current composition as a template for other shots in this step.",
                    accent_color=bg_color,
                ),
            ]
        )

    def _build_working_group(self):
        bg_color = "#2a423d"  # Very Dark Desaturated Teal
        return self.ui.VGroup(
            [
                self.ui.Label(
                    {
                        "Text": "SAVING & ITERATION",
                        "Weight": 0,
                        "Font": self.ui.Font({"PixelSize": 11, "Bold": True}),
                    }
                ),
                self.create_button(
                    "SaveButton",
                    "Save",
                    "ramsave.png",
                    tooltip="Overwrite the current working file version.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "IncrementalSaveButton",
                    "Incremental Save",
                    "ramsaveincremental.png",
                    tooltip="Save a new version of the current file (v001 -> v002).",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "CommentButton",
                    "Add Comment",
                    "ramcomment.png",
                    tooltip="Add a note to the current version in the Ramses database.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "RetrieveButton",
                    "Retrieve Version",
                    "ramretrieve.png",
                    tooltip="Open a previous version of this composition from the _versions folder.",
                    accent_color=bg_color,
                ),
            ]
        )

    def _build_publish_group(self):
        bg_color = "#2a422a"  # Very Dark Desaturated Green
        return self.ui.VGroup(
            [
                self.ui.Label(
                    {
                        "Text": "REVIEW & PUBLISH",
                        "Weight": 0,
                        "Font": self.ui.Font({"PixelSize": 11, "Bold": True}),
                    }
                ),
                self.create_button(
                    "PreviewButton",
                    "Create Preview",
                    "rampreview.png",
                    tooltip="Generate a preview render for review.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "UpdateStatusButton",
                    "Update Status / Publish",
                    "ramstatus.png",
                    tooltip="Change the shot status (WIP, Review, Done) and optionally publish the final comp.",
                    accent_color=bg_color,
                ),
            ]
        )

    def _build_settings_group(self):
        bg_color = "#333333"  # Dark Grey
        return self.ui.VGroup(
            [
                self.ui.Label(
                    {
                        "Text": "SETTINGS & INFO",
                        "Weight": 0,
                        "Font": self.ui.Font({"PixelSize": 11, "Bold": True}),
                    }
                ),
                self.create_button(
                    "PubSettingsButton",
                    "Publish Settings",
                    "rampublishsettings.png",
                    tooltip="Configure YAML settings for automated publishing.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "SettingsButton",
                    "Plugin Settings",
                    "ramsettings.png",
                    tooltip="Configure Ramses paths, ports, and default frame ranges.",
                    accent_color=bg_color,
                ),
                self.create_button(
                    "AboutButton",
                    "About",
                    "ramses.png",
                    tooltip="Information about Ramses-Fusion and Overmind Studios.",
                    accent_color=bg_color,
                ),
            ]
        )

    def create_button(
        self,
        id_name,
        text,
        icon_name,
        weight=0,
        tooltip="",
        min_size=None,
        max_size=None,
        accent_color=None,
    ):
        # Base Style
        ss = f"QPushButton {{ text-align: left; padding-left: 12px; border: 1px solid #222; border-radius: 3px;"
        if accent_color:
            ss += f" background-color: {accent_color}; }}"
            # Calculate Hover (slightly brighter)
            h = accent_color.lstrip("#")
            hr, hg, hb = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            hover = "#%02x%02x%02x" % (
                min(255, hr + 15),
                min(255, hg + 15),
                min(255, hb + 15),
            )
            # Calculate Pressed (slightly darker)
            pressed = "#%02x%02x%02x" % (
                max(0, hr - 10),
                max(0, hg - 10),
                max(0, hb - 10),
            )

            ss += f" QPushButton:hover {{ background-color: {hover}; }}"
            ss += f" QPushButton:pressed {{ background-color: {pressed}; }}"
            ss += f" QPushButton:disabled {{ background-color: #222; color: #555; border: 1px solid #1a1a1a; }}"
        else:
            ss += " }"

        return self.ui.Button(
            {
                "ID": id_name,
                "Text": text if text else "",
                "Weight": weight,
                "ToolTip": tooltip,
                "MinimumSize": min_size or [16, 28],
                "MaximumSize": max_size or [2000, 28],
                "IconSize": [16, 16],
                "Icon": self._get_icon(icon_name),
                "StyleSheet": ss,
            }
        )

    def show_settings_window(self, ev):
        win_id = "SettingsWin"
        dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses Settings",
                "ID": win_id,
                "Geometry": [200, 200, 550, 150],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 5},
                    [
                        self.ui.HGroup(
                            [
                                self.ui.Label(
                                    {"Text": "Ramses executable path:", "Weight": 1}
                                ),
                                self.ui.LineEdit(
                                    {
                                        "ID": "RamsesPathTxt",
                                        "Weight": 2,
                                        "Text": self.settings.ramsesClientPath,
                                    }
                                ),
                            ]
                        ),
                        self.ui.HGroup(
                            [
                                self.ui.Label(
                                    {"Text": "Ramses client port:", "Weight": 1}
                                ),
                                self.ui.LineEdit(
                                    {
                                        "ID": "RamsesPortTxt",
                                        "Weight": 2,
                                        "Text": str(self.settings.ramsesClientPort),
                                    }
                                ),
                            ]
                        ),
                        self.ui.HGroup(
                            [
                                self.ui.Label(
                                    {"Text": "Comp Start Frame:", "Weight": 1}
                                ),
                                self.ui.LineEdit(
                                    {
                                        "ID": "StartFrameTxt",
                                        "Weight": 2,
                                        "Text": str(
                                            self.settings.userSettings.get(
                                                "compStartFrame", 1001
                                            )
                                        ),
                                    }
                                ),
                            ]
                        ),
                        self.ui.HGroup(
                            [
                                self.ui.Button(
                                    {"ID": "SaveSettingsButton", "Text": "Save"}
                                ),
                                self.ui.Button(
                                    {"ID": "CloseSettingsButton", "Text": "Close"}
                                ),
                            ]
                        ),
                    ],
                )
            ],
        )

        itm = dlg.GetItems()

        def save_settings(ev):
            self.settings.ramsesClientPort = int(itm["RamsesPortTxt"].Text)
            self.settings.ramsesClientPath = str(itm["RamsesPathTxt"].Text)
            try:
                self.settings.userSettings["compStartFrame"] = int(
                    itm["StartFrameTxt"].Text
                )
            except ValueError:
                self.settings.userSettings["compStartFrame"] = 1001
            self.settings.save()
            self.log("Settings Saved.", ram.LogLevel.Info)

        def close_settings(ev):
            dlg.On[win_id].Close = None
            dlg.On.CloseSettingsButton.Clicked = None
            dlg.On.SaveSettingsButton.Clicked = None
            self.disp.ExitLoop()

        dlg.On[win_id].Close = close_settings
        dlg.On.CloseSettingsButton.Clicked = close_settings
        dlg.On.SaveSettingsButton.Clicked = save_settings

        self.dlg.Enabled = False
        try:
            dlg.Show()
            self.disp.RunLoop()
        finally:
            dlg.Hide()
            self.dlg.Enabled = True

    def show_about_window(self, ev):
        win_id = "AboutWin"
        dlg = self.disp.AddWindow(
            {
                "WindowTitle": "About Ramses-Fusion",
                "ID": win_id,
                "Geometry": [200, 200, 450, 300],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 0},
                    [
                        self.ui.HGroup(
                            {"Weight": 0},
                            [
                                self.ui.HGap(0, 1),
                                self.ui.Button(
                                    {
                                        "ID": "Logo",
                                        "Icon": self._get_icon("overmind.png"),
                                        "IconSize": [128, 128],
                                        "Flat": True,
                                        "Enabled": True,
                                        "StyleSheet": "border: none;",
                                        "MaximumSize": [128, 128],
                                        "MinimumSize": [128, 128],
                                    }
                                ),
                                self.ui.HGap(0, 1),
                            ],
                        ),
                        self.ui.VGap(10),
                        self.ui.Label(
                            {
                                "ID": "Info",
                                "Text": "<p align='center'>Ramses-Fusion for Overmind Studios. <br>Copyright &copy; 2026 Overmind Studios.</p>",
                                "Alignment": [{"AlignHCenter": True, "AlignTop": True}],
                                "WordWrap": True,
                                "OpenExternalLinks": True,
                            }
                        ),
                        self.ui.Label(
                            {
                                "ID": "URL",
                                "Text": '<p align="center">Web: <a href="https://www.overmind-studios.de">Overmind Studios</a></p>',
                                "Alignment": [{"AlignHCenter": True, "AlignTop": True}],
                                "WordWrap": True,
                                "OpenExternalLinks": True,
                            }
                        ),
                        self.ui.VGap(),
                        self.ui.Button({"ID": "AboutCloseButton", "Text": "Close"}),
                    ],
                )
            ],
        )

        def on_close(ev):
            dlg.On.AboutCloseButton.Clicked = None
            dlg.On[win_id].Close = on_close
            self.disp.ExitLoop()

        dlg.On.AboutCloseButton.Clicked = on_close
        dlg.On[win_id].Close = on_close

        self.dlg.Enabled = False
        try:
            dlg.Show()
            self.disp.RunLoop()
        finally:
            dlg.Hide()
            self.dlg.Enabled = True

    # --- Handlers ---

    def on_run_ramses(self, ev):
        self.ramses.showClient()

    def on_switch_shot(self, ev):
        """Interactive one-page wizard for switching/creating shots with cascading dropdowns."""
        if not self._check_connection():
            return

        ui = self.ui
        disp = self.disp
        host = self.ramses.host
        daemon = self.ramses.daemonInterface()

        # 1. Initial Data Fetch (Minimal)
        all_projects = daemon.getObjects("RamProject")
        if not all_projects:
            self.log("No projects found in Ramses.", ram.LogLevel.Warning)
            return

        # Pre-cache states once for global state names (small payload)
        all_states = self.ramses.states()
        state_map = {str(s.uuid()): str(s.shortName()).upper() for s in all_states}

        # Session Cache for this wizard instance
        session_cache = {
            "projects": all_projects,
            "project_data": {},  # {proj_uuid: {"shots": [], "seq_map": {}, "steps": []}}
            "status_cache": {},  # {(shot_uuid, step_uuid): status}
            "current_shots": [],
            "current_seq_map": {},
            "current_steps": [],
            "shot_options": [],
            "initial_step_idx": -1,
            "last_proj_idx": -1,
        }

        cur_project = self._get_project()
        cur_step = self.current_step
        cur_item = self.current_item

        # 2. Build UI
        win_id = f"ShotWizard_{int(os.getpid())}"
        dlg = disp.AddWindow(
            {
                "WindowTitle": "Ramses: Switch Shot",
                "ID": win_id,
                "Geometry": [400, 400, 500, 180],
            },
            ui.VGroup(
                [
                    ui.VGap(10),
                    ui.VGroup(
                        {"Spacing": 5},
                        [
                            ui.HGroup(
                                [
                                    ui.Label({"Text": "Project:", "Weight": 0.25}),
                                    ui.ComboBox({"ID": "ProjCombo", "Weight": 0.75}),
                                ]
                            ),
                            ui.HGroup(
                                [
                                    ui.Label({"Text": "Step:", "Weight": 0.25}),
                                    ui.ComboBox({"ID": "StepCombo", "Weight": 0.75}),
                                ]
                            ),
                            ui.HGroup(
                                [
                                    ui.Label({"Text": "Shot:", "Weight": 0.25}),
                                    ui.ComboBox({"ID": "ShotCombo", "Weight": 0.75}),
                                ]
                            ),
                        ],
                    ),
                    ui.VGap(10),
                    ui.HGroup(
                        [
                            ui.HGap(200),
                            ui.Button({"ID": "OkBtn", "Text": "OK", "Weight": 0.1}),
                            ui.Button(
                                {"ID": "CancelBtn", "Text": "Cancel", "Weight": 0.1}
                            ),
                        ]
                    ),
                    ui.VGap(5),
                ]
            ),
        )

        itm = dlg.GetItems()

        # 3. Logic: Update Helpers
        def update_shots(ev=None):
            try:
                itm["ShotCombo"].Clear()
                session_cache["shot_options"] = []

                step_idx = int(itm["StepCombo"].CurrentIndex)
                if step_idx < 0 or not session_cache["current_steps"]:
                    return

                selected_step = session_cache["current_steps"][step_idx]
                step_uuid = str(selected_step.uuid())

                shots = session_cache["current_shots"]
                seq_map = session_cache["current_seq_map"]

                # 1. Identify missing statuses in cache
                missing_keys = []
                for shot in shots:
                    cache_key = (str(shot.uuid()), step_uuid)
                    if cache_key not in session_cache["status_cache"]:
                        missing_keys.append((shot, selected_step))

                # 2. Parallel Fetch (ThreadPoolExecutor)
                if missing_keys:
                    def fetch_status_task(args):
                        s_obj, s_stp = args
                        try:
                            # Return ((key), result)
                            return (str(s_obj.uuid()), str(s_stp.uuid())), s_obj.currentStatus(s_stp)
                        except Exception:
                            return (str(s_obj.uuid()), str(s_stp.uuid())), None

                    # Use max_workers=20 to speed up I/O bound socket calls
                    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                        results = executor.map(fetch_status_task, missing_keys)
                        for key, status in results:
                            session_cache["status_cache"][key] = status

                # 3. Populate UI from cache
                valid_options = []
                for shot in shots:
                    shot_uuid = str(shot.uuid())
                    
                    cache_key = (shot_uuid, step_uuid)
                    status = session_cache["status_cache"].get(cache_key)

                    if status:
                        st_uuid = str(ram.RamObject.getUuid(status.get("state")))
                        if state_map.get(st_uuid) in ["NO", "STB"]:
                            continue

                    # Resolve expected path
                    expected_path = shot.stepFilePath(
                        step=selected_step, extension="comp"
                    )
                    exists = bool(expected_path)
                    if not exists:
                        # Construct a virtual path for non-existent files
                        folder = shot.stepFolderPath(selected_step)
                        fn_info = ram.RamFileInfo()
                        fn_info.project = shot.projectShortName()
                        fn_info.ramType = ram.ItemType.SHOT
                        fn_info.shortName = shot.shortName()
                        fn_info.step = selected_step.shortName()
                        fn_info.extension = "comp"
                        expected_path = os.path.join(folder, fn_info.fileName())

                    seq_name = seq_map.get(
                        str(ram.RamObject.getUuid(shot.get("sequence"))), "None"
                    )

                    if exists:
                        state_name = status.state().name() if status else "WIP"
                        label = f"{seq_name} / {shot.shortName()} [{state_name}]"
                    else:
                        label = f"{seq_name} / {shot.shortName()} [EMPTY - Create New]"

                    valid_options.append(
                        {
                            "label": label,
                            "shot": shot,
                            "path": expected_path,
                            "exists": exists,
                        }
                    )

                session_cache["shot_options"] = valid_options
                for opt in valid_options:
                    itm["ShotCombo"].AddItem(opt["label"])

                # Pre-selection logic (Only on initial load or if project/step matches current)
                if cur_item and step_idx == session_cache["initial_step_idx"]:
                    cur_uuid = str(cur_item.uuid())
                    for i, opt in enumerate(valid_options):
                        if str(opt["shot"].uuid()) == cur_uuid:
                            itm["ShotCombo"].CurrentIndex = i
                            break
                else:
                    itm["ShotCombo"].CurrentIndex = 0
            except Exception as e:
                self.log(f"Error updating shots: {e}", ram.LogLevel.Critical)

        def update_steps(ev=None):
            try:
                itm["StepCombo"].Clear()

                all_steps = session_cache["current_steps"]
                fusion_steps = []
                for s in all_steps:
                    s_data = s.data()
                    is_fusion = False

                    # DCC Detection (Broadened for studio compatibility)
                    apps = s_data.get("applications", [])
                    if isinstance(apps, list):
                        for app_uuid in apps:
                            app_data = daemon.getData(str(app_uuid), "RamApplication")
                            app_name = str(app_data.get("name", "")).upper()
                            if "FUSION" in app_name or "BMF" in app_name:
                                is_fusion = True
                                break

                    if not is_fusion:
                        for key in ["application", "software", "app", "dcc"]:
                            val = str(s_data.get(key, "")).upper()
                            if "FUSION" in val or "BMF" in val:
                                is_fusion = True
                                break
                        if not is_fusion and "FUSION" in s.shortName().upper():
                            is_fusion = True
                        if not is_fusion:
                            stgs = s.generalSettings("yaml")
                            if isinstance(stgs, dict):
                                stg_val = str(stgs.get("application", "")).upper()
                                if "FUSION" in stg_val or "BMF" in stg_val:
                                    is_fusion = True

                    if is_fusion:
                        fusion_steps.append(s)

                if not fusion_steps:
                    fusion_steps = all_steps

                session_cache["current_steps"] = fusion_steps
                for s in fusion_steps:
                    itm["StepCombo"].AddItem(s.name())

                # Pre-selection logic
                proj_idx = int(itm["ProjCombo"].CurrentIndex)
                if proj_idx >= 0:
                    proj = session_cache["projects"][proj_idx]
                    if cur_step and str(proj.uuid()) == str(cur_project.uuid()):
                        cur_uuid = str(cur_step.uuid())
                        for i, s in enumerate(fusion_steps):
                            if str(s.uuid()) == cur_uuid:
                                itm["StepCombo"].CurrentIndex = i
                                session_cache["initial_step_idx"] = i
                                break
                    else:
                        itm["StepCombo"].CurrentIndex = 0

                update_shots()
            except Exception as e:
                self.log(f"Error updating steps: {e}", ram.LogLevel.Critical)

        def on_project_changed(ev=None):
            try:
                idx = int(itm["ProjCombo"].CurrentIndex)
                if idx < 0 or idx == session_cache["last_proj_idx"]:
                    return
                session_cache["last_proj_idx"] = idx

                proj = session_cache["projects"][idx]
                proj_uuid = str(proj.uuid())

                if proj_uuid not in session_cache["project_data"]:
                    self.log(f"Loading {proj.name()}...", ram.LogLevel.Info)

                    # 1. Chunked Shot Fetching: Fetch by sequence to avoid 64KB API buffer limit
                    sequences = proj.sequences()
                    seq_map = {str(s.uuid()): s.shortName() for s in sequences}

                    shots = []
                    # Get shots per sequence
                    for seq in sequences:
                        shots.extend(proj.shots(sequence=seq))
                    # Get shots with no sequence
                    shots.extend(proj.shots(sequence=""))

                    # Remove duplicates
                    unique_shots = []
                    seen_uuids = set()
                    for s in shots:
                        u = str(s.uuid())
                        if u not in seen_uuids:
                            unique_shots.append(s)
                            seen_uuids.add(u)

                    # 2. Steps: Fetch only project-relevant steps
                    steps = proj.steps(ram.StepType.SHOT_PRODUCTION)

                    session_cache["project_data"][proj_uuid] = {
                        "shots": unique_shots,
                        "seq_map": seq_map,
                        "steps": steps,
                    }

                p_data = session_cache["project_data"][proj_uuid]
                session_cache["current_shots"] = p_data["shots"]
                session_cache["current_seq_map"] = p_data["seq_map"]
                session_cache["current_steps"] = p_data["steps"]

                update_steps()
            except Exception as e:
                self.log(f"Error loading project: {e}", ram.LogLevel.Critical)

        # 4. Event Binding
        dlg.On.ProjCombo.CurrentIndexChanged = on_project_changed
        dlg.On.StepCombo.CurrentIndexChanged = (
            update_shots  # Changing step refreshes shots
        )
        # dlg.On.ShotCombo.CurrentIndexChanged = None # Unbound to prevent loop during population

        results = {"confirmed": False}

        def on_ok(ev):
            results["confirmed"] = True
            disp.ExitLoop()

        def on_cancel(ev):
            disp.ExitLoop()

        dlg.On.OkBtn.Clicked = on_ok
        dlg.On.CancelBtn.Clicked = on_cancel
        dlg.On[win_id].Close = on_cancel

        # 5. Initialization
        for p in session_cache["projects"]:
            itm["ProjCombo"].AddItem(p.name())

        initial_proj_idx = 0
        if cur_project:
            cur_p_uuid = str(cur_project.uuid())
            for i, p in enumerate(session_cache["projects"]):
                if str(p.uuid()) == cur_p_uuid:
                    initial_proj_idx = i
                    break

        # Trigger cascade: Project -> Step -> Shot
        itm["ProjCombo"].CurrentIndex = initial_proj_idx
        on_project_changed()

        # 6. Show Dialog
        self.dlg.Enabled = False
        try:
            dlg.Show()
            disp.RunLoop()
        finally:
            dlg.Hide()
            self.dlg.Enabled = True

        # 7. Execution
        if results["confirmed"] and session_cache["shot_options"]:
            shot_idx = int(itm["ShotCombo"].CurrentIndex)
            step_idx = int(itm["StepCombo"].CurrentIndex)

            if shot_idx >= 0 and step_idx >= 0:
                shot_data = session_cache["shot_options"][shot_idx]
                selected_step = session_cache["current_steps"][step_idx]

                if not shot_data["exists"]:
                    selected_path = shot_data["path"]
                    use_template = None
                    tpl_folder = selected_step.templatesFolderPath()
                    template_files = []
                    if tpl_folder and os.path.isdir(tpl_folder):
                        template_files = [
                            f for f in os.listdir(tpl_folder) if f.endswith(".comp")
                        ]

                    if template_files:
                        tpl_opts = {"0": "None - Empty Composition"}
                        for i, f in enumerate(template_files):
                            tpl_opts[str(i + 1)] = f
                        tpl_res = host._request_input(
                            "Select Template",
                            [
                                {
                                    "id": "Tpl",
                                    "label": "Template:",
                                    "type": "combo",
                                    "options": tpl_opts,
                                }
                            ],
                        )
                        if tpl_res:
                            idx = int(tpl_res["Tpl"])
                            if idx > 0:
                                use_template = os.path.join(
                                    tpl_folder, template_files[idx - 1]
                                )
                            else:
                                host.fusion.NewComp()
                        else:
                            return

                    if use_template:
                        self.log(
                            f"Creating shot from template: {use_template}",
                            ram.LogLevel.Info,
                        )
                        if host.open(use_template):
                            host.comp.Save(host.normalizePath(selected_path))
                    elif not template_files:
                        init_res = host._request_input(
                            "Initialize Shot",
                            [
                                {
                                    "id": "Mode",
                                    "label": "No template found. Use:",
                                    "type": "combo",
                                    "options": {
                                        "0": "Empty Composition",
                                        "1": "Current Composition as base",
                                    },
                                }
                            ],
                        )
                        if not init_res:
                            return
                        if init_res["Mode"] == 0:
                            host.fusion.NewComp()
                        host.comp.Save(host.normalizePath(selected_path))
                    else:
                        host.comp.Save(host.normalizePath(selected_path))

                    if host.save(comment="Initial creation", setupFile=True):
                        self.refresh_header()
                        self.log(
                            f"New shot initialized: {selected_path}", ram.LogLevel.Info
                        )
                else:
                    if host.open(shot_data["path"]):
                        self.refresh_header()

    def on_import(self, ev):
        if not self._check_connection():
            return
        self.ramses.host.importItem()

    def on_replace(self, ev):
        if not self._check_connection():
            return
        self.ramses.host.replaceItem()

    def on_save(self, ev):
        if not self._check_connection():
            return

        # Ensure anchors are synced before saving
        self._sync_render_anchors()

        # Let the API decide if setup is needed based on project existence
        has_project = self._get_project() is not None
        if self.ramses.host.save(setupFile=has_project):
            self.refresh_header()

    def on_incremental_save(self, ev):
        if not self._check_connection():
            return

        # Ensure anchors are synced before saving
        self._sync_render_anchors()

        has_project = self._get_project() is not None
        if self.ramses.host.save(incremental=True, setupFile=has_project):
            self.refresh_header()

    def on_comment(self, ev):
        if not self._check_connection():
            return
        res = self.ramses.host._request_input(
            "Add Comment",
            [
                {
                    "id": "Comment",
                    "label": "Comment:",
                    "type": "text",
                    "default": "",
                    "lines": 5,
                }
            ],
        )
        if res and res["Comment"]:
            host = self.ramses.host
            has_project = self.ramses.project() is not None

            # Cache the status before save if possible (less network hit than currentStatus after save)
            status = host.currentStatus()

            if host.save(comment=res["Comment"], setupFile=has_project):
                # 1. Update Database Status
                if status:
                    status.setComment(res["Comment"])
                    status.setVersion(host.currentVersion())

                self.refresh_header()

    def on_update_status(self, ev):
        if not self._check_connection():
            return

        # Pre-publish Validation
        is_valid, msg = self._validate_publish(check_preview=False, check_final=True)
        if not is_valid:
            res = self.ramses.host._request_input(
                "Validation Warning",
                [
                    {
                        "id": "W",
                        "label": "Technical Mismatches found:",
                        "type": "text",
                        "default": msg,
                        "lines": 4,
                    },
                    {
                        "id": "Mode",
                        "label": "Action:",
                        "type": "combo",
                        "options": {
                            "0": "Continue anyway (Force)",
                            "1": "Abort and fix settings",
                        },
                    },
                ],
            )
            if not res or res["Mode"] == 1:
                return

        if self.ramses.host.updateStatus():
            self.refresh_header()

    def on_preview(self, ev):
        if not self._check_connection():
            return

        # Pre-Preview Validation
        is_valid, msg = self._validate_publish(check_preview=True, check_final=False)
        if not is_valid:
            res = self.ramses.host._request_input(
                "Validation Warning",
                [
                    {
                        "id": "W",
                        "label": "Technical Mismatches found:",
                        "type": "text",
                        "default": msg,
                        "lines": 4,
                    },
                    {
                        "id": "Mode",
                        "label": "Action:",
                        "type": "combo",
                        "options": {
                            "0": "Continue anyway (Force)",
                            "1": "Abort and fix settings",
                        },
                    },
                ],
            )
            if not res or res["Mode"] == 1:
                return

        self.ramses.host.savePreview()

    def on_publish_settings(self, ev):
        step = self._require_step()
        if not step:
            return

        current_yaml = step.publishSettings()
        res = self.ramses.host._request_input(
            f"Publish Settings: {step.name()}",
            [
                {
                    "id": "YAML",
                    "label": "YAML Config:",
                    "type": "text",
                    "default": current_yaml or "",
                    "lines": 15,
                }
            ],
        )
        if res:
            step.setPublishSettings(res["YAML"])

    def on_save_template(self, ev):
        step = self._require_step()
        if not step:
            return

        res = self.ramses.host._request_input(
            "Save as Template",
            [
                {
                    "id": "Name",
                    "label": "Template Name:",
                    "type": "line",
                    "default": "NewTemplate",
                }
            ],
        )
        if not res or not res["Name"]:
            return

        name = re.sub(r"[^a-zA-Z0-9\- ]", "", res["Name"])
        nm = ram.RamFileInfo()
        nm.project = step.projectShortName()
        nm.ramType = ram.ItemType.GENERAL
        nm.shortName = name
        nm.step = step.shortName()
        nm.extension = "comp"

        tpl_folder = step.templatesFolderPath()
        if not tpl_folder:
            self.log(
                "Step does not have a valid templates folder.", ram.LogLevel.Warning
            )
            return

        path = os.path.join(tpl_folder, nm.fileName())

        comp = self.ramses.host.comp
        if comp:
            comp.Save(self.ramses.host.normalizePath(path))
            self.log(f"Template '{name}' saved to {path}", ram.LogLevel.Info)

    def on_setup_scene(self, ev):
        if not self._check_connection():
            return

        item = self.current_item
        step = self.current_step

        # Use the optimized host implementation to collect settings
        settings = self.ramses.host.collectItemSettings(item)
        if not settings:
            self.log(
                "No active Ramses project found or context is invalid.",
                ram.LogLevel.Warning,
            )
            return

        # Apply directly and refresh UI
        self.ramses.host._setupCurrentFile(item, step, settings)
        self._create_render_anchors()
        self.refresh_header()

    def on_open(self, ev):
        if self.ramses.host.open():
            self.refresh_header()

    def on_retrieve(self, ev):
        if self.ramses.host.restoreVersion():
            self.refresh_header()

    def on_close(self, ev):
        self.disp.ExitLoop()


if __name__ == "__main__":
    app = RamsesFusionApp()
    app.show_main_window()
