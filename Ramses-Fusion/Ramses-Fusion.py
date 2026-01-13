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

        self.ui = fu.UIManager
        self.disp = bmd.UIDispatcher(self.ui)
        self.script_dir = script_dir
        self.icon_dir = os.path.join(self.script_dir, "icons")
        self.dlg = None
        self._last_path = ""  # Track path for auto-refresh
        self._project_cache = None

    @property
    def current_item(self):
        return self.ramses.host.currentItem()

    @property
    def current_step(self):
        return self.ramses.host.currentStep()

    def _get_project(self):
        """Cached access to the current project."""
        if not self._project_cache:
            self._project_cache = self.ramses.project()
        return self._project_cache

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

        def _get_context_text(self):
            item = self.current_item
            step = self.current_step
    
            if not item:
                return "<font color='#777'>No Active Ramses Item</font>"
    
            project = self._get_project()
            project_name = project.name() if project else item.projectShortName()
            item_name = item.shortName()
            step_name = step.name() if step else "No Step"
            return f"<font color='#555'>{project_name} / </font><b>{item_name}</b><br><font color='#999'>{step_name}</font>"
    
        def _get_footer_text(self):
            user = self.ramses.user()
            user_name = user.name() if user else "Not Logged In"
            return f"<font color='#555'>User: {user_name} | Ramses API {self.settings.version}</font>"
    
        def refresh_header(self):
            """Updates the context label and footer with current info."""
            if not self._check_connection():
                return
                
            if self.dlg:
                self._project_cache = None # Reset cache on manual refresh
                self._last_path = self.ramses.host.currentFilePath()
                items = self.dlg.GetItems()
                items["ContextLabel"].Text = self._get_context_text()
                items["RamsesVersion"].Text = self._get_footer_text()
    def show_main_window(self):
        # Initial path capture
        self._last_path = self.ramses.host.currentFilePath()

        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses-Fusion",
                "ID": "MainWin",
                "Geometry": [200, 200, 380, 800],
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
                                                        "Icon": self.ui.Icon(
                                                            {
                                                                "File": os.path.join(
                                                                    self.script_dir,
                                                                    "icons",
                                                                    "ramupdate.png",
                                                                )
                                                            }
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
                                                                    self.ui.Label({
                                                                        "ID": "RamsesVersion",
                                                                        "Text": self._get_footer_text(),
                                                                        "Alignment": {"AlignHCenter": True},
                                                                        "Weight": 0,
                                                                    }),
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

    def create_button(self, id_name, text, icon_name, weight=0, tooltip=""):
        icon_path = os.path.join(self.script_dir, "icons", icon_name)
        return self.ui.Button(
            {
                "ID": id_name,
                "Text": "  " + text if text else "",
                "Weight": weight,
                "ToolTip": tooltip,
                "Icon": self.ui.Icon({"File": icon_path}),
            }
        )

    def show_settings_window(self, ev):
        dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses Settings",
                "ID": "SettingsWin",
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
            self.ramses.host.log("Settings Saved.", ram.LogLevel.Info)

        def close_settings(ev):
            self.disp.ExitLoop()

        dlg.On.SettingsWin.Close = close_settings
        dlg.On.CloseSettingsButton.Clicked = close_settings
        dlg.On.SaveSettingsButton.Clicked = save_settings

        dlg.Show()
        self.disp.RunLoop()
        dlg.Hide()

    def show_about_window(self, ev):
        dlg = self.disp.AddWindow(
            {
                "WindowTitle": "About Ramses-Fusion",
                "ID": "AboutWin",
                "Geometry": [200, 200, 450, 150],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 0},
                    [
                        self.ui.Label(
                            {
                                "ID": "Info",
                                "Text": "Ramses-Fusion for Overmind Studios. <p>Copyright &copy; 2025 Overmind Studios.</p>",
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
        dlg.On.AboutCloseButton.Clicked = lambda ev: self.disp.ExitLoop()
        dlg.On.AboutWin.Close = lambda ev: self.disp.ExitLoop()
        dlg.Show()
        self.disp.RunLoop()
        dlg.Hide()

    # --- Handlers ---

    def on_run_ramses(self, ev):
        self.ramses.showClient()

    def on_switch_shot(self, ev):
        if not self._check_connection(): return
        current_step = self.current_step
        if not current_step:
            self.ramses.host.log(
                "Open a valid Ramses file first to set the context.",
                ram.LogLevel.Warning,
            )
            return

        # 1. Bulk fetch shots and sequences for efficiency
        self.ramses.host.log("Fetching shots list...", ram.LogLevel.Info)
        all_shots = self.ramses.daemonInterface().getObjects("RamShot")
        all_seqs = self.ramses.daemonInterface().getObjects("RamSequence")
        seq_map = {s.uuid(): s.shortName() for s in all_seqs}

        # 2. Find templates for this step
        template_files = []
        tpl_folder = current_step.templatesFolderPath()
        if os.path.isdir(tpl_folder):
            template_files = [f for f in os.listdir(tpl_folder) if f.endswith(".comp")]

        # 3. Map shots to options
        shot_options = {}
        shot_data_map = {}  # label -> data
        
        # Sort shots by sequence then name
        all_shots.sort(key=lambda s: (seq_map.get(s.get("sequence", ""), ""), s.shortName()))

        for shot in all_shots:
            status = shot.currentStatus(current_step)
            # Skip shots that have "Nothing to do" (NO) or "Standby" (STB)
            if status and status.state().shortName() in ["NO", "STB"]:
                continue

            # Construct filename using official API standards
            nm = ram.RamFileInfo()
            nm.project = shot.projectShortName()
            nm.ramType = shot.itemType()
            nm.shortName = shot.shortName()
            nm.step = current_step.shortName()
            nm.extension = "comp"
            filename = nm.fileName()

            # Mimic API step folder calculation safely
            # Use daemon directly to get path without triggering folder creation
            shot_root = self.ramses.daemonInterface().getPath(shot.uuid(), "RamShot")
            if not shot_root: continue
            
            step_folder_name = os.path.splitext(filename)[0]
            expected_path = os.path.join(shot_root, step_folder_name, filename).replace(
                "\\", "/"
            )

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
            self.ramses.host.log("No shots found in project.", ram.LogLevel.Info)
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
                    self.ramses.host.log(
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
                    self.ramses.host.log(
                        f"New shot initialized: {selected_path}", ram.LogLevel.Info
                    )

            # 7. Standard Open
            else:
                if self.ramses.host.open(data["path"]):
                    self.refresh_header()

    def on_import(self, ev):
        if not self._check_connection(): return
        self.ramses.host.importItem()

    def on_replace(self, ev):
        if not self._check_connection(): return
        self.ramses.host.replaceItem()

    def on_save(self, ev):
        if not self._check_connection(): return
        has_project = self.ramses.project() is not None
        if self.ramses.host.save(setupFile=has_project):
            self.refresh_header()

    def on_incremental_save(self, ev):
        if not self._check_connection(): return
        has_project = self.ramses.project() is not None
        if self.ramses.host.save(incremental=True, setupFile=has_project):
            self.refresh_header()

    def on_comment(self, ev):
        if not self._check_connection(): return
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
            has_project = self.ramses.project() is not None
            if self.ramses.host.save(comment=res["Comment"], setupFile=has_project):
                status = self.ramses.host.currentStatus()
                if status:
                    status.setComment(res["Comment"])
                    status.setVersion(self.ramses.host.currentVersion())
                self.refresh_header()

    def on_update_status(self, ev):
        if not self._check_connection(): return
        if self.ramses.host.updateStatus():
            self.refresh_header()

    def on_preview(self, ev):
        if not self._check_connection(): return
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
        path = os.path.join(step.templatesFolderPath(), nm.fileName())

        comp = self.ramses.host.comp
        if comp:
            comp.Save(path)
            self.ramses.host.log(
                f"Template '{name}' saved to {path}", ram.LogLevel.Info
            )

    def on_setup_scene(self, ev):
        if self.ramses.project():
            self.ramses.host.setupCurrentFile()
            self.refresh_header()
        else:
            self.ramses.host.log(
                "No active Ramses project found. Cannot setup scene parameters.",
                ram.LogLevel.Warning,
            )

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
