"""A searchable List widget"""

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

class RamSearchListWidget( qw.QWidget ):
    """A searchable List widget"""

    def __init__(self, listWidget:qw.QListWidget=None, parent = None):
        super(RamSearchListWidget,self).__init__(parent)

        layout = qw.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(3)

        self.searchEdit = qw.QLineEdit(self)
        self.searchEdit.setPlaceholderText("Search...")
        layout.addWidget(self.searchEdit)

        if not listWidget:
            self.list = qw.QListWidget()
        else:
            self.list = listWidget
        layout.addWidget(listWidget)

        self.searchEdit.textChanged.connect( self.__search )

    @qc.Slot()
    def __search(self, search:str):
        search = search.lower()
        for i in range(0, self.list.count()):
            item = self.list.item(i)
            item.setHidden(
                search != '' and search not in item.text().lower()
                )

    def listWidget(self):
        """The list widget"""
        return self.list
    
