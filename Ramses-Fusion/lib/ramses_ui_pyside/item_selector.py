"""! @brief A selectable and filterable list of items (Shots/Assets)
 @file item_selector.py
 @section authors Author(s)
  - Created by Nicolas Dufresne on 10/30/2024 .
"""

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
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc

from ramses import RAMSES, ItemType, RamItem

from ramses_ui_pyside.object_combobox import RamObjectBox
from ramses_ui_pyside.object_listwidget import RamObjectListWidget
from ramses_ui_pyside.search_list import RamSearchListWidget

class RamItemSelectWidget( qw.QWidget ):
    """A selectable and filterable list of items (Shots/Assets)"""

    currentItemChanged = qc.Signal(RamItem)

    def __init__(self, parent:qw.QWidget=None):
        """!
        @brief Creates the item list
        """

        super(RamItemSelectWidget, self).__init__(parent)

        self.__widget_setupUi()
        self.__widget_connectEvents()

    def __widget_setupUi(self):

        layout = qw.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(3)

        self.groupBox = RamObjectBox()
        self.groupBox.setUseNone()
        layout.addWidget(self.groupBox)

        self.list = RamObjectListWidget()
        layout.addWidget(RamSearchListWidget(self.list))

    def __widget_connectEvents(self):
        self.groupBox.currentIndexChanged.connect( self.__updateList )
        self.list.currentItemChanged.connect( self.__itemChanged )

    @qc.Slot()
    def __updateList(self):

        items = ()
        if self.__type == ItemType.SHOT:
            items = RAMSES.project().shots(
                sequence=self.groupBox.currentObject(),
                lazyLoading=False
                )
        elif self.__type == ItemType.ASSET:
            items = RAMSES.project().assets(
                assetGroup=self.groupBox.currentObject(),
                lazyLoading=False
                )

        self.list.setObjects(items)

    @qc.Slot()
    def __itemChanged(self):
        self.currentItemChanged.emit(self.currentItem())

    def setType(self, type:ItemType):
        """Set the type of items to list (shots or assets)"""
        self.__type = type
        if self.__type == ItemType.SHOT:
            self.setGroups(RAMSES.project().sequences(lazyLoading=False))
        elif self.__type == ItemType.ASSET:
            self.setGroups(RAMSES.project().assetGroups(lazyLoading=False))
        self.__updateList()

    def setGroups(self, groups:list):
        """Sets/Overrides the group list"""
        self.groupBox.setObjects(groups)

    def setGroup(self, group):
        """Sets the current group"""
        self.groupBox.setCurrentObject(group)

    def currentItem(self):
        """Gets the current item (asset or shot)"""
        return self.list.currentObject()

    def setCurrentItem(self, item):
        """Sets the current item (asset or shot)"""
        self.list.setCurrentObject(item)

if __name__ == "__main__":
    w = RamItemSelectWidget()
    w.setType(ItemType.ASSET)
    w.show()
