"""! @brief Set item status dialog
 @file status_dialog.py
 @section authors Author(s)
  - Created by Nicolas Dufresne on 10/15/2024 .
 @license GNU-GPLv3
 @copyright (c) 2025 Nicolas Dufresne and contributors
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

from ramses import RAMSES, RamStatus, RamState, log, LogLevel
from ramses_ui_pyside.dialog import RamDialog
from ramses_ui_pyside.state_combobox import RamStateBox


class RamStatusDialog(RamDialog):
    """Set item status dialog"""

    def __init__(self, status:RamStatus=None, parent:qw.QWidget=None):
        """!
        @brief Creates the status dialog

        Parameters : 
            @param status : RamStatus => Initial status.
            @param parent = None => The parent QWidget

        """

        super(RamStatusDialog, self).__init__(parent)
        self.__setup_ui()
        self.__connectEvents()

        if not RAMSES.project():
            log( "Project not available: You must log in Ramses first!", LogLevel.Critical)
            self.uberLayout.addWidget( qw.QLabel("Project not available: You must log in Ramses first!") )
            self.mainWidget.setEnabled(False)
            self.saveButton.setEnabled(False)
        elif status:
            self.setComment(status.comment())
            self.setCompletionRatio(status.completionRatio())
            self.setState(status.state())

    def __setup_ui(self):
        self.setWindowTitle( "Update status" )
        self.setMinimumWidth( 400 )

        stateLayout = qw.QHBoxLayout()
        stateLayout.setContentsMargins(0,0,0,0)
        stateLayout.setSpacing(3)
        self.mainLayout.addLayout(stateLayout)

        self.stateBox = RamStateBox()
        stateLayout.addWidget(self.stateBox)

        self.completionSlider = qw.QSlider( qc.Qt.Horizontal )
        self.completionSlider.setMaximum(100)
        self.completionSlider.setValue(50)
        stateLayout.addWidget(self.completionSlider)

        self.completionBox = qw.QSpinBox()
        self.completionBox = qw.QSpinBox( )
        self.completionBox.setMinimum( 0 )
        self.completionBox.setMaximum( 100 )
        self.completionBox.setSuffix( "%" )
        self.completionBox.setValue(50)
        stateLayout.addWidget( self.completionBox )

        self.commentEdit = qw.QTextEdit()
        self.mainLayout.addWidget(self.commentEdit)

        optionsLayout = qw.QFormLayout()
        self.mainLayout.addLayout(optionsLayout)

        optionsButtonsLayout = qw.QVBoxLayout()
        optionsButtonsLayout.setContentsMargins(0,0,0,0)
        optionsButtonsLayout.setSpacing(3)

        self.publishBox = qw.QCheckBox("Publish the current scene.")
        optionsButtonsLayout.addWidget(self.publishBox)
        self.publishSettingsBox = qw.QCheckBox("Edit publish settings.")
        self.publishSettingsBox.setEnabled(False)
        optionsButtonsLayout.addWidget(self.publishSettingsBox)
        self.previewBox = qw.QCheckBox("Create preview files (thumbnail or playblast).")
        optionsButtonsLayout.addWidget(self.previewBox)

        optionsLayout.addRow("Options:", optionsButtonsLayout)

        self.saveButton = qw.QPushButton("Save and Update Status")
        self.buttonsLayout.addWidget( self.saveButton )
        self.cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self.cancelButton )

    def __connectEvents(self):
        self.saveButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        self.publishBox.clicked.connect(self.__updatePublish)

        self.completionBox.valueChanged.connect(self.__updateCompletion)
        self.completionSlider.valueChanged.connect(self.__updateCompletion)

    @qc.Slot(int)
    def __updateCompletion(self, c:int):
        self.completionBox.setValue(c)
        self.completionSlider.setValue(c)

    @qc.Slot(bool)
    def __updatePublish(self, p):
        self.publishSettingsBox.setEnabled(p)
        if not p:
            self.publishSettingsBox.setChecked(False)

    def comment(self) -> str:
        """The current comment"""
        return self.commentEdit.toPlainText()

    def setComment(self, comment:str):
        """Set the comment"""
        self.commentEdit.setPlainText(comment)

    def completionRatio(self) -> int:
        """The current completion ratio"""
        return self.completionBox.value()

    def setCompletionRatio(self, completionRatio:int):
        """Set the completion ratio"""
        self.completionBox.setValue(completionRatio)

    def state(self) -> RamState:
        """The selected state"""
        return self.stateBox.currentState()

    def setState(self, state:RamState):
        """Set the current state"""
        self.stateBox.setCurrentState(state)

    def publish(self) -> bool:
        """Whether to publish"""
        return self.publishBox.isChecked()

    def showPublishSettings(self) -> bool:
        """Whether to force show publish settings"""
        return self.publishSettingsBox.isChecked()

    def savePreview(self) -> bool:
        """Whether to save a preview of the current file"""
        return self.previewBox.isChecked()

if __name__ == "__main__":
    d = RamStatusDialog()
    d.exec_()
