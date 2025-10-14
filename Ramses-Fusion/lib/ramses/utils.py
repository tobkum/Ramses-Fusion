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
from uuid import uuid4

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
