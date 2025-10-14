# -*- coding: utf-8 -*-
"""The main Ramses class"""

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
import yaml
from subprocess import Popen, PIPE
from datetime import datetime, timedelta

from .file_manager import RamFileManager
from .file_info import RamFileInfo
from .metadata_manager import RamMetaDataManager
from .logger import log
from .constants import LogLevel, Log
from .daemon_interface import RamDaemonInterface
from .ram_settings import RamSettings
from .utils import load_module_from_path
from .constants import ItemType

SETTINGS = RamSettings.instance()
DAEMON = RamDaemonInterface.instance()

class Ramses( object ):
    """The main class. One (and only one) instance globally available, instantiated during init time.

    Static Attributes:
        instance: Ramses
            The unique Ramses instance
    """

    # API Settings
    _version = SETTINGS.version
    apiReferenceUrl = SETTINGS.apiReferenceUrl
    addonsHelpUrl = SETTINGS.addonsHelpUrl
    generalHelpUrl = SETTINGS.generalHelpUrl

    _instance = None

    def __init__(self):
        """
        Ramses is a singleton and cannot be initialized with `Ramses()`. Call Ramses.instance() instead.

        Raises:
            RuntimeError
        """
        raise RuntimeError("Ramses can't be initialized with `Ramses()`, it is a singleton. Call Ramses.instance() instead.")

    @classmethod
    def instance( cls ):
        """Returns the unique Ramses instance"""
        if cls._instance is None:

            cls._instance = cls.__new__(cls)

            log("I'm trying to contact the Ramses Client.", LogLevel.Info)
            cls._instance.connect()

            cls._offline = True

            cls.publishScripts = []
            cls.statusScripts = []
            cls.importScripts = []
            cls.replaceScripts = []
            cls.openScripts = []
            cls.saveScripts = []
            cls.saveAsScripts = []
            cls.saveTemplateScripts = []

            cls.userScripts = {}

            # Get the default state (TO Do)
            cls.defaultState = cls._instance.state("WIP")

        return cls._instance

    def currentProject(self):
        """The current project.

        Returns:
            RamProject or None
        """
        return DAEMON.getCurrentProject()

    def setCurrentProject( self, project ):
        """Sets the current project (useful if offline)"""
        DAEMON.setCurrentProject( project.uuid() )

    def currentUser(self):
        """The current user.

        Returns:
            RamUser or None
        """
        return DAEMON.getCurrentUser()

    def online(self):
        """True if connected to the Daemon and the Daemon is responding.

        Returns:
            bool
        """
        return not self._offline

    def alternativeFolderPaths(self):  # TODO
        """A list of alternative absolute paths to the main Ramses folder.
        Missing files will be looked for in these paths (and copied to the main path if available),
        and they will be used if the main path is not available.

        Returns:
            str list
        """
        pass

    def backupFolderPath(self):  # TODO
        """A copy of the main folder where all files are stored.

        Returns:
            str
        """
        pass

    def folderPath(self):
        """The absolute path to the main Ramses folder, containing projects by default,
        config files, user folders, admin files…

        Returns:
            str
        """
        return DAEMON.getRamsesFolderPath()

    def projectsPath(self):
        """Returns the default path for projects"""

        folderPath = self.folderPath()
        if folderPath == "":
            return ""

        return RamFileManager.buildPath((
            folderPath,
            SETTINGS.folderNames.projects
        ))

    def usersPath(self):
        """Returns the default path for users"""

        folderPath = self.folderPath()
        if folderPath == "":
            return ""

        return RamFileManager.buildPath((
            folderPath,
            SETTINGS.folderNames.users
        ))

    def connect(self):
        """Checks Daemon availability and initiates the connection. Returns success.

        Returns:
            bool
        """

        # Check if already online
        self._offline = False
        if DAEMON.online():
            user = self.currentUser()
            if user:
                return True
            else:
                DAEMON.raiseWindow()
                log( Log.NoUser, LogLevel.Info )
        else:
            # Try to open the client
            self.showClient()

        self._offline = True
        return False

    def disconnect(self):
        """Gets back to offline mode.

        Returns:
            bool
        """
        self._offline = True

    def daemonInterface(self):
        """The Daemon interface.

        Returns:
            RamDaemonInterface
        """
        return DAEMON

    def project(self, shortName):
        """
        Gets a project using its shortName
        
        return:
            RamProject
        """
        projs = self.projects()
        for p in projs:
            if p.shortName() == shortName:
                return p
        return None

    def projects(self):
        """The list of available projects.

        Returns:
            list of RamProject
        """
        return DAEMON.getProjects()

    def state(self, stateShortName="WIP"):
        """Gets a specific state.

        Args:
            stateShortName (str, optional): Defaults to "WIP".

        Returns:
            RamState
        """

        if not self._offline:
            stts = self.states()
            for stt in stts:
                if stt.shortName() == stateShortName:
                    return stt
        return None

    def states(self):
        """The list of available states.

        Returns:
            list of RamState
        """
        from ramses.ram_state import RamState
        states = DAEMON.getObjects( "RamState" )
        # Order before returning
        states.sort( key=RamState.stateSorter )
        return states

    def showClient(self):
        """Raises the Ramses Client window, launches the client if it is not already running.
        """

        if SETTINGS.ramsesClientPath == "":
            self._offline = True
            return False

        try:
            p = Popen(SETTINGS.ramsesClientPath, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except: # pylint: disable=bare-except
            log("The Client is not available at " + SETTINGS.ramsesClientPath, LogLevel.Critical)
            return False

        if not p.poll():
            del p
        else:
            log("The Client can't be launched correctly.", LogLevel.Critical)
            return False

        return True

    def settings(self):
        """

        Args:
            (RamSettings): settings
        """
        return SETTINGS

    @staticmethod
    def version():
        """The current version of this API

        Returns:
            str
        """
        return Ramses._version

    def addToRecentFiles( self, file ):
        """Adds the file to the recent file list"""
        if file in SETTINGS.recentFiles:
            SETTINGS.recentFiles.pop( SETTINGS.recentFiles.index(file) )
        SETTINGS.recentFiles.insert(0, file)
        SETTINGS.recentFiles = SETTINGS.recentFiles[0:20]
        SETTINGS.save()

    # === EVENTS and HANDLERS ===

    def publish(self, filePath, publishOptions=None, showPublishOptions=False ):
        """Publishes the item; runs the list of scripts Ramses.publishScripts
        Returns an error code:
            - -1: One of the scripts interrupted the process
            - 0: Published file
            - 1: Invalid item or step, did not publish"""
        from .ram_item import RamItem
        from .ram_step import RamStep

        okToContinue = True

        # Load item and step
        item = RamItem.fromPath( filePath )
        step = RamStep.fromPath( filePath )

        if not item or not step:
            return 1

        if not publishOptions:
            publishOptionsStr = step.publishSettings()
            if publishOptionsStr != "":
                publishOptions = yaml.safe_load( publishOptionsStr )

        log("Publishing " + str(item) + " for " + str(step))

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_publish" in dir(m):
                okToContinue = m.before_publish(filePath, item, step, publishOptions, showPublishOptions)
                if okToContinue is False:
                    log("A Script interrupted the publish process before it was run: " + s, LogLevel.Info)
                    return -1

        for script in self.publishScripts:
            okToContinue = script(filePath, item, step, publishOptions, showPublishOptions)
            if okToContinue is False:
                return -1

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_publish" in dir(m):
                okToContinue = m.on_publish(filePath, item, step, publishOptions, showPublishOptions)
                if okToContinue is False:
                    log("A Script interrupted the publish process: " + s, LogLevel.Info)
                    return -1

        return 0

    def updateStatus(self, item, status, step=None):
        """Runs the scripts in Ramses.instance().statusScripts."""

        okToContinue = True

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_update_status" in dir(m):
                okToContinue = m.before_update_status(item, status, step)
                if okToContinue is False:
                    log("A Script interrupted the update process before it was run: " + s, LogLevel.Info)
                    return -1

        for script in self.statusScripts:
            okToContinue = script( item, status, step)
            if okToContinue is False:
                return -1

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_update_status" in dir(m):
                okToContinue = m.on_update_status(item, status, step)
                if okToContinue is False:
                    log("A Script interrupted the update process: " + s, LogLevel.Info)
                    return -1
                
        return 0

    def openFile( self, filePath ):
        """Runs the scripts in Ramses.instance().openScripts."""
        from .ram_item import RamItem
        from .ram_step import RamStep

        okToContinue = True

        item = RamItem.fromPath( filePath )
        step = RamStep.fromPath( filePath )

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_open" in dir(m):
                okToContinue = m.before_open(  filePath, item,step )
                if okToContinue is False:
                    log("A Script interrupted the open file process: " + s, LogLevel.Info)
                    return -1

        # Restore the file if it's a version
        if RamFileManager.inVersionsFolder( filePath ):
            filePath = RamFileManager.restoreVersionFile( filePath, False )

        if not item:
            item = RamItem.fromPath( filePath )
        if not step:
            step = RamStep.fromPath( filePath )

        for script in self.openScripts:
            okToContinue = script( filePath, item, step )
            if okToContinue is False:
                return -1

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_open" in dir(m):
                okToContinue = m.on_open( filePath, item, step )
                if okToContinue is False:
                    log("A Script interrupted the open file process: " + s, LogLevel.Info)
                    return -1

        self.addToRecentFiles( filePath )

        return 0

    def importItem(self, current_file_path, import_file_paths, item, step=None, importOptions=None, showImportOptions=False ):
        """Runs the scripts in Ramses.instance().importScripts."""
        from .ram_step import RamStep

        okToContinue = True

        # Get the current step
        currentStep = RamStep.fromPath( current_file_path )
        # Get the import options
        if not importOptions and step is not None:
            importOptions = { "formats": [] }
            for p in step.outputPipes():
                log("Checking pipe: " + str(p), LogLevel.Debug)
                if currentStep is None or currentStep.shortName() == p.inputStepShortName():
                    for f in p.pipeFiles():
                        optionsStr = f.customSettings()
                        log("Found options:\n" + optionsStr, LogLevel.Debug)
                        if optionsStr != "":
                            options = yaml.safe_load( optionsStr )
                            importOptions['formats'].append( options )

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_import_item" in dir(m):
                okToContinue = m.before_import_item( import_file_paths, item, step, importOptions, showImportOptions )
                if okToContinue is False:
                    log("A Script interrupted the import process before it was run: " + s, LogLevel.Info)
                    return -1

        for script in self.importScripts:
            okToContinue = script( import_file_paths, item, step, importOptions, showImportOptions )
            if okToContinue is False:
                return -1

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_import_item" in dir(m):
                okToContinue = m.on_import_item( import_file_paths, item, step, importOptions, showImportOptions )
                if okToContinue is False:
                    log("A Script interrupted the import process: " + s, LogLevel.Info)
                    return -1

        return 0

    def replaceItem(self, current_file_path, filePath, item, step=None, importOptions=None, showImportOptions=False):
        """Runs the scripts in Ramses.instance().replaceScripts."""
        from .ram_step import RamStep

        okToContinue = True

        # Get the current step
        currentStep = RamStep.fromPath( current_file_path )
        extension = os.path.splitext(filePath)[1][1:]

        # Get options
        if not importOptions:
            importOptions = { "formats": [] }
            for p in step.outputPipes():
                if currentStep is None or currentStep.shortName() == p.inputStepShortName():
                    for f in p.pipeFiles():
                        optionStr = f.customSettings()
                        if optionStr != "":
                            options = yaml.safe_load( optionStr )
                            if 'formats' not in importOptions:
                                continue
                            if options['format'] == extension:
                                importOptions['formats'].append( options )
                                break
                    break

        if 'formats' not in importOptions:
            importOptions['formats'] = ()

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_replace_item" in dir(m):
                okToContinue = m.before_replace_item( filePath, item, step, importOptions, showImportOptions )
                if okToContinue is False:
                    log("A Script interrupted the replace process before it was run: " + s, LogLevel.Info)
                    return -1

        for script in self.replaceScripts:
            okToContinue = script( filePath, item, step, importOptions, showImportOptions )
            if okToContinue is False:
                return -1

        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_replace_item" in dir(m):
                okToContinue = m.on_replace_item(  filePath, item,step, importOptions, showImportOptions )
                if okToContinue is False:
                    log("A Script interrupted the replace process: " + s, LogLevel.Info)
                    return -1
                
        return 0

    def saveFile( self, filePath, incrementVersion=False, comment=None, newStateShortName=None ):
        """Runs the scripts in Ramses.instance().saveScripts.
        Returns an error code:
            - -1: One of the scripts interrupted the process
            - 0: Saved
            - 1: Malformed file name, can't get the item or step from the file. The file was not saved.
            - 2: The file was a restored version, it's been incremented then saved as a working file.
            - 3: The file was misplaced (in a reserved folder), and was incremented and saved in the right place.
            - 4: The file was too old (according to RamSettings.autoIncrementTimeout) and was incremented and saved."""

        from .ram_item import RamItem
        from .ram_step import RamStep

        returnCode = 0
        incrementReason = ""

        # Check if this is a restored version
        nm = RamFileInfo()
        nm.setFilePath( filePath )
        if nm.isRestoredVersion:
            incrementVersion = True
            incrementReason = "we're restoring the older version " + str(nm.restoredVersion) + "."
            returnCode = 2

        # If the current file is inside a preview/publish/version subfolder, we're going to increment
        # to be sure to not lose the previous working file.
        if RamFileManager.inReservedFolder( filePath ) and not incrementVersion:
            incrementVersion = True
            incrementReason = "the file was misplaced."
            returnCode = 3

        # Make sure we have the correct save file path
        saveFilePath = RamFileManager.getSaveFilePath( filePath )
        if saveFilePath == '':
            return 1

        # If the timeout has expired, we're also incrementing
        prevVersionInfo = RamFileManager.getLatestVersionInfo( saveFilePath, previous=True )
        modified = prevVersionInfo.date
        now = datetime.today()
        timeout = timedelta(seconds = SETTINGS.autoIncrementTimeout * 60 )
        if  timeout < now - modified and not incrementVersion:
            incrementReason = "the file was too old."
            incrementVersion = True
            returnCode = 4

        # Get the RamItem and RamStep
        item = RamItem.fromPath( filePath )
        step = RamStep.fromPath( filePath )

        # Get the version
        versionInfo = RamFileManager.getLatestVersionInfo( saveFilePath )
        version = versionInfo.version
        if incrementVersion:
            version += 1

        # Update the comment
        if incrementReason != "":
            comment = "Auto-Increment because " + incrementReason

        # Check the state
        if newStateShortName is None:
            newStateShortName = 'v'
            if self.defaultState:
                newStateShortName = self.defaultState.shortName()
        if not incrementVersion:
            newStateShortName = ""

        okToContinue = True

        # Load user before scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_save" in dir(m):
                okToContinue = m.before_save( saveFilePath, item, step, version, comment, incrementVersion )
                if okToContinue is False:
                    log("A Script interrupted the save process: " + s, LogLevel.Info)
                    return -1

        # Add-on registered scripts
        for script in self.saveScripts:
            okToContinue = script( saveFilePath, item, step, version, comment, incrementVersion )
            if okToContinue is False:
                return -1

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_save" in dir(m):
                okToContinue = m.on_save( saveFilePath, item, step, version, comment, incrementVersion )
                if okToContinue is False:
                    log("A Script interrupted the save process: " + s, LogLevel.Info)
                    return -1

        # Backup / Increment
        backupFilePath = RamFileManager.copyToVersion( saveFilePath, incrementVersion, newStateShortName )

        # Write the comment
        RamMetaDataManager.setComment( backupFilePath, comment )
        if comment is not None and incrementReason == "":
            log( "I've added this comment to the current version: " + comment )
        elif incrementReason != "":
            log("I've incremented the version for you because " + incrementReason)

        log( "File saved! The version is now: " + str(version) )

        self.addToRecentFiles( saveFilePath )

        return returnCode

    def saveFileAs(self, currentFilePath, fileExtension, item, step, resource=""):
        """Runs the scripts in Ramses.instance().saveAsScripts
         Returns an error code:
            - -1: One of the scripts interrupted the process
            - 0: Saved file
            - 1: Saved as a new version because the file already exists"""

        returnCode = 0

        # Get the file path
        folderPath = item.stepFolderPath( step )
        nm = RamFileInfo()
        nm.project = step.project().shortName()
        nm.ramType = item.itemType()
        nm.shortName = item.shortName()
        nm.step = step.shortName()
        nm.extension = fileExtension
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
            log( 'I\'ve added this comment for you: "Overwritten by an external file."' )
            returnCode = 1

        # Load user before scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_save_as" in dir(m):
                okToContinue = m.before_save_as( filePath, item, step, resource )
                if okToContinue is False:
                    log("A Script interrupted the save as process: " + s, LogLevel.Info)
                    return -1

        # Add-on registered scripts
        for script in self.saveAsScripts:
            okToContinue = script( filePath, item, step, resource )
            if okToContinue is False:
                return -1

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_save_as" in dir(m):
                okToContinue = m.on_save_as( filePath, item, step, resource )
                if okToContinue is False:
                    log("A Script interrupted the save as process: " + s, LogLevel.Info)
                    return -1

        # Create the first version ( or increment existing )
        RamFileManager.copyToVersion( filePath, increment=True )

        log( "Scene saved as: " + filePath )
        self.addToRecentFiles( filePath )

        return returnCode

    def saveTemplate( self, fileExtension, step, templateName="Template" ):
        """Runs the scripts in Ramses.instance().saveTemplateScripts
         Returns an error code:
            - -1: One of the scripts interrupted the process
            - 0: Saved template"""

        from .ram_item import RamItem

        log("Saving as template...")

        # Get the folder and filename
        projectShortName = step.project().shortName()
        stepShortName = step.shortName()
        nm = RamFileInfo()
        nm.project = projectShortName
        nm.step = stepShortName
        nm.ramType = ItemType.GENERAL
        nm.shortName = templateName

        saveFolder = os.path.join(
            step.templatesFolderPath(),
            nm.fileName()
        )

        nm.extension = fileExtension
        saveName = nm.fileName()

        if not os.path.isdir( saveFolder ):
            os.makedirs(saveFolder)
        saveFilePath = RamFileManager.buildPath((
            saveFolder,
            saveName
        ))

        item = RamItem.fromPath(saveFilePath)

        # Load user before scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "before_save_template" in dir(m):
                okToContinue = m.before_save_template( saveFilePath, item, step, templateName )
                if okToContinue is False:
                    log("A Script interrupted the save template process: " + s, LogLevel.Info)
                    return -1

        # Add-on registered scripts
        for script in self.saveTemplateScripts:
            okToContinue = script( saveFilePath, item, step, templateName )
            if okToContinue is False:
                return -1

        # Load user scripts
        for s in SETTINGS.userScripts:
            if not os.path.isfile(s):
                log("Sorry, I can't find and run this user script: " + s, LogLevel.Critical)
                continue
            m = load_module_from_path(s)
            if "on_save_template" in dir(m):
                okToContinue = m.on_save_template( saveFilePath, item, step, templateName )
                if okToContinue is False:
                    log("A Script interrupted the save template process: " + s, LogLevel.Info)
                    return -1

        log('Template saved as: ' + saveName + ' in ' + saveFolder)
        self.addToRecentFiles( saveFilePath )
        return 0
