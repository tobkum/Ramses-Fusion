import ramses as ram

ui = fu.UIManager
disp = bmd.UIDispatcher(ui)

dlg = disp.AddWindow(
    {
        "WindowTitle": "Overmind Studios Ramses Toolbox",
        "ID": "MainWin",
        "Geometry": [200, 200, 250, 350],
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
                            {"File": "Scripts:/Comp/Overmind Studios/icons/ramses.png"}
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
                            {"File": "Scripts:/Comp/Overmind Studios/icons/save.png"}
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
                            {"File": "Scripts:/Comp/Overmind Studios/icons/comment.png"}
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/incrementalSave.png"
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/updateStatus.png"
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
                            {"File": "Scripts:/Comp/Overmind Studios/icons/preview.png"}
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/template.png"
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/setupScene.png"
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
                            {"File": "Scripts:/Comp/Overmind Studios/icons/open.png"}
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/retrieveVersion.png"
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/publishSettings.png"
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
                                "File": "Scripts:/Comp/Overmind Studios/icons/Settings.png"
                            }
                        ),
                    }
                ),
            ],
        ),
    ],
)

itm = dlg.GetItems()


# The window was closed
def _func(ev):
    disp.ExitLoop()


dlg.On.RamsesButton.Clicked = _func
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
dlg.On.SettingsButton.Clicked = _func


dlg.On.MainWin.Close = _func

# Add your GUI element based event functions here:

dlg.Show()
disp.RunLoop()
dlg.Hide()
