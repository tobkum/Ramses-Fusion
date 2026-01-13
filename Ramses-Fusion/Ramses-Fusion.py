import sys
import os
import re

# Add the 'lib' directory to Python's search path
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
except NameError:
    # Fallback for environments where __file__ is not defined
    script_dir = os.path.dirname(os.path.realpath(fu.MapPath('Scripts:/Comp/Ramses-Fusion/Ramses-Fusion.py')))

lib_path = os.path.join(script_dir, 'lib')
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
        self.dlg = None

    def show_main_window(self):
        # Get Current Context
        item = self.ramses.host.currentItem()
        step = self.ramses.host.currentStep()
        
        context_text = "<font color='#777'>No Active Ramses Item</font>"
        if item:
            project = item.project()
            project_name = project.name() if project else item.projectShortName()
            item_name = item.shortName()
            step_name = step.name() if step else "No Step"
            context_text = f"<font color='#555'>{project_name} / </font><b>{item_name}</b><br><font color='#999'>{step_name}</font>"

        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses-Fusion",
                "ID": "MainWin",
                "Geometry": [200, 200, 380, 800],
            },
            [
                self.ui.VGroup({"Spacing": 0, "Weight": 1}, [
                    self.ui.VGap(15),
                    self.ui.HGroup({"Weight": 1}, [
                        self.ui.HGap(15),
                        self.ui.VGroup({"Spacing": 4, "Weight": 1}, [
                            # Context Header
                            self.ui.Label({
                                "ID": "ContextLabel",
                                "Text": context_text,
                                "Alignment": {"AlignHCenter": True, "AlignTop": True},
                                "WordWrap": True,
                                "Weight": 0,
                            }),
                            self.ui.VGap(10),

                            # Section: Project & Files
                            self.ui.Label({"Text": "PROJECT & FILES", "Weight": 0, "Font": self.ui.Font({"PixelSize": 11, "Bold": True})}),
                            self.create_button("RamsesButton", "Open Ramses Client", "ramses.png"),
                            self.create_button("OpenButton", "Open Composition", "open.png"),
                            self.create_button("RetrieveButton", "Retrieve Version", "retrieveVersion.png"),
                            self.ui.VGap(8),

                            # Section: Pipeline
                            self.ui.Label({"Text": "PIPELINE", "Weight": 0, "Font": self.ui.Font({"PixelSize": 11, "Bold": True})}),
                            self.create_button("ImportButton", "Import Asset", "open.png"),
                            self.create_button("ReplaceButton", "Replace Loader", "retrieveVersion.png"),
                            self.create_button("SetupSceneButton", "Setup Scene", "setupScene.png"),
                            self.ui.VGap(8),

                            # Section: Working
                            self.ui.Label({"Text": "WORKING", "Weight": 0, "Font": self.ui.Font({"PixelSize": 11, "Bold": True})}),
                            self.create_button("SaveButton", "Save", "save.png"),
                            self.create_button("IncrementalSaveButton", "Incremental Save", "incrementalSave.png"),
                            self.create_button("CommentButton", "Add Comment", "comment.png"),
                            self.ui.VGap(8),

                            # Section: Publish
                            self.ui.Label({"Text": "PUBLISH / STATUS", "Weight": 0, "Font": self.ui.Font({"PixelSize": 11, "Bold": True})}),
                            self.create_button("UpdateStatusButton", "Update Status/Publish", "updateStatus.png"),
                            self.create_button("PreviewButton", "Create Preview", "preview.png"),
                            
                            # Spacer to push everything up
                            self.ui.VGap(0, 1),

                            # Footer
                            self.ui.HGroup({"Weight": 0}, [
                                self.create_button("PubSettingsButton", "", "publishSettings.png", weight=1),
                                self.create_button("SettingsButton", "", "Settings.png", weight=1),
                                self.create_button("AboutButton", "", "Settings.png", weight=1),
                            ]),
                            self.ui.Label(
                                {
                                    "ID": "RamsesVersion",
                                    "Text": "Ramses API " + self.settings.version,
                                    "Alignment": {"AlignHCenter": True},
                                    "Weight": 0,
                                }
                            ),
                        ]),
                        self.ui.HGap(15),
                    ]),
                    self.ui.VGap(15),
                ])
            ]
        )

        # Bind Events
        self.dlg.On.RamsesButton.Clicked = self.on_run_ramses
        self.dlg.On.ImportButton.Clicked = self.on_import
        self.dlg.On.ReplaceButton.Clicked = self.on_replace
        self.dlg.On.SaveButton.Clicked = self.on_save
        self.dlg.On.CommentButton.Clicked = self.on_comment
        self.dlg.On.IncrementalSaveButton.Clicked = self.on_incremental_save
        self.dlg.On.UpdateStatusButton.Clicked = self.on_update_status
        self.dlg.On.PreviewButton.Clicked = self.on_preview
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

    def create_button(self, id_name, text, icon_name, weight=0):
        icon_path = os.path.join(self.script_dir, "icons", icon_name)
        return self.ui.Button(
            {
                "ID": id_name,
                "Text": "  " + text if text else "",
                "Weight": weight,
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
                        self.ui.HGroup([
                            self.ui.Label({"Text": "Ramses executable path:", "Weight": 1}),
                            self.ui.LineEdit({"ID": "RamsesPathTxt", "Weight": 2, "Text": self.settings.ramsesClientPath}),
                        ]),
                        self.ui.HGroup([
                            self.ui.Label({"Text": "Ramses client port:", "Weight": 1}),
                            self.ui.LineEdit({"ID": "RamsesPortTxt", "Weight": 2, "Text": str(self.settings.ramsesClientPort)}),
                        ]),
                        self.ui.HGroup([
                            self.ui.Label({"Text": "Comp Start Frame:", "Weight": 1}),
                            self.ui.LineEdit({"ID": "StartFrameTxt", "Weight": 2, "Text": str(self.settings.userSettings.get("compStartFrame", 1001))}),
                        ]),
                        self.ui.HGroup([
                            self.ui.Button({"ID": "SaveSettingsButton", "Text": "Save"}),
                            self.ui.Button({"ID": "CloseSettingsButton", "Text": "Close"}),
                        ]),
                    ],
                )
            ],
        )

        itm = dlg.GetItems()

        def save_settings(ev):
            self.settings.ramsesClientPort = int(itm["RamsesPortTxt"].Text)
            self.settings.ramsesClientPath = str(itm["RamsesPathTxt"].Text)
            try:
                self.settings.userSettings["compStartFrame"] = int(itm["StartFrameTxt"].Text)
            except ValueError:
                self.settings.userSettings["compStartFrame"] = 1001
            self.settings.save()
            print("Ramses: Settings Saved.")

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
                        self.ui.Label({
                            "ID": "Info",
                            "Text": "Ramses-Fusion for Overmind Studios. <p>Copyright &copy; 2025 Overmind Studios.</p>",
                            "Alignment": [{"AlignHCenter": True, "AlignTop": True}],
                            "WordWrap": True,
                            "OpenExternalLinks": True,
                        }),
                        self.ui.Label({
                            "ID": "URL",
                            "Text": 'Web: <a href="https://www.overmind-studios.de">Overmind Studios</a>',
                            "Alignment": [{"AlignHCenter": True, "AlignTop": True}],
                            "WordWrap": True,
                            "OpenExternalLinks": True,
                        }),
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

    def on_import(self, ev):
        self.ramses.host.importItem()

    def on_replace(self, ev):
        self.ramses.host.replaceItem()

    def on_save(self, ev):
        self.ramses.host.save()

    def on_incremental_save(self, ev):
        self.ramses.host.save(incremental=True)

    def on_comment(self, ev):
        res = self.ramses.host._request_input("Add Comment", [
            {'id': 'Comment', 'label': 'Comment:', 'type': 'text', 'default': '', 'lines': 5}
        ])
        if res and res['Comment']:
            if self.ramses.host.save(comment=res['Comment']):
                status = self.ramses.host.currentStatus()
                if status:
                    status.setComment(res['Comment'])
                    status.setVersion(self.ramses.host.currentVersion())

    def on_update_status(self, ev):
        self.ramses.host.updateStatus()

    def on_preview(self, ev):
        self.ramses.host.savePreview()

    def on_publish_settings(self, ev):
        step = self.ramses.host.currentStep()
        if not step:
            self.ramses.host._request_input("Ramses Warning", [
                {'id': 'W', 'label': '', 'type': 'text', 'default': 'Save as valid Step first.', 'lines': 1}
            ])
            return
        
        current_yaml = step.publishSettings()
        res = self.ramses.host._request_input(f"Publish Settings: {step.name()}", [
            {'id': 'YAML', 'label': 'YAML Config:', 'type': 'text', 'default': current_yaml or "", 'lines': 15}
        ])
        if res:
            step.setPublishSettings(res['YAML'])

    def on_save_template(self, ev):
        step = self.ramses.host.currentStep()
        if not step:
            self.ramses.host._request_input("Ramses Warning", [
                {'id': 'W', 'label': '', 'type': 'text', 'default': 'Save as valid Step first.', 'lines': 1}
            ])
            return
            
        res = self.ramses.host._request_input("Save as Template", [
            {'id': 'Name', 'label': 'Template Name:', 'type': 'line', 'default': 'NewTemplate'}
        ])
        if not res or not res['Name']: return
        
        name = re.sub(r'[^a-zA-Z0-9\-]', '', res['Name'])
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
            print(f"Ramses: Template '{name}' saved to {path}")

    def on_setup_scene(self, ev):
        self.ramses.host.setupCurrentFile()

    def on_open(self, ev):
        if self.ramses.host.open():
            self.disp.ExitLoop()

    def on_retrieve(self, ev):
        self.ramses.host.restoreVersion()

    def on_close(self, ev):
        self.disp.ExitLoop()

if __name__ == "__main__":
    app = RamsesFusionApp()
    app.show_main_window()
