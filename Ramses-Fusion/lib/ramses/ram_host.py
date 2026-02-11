"""! @brief
    The RamHost class
    This is an abstract class to be reimplemented by Ramses Add-ons.
    It is an abstraction layer for accessing DCC apps useful functions and propreties
    like saving files, getting the current file path, the version of the app, etc.

    The RamHost class corresponding to the environment running the Ramses Python API
    should be availabe as Ramses.host() if the Ramses Add-on implementation is correct.

    See the example scripts for default implementations of several DCC apps.

    See the official Ramses Add-ons as examples
    of a complete implementation of the RamHost and the Ramses API in DCC apps.
 @file ram_host.py
 @section authors Author(s)
  - Created by Nicolas Dufresne on 10/15/2024 .
 @license GNU-GPLv3
 @copyright (c) 2025 Nicolas Dufresne and contributors
"""

#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#======================= END GPL LICENSE BLOCK ========================

import os
from datetime import datetime, timedelta
import tempfile
import yaml
from .ram_step import RamStep
from .ram_item import RamItem
from .ram_status import RamStatus
from .constants import LogLevel, Log, FolderNames, ItemType
from .file_manager import RamFileManager
from .file_info import RamFileInfo
from .metadata_manager import RamMetaDataManager
from .utils import load_module_from_path
from .ram_settings import RamSettings
from .ramses import Ramses
from .ram_state import RamState
from .utils import checkUpdate

SETTINGS = RamSettings.instance()
RAMSES = Ramses.instance()
DAEMON = RAMSES.daemonInterface()

