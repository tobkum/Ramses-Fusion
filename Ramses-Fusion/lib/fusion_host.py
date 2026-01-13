# -*- coding: utf-8 -*-
import os
from ramses import RamHost, RamItem, RamStep, RamStatus, RamFileInfo, LogLevel, ItemType, RAMSES

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
        if not self.comp:
            return False
        
        self.comp.Lock()
        for path in filePaths:
            self.comp.AddTool("Loader", -32768, -32768, {"Clip": path})
        self.comp.Unlock()
        
        self.log(f"Imported {len(filePaths)} item(s).", LogLevel.Info)
        return True

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        # Use Fusion File Request
        path = self.fusion.RequestFile(
            "", 
            {
                "FReqB_SeqGather": 1, 
                "FReqS_Title": "Import File",
                "FReqS_Filter": "All Files (*.*)|*.*"
            }
        )
        if not path:
            return None
        
        return {'filePaths': [path]}

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        # Use Fusion File Request
        path = self.fusion.RequestFile(
            "", 
            {
                "FReqB_SeqGather": 1, 
                "FReqS_Title": "Open Composition",
                "FReqS_Filter": "Fusion Comp (*.comp)|*.comp"
            }
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
        if not self.comp:
            return False
            
        if not filePaths:
            return False
            
        new_path = filePaths[0]
        selected_tools = self.comp.GetToolList(True).values()
        
        if not selected_tools:
            self.log("No tools selected to replace.", LogLevel.Warning)
            return False

        replaced_count = 0
        
        self.comp.Lock()
        for tool in selected_tools:
            # Check if tool has "Clip" input by trying to set it
            if tool.ID == "Loader":
                tool.Clip[self.comp.CurrentTime] = new_path
                replaced_count += 1
            else:
                pass
                
        self.comp.Unlock()
        
        if replaced_count > 0:
            self.log(f"Replaced source in {replaced_count} Loader(s) with {os.path.basename(new_path)}.", LogLevel.Info)
            return True
        else:
            self.log("No compatible Loader node selected.", LogLevel.Warning)
            return False

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        return None

    def _restoreVersionUI(self, versionFiles:list) -> str:
        # Format for Fusion AskUser: {'Name': 'Input', ...}
        if not versionFiles:
            return ""
        # For now, we return the first one (latest previous)
        return versionFiles[0]

    def _saveAsUI(self) -> dict:
        self._log("Opening Save As Dialog...", LogLevel.Debug)
        
        # Corrected signature: RequestFile(filename, attrs_dict)
        path = self.fusion.RequestFile(
            "untitled.comp", 
            "",
            {
                "FReqB_Save": 1,
                "FReqB_SeqGather": 0,
                "FReqS_Title": "Save Ramses File",
                "FReqS_Filter": "Fusion Comp (*.comp)|*.comp"
            }
        )
        
        if not path:
            return None

        # Create virtual items based on the path selected by the user
        nm = RamFileInfo()
        nm.setFilePath(path)
        
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        step = RamStep.fromPath(path)
        
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
        res = self.fusion.AskUser("Save Changes?", {"1": {"Name": "Save Changes", "Type": "Text", "Readonly": True, "Lines": 1}})
        return 'save'

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        if not self.comp:
            return False
            
        # Re-collect settings directly from Ramses objects to bypass API bugs
        project = RAMSES.project()
        if not project:
            self.log("No current project found in Ramses.", LogLevel.Warning)
            return False
            
        width = project.width()
        height = project.height()
        fps = project.framerate()
        duration = 0.0
        
        if item:
            if item.itemType() == ItemType.SHOT:
                duration = item.duration()
                seq = item.sequence()
                if seq:
                    width = seq.width()
                    height = seq.height()
                    fps = seq.framerate()
            elif item.itemType() == ItemType.ASSET:
                # Use project defaults for assets
                pass

        total_frames = int(duration * fps)
        if total_frames <= 0:
            total_frames = 100 # Fallback default
            
        start = SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1
        
        # Fusion attributes for frame range
        attrs = {
            "COMPN_GlobalStart": float(start),
            "COMPN_GlobalEnd": float(end),
            "COMPN_RenderStart": float(start),
            "COMPN_RenderEnd": float(end),
            "COMPS_Name": item.name() if item else "Untitled"
        }
        
        # Set preferences for resolution and FPS
        self.comp.SetPrefs("Comp.FrameFormat.Width", width)
        self.comp.SetPrefs("Comp.FrameFormat.Height", height)
        self.comp.SetPrefs("Comp.FrameFormat.Rate", fps)
        
        # Apply attributes
        self.comp.SetAttrs(attrs)
        
        self.log(f"Scene Setup Complete: {width}x{height} @ {fps}fps, Range: {start}-{end} ({total_frames} frames)", LogLevel.Info)
        return True

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        # Get states from Ramses
        states = RAMSES.states()
        state_options = {}
        state_list = []
        
        # Default index
        default_state_idx = 0
        current_state_short = ""
        if currentStatus:
            current_state_short = currentStatus.state().shortName()

        for i, s in enumerate(states):
            state_options[str(i)] = s.name()
            state_list.append(s)
            if s.shortName() == current_state_short:
                default_state_idx = i
            elif s.shortName() == "WIP" and not current_state_short:
                default_state_idx = i

        # Define the dialog
        dialog = {
            "Comment": {
                "Name": "Comment",
                "Type": "Text",
                "Default": currentStatus.comment() if currentStatus else "",
                "Lines": 3
            },
            "State": {
                "Name": "State",
                "Type": "Combo",
                "Options": state_options,
                "Default": float(default_state_idx)
            },
            "Ratio": {
                "Name": "Completion Ratio (%)",
                "Type": "Slider",
                "Default": float(currentStatus.completionRatio()) if currentStatus else 50.0,
                "Integer": True,
                "Min": 0,
                "Max": 100
            },
            "Publish": {
                "Name": "Publish Version",
                "Type": "Checkbox",
                "Default": 0.0
            }
        }

        ret = self.fusion.AskUser("Update Status", dialog)
        
        if not ret:
            return None
            
        # Map selected index back to state object
        selected_state_idx = int(ret.get("State", 0))
        selected_state = state_list[selected_state_idx]
        
        return {
            "comment": ret.get("Comment", ""),
            "completionRatio": int(ret.get("Ratio", 50)),
            "publish": bool(ret.get("Publish", False)),
            "state": selected_state,
            "showPublishUI": False,
            "savePreview": False
        }
