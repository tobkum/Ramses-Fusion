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

import socket
import json
import time
import os
from .logger import log, printException
from .constants import LogLevel, Log, StepType

class RamDaemonCachedObject( ):

    def __init__(self, key:str, data, category:str ):
        self.__key = key
        self.__category = category
        self.__data = data
        self.__time = time.time()

    def key(self):
        return self.__key
        
    def category(self):
        return self.__category

    def data(self):
        return self.__data

    def time(self):
        return self.__time

    def elapsed(self):
        return time.time() - self.__time

class RamDaemonInterface( object ):
    """The Class used to communicate with the Ramses Daemon

    Attributes:
        port: int.
            The listening port of the daemon
        online: bool (read-only).
            True if the Daemon is available
    """

    _instance = None
    _address = 'localhost'
    _cache:dict = {}

    @staticmethod
    def checkReply( obj ):
        if not obj:
            return {}
        if obj['accepted'] and obj['success'] and obj['content'] is not None:
            return obj['content']
        return {}

    @classmethod
    def instance( cls ):
        from .ram_settings import RamSettings

        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._port = RamSettings.instance().ramsesClientPort

        return cls._instance

    def __init__(self):
        """
        Args:
            port: int.
        """
        raise RuntimeError("RamDaemonInterface can't be initialized with `RamDaemonInterface()`, it is a singleton. Call RamDaemonInterface.instance() or Ramses.instance().daemonInterface() instead.")

    def online(self):
        """Checks if the daemon is available"""
        return self.__testConnection()

    def ping(self):
        """Gets the version and current user of the ramses daemon.

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.

        Returns: dict.
            Read http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        """
        return self.__post('ping', 65536)

    def raiseWindow(self):
        """Raises the Ramses Client application main window.

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        """
        self.__post('raise')

    def getRamsesFolderPath(self):
        """Gets the path of the main Ramses folder"""
        reply = self.__post( "getRamsesFolder", 65536 )
        content = self.checkReply(reply)
        return content.get("path", "")

    def getObjects( self, objectType ):
        """Gets the list of the objects

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.

        Returns: list of RamObject.
        """

        from .ram_asset import RamAsset
        from .ram_assetgroup import RamAssetGroup
        from .ram_filetype import RamFileType
        from .ram_item import RamItem
        from .ram_object import RamObject
        from .ram_pipe import RamPipe
        from .ram_pipefile import RamPipeFile
        from .ram_project import RamProject
        from .ram_sequence import RamSequence
        from .ram_shot import RamShot
        from .ram_state import RamState
        from .ram_status import RamStatus
        from .ram_step import RamStep
        from .ram_user import RamUser

        reply = self.__post(
            (
                "getObjects",
                ("type", objectType)
            ),
            65536 )
        content = self.checkReply(reply)
        objs = content.get("objects", ())
        objects = []
        for obj in objs:
            uuid = obj.get("uuid", "")
            data = obj.get("data", {})
            # Cache data
            self.__cacheObjectData(uuid, data)

            o = None
            if objectType == "RamObject":
                o = RamObject( uuid, data=data)
            elif objectType == "RamAsset":
                o = RamAsset( uuid, data=data)
            elif objectType == "RamAssetGroup":
                o = RamAssetGroup( uuid, data=data)
            elif objectType == "RamFileType":
                o = RamFileType( uuid, data=data)
            elif objectType == "RamItem":
                o = RamItem( uuid, data=data)
            elif objectType == "RamPipe":
                o = RamPipe( uuid, data=data)
            elif objectType == "RamPipeFile":
                o = RamPipeFile( uuid, data=data)
            elif objectType == "RamProject":
                o = RamProject( uuid, data=data)
            elif objectType == "RamSequence":
                o = RamSequence( uuid, data=data)
            elif objectType == "RamShot":
                o = RamShot( uuid, data=data)
            elif objectType == "RamState":
                o = RamState( uuid, data=data)
            elif objectType == "RamStatus":
                o = RamStatus( uuid, data=data)
            elif objectType == "RamStep":
                o = RamStep( uuid, data=data)
            elif objectType == "RamUser":
                o = RamUser( uuid, data=data)
            if o:
                objects.append(o)
        return objects

    def getShots(self, sequenceUuid="", includeData=False):
        """Gets the list of shots for this project"""

        from .ram_shot import RamShot
        
        includeDataStr = "0"
        if includeData:
            includeDataStr = "1"

        shots = []

        reply =  self.__post(
            (
                "getShots",
                ('sequenceUuid', sequenceUuid),
                ('includeData', includeDataStr)
            ),
            bufsize=6553600,
            timeout=5
        )

        content = self.checkReply(reply)
        shotList = content.get("shots", ())
        for shot in shotList:
            if includeData:
                uuid = shot.get('uuid', "")
                data = shot.get('data', {})
                ramShot = RamShot( uuid, data=data )
                # Cache Data
                self.__cacheObjectData(uuid, data)
            else:
                ramShot = RamShot( shot )
            shots.append( ramShot )
        return shots

    def getAssetGroups(self):
        """Gets the list of asset groups for this project"""

        from .ram_assetgroup import RamAssetGroup

        assetGroups = []

        reply =  self.__post(
            (
                "getAssetGroups",
            ),
            65536 )

        content = self.checkReply(reply)
        agListUuid = content.get("assetGroups", ())
        for uuid in agListUuid:
            ag = RamAssetGroup( uuid )
            assetGroups.append( ag )
        return assetGroups

    def getSequences(self):
        """Gets the list of sequences for this project"""

        from .ram_sequence import RamSequence

        sequences = []

        reply =  self.__post(
            (
                "getSequences",
            ),
            65536 )

        content = self.checkReply(reply)
        seqListUuid = content.get("sequences", ())
        for uuid in seqListUuid:
            seq = RamSequence( uuid )
            sequences.append( seq )
        return sequences

    def getAssets(self, groupUuid="", includeData=False):
        """Gets the list of assets for this project"""

        from .ram_asset import RamAsset

        includeDataStr = "0"
        if includeData:
            includeDataStr = "1"

        assets = []

        reply =  self.__post(
            (
                "getAssets",
                ('groupUuid', groupUuid),
                ('includeData', includeDataStr)
            ),
            bufsize=6553600,
            timeout=5 # May be a big list
        )

        content = self.checkReply(reply)
        assetList = content.get("assets", ())
        for asset in assetList:
            if includeData:
                uuid = asset.get('uuid', "")
                data = asset.get('data', {})
                ramAsset = RamAsset( uuid, data=data )
                # Cache Data
                self.__cacheObjectData(uuid, data)
            else:
                ramAsset = RamAsset( asset )

            assets.append( ramAsset )
        return assets

    def getPipes(self):
        """Gets the list of pipes for this project"""

        from .ram_pipe import RamPipe

        pipes = []

        reply =  self.__post(
            (
                "getPipes",
            ),
            65536 )

        content = self.checkReply(reply)
        pipeListUuid = content.get("pipes", ())
        for uuid in pipeListUuid:
            pipe = RamPipe( uuid )
            pipes.append( pipe )
        return pipes

    def getSteps(self, stepType=StepType.ALL):
        """Gets the list of steps for this project"""

        from .ram_step import RamStep

        steps = []

        reply =  self.__post(
            (
                "getSteps",
                ('type', stepType)
            ),
            65536 )

        content = self.checkReply(reply)
        stepListUuid = content.get("steps", ())
        for uuid in stepListUuid:
            step = RamStep( uuid )
            steps.append( step )
        return steps

    def getProject(self):
        """Gets the current project

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        
        Returns: RamProject.
        """

        from .ram_project import RamProject

        reply = self.__post( "getProject", 65536 )
        content = self.checkReply(reply)
        uuid = content.get("uuid", "")
        if uuid == "":
            return None
        data = content.get("data", {})
        return RamProject(uuid, data)

    def getUser(self):
        """Gets the current user"""
        from .ram_user import RamUser
        content = self.checkReply( self.ping() )
        uuid =  content.get("userUuid", "")
        if uuid == "":
            return None
        return RamUser( uuid )

    def getData(self, uuid:str, objectType:str, cacheTimeout=2 ):
        """Gets the data for a specific RamObject.
        This is a cached method, the default cache duration is 2S

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        
        Returns: dict.
        """

        # Check if it is available in the cache
        cache = self.__getCacheObjectData(uuid, cacheTimeout)
        if cache:
            return cache.data()

        reply =  self.__post(
            (
                "getData",
                ('uuid', uuid),
                ('objectType', objectType),
            ),
            65536 )
        content = self.checkReply(reply)
        data = content.get('data', {})
        self.__cacheObjectData(uuid, data)
        return data

    def setData(self, uuid:str, data:str, objectType:str):
        """Sets the data of a specific RamObject.

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        
        Returns: dict.
        """

        if not isinstance(data, str):
            data = json.dumps(data)

        return self.__post( (
            "setData",
            ('uuid', uuid),
            ('data', data),
            ('objectType', objectType),
            ), 65536 )

    def getPath(self, uuid:str, objectType:str, cacheTimeout=30):
        """Gets the path for a specific RamObject.

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        
        Returns: dict.
        """

        # Get in cache
        cache = self.__getCacheObjectPath(uuid, cacheTimeout)
        if cache:
            return cache.data()

        reply =  self.__post( (
            "getPath",
            ('uuid', uuid),
            ('objectType', objectType),
            ), 65536 )
        content = self.checkReply(reply)
        path = content.get("path", "")

        self.__cacheObjectPath(uuid, path)
        return path

    def uuidFromPath(self, path, ramType ):
        """Gets the uuid of an Object using its path.

        Read the Ramses Daemon reference at http://ramses.rxlab.guide/dev/daemon-reference/ for more information.
        
        Returns: dict.
        """

        if path == "":
            return ""

        reply = self.__post( (
            "uuidFromPath",
            ('path', path),
            ('objectType', ramType),
            ), 65536 )
        content = self.checkReply(reply)
        return content.get("uuid", "")

    def create(self, uuid, data, objectType):
        """Creates a new object in the database"""

        if not isinstance(data, str):
            data = json.dumps(data)

        return self.__post( (
            "create",
            ("uuid", uuid),
            ('data', data),
            ("type", objectType)
            ), 65536)

    def getStatus(self, itemUuid, stepUuid):
        """Gets the status of an item & step"""

        from .ram_status import RamStatus

        reply =  self.__post(
            (
                "getStatus",
                ('itemUuid', itemUuid),
                ('stepUuid', stepUuid)
            ),
            65536 )
        content = self.checkReply(reply)
        uuid = content.get("uuid", "")
        if uuid == "":
            return None
        return RamStatus(uuid, content.get("data", {}))

    def setStatusModifiedBy(self, uuid, userUuid = "current"):
        """Sets the user who's modified the status.
        
        If userUuid is 'current', it will be the current user in the Ramses Client
        """

        return self.__post(
            (
                "setStatusModifiedBy",
                ('uuid', uuid),
                ('userUuid', userUuid)
            ),
            65536 )

    def uiShowConsole(self, tab:str="main"):
        """Shows the console tab in the app"""

        return self.__post(
            (
                "uiShowConsole",
                ('tab', tab)
            )
            )

    def uiShowScriptEditor(self):
        """Shows the script editor tab in the app"""

        return self.__post('uiShowScriptEditor')

    def __buildQuery(self, query):
        """Builds a query from a list of args

        Args:
            query: str or tuple.
                If query is a str, it is returned as is.
                If it's a tuple, each item can be either an argument as a string, or a 2-tuple key/value pair.

        Returns: str.
            The query string in the form "key1&key2=value2&key3=value3"
        """

        if isinstance(query, str):
            return query

        queryList = []

        for arg in query:
            if isinstance(arg, str):
                if arg:
                    queryList.append(arg)
            elif len(arg) == 1:
                queryList.append(arg[0])
            elif len(arg) > 1:
                if arg[1] == "":
                    queryList.append(arg[0])
                else:
                    queryList.append( "=".join(arg) )

        return "&".join(queryList)

    def __post(self, query, bufsize = 0, timeout=2):
        """Posts a query and returns a dict corresponding to the json reply
        
        Args:
            query: tuple.
                The list of arguments, which are themselves 2-tuples of key-value pairs (value may be an empty string)
            bufsize: int.
                The maximum amount of data to be received at once is specified by bufsize.
            timeout: int.
                The request timeout in seconds
                
        Returns: dict or None.
            The Daemon reply converted from json to a python dict.
            None if there is an error or the Daemon is unavailable.
        """

        from .ramses import Ramses

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)

        query = self.__buildQuery( query )

        log( query, LogLevel.DataSent)

        try:
            s.connect((self._address, self._port))
        except Exception as e: #pylint: disable=broad-except
            log("Daemon can't be reached", LogLevel.Debug)
            log(str(e), LogLevel.Critical)
            ramses = Ramses.instance()
            ramses.disconnect()
            return

        s.sendall(query.encode('utf-8'))

        if bufsize == 0:
            s.close()
            return None

        data = s.recv(bufsize)
        s.close()

        try:
            obj = json.loads(data)
        except: # pylint: disable=bare-except
            log("Invalid reply data from the Ramses Daemon.", LogLevel.Critical)
            log(str(data), LogLevel.Debug)
            printException()
            obj = {
                'accepted': False,
                'success': False
            }
            return obj

        log (str(data), LogLevel.DataReceived )

        if not obj['accepted']: log("Unknown Ramses Daemon query: " + obj['query'], LogLevel.Critical)
        if not obj['success']: log("Warning: the Ramses Daemon could not reply to the query: " + obj['query'], LogLevel.Debug)       
        if obj['message']: log(obj['message'], LogLevel.Debug)

        return obj

    def __testConnection(self):
        """Checks if the Ramses Daemon is available"""

        data = self.ping()

        if data is None:
            log("Daemon unavailable", LogLevel.Debug)
            return False

        content = data['content']
        if content is None:
            log("Daemon did not reply correctly")
            return False
        if content['ramses'] == "Ramses":
            return True
        if content['ramses'] == "Ramses-Client":
            return True

        log("Invalid content in the Daemon reply", LogLevel.Critical)
        return False

    def __checkUser(self):
        data = self.ping()

        if data is None:
            return False

        if 'content' in data:
            content = data['content']
        else:
            return False

        if content is None:
            return False

        if 'userUuid' in content:
            ok = content['userUuid'] != ""
        else:
            return False

        return ok

    def __noUserReply(self, query):
        log( Log.NoUser, LogLevel.Debug)
        return {
            'accepted': False,
            'success': False,
            'message': Log.NoUser,
            'query': query,
            'content': None
        }

    def __cacheObjectData(self, uuid, data):
        self.__cache('data', uuid, data)

    def __getCacheObjectData(self, uuid, timeout=2):
        return self.__getCache('data', uuid, timeout)

    def __cacheObjectPath(self, uuid, path):
        self.__cache('path', uuid, path)

    def __getCacheObjectPath(self, uuid, timeout=30):
        return self.__getCache('path', uuid, timeout)

    def __cache(self, category, key, data):
        cache = RamDaemonCachedObject(key, data, category)
        if not category in self._cache:
            self._cache[category]  = {}
        self._cache[category][key] = cache

    def __getCache(self, category, key, timeout=-1):
        if not category in self._cache:
            return None
        cat = self._cache[category]
        cache = cat.get(key, None)
        if not cache:
            return None

        if timeout <= 0:
            return cache

        if cache.elapsed() > timeout:
            return None

        return cache
