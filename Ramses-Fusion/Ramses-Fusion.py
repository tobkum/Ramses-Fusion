import sys
import os

# Add the 'lib' directory to Python's search path to find the ramses package.
# This makes the script self-contained and avoids cluttering Fusion's script menu.
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
except NameError:
    # Fallback for environments where __file__ is not defined, like in some Fusion contexts
    script_dir = os.path.dirname(os.path.realpath(fu.MapPath('Scripts:/Comp/Ramses-Fusion/Ramses-Fusion.py')))

lib_path = os.path.join(script_dir, 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

import sys
import os

# Add the 'lib' directory to Python's search path
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
except NameError:
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
        
        # Initialize Host with Fusion instance
        # Comp is accessed dynamically in the host
        self.ramses.host = fusion_host.FusionHost(fu)
        
        self.ui = fu.UIManager
        self.disp = bmd.UIDispatcher(self.ui)
        self.script_dir = script_dir

    def show_main_window(self):
        self.dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses-Fusion",
                "ID": "MainWin",
                "Geometry": [200, 200, 250, 450],
            },
            [
                self.ui.VGroup(
                    {
                        "Spacing": 0,
                    },
                    [
                        self.create_button("RamsesButton", "Open Ramses Client", "ramses.png"),
                        self.create_button("SaveButton", "Save", "save.png"),
                        self.create_button("CommentButton", "Comment", "comment.png"),
                        self.create_button("IncrementalSaveButton", "Incremental Save", "incrementalSave.png"),
                        self.create_button("UpdateStatusButton", "Update Status/Publish", "updateStatus.png"),
                        self.create_button("PreviewButton", "CreatePreview", "preview.png"),
                        self.create_button("TemplateButton", "Save as Template", "template.png"),
                        self.create_button("SetupSceneButton", "Setup Scene", "setupScene.png"),
                        self.create_button("OpenButton", "Open", "open.png"),
                        self.create_button("RetrieveButton", "Retrieve Version", "retrieveVersion.png"),
                        self.create_button("PubSettingsButton", "Publishing Settings", "publishSettings.png"),
                        self.create_button("SettingsButton", "Settings", "Settings.png"),
                        self.create_button("AboutButton", "About", "Settings.png"),
                        self.ui.Label(
                            {
                                "ID": "RamsesVersion",
                                "Text": "Ramses API version: " + self.settings.version,
                            }
                        ),
                    ],
                ),
            ],
        )

        # Bind Events
        self.dlg.On.RamsesButton.Clicked = self.on_run_ramses
        self.dlg.On.SaveButton.Clicked = self.on_save
        self.dlg.On.CommentButton.Clicked = self.on_update_status
        self.dlg.On.IncrementalSaveButton.Clicked = self.on_incremental_save
        self.dlg.On.UpdateStatusButton.Clicked = self.on_update_status
        self.dlg.On.PreviewButton.Clicked = self.on_preview
        self.dlg.On.TemplateButton.Clicked = self.on_dummy 
        self.dlg.On.SetupSceneButton.Clicked = self.on_setup_scene
        self.dlg.On.OpenButton.Clicked = self.on_open
        self.dlg.On.RetrieveButton.Clicked = self.on_retrieve
        self.dlg.On.PubSettingsButton.Clicked = self.on_dummy
        self.dlg.On.SettingsButton.Clicked = self.show_settings_window
        self.dlg.On.AboutButton.Clicked = self.show_about_window
        self.dlg.On.MainWin.Close = self.on_close

        self.dlg.Show()
        self.disp.RunLoop()
        self.dlg.Hide()

    def create_button(self, id_name, text, icon_name):
        # Helper to create buttons with icons relative to the script path
        # Note: Fusion expects "Scripts:/..." style or absolute paths
        # We try to construct a path that Fusion understands
        
        # Determine icon path logic
        # If script_dir starts with the fusion scripts path, we can try to use relative
        # But safest is absolute path passed to icon
        
        icon_path = os.path.join(self.script_dir, "icons", icon_name)
        
        return self.ui.Button(
            {
                "ID": id_name,
                "Text": "   " + text,
                "Flat": False,
                "IconSize": [16, 16],
                "MinimumSize": [16, 16],
                "Margin": 1,
                "Icon": self.ui.Icon({"File": icon_path}),
            }
        )

    def show_settings_window(self, ev):
        dlg = self.disp.AddWindow(
            {
                "WindowTitle": "Ramses Settings",
                "ID": "SettingsWin",
                "Geometry": [200, 200, 550, 100],
            },
            [
                self.ui.VGroup(
                    {"Spacing": 5},
                    [
                        self.ui.HGroup(
                            {"Spacing": 5},
                            [
                                self.ui.Label({"Text": "Ramses executable path:"}),
                                self.ui.LineEdit(
                                    {
                                        "ID": "RamsesPathTxt",
                                        "Weight": 2,
                                        "Text": self.settings.ramsesClientPath,
                                        "PlaceholderText": "Path to Ramses.exe",
                                    }
                                ),
                            ],
                        ),
                        self.ui.HGroup(
                            {"Spacing": 0},
                            [
                                self.ui.Label({"Text": "Ramses client port:"}),
                                self.ui.LineEdit(
                                    {
                                        "ID": "RamsesPortTxt",
                                        "Weight": 2,
                                        "Text": str(self.settings.ramsesClientPort),
                                        "PlaceholderText": "Port number",
                                    }
                                ),
                            ],
                        ),
                        self.ui.HGroup(
                            {"Spacing": 5},
                            [
                                self.ui.Button({"ID": "SaveSettingsButton", "Text": "Save"}),
                                self.ui.Button({"ID": "CloseSettingsButton", "Text": "Close"}),
                            ],
                        ),
                    ],
                )
            ],
        )

        itm = dlg.GetItems()

        def save_settings(ev):
            self.settings.ramsesClientPort = int(itm["RamsesPortTxt"].Text)
            self.settings.ramsesClientPath = str(itm["RamsesPathTxt"].Text)
            self.settings.save()

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
                                "Text": "Ramses-Fusion was coded by Tobias Kummer for Overmind Studios. <p>Copyright &copy; 2025 Overmind Studios - Kummer, Gerhardt & Kraus GbR.</p>",
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

        def close_about(ev):
             self.disp.ExitLoop()

        dlg.On.AboutCloseButton.Clicked = close_about
        dlg.On.AboutWin.Close = close_about

        dlg.Show()
        self.disp.RunLoop()
        dlg.Hide()

    # --- Handlers ---

    def on_run_ramses(self, ev):
        self.ramses.showClient()

    def on_save(self, ev):
        self.ramses.host.save()

    def on_incremental_save(self, ev):
        self.ramses.host.save(incremental=True)

    def on_update_status(self, ev):
        self.ramses.host.updateStatus()

    def on_preview(self, ev):
        self.ramses.host.savePreview()

    def on_setup_scene(self, ev):
        self.ramses.host.setupCurrentFile()

    def on_open(self, ev):
        if self.ramses.host.open():
            self.disp.ExitLoop()

    def on_retrieve(self, ev):
        self.ramses.host.restoreVersion()

    def on_dummy(self, ev):
        pass

    def on_close(self, ev):
        self.disp.ExitLoop()

# Main Execution
if __name__ == "__main__":
    app = RamsesFusionApp()
    app.show_main_window()