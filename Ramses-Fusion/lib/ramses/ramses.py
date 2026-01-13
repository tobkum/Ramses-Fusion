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

    # The Host app
    host = None

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

            log("I'm trying to contact the Ramses Client.", LogLevel.Debug)
            cls._instance.connect()

            cls._offline = True

            cls.host = None

            cls.publishScripts = []
            cls.statusScripts = []
            cls.importScripts = []
            cls.replaceScripts = []
            cls.openScripts = []
            cls.saveTemplateScripts = []

            cls.userScripts = {}

        return cls._instance

    def user(self):
        """The current user.

        Returns:
            RamUser or None
        """
        return DAEMON.getUser()

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
            user = self.user()
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

    def project(self):
        """The current project.

        Returns:
            RamProject or None
        """
        return DAEMON.getProject()

    def defaultState(self):
        """The default state"""
        return self.state('WIP')

    def state(self, stateShortName="WIP"):
        """Gets a specific state.

        Args:
            stateShortName (str, optional): Defaults to "WIP".

        Returns:
            RamState
        """

        from .ram_state import RamState

        if not self._offline:
            stts = self.states()
            for stt in stts:
                if stt.shortName() == stateShortName:
                    return stt
        return RamState(uuid='',data={'shortName': stateShortName, 'name': stateShortName})

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

    def showConsole(self, tab:str="main"):
        """Shows the console in the app"""
        DAEMON.uiShowConsole(tab)

    def showScriptEditor(self):
        """Shows the script editor in the app"""
        DAEMON.uiShowScriptEditor()

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
