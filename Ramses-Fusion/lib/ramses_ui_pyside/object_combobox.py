# -*- coding: utf-8 -*-
"""A ComboBox for displaying RamObjects"""

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

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtGui as qg
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtGui as qg
    from PySide6 import QtCore as qc

from ramses import RamObject

class RamObjectBox( qw.QComboBox ):
    """A ComboBox for displaying RamObjects"""

    currentObjectChanged = qc.Signal(RamObject)

    def __init__(self, parent = None):
        super(RamObjectBox,self).__init__(parent)

        self.__useNone = False
        self.__noneItemName = 'All'

        self.currentIndexChanged.connect( self.indexChanged )

        pal = self.palette()
        self.defaultColor = pal.color(qg.QPalette.Button)

    @qc.Slot()
    def indexChanged(self, i):
        """Sets the color of the box"""

        color = self.defaultColor

        obj = self.itemData(i)
        if obj:
            colorName = self.itemData(i).colorName()
            color = qg.QColor( colorName )
            # adjust Lightness
            if color.lightness() > 120:
                color.setHsl( color.hue(), color.saturation(), 120)

        pal = self.palette()
        pal.setColor(qg.QPalette.Button, color)
        self.setPalette(pal)

        self.currentObjectChanged.emit(obj)

    def setCurrentObject(self, ramObject):
        """Sets the current ramobject"""
        i = 0
        while i < self.count():
            if self.itemData( i ) == ramObject:
                self.setCurrentIndex( i )
                return
            i = i+1
        self.setCurrentIndex( -1 )

    def currentObject(self):
        """Gets the current ramobject"""
        return self.itemData( self.currentIndex() )

    def setObjects(self, objects:list):
        """!
        @brief Set the list of objects

        Parameters : 
            @param objects : list => The RamObject list
        """
        self.clear()

        if self.__useNone:
            self.addItem(self.__noneItemName, None)

        for obj in objects:
            self.addItem(str(obj), obj)

    def setUseNone(self, noneItemName:str='All'):
        self.__useNone = True
        self.__noneItemName = noneItemName
