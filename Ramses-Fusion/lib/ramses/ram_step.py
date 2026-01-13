# -*- coding: utf-8 -*-

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
from .ram_object import RamObject
from .logger import log
from .constants import StepType, FolderNames, LogLevel
from .file_manager import RamFileManager
from .file_info import RamFileInfo
from .daemon_interface import RamDaemonInterface

# Keep the daemon at hand
DAEMON = RamDaemonInterface.instance()

class RamStep( RamObject ):
    """A step in the production of the shots or assets of the project."""

    @staticmethod
    def fromPath( path ):
        """Creates a step from any path, if possible
        by extracting step info from the path"""
        from .ram_status import RamStatus
        from .ramses import Ramses
        RAMSES = Ramses.instance()

        # First, try to see if this is the path of a step
        uuid = DAEMON.uuidFromPath( path, "RamStep" )

        if uuid != "":
            return RamStep(uuid)

        # Now, try to see if this is the path of a status
        status = RamStatus.fromPath( path )
        if status:
            return status.step()

        # Let's use the file name
        nm = RamFileInfo()
        nm.setFilePath(path)
        # Get the corresponding step
        step = RamStep.fromName(nm.step)
        if step:
            return step

        log( "The given path does not belong to a step", LogLevel.Debug )
        return None

    @staticmethod
    def fromName( shortName:str, name='', stepType=StepType.ALL):
        """Returns a step using its shortname and name"""
        steps = DAEMON.getSteps(stepType)
        for step in steps:
            if step.shortName() != shortName:
                continue
            if name == '':
                return step
            if step.name() == name:
                return step
        return None

    @staticmethod
    def fromString( stepStr:str ):
        """Returns a step from its string as returned by str(RamStep)"""
        stepList = stepStr.split(' | ')
        if len(stepList) < 2:
            return RamStep.fromName( stepList[0] )

        return RamStep.fromName(stepList[0], stepList[1])

    def __init__( self, uuid="", data = None, create=False ):
        """
        Args:
            uuid (str)
        """
        super(RamStep, self).__init__( uuid, data, create, "RamStep" )

    def inputPipes( self ):
        """The pipes coming to this step"""
        project = self.project()
        if project is None:
            return ()

        inputPipes = []
        pipes = project.pipes()

        for pipe in pipes:
            if pipe.inputStep() == self:
                inputPipes.append(pipe)

        return inputPipes

    def outputPipes( self ):
        """The pipes going out of this step"""
        project = self.project()
        if project is None:
            return ()

        outputPipes = []
        pipes = project.pipes()

        for pipe in pipes:
            if pipe.outputStep() == self:
                outputPipes.append(pipe)

        return outputPipes

    def templatesFolderPath( self ):
        """The path to the template files of this step
        Returns:
            str
        """

        templatesFolder = ""

        stepFolder = self.folderPath()

        if stepFolder == '':
            return ''

        templatesFolder = RamFileManager.buildPath((
            stepFolder,
            FolderNames.stepTemplates
        ))

        if not os.path.isdir(templatesFolder):
            os.makedirs(templatesFolder)

        return templatesFolder

    def templatesPublishPath( self ):
        """The path to the folder where templates are published"""
        templatesFolderPath = self.templatesFolderPath()
        if templatesFolderPath == '':
            return ''

        folder = RamFileManager.buildPath((
            templatesFolderPath,
            FolderNames.publish
        ))

        if not os.path.isdir(folder):
            os.makedirs(folder)

        return folder

    def templatesPublishedVersionFolderPaths( self ):
        """The published folders for the templates of this step"""
        templatesPublishPath = self.templatesPublishPath()

        versionFolders = []

        for f in os.listdir(templatesPublishPath):
            folderPath = RamFileManager.buildPath(( templatesPublishPath, f ))
            if not os.path.isdir(folderPath): continue
            versionFolders.append( folderPath )

        versionFolders.sort(key=RamFileManager._publishVersionFoldersSorter)

        return versionFolders

    def stepType( self ):
        """The type of this step, one of StepType.PRE_PRODUCTION, StepType.SHOT_PRODUCTION,
            StepType.ASSET_PRODUCTION, StepType.POST_PRODUCTION

        Returns:
            enumerated value
        """

        stepType = self.get("type", "asset")
        if stepType == "asset":
            return StepType.ASSET_PRODUCTION
        elif stepType == "shot":
            return StepType.SHOT_PRODUCTION
        elif stepType == "pre":
            return StepType.PRE_PRODUCTION
        elif stepType == "post":
            return StepType.POST_PRODUCTION
        return StepType.ALL

    def publishSettings(self, fmt="str"):
        """Returns the publish settings, as a string,
        which should be a yaml document, according to the Ramses guidelines.
        But this string is user-defined and can be anything set in the Ramses Client."""

        as_str = self.get("publishSettings", "")
        return self.parseSettings(
            as_str,
            fmt,
            self.shortName() + " step general settings"
            )

    def generalSettings(self, fmt="str"):
        """Returns the step custom settings.

        The return format can be:
        - 'str': which should be a yaml document, according to the Ramses guidelines.
        But this string is user-defined and can be anything set in the Ramses Client.
        - 'yaml' or 'json': returns a python dict after parsing the string. Use in conjunction with
        print error (instead of raising) for a non blocking parse just automatically printing a nice 
        explanation to the user. In case of error, returns None

        return str or dict or None
        """
        as_str = self.get("customSettings", "")
        return self.parseSettings(
            as_str,
            fmt,
            self.shortName() + " step general settings"
            )

    def setPublishSettings(self, settings):
        """Sets new publish settings for this step"""
        self.set("publishSettings", settings)

    def setGeneralSettings(self, settings):
        """Sets new general settings for this step"""
        self.set("customSettings", settings)

    def importSettings(self, fmt="str"):
        """Returns the import settings, as a string,
        which should be a yaml document, according to the Ramses guidelines.
        But this string is user-defined and can be anything set in the Ramses Client."""

        as_str = self.get("importSettings", "")
        return self.parseSettings(
            as_str,
            fmt,
            self.shortName() + " step import settings"
            )
    
    def setImportSettings(self, settings):
        """Sets new import settings for this step"""
        self.set("importSettings", settings)