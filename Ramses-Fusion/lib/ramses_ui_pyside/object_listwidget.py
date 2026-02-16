"""A List widget for RamObjects"""

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

class RamObjectListWidget( qw.QListWidget ):
    """A List widget for RamObjects"""

    def __init__(self, parent = None):
        super(RamObjectListWidget,self).__init__(parent)

    def setCurrentObject(self, ramObject):
        """Sets the current ramobject"""
        i = 0
        while i < self.count():
            listItem = self.item(i)
            item = listItem.data(qc.Qt.UserRole)
            sel = item == ramObject
            listItem.setSelected(sel)
            if sel:
                self.scrollToItem(listItem, qw.QAbstractItemView.PositionAtCenter)
            i = i+1

    def currentObject(self):
        """Gets the current ramobject"""

        listItem = self.currentItem()
        if not listItem:
            return None
        
        return listItem.data(qc.Qt.UserRole)

    def setObjects(self, objects:list):
        """!
        @brief Set the list of objects

        Parameters : 
            @param objects : list => The RamObject list
        """

        self.clear()

        for obj in objects:
            n = str(obj)
            listItem = qw.QListWidgetItem( n )
            listItem.setData( qc.Qt.UserRole, obj )
            self.addItem( listItem )
