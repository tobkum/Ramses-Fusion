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

import sys
import os

# Make sure yaml is available
yaml_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'yaml'
    )
if os.path.isdir( yaml_path ):
    sys.path.append( yaml_path )

from .logger import log, printException
from .ram_settings import RamSettings
from .constants import ItemType, Log, LogLevel, StepType, UserRole, FileNames
from .ram_object import RamObject
from .ram_state import RamState
from .ram_filetype import RamFileType
from .ram_pipe import RamPipe
from .ram_pipefile import RamPipeFile
from .ram_user import RamUser
from .ram_status import RamStatus
from .ramses import Ramses
from .ram_item import RamItem
from .ram_shot import RamShot
from .ram_asset import RamAsset
from .ram_project import RamProject
from .ram_step import RamStep
from .file_manager import RamFileManager
from .metadata_manager import RamMetaDataManager
from .file_info import RamFileInfo
from .daemon_interface import RamDaemonInterface
from .ram_host import RamHost
from . import utils as RamUtils

RAMSES = Ramses.instance()
RAM_SETTINGS = RAMSES.settings()
