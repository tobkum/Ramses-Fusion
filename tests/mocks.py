# mocks.py
import os
from unittest.mock import MagicMock

class MockTool:
    def __init__(self, name, attrs=None):
        self.Name = name
        self.attrs = attrs or {}
        # Simulate inputs as a dictionary
        self.Input = {}  
        # Attributes are stored here
        self.TileColor = {}
        self.Comments = {}
        self.Clip = {}
        # GlobalIn/Out
        self.GlobalIn = {}
        self.GlobalOut = {}

    def __setattr__(self, name, value):
        if name in ["TileColor", "Comments", "Clip", "GlobalIn", "GlobalOut"]:
            if isinstance(value, dict):
                # If setting a dict directly, we wrap it to behave like a Fusion object
                # but for simplicity in mocks we just store it
                self.__dict__[name] = value
            else:
                self.__dict__[name] = value
        else:
            super().__setattr__(name, value)


    def SetAttrs(self, attrs):
        self.attrs.update(attrs)
        # Update Name if TOOLS_Name is set
        if "TOOLS_Name" in attrs:
            self.Name = attrs["TOOLS_Name"]
        return True

    def GetAttrs(self):
        # Merge internal attrs with mandatory ID for some checks
        base = self.attrs.copy()
        if "TOOLS_Name" not in base:
            base["TOOLS_Name"] = self.Name
        # Default reg ID if not set
        if "TOOLS_RegID" not in base:
            if "Loader" in self.Name:
                base["TOOLS_RegID"] = "Loader"
            elif "Saver" in self.Name:
                base["TOOLS_RegID"] = "Saver"
        return base
        
    def SetInput(self, name, value, time=0):
        self.Input[name] = value
        
    def GetInput(self, name, time=0):
        return self.Input.get(name)

    def FindMainInput(self, index):
        # Mock connection checking - return cached input or create new one
        if not hasattr(self, '_main_input'):
            self._main_input = MockInput(self, connected=False)
        return self._main_input

    def connect_input(self):
        """Test helper to simulate a connected input."""
        if not hasattr(self, '_main_input'):
            self._main_input = MockInput(self, connected=True)
        else:
            self._main_input.connect()

    def disconnect_input(self):
        """Test helper to simulate a disconnected input."""
        if hasattr(self, '_main_input'):
            self._main_input.disconnect()

class MockInput:
    def __init__(self, owner, connected=False):
        self.owner = owner
        self.connected_output = MagicMock(name="ConnectedOutput") if connected else None

    def GetConnectedOutput(self):
        return self.connected_output

    def connect(self):
        """Test helper to simulate a connected input."""
        self.connected_output = MagicMock(name="ConnectedOutput")

    def disconnect(self):
        """Test helper to simulate a disconnected input."""
        self.connected_output = None

class MockFlowView:
    def GetPosTable(self, tool):
        # Returns {1.0: x, 2.0: y}
        return {1.0: 10, 2.0: 20}

class MockFrame:
    def __init__(self):
        self.FlowView = MockFlowView()

class MockComp:
    def __init__(self):
        self.tools = {}
        self.attrs = {
            "COMPS_FileName": "D:/Projects/Test/TEST_S_Shot01_COMP_v001.comp",
            "COMPB_Modified": False,
            "COMPN_GlobalStart": 1001.0,
            "COMPN_GlobalEnd": 1100.0,
            "COMPN_RenderStart": 1001.0,
            "COMPN_RenderEnd": 1100.0
        }
        self.prefs = {
            "Comp.FrameFormat.Width": 1920,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0,
            "Comp.FrameFormat.AspectX": 1.0,
            "Comp.FrameFormat.AspectY": 1.0
        }
        self.metadata = {}
        self.ActiveTool = None
        self.CurrentFrame = MockFrame()
        self.locked = False
        self._modified = False

    @property
    def Modified(self):
        """Track whether the comp has been modified."""
        return self._modified

    @Modified.setter
    def Modified(self, value):
        """Allow explicitly setting Modified flag (e.g., for test reset)."""
        self._modified = value

    def GetAttrs(self):
        return self.attrs

    def SetAttrs(self, attrs):
        self.attrs.update(attrs)
        self._modified = True  # Mark as dirty when attrs change
        return True

    def GetPrefs(self, pref_name=""):
        if pref_name == "Comp.FrameFormat":
            # Flattened structure logic for simplicity
            return {
                "Width": self.prefs.get("Comp.FrameFormat.Width"),
                "Height": self.prefs.get("Comp.FrameFormat.Height"),
                "Rate": self.prefs.get("Comp.FrameFormat.Rate"),
                "AspectX": self.prefs.get("Comp.FrameFormat.AspectX"),
                "AspectY": self.prefs.get("Comp.FrameFormat.AspectY")
            }
        return self.prefs

    def SetPrefs(self, prefs):
        self.prefs.update(prefs)
        self._modified = True  # Mark as dirty when prefs change

    def FindTool(self, name):
        # Fusion's FindTool usually searches by the node's Name attribute
        for tool in self.tools.values():
            if tool.Name == name:
                return tool
        return None

    def AddTool(self, type_name, x, y):
        # Simulate creating a tool
        # Ensure unique name
        base_name = type_name
        counter = 1
        while base_name in self.tools:
            base_name = f"{type_name}{counter}"
            counter += 1
            
        tool = MockTool(base_name)
        self.tools[base_name] = tool
        return tool

    def Save(self, path):
        # Record save action
        self.attrs["COMPS_FileName"] = path.replace("\\", "/")
        self.attrs["COMPB_Modified"] = False
        return True
        
    def Render(self, wait=True):
        # Mock success
        return True
        
    def Lock(self):
        self.locked = True
        
    def Unlock(self):
        self.locked = False
        
    def GetData(self, key):
        return self.metadata.get(key)

    def SetData(self, key, value):
        # Only mark as dirty if the value actually changes
        if self.metadata.get(key) != value:
            self.metadata[key] = value
            self._modified = True

class MockUIManager:
    # Minimal mock for UIManager
    def __init__(self):
        self.Button = MagicMock(side_effect=lambda attrs: MagicMock(name=f"Button_{attrs.get('ID', 'btn')}", **attrs))
        self.Label = MagicMock(side_effect=lambda attrs: MagicMock(name="Label", **attrs))

    def AddWindow(self, *args): return MagicMock(name="Dialog")
    def HGroup(self, *args): return MagicMock(name="HGroup")
    def VGroup(self, *args): return MagicMock(name="VGroup")
    def HGap(self, *args): return MagicMock(name="HGap")
    def VGap(self, *args): return MagicMock(name="VGap")
    def LineEdit(self, attrs): return MagicMock(name="LineEdit")
    def TextEdit(self, attrs): return MagicMock(name="TextEdit")
    def ComboBox(self, attrs): return MagicMock(name="ComboBox")
    def Slider(self, attrs): return MagicMock(name="Slider")
    def CheckBox(self, attrs): return MagicMock(name="CheckBox")
    def Font(self, attrs): return MagicMock(name="Font")
    def Icon(self, attrs): return MagicMock(name="Icon")

class MockFusion:
    def __init__(self):
        self._comp = MockComp()
        self.UIManager = MockUIManager()

    def GetCurrentComp(self):
        return self._comp
    
    def GetAttrs(self):
        return {'FUSION_Version': '18.5 (Mock)'}
        
    def LoadComp(self, path):
        # Simulate opening
        self._comp.attrs["COMPS_FileName"] = path.replace("\\", "/")
        return self._comp
        
    def RequestFile(self):
        return "D:/Requested/File.comp"
