"""! @brief A Dialog to show update info
 @file update_dialog.py
 @section authors Author(s)
  - Created by Nicolas Dufresne on 10/29/2024 .
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
    from PySide2 import QtGui as qg
    from PySide2 import QtCore as qc
    from PySide2 import QtWidgets as qw
except:  # pylint: disable=bare-except
    from PySide6 import QtGui as qg
    from PySide6 import QtCore as qc
    from PySide6 import QtWidgets as qw

class RamUpdateDialog( qw.QDialog ):
    """The dialog to show details about an update"""

    def __init__(self, updateResponse, toolName, toolVersion, parent=None):
        super(RamUpdateDialog, self).__init__(parent)
        self.__setupUi(updateResponse, toolName, toolVersion)

    def __setupUi(self, updateResponse, toolName, toolVersion):
        self.setModal(True)

        mainLayout = qw.QVBoxLayout()
        mainLayout.setSpacing(3)
        self.setLayout(mainLayout)

        updateInfo = updateResponse.get('data', {})

        if updateInfo.get("update", False):
            self.setWindowTitle("New " + toolName + " available!" )

            latestVersionLabel = qw.QLabel("New version: " + updateInfo.get("version") )
            mainLayout.addWidget(latestVersionLabel)

            descriptionEdit = qw.QTextEdit()
            descriptionEdit.setMarkdown(updateInfo.get("description"))
            descriptionEdit.setReadOnly(True)
            mainLayout.addWidget(descriptionEdit)

            currentVersionLabel = qw.QLabel("Current version: " + toolVersion )
            currentVersionLabel.setEnabled(False)
            mainLayout.addWidget(currentVersionLabel)

            self.__downloadURL = updateInfo.get("downloadURL", "")
            if self.__downloadURL != "":
                self.__ui_downloadButton = qw.QPushButton("Download")
                #self.__ui_downloadButton.setIcon(icon("download"))
                mainLayout.addWidget(self.__ui_downloadButton)
                self.__ui_downloadButton.clicked.connect(self.download)

            self.__changelogURL = updateInfo.get("changelogURL", "")
            if self.__changelogURL != "":
                self.__ui_changelogButton = qw.QPushButton("Changelog")
                #self.__ui_changelogButton.setIcon(icon("changelog"))
                mainLayout.addWidget(self.__ui_changelogButton)
                self.__ui_changelogButton.clicked.connect(self.changelog)

            self.__donateURL = updateInfo.get("donateURL", "")
            if self.__donateURL != "":
                self.__ui_donateButton = qw.QPushButton("I ♥ " + toolName)
                #self.__ui_donateButton.setIcon(icon("donate"))
                mainLayout.addWidget(self.__ui_donateButton)
                self.__ui_donateButton.clicked.connect(self.donate)

            self.__ui_okButton = qw.QPushButton("Close")
            #self.__ui_okButton.setIcon(icon("close"))
            mainLayout.addWidget(self.__ui_okButton)
            self.__ui_okButton.clicked.connect(self.reject)
        elif updateResponse.get("accepted", False):
            self.setWindowTitle( "Update" )

            versionLabel = qw.QLabel("I'm already up-to-date!" )
            mainLayout.addWidget(versionLabel)

            self.__ui_okButton = qw.QPushButton("Close")
            #self.__ui_okButton.setIcon(icon("close"))
            mainLayout.addWidget(self.__ui_okButton)
            self.__ui_okButton.clicked.connect(self.reject)
        elif updateResponse.get("success", False):
            self.setWindowTitle( "Server error" )
            label = qw.QLabel("Sorry, the server could not get update information." )
            mainLayout.addWidget(label)

            descriptionEdit = qw.QTextEdit(updateResponse.get("message", ""))
            descriptionEdit.setReadOnly(True)
            mainLayout.addWidget(descriptionEdit)

            self.__ui_okButton = qw.QPushButton("Close")
            #self.__ui_okButton.setIcon(icon("close"))
            mainLayout.addWidget(self.__ui_okButton)
            self.__ui_okButton.clicked.connect(self.reject)
        else:
            self.setWindowTitle( "Server error" )
            label = qw.QLabel("Sorry, there was a server error." )
            mainLayout.addWidget(label)

            self.__ui_okButton = qw.QPushButton("Close")
            #self.__ui_okButton.setIcon(icon("close"))
            mainLayout.addWidget(self.__ui_okButton)
            self.__ui_okButton.clicked.connect(self.reject)

    @qc.Slot()
    def download(self):
        """Opens the download URL"""
        qg.QDesktopServices.openUrl ( qc.QUrl( self.__downloadURL ) )
        self.close()

    @qc.Slot()
    def changelog(self):
        """Opens the changelog URL"""
        qg.QDesktopServices.openUrl ( qc.QUrl( self.__changelogURL ) )
        self.close()

    @qc.Slot()
    def donate(self):
        """Opens the donate URL"""
        qg.QDesktopServices.openUrl ( qc.QUrl( self.__donateURL ) )
        self.close()
