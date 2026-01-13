# -*- coding: utf-8 -*-
import os
import shutil
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType, RAMSES, RAM_SETTINGS

class FusionHost(RamHost):
    """
    Ramses Host implementation for Blackmagic Fusion.
    """
    def __init__(self, fusion):
        super(FusionHost, self).__init__()
        self.fusion = fusion
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
    # UI & Pipeline Implementation
    # -------------------------------------------------------------------------

    def _import(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        if not self.comp: return False
        self.comp.Lock()
        for path in filePaths:
            self.comp.AddTool("Loader", -32768, -32768, {"Clip": path})
        self.comp.Unlock()
        self.log(f"Imported {len(filePaths)} item(s).", LogLevel.Info)
        return True

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        path = self.fusion.RequestFile("", {"FReqB_SeqGather": 1, "FReqS_Title": "Import File"})
        return {'filePaths': [path]} if path else None

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        path = self.fusion.RequestFile("", {"FReqS_Title": "Open Composition", "FReqS_Filter": "Fusion Comp (*.comp)|*.comp"})
        return {'filePath': path} if path else None

    def _preview(self, previewFolderPath:str, previewFileBaseName:str, item:RamItem, step:RamStep) -> list:
        if not self.comp: return []
        # Basic implementation: Save a screenshot of the current frame
        if not os.path.exists(previewFolderPath): os.makedirs(previewFolderPath)
        preview_path = os.path.join(previewFolderPath, previewFileBaseName + ".png")
        
        # In Fusion, Render is the proper way, but for a quick "Preview", 
        # we can try to save the current viewer image if possible.
        # Minimal fallback: Warn user.
        self.log(f"Preview should be rendered to: {preview_path}", LogLevel.Warning)
        return []

    def _prePublish(self, publishInfo:RamFileInfo, publishOptions:dict) -> dict:
        return publishOptions

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

    def _publishOptions(self, proposedOptions:dict,  showPublishUI:bool=False) -> dict:
        return proposedOptions

    def _replace(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        if not self.comp or not filePaths: return False
        new_path = filePaths[0]
        selected_tools = self.comp.GetToolList(True).values()
        replaced_count = 0
        self.comp.Lock()
        for tool in selected_tools:
            if tool.ID == "Loader":
                tool.Clip[self.comp.CurrentTime] = new_path
                replaced_count += 1
        self.comp.Unlock()
        if replaced_count > 0:
            self.log(f"Replaced source in {replaced_count} Loader(s).", LogLevel.Info)
            return True
        return False

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        # Reuse Open logic for picking the replacement
        res = self._openUI(item, step)
        if res:
            return {"filePaths": [res["filePath"]]}
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        if not versionFiles: return ""
        # Simple selection via Fusion
        opts = {str(i): os.path.basename(f) for i, f in enumerate(versionFiles)}
        ret = self.fusion.AskUser("Restore Version", {"Idx": {"Name": "Version", "Type": "Combo", "Options": opts, "Default": 0.0}})
        return versionFiles[int(ret["Idx"])] if ret else ""

    def _saveAsUI(self) -> dict:
        path = self.fusion.RequestFile("untitled.comp", "", {"FReqB_Save": 1, "FReqS_Title": "Save Ramses File", "FReqS_Filter": "Fusion Comp (*.comp)|*.comp"})
        if not path: return None
        nm = RamFileInfo()
        nm.setFilePath(path)
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        step = RamStep.fromPath(path)
        if not item: item = RamItem(data={'name': 'New Item', 'shortName': 'New'}, create=False)
        if not step: step = RamStep(data={'name': 'New Step', 'shortName': 'New'}, create=False)
        return {'item': item, 'step': step, 'extension': os.path.splitext(path)[1].lstrip('.'), 'resource': nm.resource}

    def _saveChangesUI(self) -> str:
        if not self.comp: return "discard"
        res = self.fusion.AskUser("Save Changes?", {"M": {"Name": "Scene Modified", "Type": "Text", "ReadOnly": True, "Default": "Do you want to save your current composition?", "Lines": 2}})
        return "save" if res else "cancel"

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        if not self.comp: return False
        project = RAMSES.project()
        if not project: return False
        
        width = project.width()
        height = project.height()
        fps = project.framerate()
        duration = item.duration() if (item and item.itemType() == ItemType.SHOT) else 5.0
        
        total_frames = int(duration * fps)
        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1
        
        self.comp.SetPrefs("Comp.FrameFormat.Width", width)
        self.comp.SetPrefs("Comp.FrameFormat.Height", height)
        self.comp.SetPrefs("Comp.FrameFormat.Rate", fps)
        self.comp.SetAttrs({"COMPN_GlobalStart": float(start), "COMPN_GlobalEnd": float(end), "COMPN_RenderStart": float(start), "COMPN_RenderEnd": float(end)})
        
        self.log(f"Setup: {width}x{height} @ {fps}fps, Range: {start}-{end}", LogLevel.Info)
        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        states = RAMSES.states()
        if not states: return None
        state_opts = {str(i): s.name() for i, s in enumerate(states)}
        cur_short = currentStatus.state().shortName() if currentStatus else "WIP"
        def_idx = next((i for i, s in enumerate(states) if s.shortName() == cur_short), 0)

        dialog = {
            "Comment": {"Name": "Comment", "Type": "Text", "Default": currentStatus.comment() if currentStatus else "", "Lines": 3},
            "State": {"Name": "State", "Type": "Combo", "Options": state_opts, "Default": float(def_idx)},
            "Ratio": {"Name": "Completion (%)", "Type": "Slider", "Default": float(currentStatus.completionRatio()) if currentStatus else 50.0, "Integer": True, "Min": 0, "Max": 100},
            "Publish": {"Name": "Publish Now", "Type": "Checkbox", "Default": 0.0}
        }
        ret = self.fusion.AskUser("Update Status", dialog)
        if not ret: return None
        return {"comment": ret.get("Comment", ""), "completionRatio": int(ret.get("Ratio", 50)), "publish": bool(ret.get("Publish", False)), "state": states[int(ret.get("State", 0))], "showPublishUI": False, "savePreview": False}