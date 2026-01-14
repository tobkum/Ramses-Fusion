import sys
import os
import re

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

    def _check_connection(self):
        """Checks if Ramses Daemon is online and shows a dialog if not."""
        # If marked offline, try to reconnect first
        if not self.ramses.online():
            self.ramses.connect()

        if not self.ramses.online():
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
            return "<font color='#777'>No Active Ramses Item</font>"

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

            # Pre-calculate paths
            preview_path = ""
            publish_path = ""
            if self._get_project():
                try:
                    preview_folder = self.ramses.host.previewPath()
                    try:
                        pub_info = self.ramses.host.publishInfo()
                        preview_info = pub_info.copy()
                        preview_info.version = -1
                        preview_info.state = ""
                        preview_info.resource = ""
                        preview_info.extension = "mov"
                        preview_path = os.path.join(
                            preview_folder, preview_info.fileName()
                        ).replace("\\", "/")
                    except Exception:
                        preview_path = os.path.join(
                            preview_folder, "preview.mov"
                        ).replace("\\", "/")

                    publish_path = self.ramses.host.publishFilePath("mov", "").replace(
                        "\\", "/"
                    )
                except Exception as e:
                    self.log(f"Could not pre-calculate anchor paths: {e}", ram.LogLevel.Debug)

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

                        self.log(f"Created render anchor: {name}", ram.LogLevel.Info)

                # Ensure color is correct (even if existing)
                if node:
                    node.TileColor = cfg["color"]

                    # Optional: If node existed but was far away, we could enforce position here.
                    # For now, we only set position on creation as requested.
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

            if actual_frames != expected_frames:
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
        """Syncs existing _PREVIEW and _FINAL Saver paths with current version and project specs."""
        comp = self.ramses.host.comp
        project = self._get_project()
        item = self.current_item
        if not comp or not project or not item:
            return

        try:
            # 1. Resolve current Ramses paths
            pub_info = self.ramses.host.publishInfo()
            host = self.ramses.host

            # Preview: Official flat filename in the shot's _preview folder
            preview_folder = host.previewPath()
            preview_info = pub_info.copy()
            preview_info.version = -1
            preview_info.state = ""
            preview_info.resource = ""
            preview_info.extension = "mov"
            preview_path = host.normalizePath(os.path.join(
                preview_folder, preview_info.fileName()
            ))

            # Final: Master ProRes 4444 in the project's flat Output (Export) folder
            export_folder = project.exportPath()
            if export_folder:
                # Ensure the folder exists on disk
                if not os.path.isdir(export_folder):
                    try:
                        os.makedirs(export_folder)
                    except Exception:
                        pass

                # Use API to generate the standard filename without version
                final_info = pub_info.copy()
                final_info.version = -1
                final_info.state = ""
                final_info.resource = ""
                final_info.extension = "mov"
                final_filename = final_info.fileName()

                final_path = host.normalizePath(os.path.join(export_folder, final_filename))
            else:
                # Fallback only if export path is totally undefined
                final_path = host.normalizePath(host.publishFilePath("mov", ""))

            # 2. Update existing nodes
            preview_node = comp.FindTool("_PREVIEW")
            if preview_node:
                if preview_node.Clip[1] != preview_path:
                    preview_node.Clip[1] = preview_path

                if preview_node.GetInput("OutputFormat") != "QuickTimeMovies":
                    preview_node.SetInput("OutputFormat", "QuickTimeMovies", 0)

                if (
                    preview_node.GetInput("QuickTimeMovies.Compression")
                    != "Apple ProRes 422_apcn"
                ):
                    preview_node.SetInput(
                        "QuickTimeMovies.Compression", "Apple ProRes 422_apcn", 0
                    )

            final_node = comp.FindTool("_FINAL")
            if final_node:
                if final_node.Clip[1] != final_path:
                    final_node.Clip[1] = final_path

                if final_node.GetInput("OutputFormat") != "QuickTimeMovies":
                    final_node.SetInput("OutputFormat", "QuickTimeMovies", 0)

                if (
                    final_node.GetInput("QuickTimeMovies.Compression")
                    != "Apple ProRes 4444_ap4h"
                ):
                    final_node.SetInput(
                        "QuickTimeMovies.Compression", "Apple ProRes 4444_ap4h", 0
                    )
        except Exception as e:
            self.log(f"Sync Render Anchors failed: {e}", ram.LogLevel.Debug)

    def refresh_header(self):
        """Updates the context label and footer with current info."""
        if not self._check_connection():
            return

        if self.dlg:
            try:
                # Force cache refresh for project and user
                self._project_cache = None
                self._user_name_cache = None
                
                # Clear item/step path trackers to force re-fetch from host
                self._item_path = ""
                self._step_path = ""

                # Sync Savers before updating UI
                self._sync_render_anchors()

                items = self.dlg.GetItems()
                if "ContextLabel" in items:
                    items["ContextLabel"].Text = self._get_context_text()
                if "RamsesVersion" in items:
                    items["RamsesVersion"].Text = self._get_footer_text()

                # Toggle Pipeline Buttons
                item = self.current_item
                is_pipeline = item is not None and bool(item.uuid())
                
                pipeline_buttons = [
                    "SetupSceneButton", "ImportButton", "ReplaceButton", 
                    "TemplateButton", "IncrementalSaveButton", "SaveButton", 
                    "RetrieveButton", "CommentButton", "PreviewButton", 
                    "UpdateStatusButton", "PubSettingsButton"
                ]
                
                for btn_id in pipeline_buttons:
                    if btn_id in items:
                        items[btn_id].Enabled = is_pipeline

            except Exception as e:
                self.log(f"UI Refresh failed: {e}", ram.LogLevel.Debug)

    def show_main_window(self):
        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses-Fusion",
                "ID": "MainWin",
                "Geometry": [200, 200, 300, 800],
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
                                                        "Icon": self._get_icon("ramupdate.png"),
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
        self.dlg.On.RefreshButton.Clicked = lambda ev: self.refresh_header()
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
                    "OpenButton",
                    "Open Composition",
                    "open.png",
                    tooltip="Browse and open an existing Ramses composition.",
                ),
                self.create_button(
                    "SwitchShotButton",
                    "Switch Shot",
                    "open.png",
                    tooltip="Quickly jump to another shot in this project or create a new one from a template.",
                ),
                self.create_button(
                    "SetupSceneButton",
                    "Setup Scene",
                    "setupScene.png",
                    tooltip="Automatically set the resolution, FPS, and frame range based on Ramses project settings.",
                ),
                self.create_button(
                    "RamsesButton",
                    "Open Ramses Client",
                    "ramses.png",
                    tooltip="Launch the main Ramses Client application.",
                ),
            ]
        )

    def _build_pipeline_group(self):
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
                    "open.png",
                    tooltip="Import a published asset or render into the current composition.",
                ),
                self.create_button(
                    "ReplaceButton",
                    "Replace Loader",
                    "retrieveVersion.png",
                    tooltip="Replace the selected Loader node with a different version or asset.",
                ),
                self.create_button(
                    "TemplateButton",
                    "Save as Template",
                    "template.png",
                    tooltip="Save the current composition as a template for other shots in this step.",
                ),
            ]
        )

    def _build_working_group(self):
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
                    "IncrementalSaveButton",
                    "Incremental Save",
                    "incrementalSave.png",
                    tooltip="Save a new version of the current file (v001 -> v002).",
                ),
                self.create_button(
                    "SaveButton",
                    "Save",
                    "save.png",
                    tooltip="Overwrite the current working file version.",
                ),
                self.create_button(
                    "RetrieveButton",
                    "Retrieve Version",
                    "retrieveVersion.png",
                    tooltip="Open a previous version of this composition from the _versions folder.",
                ),
                self.create_button(
                    "CommentButton",
                    "Add Comment",
                    "comment.png",
                    tooltip="Add a note to the current version in the Ramses database.",
                ),
            ]
        )

    def _build_publish_group(self):
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
                    "preview.png",
                    tooltip="Generate a preview render for review.",
                ),
                self.create_button(
                    "UpdateStatusButton",
                    "Update Status / Publish",
                    "updateStatus.png",
                    tooltip="Change the shot status (WIP, Review, Done) and optionally publish the final comp.",
                ),
            ]
        )

    def _build_settings_group(self):
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
                    "publishSettings.png",
                    tooltip="Configure YAML settings for automated publishing.",
                ),
                self.create_button(
                    "SettingsButton",
                    "Plugin Settings",
                    "Settings.png",
                    tooltip="Configure Ramses paths, ports, and default frame ranges.",
                ),
                self.create_button(
                    "AboutButton",
                    "About",
                    "Settings.png",
                    tooltip="Information about Ramses-Fusion and Overmind Studios.",
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
    ):
        return self.ui.Button(
            {
                "ID": id_name,
                "Text": "  " + text if text else "",
                "Weight": weight,
                "ToolTip": tooltip,
                "MinimumSize": min_size or [16, 28],
                "MaximumSize": max_size or [2000, 28],
                "IconSize": [16, 16],
                "Icon": self._get_icon(icon_name),
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
                "Geometry": [200, 200, 450, 150],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 0},
                    [
                        self.ui.Label(
                            {
                                "ID": "Info",
                                "Text": "Ramses-Fusion for Overmind Studios. <p>Copyright &copy; 2026 Overmind Studios.</p>",
                                "Alignment": [{"AlignHCenter": True, "AlignTop": True}],
                                "WordWrap": True,
                                "OpenExternalLinks": True,
                            }
                        ),
                        self.ui.Label(
                            {
                                "ID": "URL",
                                "Text": 'Web: <a href="https://www.overmind-studios.de">Overmind Studios</a>',
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
        if not self._check_connection():
            return
        current_step = self.current_step
        if not current_step:
            self.log(
                "Open a valid Ramses file first to set the context.",
                ram.LogLevel.Warning,
            )
            return

        # 1. Bulk fetch all relevant objects once for maximum performance
        self.log("Fetching shots and statuses...", ram.LogLevel.Info)

        project = self._get_project()
        project_uuid = project.uuid() if project else None

        # Use getObjects (Bulk with Data) instead of project.shots() (UUID only, leads to N+1 requests)
        all_shots = self.ramses.daemonInterface().getObjects("RamShot")
        all_seqs = self.ramses.daemonInterface().getObjects("RamSequence")
        all_statuses = self.ramses.daemonInterface().getObjects("RamStatus")

        # Performance Optimization: Filter by project UUID if available
        # This prevents processing thousands of shots from other projects in a studio environment.
        if project_uuid:
            all_shots = [s for s in all_shots if s.get("project") == project_uuid]
            all_seqs = [s for s in all_seqs if s.get("project") == project_uuid]
            # Note: We don't filter all_statuses by project directly as the field might be missing in some Ramses versions.
            # Filtering by step_uuid in the status_map construction below is sufficient and safer.

        seq_map = {s.uuid(): s.shortName() for s in all_seqs}
        step_uuid = current_step.uuid()
        status_map = {
            s.get("item"): s for s in all_statuses if s.get("step") == step_uuid
        }

        # 2. Map shots to options
        shot_options = {}
        shot_data_map = {}  # label -> data

        # Sort shots by sequence then name
        all_shots.sort(
            key=lambda s: (seq_map.get(s.get("sequence", ""), ""), s.shortName())
        )

        for shot in all_shots:
            # Performance Optimization: Inject the already fetched project to avoid N+1 calls to DAEMON.getProject()
            # inside shot.stepFilePath() and other methods.
            shot._RamObject__project = project

            status = status_map.get(shot.uuid())
            # Skip shots that have "Nothing to do" (NO) or "Standby" (STB)
            if status and status.state().shortName() in ["NO", "STB"]:
                continue

            # Official API way to predict/get the working file path
            expected_path = shot.stepFilePath(step=current_step, extension="comp")

            if not expected_path:
                continue

            filename = os.path.basename(expected_path)
            exists = os.path.exists(expected_path)
            seq_name = seq_map.get(shot.get("sequence", ""), "None")

            if exists:
                state_name = status.state().name() if status else "WIP"
                label = f"{seq_name} / {shot.shortName()} [{state_name}]"
            else:
                label = f"{seq_name} / {shot.shortName()} [EMPTY - Create New]"

            idx = str(len(shot_options))
            shot_options[idx] = label
            shot_data_map[label] = {
                "shot": shot,
                "path": expected_path,
                "exists": exists,
                "filename": filename,
            }

        if not shot_options:
            self.log("No shots found in project.", ram.LogLevel.Info)
            return

        # 4. Show selection dialog
        res = self.ramses.host._request_input(
            "Switch / Create Shot",
            [
                {
                    "id": "Shot",
                    "label": "Select Shot:",
                    "type": "combo",
                    "options": shot_options,
                }
            ],
        )

        if res:
            selected_label = shot_options[str(res["Shot"])]
            data = shot_data_map[selected_label]
            shot_obj = data["shot"]

            # 5. Handle Creation from Template
            if not data["exists"]:
                # Use official API to resolve and create folders
                step_folder = shot_obj.stepFolderPath(current_step)
                selected_path = os.path.join(step_folder, data["filename"]).replace(
                    "\\", "/"
                )

                use_template = None

                # Fetch templates for this step
                tpl_folder = current_step.templatesFolderPath()
                template_files = []
                if tpl_folder and os.path.isdir(tpl_folder):
                    template_files = [
                        f for f in os.listdir(tpl_folder) if f.endswith(".comp")
                    ]

                if template_files:
                    # Add "Empty" as the first option
                    tpl_opts = {"0": "None - Empty Composition"}
                    for i, f in enumerate(template_files):
                        tpl_opts[str(i + 1)] = f

                    tpl_res = self.ramses.host._request_input(
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
                        if idx > 0:  # Selected a file
                            use_template = os.path.join(
                                tpl_folder, template_files[idx - 1]
                            )
                        else:  # Selected "None - Empty"
                            self.ramses.host.fusion.NewComp()
                    else:
                        return  # Cancelled

                if use_template:
                    self.log(
                        f"Creating shot from template: {use_template}",
                        ram.LogLevel.Info,
                    )
                    if self.ramses.host.open(use_template):
                        self.ramses.host.comp.Save(selected_path)
                elif not template_files:  # Fallback if no templates existed at all
                    init_res = self.ramses.host._request_input(
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
                        self.ramses.host.fusion.NewComp()
                    self.ramses.host.comp.Save(selected_path)
                else:  # User selected "None - Empty" in the list
                    self.ramses.host.comp.Save(selected_path)

                # 6. Initialize Ramses Versioning idiomaticly
                # Only attempt setup if a project is active
                has_project = self.ramses.project() is not None
                if self.ramses.host.save(
                    comment="Initial creation", setupFile=has_project
                ):
                    self.refresh_header()
                    self.log(
                        f"New shot initialized: {selected_path}", ram.LogLevel.Info
                    )

            # 7. Standard Open
            else:
                if self.ramses.host.open(data["path"]):
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
                
                # 2. Sync Metadata to Version File (for 'Retrieve Version' list)
                version_file = host.currentVersionFilePath()
                if version_file and os.path.isfile(version_file):
                    ram.RamMetaDataManager.setComment(version_file, res["Comment"])
                    
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

        name = re.sub(r"[^a-zA-Z0-9\-]", "", res["Name"])
        nm = ram.RamFileInfo()
        nm.project = step.projectShortName()
        nm.ramType = ram.ItemType.GENERAL
        nm.shortName = name
        nm.step = step.shortName()
        nm.extension = "comp"
        
        tpl_folder = step.templatesFolderPath()
        if not tpl_folder:
            self.log("Step does not have a valid templates folder.", ram.LogLevel.Warning)
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
            self.log("No active Ramses project found or context is invalid.", ram.LogLevel.Warning)
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
