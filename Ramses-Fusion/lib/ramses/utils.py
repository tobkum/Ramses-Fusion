# -*- coding: utf-8 -*-
"""General Utils Functions"""

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

import importlib.util
import sys
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen
from json import loads, dumps
from socket import timeout
import platform
import ssl
from uuid import uuid4
from .logger import log, LogLevel

def getDate( e ):
    """Used in RamItem.getStepHistory to sort the list"""
    return e.date

def escapeRegEx( string ):
    """Escapes reserved RegEx characters from a string"""
    reservedChars = "[.*+-?^=!:${|}[]\\/()"
    result = ""
    for char in string:
        if char in reservedChars:
            result = result + "\\" + char
        else:
            result = result + char
    return result

def intToStr( i, numDigits=3):
    """Converts an int to a string, prepending zeroes"""
    intStr = str(i)
    while len(intStr) < numDigits:
        intStr = '0' + intStr
    return intStr

def removeDuplicateObjectsFromList( l ):
    """Removes duplcates from a list"""
    newList = []
    for i in l:
        if not i in newList:
            newList.append(i)
    return newList

def load_module_from_path( py_path ):
    """Loads a py file as a module and returns the new module's namespace"""
    user_module_uuid = uuid4()
    user_module_name = "dupyf_user_module." + user_module_uuid.hex
    user_module_spec = importlib.util.spec_from_file_location(user_module_name, py_path)
    user_module = importlib.util.module_from_spec(user_module_spec)
    sys.modules[user_module_name] = user_module
    user_module_spec.loader.exec_module(user_module)
    return user_module

def checkUpdate(url, toolName, version, host, hostVersion, preRelease = False, language = "en"):
    """Checks if an update is available"""

    from .ramses import Ramses

    # Check os
    os  = platform.system()
    if os == "Windows":
        os = "win"
    elif os == "Darwin":
        os = "mac"
    elif os == "Linux":
        os = "linux"

    args = {
        "name": toolName,
        "version": version,
        "os": os,
        "osVersion": platform.version(),
        "host": host,
        "hostVersion": hostVersion,
        "languageCode": language,
    }

    if preRelease:
        args["preRelease"] = ""

    log("Checking for update...")
    log("Here's the data sent to the server:\n"+dumps(args), LogLevel.DataSent)

    response = request(url, args, False)
    try:
        return loads(response)
    except:
        return {}

def request(url, args=None, secured=True, timeout=4):
    """Builds a GET request with the args"""

    response = ""

    if args:
        first = True
        for arg in args:
            if first:
                url = url + '?'
                first = False
            else:
                url = url + '&'
            url = url + arg
            val = args[arg]
            if val != "":
                url = url + '=' + quote(val, safe='')

    log("GET request: " + url, LogLevel.Debug)

    try:
        response = urlopen(url, timeout=timeout)
    except URLError as error:
        if not secured and not isinstance(error.reason, timeout):
            sslContext = ssl._create_unverified_context()
            try:
                response = urlopen(url, context=sslContext, timeout=timeout)
            except URLError:
                pass

    response_data = ""
    try:
        response_data = response.read()
        log("Server response:\n" + str(response_data), LogLevel.DataReceived)
    except Exception as error:
        response_data = "invalid_data"
        log("Server response can't be read.\n"+str(error), LogLevel.Debug)

    return response_data
