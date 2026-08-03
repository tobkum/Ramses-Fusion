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

import os, json, time, tempfile
from datetime import datetime

from .file_manager import RamFileManager
from .constants import FileNames, MetaDataKeys, LogLevel
from .logger import log

class RamMetaDataManager():
    """A Class to get/set metadata from files
    
    Ramses will use a single sidecar file in the folder where the file is contained;
    thus the metadata used by Ramses is set on a per-folder basis, and is not copied when a file is copied/moved:
    it does not make sens for Ramses to have the same metadata when a file is moved."""

    @staticmethod
    def appendHistoryDate(filePath):
        """Sets a new entry in the modification history"""
        history = RamMetaDataManager.getValue(filePath, MetaDataKeys.MODIFICATION_HISTORY)
        if history is None:
            history = []
        timeStamp = time.mktime( datetime.now().timetuple() )
        history.append( int(timeStamp) )
        RamMetaDataManager.setValue(filePath, MetaDataKeys.MODIFICATION_HISTORY, history)

    @staticmethod
    def getValue(filePath, key):
        """Gets the value of a specific key for the file"""
        # copyToVersion()/restoreVersionFile() and friends can hand back None;
        # os.path.isfile(None) raises TypeError (isfile only catches OSError /
        # ValueError), so guard before touching the filesystem.
        if not filePath:
            return None
        if not os.path.isfile(filePath):
            return None
        data = RamMetaDataManager.getFileMetaData( filePath )
        if key in data:
            return data[key]
        return None

    @staticmethod
    def getPipeType(filePath):
        pipeType = RamMetaDataManager.getValue(filePath, MetaDataKeys.PIPE_TYPE)
        if pipeType is None: return ''
        return pipeType

    @staticmethod
    def setPipeType(filePath, pipeType):
        RamMetaDataManager.setValue(filePath, MetaDataKeys.PIPE_TYPE, pipeType)

    @staticmethod
    def getResource(filePath):
        resource = RamMetaDataManager.getValue(filePath, MetaDataKeys.RESOURCE)
        if resource is None: return ''
        return resource

    @staticmethod
    def setResource(filePath, resource):
        RamMetaDataManager.setValue(filePath, MetaDataKeys.RESOURCE, resource)

    @staticmethod
    def setValue(filePath, key, value):
        """Sets a value for a specific key for the file"""
        if not filePath:
            log("Metadata write skipped: no file path.", LogLevel.Debug)
            return
        # file data
        fileData = RamMetaDataManager.getFileMetaData(filePath)
        # update comment
        fileData[key] = value
        # re-set file data
        RamMetaDataManager.setFileMetaData( filePath, fileData )

    @staticmethod
    def getVersionFilePath( filePath ):
        """Gets the version file for the file"""
        version = RamMetaDataManager.getValue(filePath, MetaDataKeys.VERSION_FILE)
        if version is None:
            return -1
        return version

    @staticmethod
    def setVersionFilePath( filePath, versionfilePath ):
        """Sets a version file for the file"""
        RamMetaDataManager.setValue(filePath, MetaDataKeys.VERSION_FILE, versionfilePath)

    @staticmethod
    def setState( filePath, state):
        RamMetaDataManager.setValue(filePath, MetaDataKeys.STATE, state)

    @staticmethod
    def getState( filePath ):
        state = RamMetaDataManager.getValue(filePath, MetaDataKeys.STATE)
        if state is None: return ''
        return state

    @staticmethod
    def getDate( filePath ):
        """Gets the date for the file"""
        return RamMetaDataManager.getValue(filePath, MetaDataKeys.DATE)

    @staticmethod
    def setDate( filePath, date ):
        """Sets a date for the file"""
        if date is None: date = datetime.now()
        if not isinstance( date, int ): date = time.mktime( date.timetuple() )
        RamMetaDataManager.setValue(filePath, MetaDataKeys.DATE, date)

    @staticmethod
    def getVersion( filePath ):
        """Gets the version for the file"""
        version = RamMetaDataManager.getValue(filePath, MetaDataKeys.VERSION)
        if version is None:
            return -1
        return version

    @staticmethod
    def setVersion( filePath, version ):
        """Sets a version for the file"""
        RamMetaDataManager.setValue(filePath, MetaDataKeys.VERSION, version)

    @staticmethod
    def getComment( filePath ):
        """Gets the comment for the file"""
        comment = RamMetaDataManager.getValue(filePath, MetaDataKeys.COMMENT)
        if comment is None:
            return ''
        return comment

    @staticmethod
    def setComment( filePath, comment):
        """Sets a comment for the file"""
        RamMetaDataManager.setValue(filePath, MetaDataKeys.COMMENT, comment)

    @staticmethod
    def getMetaDataFile( path ):
        """Gets the metadata .json file for the given path"""
        folder = path
        # if it's a file or if it does not exist (yet, it may be a file being created, due to threading, it may not be available yet)
        if os.path.isfile(folder) or not os.path.exists(folder):
            folder = os.path.dirname(folder)
        if not os.path.isdir(folder):
            raise ValueError("The given path does not exist: " + folder)
                
        return RamFileManager.buildPath((
            folder,
            FileNames.META_DATA
        ))

    @staticmethod
    def getFileMetaData( filePath ):
        """Gets metadata for a specific file"""
        data = RamMetaDataManager.getMetaData( filePath )
        fileName = os.path.basename(filePath)
        if fileName in data:
            return data[fileName]
        return {}

    @staticmethod
    def getMetaData( folderPath ):
        """Reads and returns the metadata for the folder containing the given path."""
        file = RamMetaDataManager.getMetaDataFile( folderPath )
        if not os.path.exists( file ):
            return {}

        data = {}
        for _attempt in range(3):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                break
            except (json.JSONDecodeError, IOError):
                if _attempt < 2:
                    time.sleep(0.01 * (2 ** _attempt))
                    continue
                return {}

        return data

    @staticmethod
    def setFileMetaData(filePath, fileData):
        """Sets the metadata for the given file using the given dict."""
        if not filePath:
            log("Metadata write skipped: no file path.", LogLevel.Debug)
            return
        folderPath = os.path.dirname(filePath)
        fileName = os.path.basename(filePath)
        data = RamMetaDataManager.getMetaData( folderPath )
        metaFile = RamMetaDataManager.getMetaDataFile( folderPath )
        # An empty dict on top of a non-empty sidecar means the read failed,
        # not that the folder has no metadata: refuse to overwrite. (2 bytes is
        # an empty "{}"; anything larger holds real entries.)
        if not data and os.path.isfile(metaFile) and os.path.getsize(metaFile) > 2:
            log(
                "Metadata sidecar could not be read (locked or corrupt); "
                "skipping this update rather than overwriting the folder's "
                "existing metadata: " + metaFile,
                LogLevel.Critical
            )
            return
        data[fileName] = fileData
        RamMetaDataManager.setMetaData( folderPath, data )

    @staticmethod
    def setMetaData( path, data ):
        """Sets the metadata for the given path using the given dict"""
        file = RamMetaDataManager.getMetaDataFile( path )

        # Atomic write: save to temp file, then rename
        folder = os.path.dirname(file)
        os.makedirs(folder, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(dir=folder, prefix=".ram_meta_", suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding="utf8") as tf:
                json.dump(data, tf, indent=4)
            os.replace(temp_path, file)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
