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

import time
import json
import yaml
import re
import os
import uuid as UUID
from .daemon_interface import RamDaemonInterface
from .logger import log
from .file_info import RamFileInfo
from .logger import log
from .constants import LogLevel

DAEMON = RamDaemonInterface.instance()
RE_UUID = re.compile("^[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+$")

class RamObject(object):
    """The base class for most of Ramses objects."""

    @staticmethod
    def isUuid( string ):
        if string is None:
            return False
        if not isinstance(string, str):
            return False
        if RE_UUID.match(string):
            return True
        return False

    @staticmethod
    def getUuid( obj ):
        from .file_manager import RamFileManager

        if isinstance( obj, RamObject ):
            uuid = obj.uuid()
        elif obj is None:
            return ''
        else:
            uuid = obj

        return uuid

    @staticmethod
    def getShortName( obj ):
        if RamObject.isUuid( obj ):
            obj = RamObject(obj)
        if obj is None:
            return ""
        if isinstance(obj, RamObject):
            return obj.shortName()
        # Must already be a short name
        return obj

    @staticmethod
    def parseSettings( as_str, fmt='yaml', settingsName="settings" ):
        """

        """
        if fmt == 'str':
            return as_str

        if fmt == 'yaml':
            try:
                as_yaml = yaml.safe_load( as_str )
            except yaml.scanner.ScannerError as err:
                log("Sorry, there is a syntax error in the " + settingsName + ".\nSee the console for more details.",
                    LogLevel.Critical)
                print(err)
                return {}
            if not as_yaml or (
                    not isinstance(as_yaml, dict) and
                    not isinstance(as_yaml, list) and
                    not isinstance(as_yaml, tuple)
                ):
                log("It seems the "+ settingsName + " are empty or can't be read correctly",
                    LogLevel.Info)
                return {}
            return as_yaml

        if fmt == 'json':
            try:
                as_json = json.loads(as_str)
            except json.decoder.JSONDecodeError as err:
                log("Sorry, there is a syntax error in the " + settingsName + ".\nSee the console for more details.",
                    LogLevel.Critical)
                print(err)
                return {}
            return as_json

        return None

    def __init__( self, uuid="", data = None, create=False, objectType="RamObject" ):
        """
        Args:
            uuid (str): The object's uuid
        """

        self.__objectType = objectType

        if uuid == "" and not create:
            self.__virtual = True
        else:
            self.__virtual = False

        if uuid == "":
            uuid = str(UUID.uuid4())
        self.__uuid = uuid

        if isinstance(data, str):
            data = json.loads(data)

        if data:
            self.__data = data
            self.__cacheTime = time.time()
        else:
            self.__data = {}
            self.__cacheTime = 0

        if create:
            reply = DAEMON.create( self.__uuid, self.__data, objectType )
            if not DAEMON.checkReply(reply):
                log("I can't create this object.")

        self.__project = None

    def uuid( self ):
        """Returns the uuid of the object"""
        return self.__uuid

    def data( self ):
        """Gets the data for this object"""
        if self.__virtual:
            return self.__data

        # Check if the cached data is recent enough
        # there's a 2-second timeout to not post too many queries
        # and improve performance
        # ==== DISABLED: The cache system has been moved
        # ==== in the the data interface class
        # cacheElapsed = time.time() - self.__cacheTime
        # if self.__data and cacheElapsed < 2:
        #     return self.__data

        # Get the data from the daemon
        self.__data = DAEMON.getData( self.__uuid, self.__objectType )

        # ==== DISABLED: The cache system has been moved
        # ==== in the the data interface class
        # if data:
        #     self.__data = data
        #     self.__cacheTime = time.time()

        return self.__data

    def setData( self, data):
        """Saves the new data for the object"""
        if isinstance(data, str):
            data = json.loads(data)

        self.__data = data
        self.__cacheTime = time.time()

        if not self.__virtual:
            DAEMON.setData( self.__uuid, data, self.__objectType )

    def get(self, key, default = None):
        """Get a specific value in the data"""
        data = self.data()
        return data.get(key, default)

    def set(self, key, value):
        """Sets a new value in the object data"""
        data = self.data()
        data[key] = value
        self.setData(data)

    def project(self):
        """The current project"""
        if self.__project == None:
            self.__project = DAEMON.getProject()
        return self.__project

    def projectShortName(self):
        """The current project ID"""
        p = self.project()
        if p is None:
            return "Unkown"
        return p.shortName()

    def name( self ):
        """
        Returns:
            str
        """
        return self.get('name', 'Unknown Object')

    def shortName( self ):
        """
        Returns:
            str
        """
        return self.get('shortName', 'Unknown')

    def comment( self ):
        """
        Returns:
            str
        """
        return self.get('comment', '')

    def setComment( self, comment ):
        """Sets a new comment"""
        self.set("comment", comment)

    def color( self ):
        """Returns the color as (R,G,B)"""
        colorName = self.colorName().lstrip("#")
        return tuple(int(colorName[i:i+2], 16) for i in (0, 2, 4))

    def colorName(self):
        """Returns the color as #000000"""
        return self.get('color', '#e3e3e3')

    def settings( self, fmt="str" ):
        """Returns the settings of this object"""

        as_str = self.get("settings", "")
        return self.parseSettings(
            as_str,
            fmt,
            self.shortName() + " step general settings"
            )

    def folderPath( self ):
        """Returns the folder corresponding to this object"""
        if self.__virtual:
            return self.get("folderPath", "")

        p = DAEMON.getPath( self.__uuid, self.__objectType )

        if p != "" and not os.path.isdir( p ):
            try:
                os.makedirs( p )
            except:
                return ""
        return p       

    def virtual( self ):
        """Checks if this object is virtual"""
        return self.__virtual

    def __str__( self ):
        n = self.shortName()
        if self.name() != '':
            if n != '': n = n + " | "
            n = n + self.name()
        return n

    def __eq__(self, other):
        if isinstance(other, RamObject):
            try:
                return self.__uuid == other.uuid()
            except:
                return False
        # Test UUID or shortname
        if other == self.__uuid:
            return True
        if other == self.shortName():
            return True
        return False