class RamHost(object):
    """!
    @brief The RamHost class is an abstract class to be reimplemented by Ramses Add-ons.
    It is an abstraction layer for accessing DCC apps useful functions and propreties
    like saving files, getting the current file path, the version of the app, etc.

    The RamHost class corresponding to the environment running the Ramses Python API
    should be availabe as Ramses.host() if the Ramses Add-on implementation is correct.

    See the example scripts for default implementations of several DCC apps.

    See the official Ramses Add-ons as examples
    of a complete implementation of the RamHost and the Ramses API in DCC apps.
    """

    # The name of the addon
    name = "Ramses Add-on"
    # The name of the vendor/Author
    vendorName = "Ramses"
    # The version of the addon / Should be the same as the version of the Ramses app!
    version = "0.0.0"
    # Current language code of the addon
    language = "en"
    # The name of the host app
    hostName = "Host Name"
    # The version of the host app
    hostVersion = "0.0.0"
    # Is this a prerelease (e.g. Beta) version?
    preRelease = True
    # The URL to the add-on documentation
    helpURL = "https://ramses.rxlab.guide/components/addons"
    # The URL to check for addon update
    updateURL = "http://api2.rxlab.io/tools/check"

    # ======== Pure Virtual (Abstract) Methods ========
    # These methods must be reimplemented by subclasses

    # ____ Public ____

    def currentFilePath(self) -> str:
        """!
        @brief Gets the current working file path

        @return str => The file path or an empty string if it is not set.
        """
        raise NotImplementedError()

    # ____ Protected ____

    def _import(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        """!
        @brief Imports an item in the current file

        Parameters : 
            @param filePaths : list => The published file paths (str) to be imported
            @param item : RamItem => The item being imported
            @param step : RamStep => The step being imported
            @param importOptions : list => The list of import options (dict).
            An empty dict (or missing key) means "Use default values".
            If this is not an empty list, can import without any UI/Dialog.
            @param forceShowImportUI : bool => Wether to show the import settings dialog even if some import options are provided
        Returns : 
            @return bool => Success

        """
        raise NotImplementedError()

    def _importUI(self, item:RamItem, step:RamStep) -> dict:
        """!
        @brief Shows the UI to select an item to import.

        Parameters : 
            @param item : RamItem => The item to pre-select
            @param step : RamStep => The step to pre-select
        Returns : 
            @return dict => A dict containing at least { "item":RamItem, "step":RamStep } or { "filePaths":list }.
            Returns None if the user cancels.
            All other keys are optionnal, the complete dict can be:
            {
                "item":RamItem,
                "step":RamStep,
                "filePaths":list,
                "showImportUI":False
            }
        """
        raise NotImplementedError()

    def _isDirty(self) -> bool:
        """!
        @brief Checks if the current file needs to be saved before it is closed
        or before another one is opened

        Returns : 
            @return bool => True if the file is not saved
        """
        raise NotImplementedError()

    def _log(self, message:str, level:int):
        """!
        @brief Prints (or shows, or saves, or sends...) a log message.

        Parameters : 
            @param message : str => The message
            @param level : int => The log level, one of the LogLevel enum.
        """

    def _open(self, filePath:str, item:RamItem, step:RamStep) -> bool:
        """!
        @brief Opens the given file.
        This function may show a warning if the current file has to be saved,
        and call save() to save it.

        Parameters : 
            @param filePath : str => The file to open
            @param item : RamItem => The item being opened (may be None)
            @param step : RamStep => The step being opened (may be None)
        Returns:
            @return bool => Success
        """
        raise NotImplementedError()

    def _openUI(self, item:RamItem=None, step:RamStep=None) -> dict:
        """!
        @brief Shows the UI to select an item to open.

        Parameters : 
            @param item : RamItem = None => The item to pre-select
            @param step : RamStep = None => The step to pre-select
        Returns : 
            @return dict => A dict containing at least { "item":RamItem, "step":RamStep } or { "filePath":str }.
            Returns None if the user cancels.
            All other keys are optionnal, the complete dict can be:
            {
                "item":RamItem,
                "step":RamStep,
                "filePath":str,
                "resource":""
            }
        """
        raise NotImplementedError()

    def _preview(self, previewFolderPath:str, previewFileBaseName:str, item:RamItem, step:RamStep) -> list:
        """!
        @brief Saves a preview (video or image or both) of the current item
        Parameters : 
            @param previewFolderPath : str => The path where to save
            @param previewFileBaseName : str => The base name of the file to save.
            A resource name/comment can be appended (with a leading "_"), along with the file extension
            @param item : RamItem => The item being previewd
            @param step : RamStep => The step being previewd
        Returns : 
            @return list => The list of saved files. May be an empty list if failed or canceled
        """
        raise NotImplementedError()

    def _prePublish(self, publishInfo:RamFileInfo, publishOptions:dict) -> dict:
        """!
        @brief Run pre-publish cleanups and any other needed preparation

        Parameters : 
            @param publishInfo : RamFileInfo => Information about the file(s) to be published. 
            Use publishInfo.copy() to prepare each new published file
            @param publishOptions : dict => The publish settings, may be None if they're not set.
            An empty dict (or any missing key) means "Use default values".
            If it's not None, a UI may be shown to let the user set the publish settings.
            @param forceShowPublishUI : bool => Wether to force showing a publish settings dialog even if the options are set.
        Returns : 
            @return dict => The publish options, which may have been changed.
            None or False to cancel the publish process.
        """
        raise NotImplementedError()

    def _publish(self, publishInfo:RamFileInfo, publishOptions:dict) -> list:
        """!
        @brief Publishes (exports) the current item to make it available to other steps

        Parameters : 
            @param publishInfo : RamFileInfo => Information about the file(s) to be published. 
            Use publishInfo.copy() to prepare each new published file
            @param publishOptions : dict => The publish settings, may be None if they're not set. An empty dict (or any missing key) means "Use default values".
        Returns : 
            @return list => The list of published file paths, an empty list on fail or abort.
        """
        raise NotImplementedError()

    def _publishOptions(self, proposedOptions:dict,  showPublishUI:bool=False) -> dict:
        """!
        @brief Gets the publish options for the current file/item/step

        Parameters : 
            @param proposedOptions : dict => Some default options ; may be empty.
            @param showPublishUI : bool => Wether to show a publish settings dialog.
        Returns : 
            @return dict => The publish options.
        """
        raise NotImplementedError()

    def _replace(self, filePaths:list, item:RamItem, step:RamStep, importOptions:list, forceShowImportUI:bool) -> bool:
        """!
        @brief Replaces an item (the selection) in the current file

        Parameters : 
            @param filePaths : list => The published file paths (str) to be imported
            @param item : RamItem => The item being imported
            @param step : RamStep => The step being imported
            @param importOptions : list => The list of import options (dict).
            If this is not an empty list, can import without any UI/Dialog.
            @param forceShowImportUI : bool => Wether to show the import settings dialog even if some import options are provided
        Returns : 
            @return bool => Success
        """
        raise NotImplementedError()

    def _replaceUI(self, item:RamItem, step:RamStep) -> dict:
        """!
        @brief Shows the UI to select an item to replace the current selection.

        Parameters : 
            @param item : RamItem => The item to pre-select
            @param step : RamStep => The step to pre-select
        Returns : 
            @return dict => A dict containing at least { "item":RamItem, "step":RamStep } or { "filePaths":list }.
            Returns None if the user cancels.
            All other keys are optionnal, the complete dict can be:
            {
                "item":RamItem,
                "step":RamStep,
                "filePaths":list,
                "showImportUI":False
            }
        """
        raise NotImplementedError()

    def _restoreVersionUI(self, versionFiles:list) -> str:
        """!
        @brief Shows a UI to select a version file from all available versions

        Parameters : 
            @param versionFiles : list => The list of version files
        Returns : 
            @return str => The selected version file or None if the user cancelled
        """
        raise NotImplementedError()

    def _saveAs(self, filePath:str, item:RamItem, step:RamStep, version:int, comment:str, incremented:bool) -> bool:
        """!
        @brief Saves the current working file at the given location.
        The function must not show any UI and silently override any existing file, if any.

        Use RamHost.saveAs() for showing the save as UI and save as a new file,
        which in turn will call this private function.

        Parameters : 
            @param filePath : str => The path where to save the current working file.
            @param item : RamItem => The item (shot or asset) being saved.
            @param step : RamStep => The step being saved.
            @param version : int => The version being saved. This may be -1 if the version is unknown (like during the creation of a new file)
            @param comment : str => The comment associated to the version.
            @param inremented : bool => True if the version has just been incremented (or if it's a new file)
        Returns : 
            @return bool => [description]

        """
        raise NotImplementedError()

    def _saveAsUI(self) -> dict:
        """!
        @brief Shows a "Save As" UI, letting the user select an item and a step,
        and optionally set a resource name and a file fornat (extension)

        Parameters : 
        Returns : 
            @return dict => A dict containing at least { "item":RamItem, "step":RamStep, "extension":str }.
            Returns None if the user cancels.
            The extension must not include the leading ".".
            All other keys are optionnal, the complete dict can be:
            {
                "item":RamItem,
                "step":RamStep,
                "extension":str,
                "resource":""
            }
        """
        raise NotImplementedError()

    def _saveChangesUI(self) -> bool:
        """!
        @brief Asks the user to save the changes of the current file
        before it is closed or another file is opened.

        Returns : 
            @return bool => False if the user cancels
        """
        raise NotImplementedError

    def _setFileName(self, fileName:str ) -> bool:
        """!
        @brief Renames the file currently opened.
        This may not be possible in some DCC apps without saving as a new file.
        In this case, do save it.

        Returns : 
            @return bool => False if failed
        """
        raise NotImplementedError

    def _setupCurrentFile(self, item:RamItem, step:RamStep, setupOptions:dict) -> bool:
        """!
        @brief Sets the current file parameters.
        May show a UI to let the user approve the settings.

        Parameters : 
            @param item : RamItem => The item (shot or asset)
            @param step : RamStep => The step
            @param setupOptions : dict => The available settings to be applied.
            Note that you may use step.generalSettings() to use other (custom) settings.
            {
                "width":int,
                "height":int,
                "framerate":float,
                "duration":float, (0 if not a shot)
                "pixelAspectRation":float,
                "aspectRatio":float
            }
        Returns : 
            @return bool => [description]

        """
        raise NotImplementedError()

    def _statusUI(self, currentStatus:RamStatus = None) -> dict:
        """!
        @brief Shows a UI to update the status of the current item,
        and ask to publish it.

        Parameters : 
            @param currentStatus : RamStatus = None => The current status of the current item
        Returns : 
            @return dict => A dict.
            Returns None if the user cancels.
            All other keys are optionnal, the complete dict can be:
            {
                "comment":"",
                "completionRatio":50,
                "state":RAMSES.defaultState,
                "publish":False,
                "showPublishUI":False,
                "savePreview":False
            }
        """
        raise NotImplementedError()

    # ========= Public Methods =========

    def addToRecentFiles( self, filePath:str ):
        """!
        @brief Adds the file to the recent file list

        Parameters : 
            @param filePath : str => The file path

        """

        # Normalize path to avoid duplicates
        filePath = os.path.normpath(filePath)

        if filePath in SETTINGS.recentFiles:
            SETTINGS.recentFiles.pop( SETTINGS.recentFiles.index(filePath) )
        SETTINGS.recentFiles.insert(0, filePath)
        SETTINGS.recentFiles = SETTINGS.recentFiles[0:20]
        SETTINGS.save()

    def addToRecentImport(self, item:RamItem, step:RamStep):
        """!
        @brief Adds the item and step to the recent import list.
        This is useful to add a "recent" list in the UI for importing items for example.

        Parameters : 
            @param item : the item
            @param step : the step
        """
        if not item or not step:
            return
        import_data = {
            'item': item.uuid(),
            'itemType': item.itemType(),
            'step': step.uuid()
        }
        if import_data in SETTINGS.recentImport:
            SETTINGS.recentImport.pop( SETTINGS.recentImport.index(import_data) )
        SETTINGS.recentImport.insert(0, import_data)
        SETTINGS.recentImport = SETTINGS.recentImport[0:20]
        SETTINGS.save()

    def checkAddOnUpdate(self) -> dict:
        """!
        @brief [Function's description]

        Returns : 
            @return dict => The update info
        """
        return checkUpdate(self.updateURL, "ramses", self.version, self.hostName, self.hostVersion, self.preRelease, self.language)

    def createTempWorkingFile(self) -> str:
        """!
        @brief Creates a temporary working file.
        Use closeTempWorkingFile() to get back to the current file.

        Returns : 
            @return str => The temp file path
        """
        # Set a temp file name just in case something fails
        # To avoid breaking the current file.
        self.__currentFilePath = self.currentFilePath()
        currentFileName = os.path.basename(self.__currentFilePath)
        tempDir = tempfile.gettempdir()
        fileName = 'RamsesWorkingFile_' + currentFileName
        self.__tempWorkingFilePath = os.path.join(tempDir, fileName)
        self._setFileName(self.__tempWorkingFilePath)
        return self.__tempWorkingFilePath
    
    def closeTempWorkingFile(self):
        """!
        @brief Closes the temporary working file created by createTempWorkingFile(),
        and reopens the current file
        """
        if self.__tempWorkingFilePath == '':
            return
        # Reopen the original scene
        self._open(self.__currentFilePath, item=None, step=None)
        # Delete the temp file
        if os.path.isfile( self.__tempWorkingFilePath ):
            os.remove( self.__tempWorkingFilePath )
        self.__tempWorkingFilePath = ""

    def currentStep(self) -> RamStep:
        """!
        @brief Gets the current working Step, if any

        Returns : 
            @return RamStep => The current step or None
        """
        return RamStep.fromPath( self.currentFilePath() )

    def currentItem(self) -> RamItem:
        """!
        @brief Gets the current working Item, if any

        Returns : 
            @return RamItem => The current item or None

        """
        return RamItem.fromPath( self.currentFilePath(), virtualIfNotFound=True )

    def currentStatus(self) -> RamStatus:
        """!
        @brief Gets the current status, if any

        Returns : 
            @return RamStatus => The current status or none
        """
        item = self.currentItem()
        if not item:
            return None
        step = self.currentStep()
        return item.currentStatus( step )

    def currentState(self) -> RamState:
        """!
        @brief The state of the current item status

        Returns : 
            @return RamState => The state
        """
        status = self.currentStatus()
        if status:
            return status.state()

        versionInfo = RamFileManager.getLatestVersionInfo( self.currentFilePath(), '' )
        return RAMSES.state(versionInfo.state)

    def currentVersion(self) -> int:
        """!
        @brief Gets the current version of the current file
        Returns : 
            @return int => The version
        """
        versionInfo = RamFileManager.getLatestVersionInfo(
            self.currentFilePath()
        )
        return versionInfo.version

    def currentVersionFilePath(self) -> str:
        """!
        @brief The file path for the current version in the _versions subfolder

        Returns : 
            @return str => The path
        """
        versionInfo = RamFileManager.getLatestVersionInfo(
            self.currentFilePath()
        )
        return versionInfo.filePath()

    def currentVersionComment(self) -> str:
        """!
        @brief Gets the comment for the current version
        Returns : 
            @return str => The comment
        """
        # Get current comment
        latestVersionFile = RamFileManager.getLatestVersionFilePath( self.saveFilePath() )
        return RamMetaDataManager.getComment( latestVersionFile )

    def importItem(self, paths:list=(), item:RamItem=None, step:RamStep=None, resource:str="", importOptions:list = None) -> bool:
        """!
        @brief Imports an item in the current file.
        Shows an import dialog if item or step is None.

        Parameters:
            @param item : RamItem = None => The item to import.
            @param step : RamStep = None => The step to import.
            @param paths : list = () => The files to import.
            If the list is empty, automatically imports all published files.
            @param resource : str = "" => The resource to import, used only if filePaths is empty.
        Returns : 
            @return bool => Success
        """

        # Ramses must be available
        if not self.testDaemonConnection():
            return

        showImportUI = False

        if len(paths) == 0 and (not item or not step):
            itemOptions = self._importUI( self.currentItem(), self.currentStep() )
            if not itemOptions:
                return False

            paths = itemOptions.get("filePaths", ())
            item = itemOptions.get("item", None)
            step = itemOptions.get("step", None)
            showImportUI = itemOptions.get("showImportUI", False)

        if len(paths) == 0:
            if not item or not step:
                raise RuntimeError("_importUI did not return any path nor an item.")
            paths = item.latestPublishedVersionFilePaths(
                resource = resource,
                step = step
            )
            if len(paths) == 0:
                self.log("Sorry, can't find any published file for this item.", LogLevel.Critical)
                return False
        else:
            if not item:
                item = RamItem.fromPath(paths[0])
            if not step:
                step = RamStep.fromPath(paths[0])

        # Get the import options
        currentStep = self.currentStep()
        if importOptions is None:
            importOptions = ()
            if currentStep:
                importOptions = currentStep.importSettings('yaml')
                if not importOptions:
                    importOptions = ()

        # Load user scripts
        if not self.__runUserScripts("before_import_item", paths, item, step, importOptions, showImportUI):
            return False

        # Import
        if not self._import( paths, item, step, importOptions, showImportUI):
            return False

        # Load user scripts
        if not self.__runUserScripts("on_import_item", paths, item, step, importOptions, showImportUI):
            return False

        self.addToRecentImport(item, step)
        return True

    def isDirty(self) -> bool:
        """Checks if the current file needs to be saved before it is closed."""
        try:
            return self._isDirty()
        except NotImplementedError:
            return False

    def log(self, message:str, level:int = LogLevel.Info ):
        """!
        @brief Logs/shows/saves... a message

        Parameters : 
            @param message : str => The message to log
            @param level : int = LogLevel.Info => The importance of the message, on of the LogLevel enum.
        """
        from .logger import formatMessage

        message = formatMessage(message, level)
        if message.strip() == "":
            return

        self._log( message, level )

    def open(self, path:str="") -> bool:
        """!
        @brief Opens an item.
        Shows an open dialog if path is omitted.

        Parameters:
            @param filePath : str = "" => The file path to be opened.
        Returns : 
            @return bool => Success
        """

        # Ramses must be available
        if not self.testDaemonConnection():
            return

        if self._isDirty():
            doSave = self._saveChangesUI()
            if doSave == 'cancel':
                return False
            if doSave == 'save':
                self.save()

        item = None
        step = None

        if path == "":
            item = self.currentItem()
            step = self.currentStep()
            itemDict = self._openUI( item, step )
            if not itemDict:
                return False

            path = itemDict.get("filePath", "")
            item = itemDict.get("item", None)
            step = itemDict.get("step", None)
            if path == "":
                if not item or not step:
                    raise RuntimeError("_openUI did not return a path nor an item.")
                path = item.stepFilePath(
                    resource = itemDict.get("resource", ""),
                    step = step
                )
                if path == "":
                    self.log("Sorry, can't find any file for this item.", LogLevel.Critical)
                    return False

        if not item:
            item = RamItem.fromPath(path)
        if not step:
            step = RamStep.fromPath(path)

        # Restore the file if it's a version
        if RamFileManager.inVersionsFolder( path ):
            path = RamFileManager.restoreVersionFile( path, False )
            RamFileManager.waitFiles()

        # Load user scripts
        if not self.__runUserScripts("before_open", path, item, step):
            return False

        if not self._open( path, item, step ):
            return False

        # Load user scripts
        if not self.__runUserScripts("on_open", path, item, step):
            return False

        self.addToRecentFiles(path)
        return True

    def previewPath(self) -> str:
        """!
        @brief The path where preview files should be saved

        Returns : 
            @return str => The path or an empty string if the current file is not set
        """
        item = self.currentItem()
        if item:
            p = item.previewFolderPath( self.currentStep() )
            if p != "":
                return p

        p = self.currentFilePath()
        if p == "":
            return ""
        return os.path.join(
            os.path.dirname(p),
            FolderNames.preview
        )

    def publish(self, forceShowPublishUI:bool=False, incrementVersion:bool=True, publishOptions:dict=None) -> bool:
        """!
        @brief Publishes (exports) the current item
        to make it available to other steps

        Parameters : 
            @param forceShowPublishUI : bool = False => Force showing the UI with publish settings
        Returns : 
            @return bool => Success
        """

        item = self.currentItem()
        step = self.currentStep()

        if not item or not step:
            self.log("Sorry, unknown step or item, I can't publish", LogLevel.Critical)
            return False

        self.log("Publishing " + str(item) + " for " + str(step))

        # Save with a comment
        self.__save(
            self.saveFilePath(),
            comment="Published"
        )

        # Get the publish info
        publishInfo = self.publishInfo()

        # Get default publish options
        if not publishOptions:
            publishOptions = step.publishSettings('yaml')
        else:
            publishOptions = {}

        # Call protected method
        publishOptions = self._publishOptions(publishOptions, forceShowPublishUI)
        # If False or empty, the user has canceled
        if publishOptions is False or publishOptions is None:
            return False

        # Get ramses publish options
        ramPublishOptions = publishOptions.get('ramsesPublishOptions', {})
        if ramPublishOptions.get('useTempFile', False):
            self.createTempWorkingFile()

        # Load user scripts
        if not self.__runUserScripts("before_pre_publish", publishInfo, publishOptions, item, step):
            # Note:user can modify the publishOptions dict,
            # or call publishOptions.clear() first to completely replace it
            return False

        # Pre publish
        self.log("Pre-Publishing...", LogLevel.Debug)
        publishOptions = self._prePublish(publishInfo, publishOptions)
        if publishOptions is False or publishOptions is None:
            return False

        # Backup the file
        if ramPublishOptions.get('backupFile', False):
            self.__backupPublishedFile(publishInfo)

        if not self.__runUserScripts("before_publish", publishInfo, item, step, publishOptions):
            return False

        # Publish
        self.log("Publishing...", LogLevel.Debug)
        published_files = self._publish(publishInfo, publishOptions)
        if published_files is None or published_files is False:
            return False
        for file in published_files:
            self.__setPublishMetadata(file, publishInfo)

        # Load user scripts
        if not self.__runUserScripts("on_publish", published_files, publishInfo, item, step, publishOptions):
            self.closeTempWorkingFile()
            return False

        status = self.currentStatus()
        if status:
            status.setPublished(True)

        self.closeTempWorkingFile()

        # Increment
        if incrementVersion:
            self.__save(
                self.saveFilePath(),
                incrementVersion=True
            )

        return True

    def publishInfo(self) -> RamFileInfo:
        """Gets publish file info.
        
        The file info is set to be in the publish folder for the current version.
        Use publishInfo.copy() to get copies if you need to export multiple files,
        the performance will be better than calling this method multiple times.
        """
        # Already a copy to make sure everything is clean if the user doesn't make a copy
        return RamFileManager.getPublishInfo( self.saveFilePath() ).copy()

    def publishFilePath(self, extension:str, publishName:str, publishInfo:RamFileInfo=None) -> str:
        """!
        @brief Gets a file path to export an item.

        When publishing multiple files,
        Or if the currentFile is not in a standard Ramses folder
        (this may happen when creating a temp working file during the prePublish),
        pass a RamFileInfo to improve performance;
        i.e:
        info = RAMSES.host.publishInfo()
        # Do stuff, then:
        publish_path = RAMSES.host.publishFilePath( 'ext', 'some name', info)

        Parameters : 
            @param extension : str => The file extension
            @param publishName : str => A name for the published item
            @param publishInfo : RamFileInfo => A publish file info, most likely got with publishInfo()
        Returns : 
            @return str => The path to be used to export the item
        """
        if publishInfo is None:
            info = self.publishInfo()
        else:
            info = publishInfo.copy()
        info.version = -1
        info.state = ''
        info.extension = extension
        if info.resource != '':
            info.resource = info.resource + '-'
        info.resource = info.resource + publishName
        return info.filePath()

    def replaceItem(self, paths:list=(), item:RamItem=None, step:RamStep=None, resource:str="", importOptions:list = None) -> bool:
        """!
        @brief Replaces an item in the current file.
        Shows a replace dialog if item or step is None.

        Parameters:
            @param paths : list = () => The files to import.
            If the list is empty, automatically imports all published files.
            @param item : RamItem = None => The item to import.
            @param step : RamStep = None => The step to import.
            @param resource : str = "" => The resource to import, used only if filePaths is empty.
        Returns : 
            @return bool => Success
        """

        showImportUI = False

        if len(paths) == 0 and (not item or not step):
            itemOptions = self._replaceUI( self.currentItem(), self.currentStep() )
            if not itemOptions:
                return False

            paths = itemOptions.get("filePaths", ())
            item = itemOptions.get("item", None)
            step = itemOptions.get("step", None)
            showImportUI = itemOptions.get("showImportUI", False)

        if len(paths) == 0:
            if not item or not step:
                raise RuntimeError("_replaceUI did not return any path nor an item.")
            paths = item.latestPublishedVersionFilePaths(
                resource = resource,
                step = step
            )
            if len(paths) == 0:
                self.log("Sorry, can't find any published file for this item.", LogLevel.Critical)
                return False
        else:
            if not item:
                item = RamItem.fromPath(paths[0])
            if not step:
                step = RamStep.fromPath(paths[0])

        # Get the import options
        currentStep = self.currentStep()
        if importOptions is None:
            importOptions = ()
            if currentStep:
                importOptions = currentStep.importSettings('yaml')
                if not importOptions:
                    importOptions = ()

        # Load user scripts
        if not self.__runUserScripts("before_replace_item", paths, item, step, importOptions, showImportUI):
            return False

        # Import
        if not self._replace( paths, item, step, importOptions, showImportUI):
            return False

        # Load user scripts
        if not self.__runUserScripts("on_replace_item", paths, item, step, importOptions, showImportUI):
            return False

        return True

    def restoreVersion(self, versionFilePath:str="") -> bool:
        """!
        @brief Restores and opens an older version of the current item.
        Shows a version selection UI if versionFilePath is omitted.

        Parameters:
            @param versionFilePath : str = "" => The version file to restore.
            A version file can be retrieved using RamFileManager.getVersionFilePaths( RamHost.currentFilePath() )
        Returns : 
            @return bool => Success
        """

        if versionFilePath == "":
            savePath = self.saveFilePath()
            if savePath == "":
                self.log("Sorry, invalid file, I can't restore an older version of this.", LogLevel.Critical)
                return False

            # List version files
            versionFiles = RamFileManager.getVersionFilePaths( savePath )
            if len(versionFiles) == 0:
                self.log("Sorry, I can't find any older version...")
                return False

            # In descending order
            versionFiles.reverse()

            # Show the dialog
            versionFilePath = self._restoreVersionUI( versionFiles )
            if not versionFilePath:
                return False

        # Restore and open
        restoredFile = RamFileManager.restoreVersionFile( versionFilePath )
        RamFileManager.waitFiles()
        return self._open(restoredFile, self.currentItem(), self.currentStep() )

    def save(self, incremental:bool=False, comment:str=None, setupFile:bool=True) -> bool:
        """!
        @brief Saves the current file,
        Optionally showing a "save as" dialog if there's no current file

        Parameters : 
        Returns : 
            @return bool => Success
        """
        saveFilePath = self.saveFilePath()
        # if it's not right, log and try a save as
        if saveFilePath == "":
            self.log(Log.MalformedName)
            return self.saveAs()

        if setupFile:
            try:
                item = self.currentItem()
                if not self._setupCurrentFile(
                    item,
                    self.currentStep(),
                    self.__collectItemSettings(item)
                    ):
                    return False
            except NotImplementedError:
                pass

        return self.__save(saveFilePath, incremental, comment)

    def saveAs(self, setupFile:bool=True) -> bool:
        """!
        @brief Saves the current file as a new Item-Step.
        Shows the UI to ask the user for the new item and step.

        Dev: Ramses Add-ons must implement RamHost._saveAsUI() and RamHost._saveAs()

        Parameters : 
            @param setupFile : bool = True => If implemeted, sets the current file settings before saving,
            e.g. the framerate, resolution, duration, etc.
        Returns : 
            @return bool => Success
        """
        # Show the save as dialog
        saveItem = self._saveAsUI()
        if not saveItem:
            return False

        item = saveItem.get("item", None)
        if not item:
            raise ValueError("Missing RamItem")
        step = saveItem.get("step", None)
        if not step:
            raise ValueError("Missing RamStep")
        extension = saveItem.get("extension", "")
        if extension == "":
            raise ValueError("Missing extension")
        resource = saveItem.get("resource", "")

        # Get the file path
        if item.itemType == ItemType.GENERAL:
            folderPath = item.folderPath()
        else:
            folderPath = item.stepFolderPath( step )

        nm = RamFileInfo()
        nm.project = step.project().shortName()
        nm.ramType = item.itemType()
        nm.shortName = item.shortName()
        nm.step = step.shortName()
        nm.extension = extension
        nm.resource = resource
        fileName = nm.fileName()

        if not os.path.isdir(folderPath):
            os.makedirs(folderPath)

        filePath = os.path.join(folderPath, fileName)
        # Check if file exists
        if os.path.isfile( filePath ):
            # Backup
            backupFilePath = RamFileManager.copyToVersion( filePath, increment=True )
            # Be kind, set a comment
            RamMetaDataManager.setComment( backupFilePath, "Overwritten by an external file." )
            self.log( 'I\'ve added this comment for you: "Overwritten by an external file."' )

        # Load user scripts
        if not self.__runUserScripts("before_save_as", item, step, resource):
            return False

        if setupFile:
            try:
                if not self._setupCurrentFile(
                    item,
                    self.currentStep(),
                    self.__collectItemSettings(item)
                    ):
                    return False
            except NotImplementedError:
                pass

        # Actual save
        if not self._saveAs( filePath, item, step, -1, "", True ): # Virtual, pylint: disable=assignment-from-no-return:
            return False

        # Load user scripts
        if not self.__runUserScripts("on_save_as", item, step, resource):
            return False

        # Create the first version ( or increment existing )
        RamFileManager.copyToVersion( filePath, increment=True )

        self.log( "Scene saved as: " + os.path.basename(filePath) )
        self.addToRecentFiles( filePath )

        return True

    def saveFilePath(self) -> str:
        """!
        @brief Gets the path where the current file should be saved.

        Returns : 
            @return str => The file path, or an empty string if the current file can't be recognized.
        """
        currentFile = self.currentFilePath()
        return RamFileManager.getSaveFilePath( currentFile )

    def savePreview(self):
        """!
        @brief Saves a preview (video or image or both) of the current item
        """
        path = self.previewPath()
        if path == "":
            self.log("Sorry, the current file is not saved, I can't save the preview.", LogLevel.Critical)
            return False

        fileInfo = RamFileInfo()
        fileInfo.setFilePath( self.currentFilePath() )
        previewInfo = fileInfo.copy()
        previewInfo.version = -1
        previewInfo.extension = ""
        previewInfo.resource = ""
        previewInfo.state = ""

        previewFiles = self._preview( path, previewInfo.fileName(), self.currentItem(), self.currentStep() )
        # Set metadata
        for file in previewFiles:
            RamMetaDataManager.setVersion(file, self.currentVersion())
            RamMetaDataManager.setVersionFilePath(file, self.currentVersionFilePath())

    def setupCurrentFile(self):
        """!
        @brief Sets the current file settings, like the resolution, framerate, etc.
        """
        item = self.currentItem()
        self._setupCurrentFile(
            item,
            self.currentStep(),
            self.__collectItemSettings( item )
            )

    def testDaemonConnection(self) -> bool:
        """Tests if the connection to the Ramses Daemon (the app) us up and running"""
        if not DAEMON.online():
            self.log("I can't reach the Ramses daemon. Make sure the application is running and you're logged in.", LogLevel.Critical)
            return False
        return True

    def updateStatus(
        self,
        state:RamState=None,
        comment:str="",
        completionRatio:int=50,
        savePreview:bool=False,
        publish:bool=False,
        showPublishUI:bool=False) -> bool:
        """!
        @brief Updates the current item status, and saves the file

        Parameters : 
            @param state : RamState = None => The new state. If None, the UI is shown (if _statusUI() is implemented by the Add-on)
            @param comment : str = "" => The new comment
            @param completionRatio : int = 50 => The new completion ratio for the task
            @param savePreview : bool = False => Whether to save an image or video preview of the current file.
            @param publish : bool = False => Whether to publish the current item.
            @param showPublishUI : bool = False => Whether to force showing the publish settings UI, even if the settings are already set or not needed.
        Returns : 
            @return bool => Success
        """

        # Ramses must be available
        if not self.testDaemonConnection():
            return

        # First, save if we don't know the item
        if not self.currentItem() and not self.save():
            return False

        item = self.currentItem()
        step = self.currentStep()
        status = self.currentStatus()        

        if item and not status and item.itemType != ItemType.GENERAL:
            raise RuntimeError("Can't get the current status. This may be a bug in the API or the Ramses Daemon. Please report the issue to the developers.")

        # Show the dialog and get the results if needed
        if state is None:
            newStatusDict = self._statusUI(status)
            if not newStatusDict:
                return False

            publish = newStatusDict.get("publish", False)
            savePreview = newStatusDict.get("savePreview", False)
            comment = newStatusDict.get("comment", "")
            completionRatio = newStatusDict.get("completionRatio", 50)
            state = newStatusDict.get("state", RAMSES.defaultState)
            showPublishUI = newStatusDict.get("showPublishUI", False)

        # Save and Update the state in the version
        self.__save(
            self.saveFilePath(),
            incrementVersion=True,
            comment="Status change",
            newStateShortName=status.state().shortName()
        )

        # Load user scripts
        if not self.__runUserScripts("before_update_status", item, status, step):
            return False

        # Get the version and update the status
        status.setComment(comment)
        status.setCompletionRatio(completionRatio)
        status.setState(state)
        status.setVersion( self.currentVersion() )

        # Load user scripts
        if not self.__runUserScripts("on_update_status", item, status, step):
            return False

        # Publish if asked for
        if publish:
            try:
                self.publish(
                    showPublishUI,
                    incrementVersion=False
                    )
            except NotImplementedError:
                pass

        # Preview if asked for
        if savePreview:
            try:
                self.savePreview()
            except NotImplementedError:
                pass

        return True

    # ========= Private Methods =========

    def __init__(self):
        self.__currentFilePath = ""
        self.__tempWorkingFilePath = ""

    def __collectItemSettings(self, item:RamItem) -> dict:
        # be kind, collect some parameters
        project = RAMSES.project()

        settings = {
            "width":project.width(),
            "height":project.height(),
            "framerate":project.framerate(),
            "duration":0.0,
            "pixelAspectRatio":project.pixelAspectRatio(),
            "aspectRatio":project.aspectRatio()
        }

        if item and item.itemType == ItemType.SHOT:
            settings['duration'] = item.duration()
            sequence = item.group()
            if sequence:
                settings['width'] = sequence.width()
                settings['height'] = sequence.height()
                settings['pixelAspectRatio'] = sequence.pixelAspectRatio()
                settings['aspectRatio'] = sequence.aspectRatio()

        return settings

    def __runUserScripts(self, scriptName, *args) -> bool:

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                self.log("Sorry, I can't find and run this user script: " + s + "\nCalling event: " + scriptName, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            f = getattr(m, scriptName, None)
            if f is None:
                continue
            if not f(*args):
                self.log("A user script interrupted the process: " + s + "\nCalling event: " + scriptName, LogLevel.Info)
                return False

        return True

    def __save(self, filePath:str, incrementVersion:bool=False, comment:str=None, newStateShortName:str=None) -> bool:

        self.log("Saving file as: '" + os.path.basename(filePath) + "'")

        incrementReason = ""
        currentPath = self.currentFilePath()

        # Check if this is a restored version
        nm = RamFileInfo()
        nm.setFilePath( currentPath )
        if nm.isRestoredVersion:
            incrementVersion = True
            incrementReason = "we're restoring the older version " + str(nm.restoredVersion) + "."

        # If the current file is inside a preview/publish/version subfolder, we're going to increment
        # to be sure to not lose the previous working file.
        if RamFileManager.inReservedFolder( currentPath ) and not incrementVersion:
            incrementVersion = True
            incrementReason = "the file was misplaced."

        # Make sure we have the correct save file path
        saveFilePath = RamFileManager.getSaveFilePath( filePath )
        if saveFilePath == '':
            return False

        # If the timeout has expired, we're also incrementing
        prevVersionInfo = RamFileManager.getLatestVersionInfo( saveFilePath, previous=True )
        modified = prevVersionInfo.date
        now = datetime.today()
        timeout = timedelta(seconds = SETTINGS.autoIncrementTimeout * 60 )
        if  timeout < now - modified and not incrementVersion:
            incrementReason = "the file was too old."
            incrementVersion = True

        # Get the RamItem and RamStep
        item = RamItem.fromPath( filePath )
        step = RamStep.fromPath( filePath )

        # Get the version
        versionInfo = RamFileManager.getLatestVersionInfo( saveFilePath )
        version = versionInfo.version
        if version <= 0:
            version = 1
        if incrementVersion:
            version = version + 1

        # Update the comment
        if incrementReason != "":
            comment = "Auto-Increment because " + incrementReason

        # Check the state
        if newStateShortName is None:
            newStateShortName = self.currentState().shortName()

        # Load user scripts
        if not self.__runUserScripts("before_save", saveFilePath, item, step, version, comment, incrementVersion):
            return False

        # Actual save
        if not self._saveAs( saveFilePath, item, step, version, comment, incrementVersion ): # Virtual, pylint: disable=assignment-from-no-return
            return False

        # Load user scripts
        if not self.__runUserScripts("on_save", saveFilePath, item, step, version, comment, incrementVersion):
            return False

        # Backup / Increment
        backupFilePath = RamFileManager.copyToVersion( saveFilePath, incrementVersion, newStateShortName )

        # Write the comment
        RamMetaDataManager.setComment( backupFilePath, comment )
        if comment is not None and incrementReason == "":
            self.log( "I've added this comment to the current version: " + comment )
        elif incrementReason != "":
            self.log("I've incremented the version for you because " + incrementReason)

        self.log( "File saved! The version is now: " + str(version) )

        self.addToRecentFiles( saveFilePath )

        return True

    def __setPublishMetadata(self, path:str, publishInfo:RamFileInfo):
        RamMetaDataManager.setVersion( path, publishInfo.version )
        RamMetaDataManager.setState( path, publishInfo.state )
        RamMetaDataManager.setResource( path, publishInfo.resource )

    def __backupPublishedFile( self, publishInfo:RamFileInfo=None ):
        """!
        @brief Backs up the current file in a published folder corresponding to the current version.

        This function should be called during the publish process (implemented by Ramses Add-ons in _publish())
        To backup the file exactly as it is, ready just before exports are made, i.e. after all cleanup process.
        
        When publishing multiple files,
        Or if the currentFile is not in a standard Ramses folder
        (this may happen when creating a temp working file during the prePublish),
        pass a RamFileInfo to improve performance;
        i.e:
        info = RAMSES.host.publishInfo()
        # Do stuff, then:
        publish_path = RAMSES.host.publishFilePath( 'ext', 'some name', info)

        Parameters : 
            @param self => [description]
            @param publishInfo : RamFileInfo = None => [description]

        """

        if publishInfo is None:
            info = self.publishInfo()
        else:
            info = publishInfo.copy()
        version = info.version
        info.version = -1
        info.state = ''
        info.isBackup = True
        # Save
        previousPath = self.currentFilePath()
        filepath = info.filePath()
        self._saveAs(
            filepath,
            None,
            None,
            -1,
            '',
            False
        )
        RamMetaDataManager.appendHistoryDate( filepath )
        RamMetaDataManager.setVersion( filepath, version )
        # Reopen current file path if it exists
        if os.path.isfile(previousPath):
            self._open(previousPath, None, None)
