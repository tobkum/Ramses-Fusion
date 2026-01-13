# -*- coding: utf-8 -*-
import os
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType

class FusionHost(RamHost):
    """
    Ramses Host implementation for Blackmagic Fusion.
    """
    def __init__(self, fusion):
        super(FusionHost, self).__init__()
        self.fusion = fusion
        self.hostName = "Fusion"
        # Try to get version if possible
        try:
            self.hostVersion = str(self.fusion.GetAttrs().get('FUSION_Version', 'Unknown'))
        except:
            self.hostVersion = "Unknown"

    @property
    def comp(self):
        """Always get the currently active composition."""
        return self.fusion.GetCurrentComp()

    def currentFilePath(self) -> str:
        if not self.comp:
            return ""
        attrs = self.comp.GetAttrs()
        filename = attrs.get('COMPS_FileName', '')
        if filename:
            return filename
        return ""

    def _isDirty(self) -> bool:
        if not self.comp:
            return False
        return self.comp.GetAttrs().get('COMPB_Modified', False)

    def _log(self, message:str, level:int):
        # Print to Fusion Console
        print("[Ramses] " + str(message))

    def _saveAs(self, filePath:str, item:RamItem, step:RamStep, version:int, comment:str, incremented:bool) -> bool:
        if not self.comp:
            return False
        try:
            self.comp.Save(filePath)
            return True
        except Exception as e:
            self.log("Failed to save file: " + str(e), LogLevel.Critical)
            return False

    def _open(self, filePath:str, item:RamItem, step:RamStep) -> bool:
        if os.path.exists(filePath):
            self.fusion.LoadComp(filePath)
            return True
        return False
    
    def _setFileName(self, fileName:str ) -> bool:
        if self.comp:
            self.comp.SetAttrs({'COMPS_FileName': fileName})
            return True
        return False

    # -------------------------------------------------------------------------
    # UI Implementation
    # -------------------------------------------------------------------------

    def _import(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        # Basic import: Loaders
        if not self.comp:
            return False
        
        self.comp.Lock()
        for path in filePaths:
            self.comp.AddTool("Loader", -32768, -32768, {"Clip": path})
        self.comp.Unlock()
        return True

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        # Use Fusion File Request
        path = self.fusion.RequestFile(
            "", 
            "", 
            {"FReqB_SeqGather": True, "FReqS_Title": "Import File"}
        )
        if not path:
            return None
        
        return {'filePaths': [path]}

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        # Use Fusion File Request
        path = self.fusion.RequestFile(
            "", 
            "", 
            {"FReqB_SeqGather": True, "FReqS_Title": "Open Composition"}
        )
        if not path:
            return None

        return {'filePath': path}

    def _preview(self, previewFolderPath:str, previewFileBaseName:str, item:RamItem, step:RamStep) -> list:
        # TODO: Implement Render Node creation and render
        self.log("Preview generation not fully implemented. Please render manually to: " + previewFolderPath, LogLevel.Warning)
        return []

    def _prePublish(self, publishInfo:RamFileInfo, publishOptions:dict) -> dict:
        return publishOptions

    def _publish(self, publishInfo:RamFileInfo, publishOptions:dict) -> list:
        # In Fusion, publishing usually means rendering or saving a clean comp
        # For now, we will assume we are publishing the Comp file itself
        src = self.currentFilePath()
        dst = publishInfo.filePath()
        
        import shutil
        try:
            shutil.copy2(src, dst)
            return [dst]
        except Exception as e:
            self.log(f"Publish failed: {e}", LogLevel.Critical)
            return []

    def _publishOptions(self, proposedOptions:dict,  showPublishUI:bool=False) -> dict:
        return proposedOptions

    def _replace(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        # Difficult to implement generic replace in Fusion without context (which node?)
        return False

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        # Simple dropdown input dialog
        # Fusion Input dialogs are limited, we'll try to list the top 10
        
        # Format for Fusion AskUser: {'Name': 'Input', ...}
        # It's hard to make a dynamic dropdown list in pure scripts without UIDispatcher logic inside Host.
        # Since Host should be UI agnostic (abstract), we usually return the path.
        # For this example, we just take the previous one or fail.
        if not versionFiles:
            return ""
        
        # Ideally: Show a Window. For now, we return the first one (latest previous)
        return versionFiles[0]

    def _saveAsUI(self) -> dict:
        path = self.fusion.RequestFile(
            "", 
            "", 
            {"FReqB_Save": True, "FReqS_Title": "Save Ramses File"}
        )
        
        if not path:
            return None

        # Create virtual items based on the path selected by the user
        # This allows saving anywhere, even if it's not strictly a Ramses structure yet
        # (The API will handle folder structure if the path allows it)
        
        # Create a virtual item/step from the path to satisfy the API return requirement
        nm = RamFileInfo()
        nm.setFilePath(path)
        
        # If the user picked a random path, these might be empty. 
        # The API requires an Item and Step object.
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        step = RamStep.fromPath(path)
        
        # Fallback if path is not a valid Ramses path
        if not item:
            item = RamItem(data={'name': 'New Item', 'shortName': 'New'}, create=False)
        if not step:
            step = RamStep(data={'name': 'New Step', 'shortName': 'New'}, create=False)
            
        ext = os.path.splitext(path)[1].lstrip('.')
        
        return {
            'item': item,
            'step': step,
            'extension': ext,
            'resource': nm.resource
        }

    def _saveChangesUI(self) -> bool:
        # Fusion usually asks automatically on Close, but here we are checking logic.
        # We can try to use AskUser
        res = self.fusion.AskUser("Save Changes?", {"1": {"Name": "Save Changes", "Type": "Text", "Readonly": True, "Lines": 1}})
        # AskUser is limited. Let's assume 'save'
        return 'save'

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        if not self.comp:
            return False
            
        width = setupOptions.get('width', 1920)
        height = setupOptions.get('height', 1080)
        fps = setupOptions.get('framerate', 24.0)
        
        attrs = {
            "COMPN_GlobalStart": 0,
            "COMPN_GlobalEnd": int(setupOptions.get('duration', 0) * fps),
            "COMPS_Name": item.name() if item else "Untitled"
        }
        
        # Set preferences (Prefs are nested, simplified here)
        self.comp.SetPrefs("Comp.FrameFormat.Width", width)
        self.comp.SetPrefs("Comp.FrameFormat.Height", height)
        self.comp.SetPrefs("Comp.FrameFormat.Rate", fps)
        
        self.comp.SetAttrs(attrs)
        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        # Simple input for comment
        ui = self.fusion.UIManager
        disp = self.fusion.UIDispatcher(ui)
        
        # We need to return a dict, so we might need a small blocking window here.
        # However, running a UIDispatcher Loop inside another might be tricky if not careful.
        # For simplicity in this script, we'll return default values.
        
        return {
            "comment": "Updated via Fusion",
            "completionRatio": 50,
            "publish": False
        }

