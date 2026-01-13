# -*- coding: utf-8 -*-
import os
import shutil
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType, RAMSES, RAM_SETTINGS

class FusionHost(RamHost):
    """
    Ramses Host implementation for Blackmagic Fusion.
    """
    def __init__(self, fusion_obj):
        super(FusionHost, self).__init__()
        self.fusion = fusion_obj
        self.hostName = "Fusion"
        
        try:
            self.hostVersion = str(self.fusion.GetAttrs().get('FUSION_Version', 'Unknown'))
        except:
            self.hostVersion = "Unknown"

    @property
    def comp(self):
        """Always get the currently active composition."""
        return self.fusion.GetCurrentComp()

    def currentFilePath(self) -> str:
        if not self.comp: return ""
        return self.comp.GetAttrs().get('COMPS_FileName', '')

    def _isDirty(self) -> bool:
        if not self.comp: return False
        return self.comp.GetAttrs().get('COMPB_Modified', False)

    def _log(self, message:str, level:int):
        print("[Ramses] " + str(message))

    def _saveAs(self, filePath:str, item:RamItem, step:RamStep, version:int, comment:str, incremented:bool) -> bool:
        if not self.comp: return False
        try:
            self.comp.Save(filePath)
            return True
        except Exception as e:
            self.log(f"Failed to save: {e}", LogLevel.Critical)
            return False

    def _open(self, filePath:str, item:RamItem, step:RamStep) -> bool:
        if os.path.exists(filePath):
            self.fusion.LoadComp(filePath)
            return True
        return False
    
    def _setFileName(self, fileName:str ) -> bool:
        if not self.comp: return False
        return self.comp.SetAttrs({'COMPS_FileName': fileName})

    # -------------------------------------------------------------------------
    # UI Implementation helpers using UIManager
    # -------------------------------------------------------------------------

    def _request_input(self, title, fields):
        """
        Custom helper to show a dialog using UIManager instead of AskUser.
        """
        ui = self.fusion.UIManager
        disp = bmd.UIDispatcher(ui)
        
        rows = []
        # Calculate height
        total_height = 80 # Buttons + Margins
        
        for f in fields:
            label = ui.Label({"Text": f['label'], "Weight": 0.25})
            if f['type'] == 'text':
                h = f.get('lines', 1) * 25 + 20
                ctrl = ui.TextEdit({"ID": f['id'], "Text": str(f.get('default', '')), "Weight": 0.75, "MinimumSize": [200, h]})
                total_height += h
            elif f['type'] == 'line':
                ctrl = ui.LineEdit({"ID": f['id'], "Text": str(f.get('default', '')), "Weight": 0.75})
                total_height += 30
            elif f['type'] == 'combo':
                ctrl = ui.ComboBox({"ID": f['id'], "Weight": 0.75})
                for k, v in sorted(f.get('options', {}).items()):
                    ctrl.AddItem(v)
                ctrl.CurrentIndex = int(f.get('default', 0))
                total_height += 30
            elif f['type'] == 'slider':
                ctrl = ui.Slider({"ID": f['id'], "Value": float(f.get('default', 50)), "Minimum": 0, "Maximum": 100, "Weight": 0.75})
                total_height += 30
            elif f['type'] == 'checkbox':
                ctrl = ui.CheckBox({"ID": f['id'], "Checked": bool(f.get('default', False)), "Text": "", "Weight": 0.75})
                total_height += 30
            
            rows.append(ui.HGroup([label, ctrl]))

        dlg = disp.AddWindow(
            {"WindowTitle": title, "ID": "CustomDlg", "Geometry": [400, 400, 500, total_height]},
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
            disp.ExitLoop()
            
        dlg.On.OkBtn.Clicked = on_ok
        dlg.On.CancelBtn.Clicked = lambda ev: disp.ExitLoop()
        dlg.On.CustomDlg.Close = lambda ev: disp.ExitLoop()
        
        dlg.Show()
        disp.RunLoop()
        dlg.Hide()
        
        return results if results else None

    # -------------------------------------------------------------------------
    # Pipeline Implementation
    # -------------------------------------------------------------------------

    def _import(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        if not self.comp: return False
        self.comp.Lock()
        for path in filePaths:
            self.comp.AddTool("Loader", -32768, -32768, {"Clip": path})
        self.comp.Unlock()
        return True

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        path = self.fusion.RequestFile()
        return {'filePaths': [path]} if path else None

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        path = self.fusion.RequestFile()
        return {'filePath': path} if path else None

    def _preview(self, previewFolderPath:str, previewFileBaseName:str, item:RamItem, step:RamStep) -> list:
        return []

    def _publish(self, publishInfo:RamFileInfo, publishOptions:dict) -> list:
        src = self.currentFilePath()
        if not src or not os.path.exists(src): return []
        dst = publishInfo.filePath()
        try:
            shutil.copy2(src, dst)
            return [dst]
        except Exception as e:
            self.log(f"Publish failed: {e}", LogLevel.Critical)
            return []

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        res = self._openUI(item, step)
        if res: return {"filePaths": [res["filePath"]]}
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        if not versionFiles: return ""
        opts = {str(i): os.path.basename(f) for i, f in enumerate(versionFiles)}
        res = self._request_input("Restore Version", [
            {'id': 'Idx', 'label': 'Version:', 'type': 'combo', 'options': opts}
        ])
        return versionFiles[res['Idx']] if res else ""

    def _saveAsUI(self) -> dict:
        path = self.fusion.RequestFile()
        if not path: return None
        nm = RamFileInfo(); nm.setFilePath(path)
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        step = RamStep.fromPath(path)
        if not item: item = RamItem(data={'name': 'New', 'shortName': 'New'}, create=False)
        if not step: step = RamStep(data={'name': 'New', 'shortName': 'New'}, create=False)
        return {'item': item, 'step': step, 'extension': os.path.splitext(path)[1].lstrip('.'), 'resource': nm.resource}

    def _saveChangesUI(self) -> str:
        res = self._request_input("Save Changes?", [
            {'id': 'Msg', 'label': '', 'type': 'line', 'default': 'Save current composition? (OK to save, Cancel to discard)'}
        ])
        return "save" if res else "discard"

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        if not self.comp: return False
        project = RAMSES.project()
        if not project: return False
        fps = project.framerate()
        duration = item.duration() if (item and item.itemType() == ItemType.SHOT) else 5.0
        total_frames = int(duration * fps)
        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1
        self.comp.SetPrefs("Comp.FrameFormat.Rate", fps)
        self.comp.SetAttrs({"COMPN_GlobalStart": float(start), "COMPN_GlobalEnd": float(end), "COMPN_RenderStart": float(start), "COMPN_RenderEnd": float(end)})
        self.log(f"Setup applied: Start {start}, Duration {total_frames}", LogLevel.Info)
        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        states = RAMSES.states()
        if not states: return None
        state_opts = {str(i): s.name() for i, s in enumerate(states)}
        
        cur_comment = currentStatus.comment() if currentStatus else ""
        cur_ratio = currentStatus.completionRatio() if currentStatus else 50
        cur_short = currentStatus.state().shortName() if currentStatus else "WIP"
        def_idx = next((i for i, s in enumerate(states) if s.shortName() == cur_short), 0)

        res = self._request_input("Update Status", [
            {'id': 'Comment', 'label': 'Comment:', 'type': 'text', 'default': cur_comment, 'lines': 6},
            {'id': 'State', 'label': 'State:', 'type': 'combo', 'options': state_opts, 'default': def_idx},
            {'id': 'Ratio', 'label': 'Ratio (%):', 'type': 'slider', 'default': cur_ratio},
            {'id': 'Publish', 'label': 'Publish:', 'type': 'checkbox', 'default': False}
        ])
        
        if not res: return None
        
        selected_state = states[res['State']]
        self.log(f"UI selected state: {selected_state.name()} ({selected_state.shortName()})", LogLevel.Debug)
        
        return {
            "comment": res['Comment'], 
            "completionRatio": int(res['Ratio']), 
            "publish": res['Publish'], 
            "state": selected_state, 
            "showPublishUI": False, 
            "savePreview": False
        }