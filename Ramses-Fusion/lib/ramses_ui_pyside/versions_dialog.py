"""A Simple dialog to select a file version."""

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

import os

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc

from ramses import RamFileInfo, RamMetaDataManager

from ramses_ui_pyside.dialog import RamDialog
from ramses_ui_pyside.search_list import RamSearchListWidget

class RamVersionDialog( RamDialog ):
    """A Simple dialog to select a file version."""

    def __init__(self, versionFiles:list=(), parent = None):
        super(RamVersionDialog,self).__init__(parent)
        self.__setupUi(versionFiles)
        self.__connectEvents()

    def __setupUi(self, versionFiles):
        self.setWindowTitle( "Select a version" )
        self.setMinimumWidth(400)

        self.list = qw.QListWidget()
        self.mainLayout.addWidget( RamSearchListWidget(self.list) )
        self.setVersionFiles(versionFiles)

        self.restoreButton = qw.QPushButton("Restore version")
        self.buttonsLayout.addWidget( self.restoreButton )
        self.cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self.cancelButton )

    def __connectEvents(self):
        self.restoreButton.clicked.connect( self.accept )
        self.cancelButton.clicked.connect( self.reject )

    def setVersionFiles(self, versionFiles:list):
        """Sets the list of versions to be displayed"""

        print(versionFiles)
        for v in versionFiles:
            fileName = os.path.basename( v )
            nm = RamFileInfo()
            if not nm.setFileName( fileName ):
                continue
            comment = RamMetaDataManager.getComment( v )
            itemText = nm.state + ' | ' + str( nm.version )
            if comment != "":
                itemText = itemText + ' | ' + comment
            item = qw.QListWidgetItem( itemText )
            item.setData(qc.Qt.UserRole, v)
            self.list.addItem(item)

    def currentFilePath(self):
        """The selected file path"""
        item = self.list.currentItem()
        if not item:
            return ''
        return item.data(qc.Qt.UserRole)

if __name__ == "__main__":
    d = RamVersionDialog()
    if d.exec_():
        print(d.currentFilePath())
    else:
        print("Cancelled")
