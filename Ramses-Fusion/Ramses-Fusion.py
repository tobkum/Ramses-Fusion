import ramses as ram
from os import system

RAMSES = ram.Ramses.instance()
SETTINGS = ram.RamSettings.instance()

ui = fu.UIManager
disp = bmd.UIDispatcher(ui)


def MainWindow():
    dlg = disp.AddWindow(
        {
            "WindowTitle": "Ramses-Fusion",
            "ID": "MainWin",
            "Geometry": [200, 200, 250, 450],
        },
        [
            ui.VGroup(
                {
                    "Spacing": 0,
                },
                [  # Add your GUI elements here:
                    ui.Button(
                        {
                            "ID": "RamsesButton",
                            "Text": "   Open Ramses Client",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {"File": "Scripts:/Comp/Ramses-Fusion/icons/ramses.png"}
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "SaveButton",
                            "Text": "   Save",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {"File": "Scripts:/Comp/Ramses-Fusion/icons/save.png"}
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "CommentButton",
                            "Text": "   Comment",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/comment.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "IncrementalSaveButton",
                            "Text": "   Incremental Save",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/incrementalSave.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "UpdateStatusButton",
                            "Text": "   Update Status/Publish",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/updateStatus.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "PreviewButton",
                            "Text": "   CreatePreview",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/preview.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "TemplateButton",
                            "Text": "   Save as Template",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/template.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "SetupSceneButton",
                            "Text": "   Setup Scene",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/setupScene.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "OpenButton",
                            "Text": "   Open",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {"File": "Scripts:/Comp/Ramses-Fusion/icons/open.png"}
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "RetrieveButton",
                            "Text": "   Retrieve Version",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/retrieveVersion.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "PubSettingsButton",
                            "Text": "   Publishing Settings",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/publishSettings.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "SettingsButton",
                            "Text": "   Settings",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/Settings.png"
                                }
                            ),
                        }
                    ),
                    ui.Button(
                        {
                            "ID": "AboutButton",
                            "Text": "   About",
                            "Flat": False,
                            "IconSize": [16, 16],
                            "MinimumSize": [16, 16],
                            "Margin": 1,
                            "Icon": ui.Icon(
                                {
                                    "File": "Scripts:/Comp/Ramses-Fusion/icons/Settings.png"
                                }
                            ),
                        }
                    ),
                    ui.Label(
                        {
                            "ID": "RamsesVersion",
                            "Text": "Ramses API version: " + SETTINGS.version,
                        }
                    ),
                ],
            ),
        ],
    )

    itm = dlg.GetItems()

    dlg.On.RamsesButton.Clicked = RunRamses
    dlg.On.SaveButton.Clicked = _func
    dlg.On.CommentButton.Clicked = _func
    dlg.On.IncrementalSaveButton.Clicked = _func
    dlg.On.UpdateStatusButton.Clicked = _func
    dlg.On.PreviewButton.Clicked = _func
    dlg.On.TemplateButton.Clicked = _func
    dlg.On.SetupSceneButton.Clicked = _func
    dlg.On.OpenButton.Clicked = _func
    dlg.On.RetrieveButton.Clicked = _func
    dlg.On.PubSettingsButton.Clicked = _func
    dlg.On.SettingsButton.Clicked = SettingsWindow
    dlg.On.AboutButton.Clicked = AboutWindow

    dlg.On.MainWin.Close = _func

    dlg.Show()
    disp.RunLoop()
    dlg.Hide()


def SettingsWindow(ev):
    dlg = disp.AddWindow(
        {
            "WindowTitle": "Ramses Settings",
            "ID": "SettingsWin",
            "Geometry": [200, 200, 550, 100],
        },
        [
            ui.VGroup(
                {
                    "Spacing": 5,
                },
                [
                    ui.HGroup(
                        {
                            "Spacing": 5,
                        },
                        [
                            ui.Label({"Text": "Ramses executable path:"}),
                            ui.LineEdit(
                                {
                                    "ID": "RamsesPathTxt",
                                    "Weight": 2,
                                    "Text": SETTINGS.ramsesClientPath,
                                    "PlaceholderText": "Path to Ramses.exe",
                                }
                            ),
                        ],
                    ),
                    ui.HGroup(
                        {
                            "Spacing": 0,
                        },
                        [
                            ui.Label({"Text": "Ramses client port:"}),
                            ui.LineEdit(
                                {
                                    "ID": "RamsesPortTxt",
                                    "Weight": 2,
                                    "Text": str(SETTINGS.ramsesClientPort),
                                    "PlaceholderText": "Port number",
                                }
                            ),
                        ],
                    ),
                    ui.HGroup(
                        {
                            "Spacing": 5,
                        },
                        [
                            ui.Button(
                                {
                                    "ID": "btnSaveSettings",
                                    "Text": "Save",
                                }
                            ),
                            ui.Button(
                                {
                                    "ID": "btnCloseSettings",
                                    "Text": "Close",
                                }
                            ),
                        ],
                    ),
                ],
            )
        ],
    )

    itm = dlg.GetItems()

    def SaveSettings(ev):
        SETTINGS.ramsesClientPort = int(itm["RamsesPortTxt"].Text)
        SETTINGS.ramsesClientPath = str(itm["RamsesPathTxt"].Text)
        SETTINGS.save()

    dlg.On.SettingsWin.Close = _func
    dlg.On.btnCloseSettings.Clicked = _func
    dlg.On.btnSaveSettings.Clicked = SaveSettings

    dlg.Show()
    disp.RunLoop()
    dlg.Hide()


def AboutWindow(ev):
    dlg = disp.AddWindow(
        {
            "WindowTitle": "About Ramses-Fusion",
            "ID": "AboutWin",
            "Geometry": [200, 200, 450, 200],
        },
        [
            ui.VGroup(
                {
                    "Spacing": 0,
                },
                [
                    ui.Label(
                        {
                            "ID": "Info",
                            "Text": "Ramses-Fusion was coded by Tobias Kummer for Overmind Studios. <p>Copyright &copy; 2024 Overmind Studios - Kummer & Gerhardt GbR.</p>",
                            "Alignment": [
                                {
                                    "AlignHCenter": True,
                                    "AlignTop": True,
                                }
                            ],
                            "WordWrap": True,
                            "OpenExternalLinks": True,
                        }
                    ),
                    ui.Label(
                        {
                            "ID": "URL",
                            "Text": 'Web: <a href="https://www.overmind-studios.de">Overmind Studios</a>',
                            "Alignment": [
                                {
                                    "AlignHCenter": True,
                                    "AlignTop": True,
                                }
                            ],
                            "WordWrap": True,
                            "OpenExternalLinks": True,
                        }
                    ),
                ],
            )
        ],
    )
    itm = dlg.GetItems()

    dlg.On.AboutButton2.Clicked = _func

    dlg.On.AboutWin.Close = _func

    dlg.Show()
    disp.RunLoop()
    dlg.Hide()


def RunRamses(ev):
    system('"' + SETTINGS.ramsesClientPath + '"')

def _func(ev):
    disp.ExitLoop()


print(SETTINGS.ramsesClientPort)
print(SETTINGS.ramsesClientPath)
for project in RAMSES.projects():
    print(project.framerate())

print(
    "Comp dependency: "
    + str(ram.RamProject.fromPath(comp.GetAttrs()["COMPS_FileName"]))
)
MainWindow()
