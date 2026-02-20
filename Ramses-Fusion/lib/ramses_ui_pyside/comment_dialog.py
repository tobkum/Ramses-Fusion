"""! @brief A Simple dialog to ask for a comment for a file version.
 @file comment_dialog.py
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
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw

from ramses import RamUtils
from ramses_ui_pyside.dialog import RamDialog

class RamCommentDialog( RamDialog ):
    def __init__(self, version:int, comment:str="", parent = None):
        super(RamCommentDialog,self).__init__(parent)
        self.__setupUi(RamUtils.intToStr(version), comment)
        self.__connectEvents()

    def __setupUi(self, version:str, comment:str=""):
        self.setWindowTitle( "Add a comment to the current version ( v"+version+" )" )
        self.setMinimumWidth(400)

        self.textEdit = qw.QLineEdit()
        self.textEdit.setPlaceholderText("New comment")
        self.textEdit.setText(comment)
        self.mainLayout.addWidget(self.textEdit)

        self._saveButton = qw.QPushButton("Add Comment and Save")
        self.buttonsLayout.addWidget( self._saveButton )
        self._cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self._cancelButton )

    def __connectEvents(self):
        self._saveButton.clicked.connect( self.accept )
        self._cancelButton.clicked.connect( self.reject )

    def comment(self):
        """The current comment"""
        return self.textEdit.text()

    def setComment(self, comment):
        """Sets the comment"""
        self.textEdit.setText(comment)

if __name__ == '__main__':
    dialog = RamCommentDialog(2)
    ok = dialog.exec_()
    print(ok)
