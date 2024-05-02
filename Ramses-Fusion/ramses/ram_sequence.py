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

from .ram_object import RamObject
from .daemon_interface import RamDaemonInterface

DAEMON = RamDaemonInterface.instance()

class RamSequence( RamObject ):

    def __init__( self, uuid="", data = None, create=False ):
        """
        Args:
            uuid (str)
        """
        super(RamSequence, self).__init__( uuid, data, create, "RamSequence" )

    def project(self):
        """Returns the project this sequence belongs to
        Returns:
            RamProject"""
        from .ram_project import RamProject
        uuid = self.get("project", "")
        if uuid != "":
            return RamProject(uuid)
        return None

    def shots(self):
        """Gets the list of shots contained in this sequence
        Returns:
            str[]"""

        return DAEMON.getShots("", self.uuid())
    
    def width( self ):
        """The sequence width in pixels
        Returns:
            int"""
        
        if self.get("overrideResolution"):
            return self.get("width", 1920)
        project = self.project()
        if project:
            return project.width()
        return 1920
    
    def height( self ):
        """The sequence height in pixels
        Returns:
            int"""
        
        if self.get("overrideResolution"):
            return self.get("height", 1080)
        project = self.project()
        if project:
            return project.height()
        return 1080
    
    def framerate( self ):
        """The sequence framerate
        Returns:
            float
        """

        if self.get("overrideFramerate"):
            return self.get("framerate", 24.0)
        project = self.project()
        if project:
            return project.framerate()
        return 24.0

