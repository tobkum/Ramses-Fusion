"""! @brief Save As/Create scene Dialog
 @file save_as_dialog.py
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

from ramses import (
    RAMSES,
    log,
    LogLevel,
    ItemType,
    RamFileInfo,
    RamFileManager,
    RamItem,
    )
from ramses_ui_pyside.object_combobox import RamObjectBox
from ramses_ui_pyside.step_combobox import RamStepBox
from ramses_ui_pyside.dialog import RamDialog
from ramses_ui_pyside.itemstep_selector import RamItemStepSelectWidget
from ramses_ui_pyside.formlayout import RamFormLayout

class RamSaveAsDialog( RamDialog ):
    """Save As/Create scene Dialog"""

    def __init__(self, fileTypes:list, parent:qw.QWidget=None):
        """!
        @brief Creates the save as dialog

        Parameters : 
            @param fileTypes : list => A list of dict. Each dict is: { "extension": "ext", "name":"Type name" }
            @param parent = None => The parent QWidget

        """

        super(RamSaveAsDialog, self).__init__(parent)

        self.__project = RAMSES.project()
        self.__useCustomPath = False
        self.__setup_ui(fileTypes)
        self.__connectEvents()

        if not RAMSES.project():
            log( "Project not available: You must log in Ramses first!", LogLevel.Critical)
            self.uberLayout.addWidget( qw.QLabel("Project not available: You must log in Ramses first!") )
            self.mainWidget.setEnabled(False)
            self._saveButton.setEnabled(False)

    def __setup_ui(self, fileTypes):
        self.setWindowTitle( "Save as..." )
        self.setMinimumWidth(400)

        self.itemSelector = RamItemStepSelectWidget()
        self.itemSelector.setCurrentStep(None) # Force to manually set a step
        self.mainLayout.addWidget(self.itemSelector)

        formLayout = RamFormLayout()
        self.mainLayout.addLayout(formLayout)

        self.resourceEdit = qw.QLineEdit()
        formLayout.addRow( "Resource:", self.resourceEdit)

        self.extensionBox = qw.QComboBox()
        for fileType in fileTypes:
            ext = fileType.get('extension', '')
            name = fileType.get('name', '')

            if ext == '':
                raise ValueError("The fileTypes must have a non-empty 'extension' property.")
            if name == '':
                raise ValueError("The fileTypes must have a non-empty 'name' property.")

            self.extensionBox.addItem(name, ext)

        formLayout.addRow("File Type:", self.extensionBox)

        locationLayout = qw.QHBoxLayout()
        locationLayout.setSpacing(3)
        locationLayout.setContentsMargins(0,0,0,0)

        self.locationEdit = qw.QLineEdit()
        self.locationEdit.setEnabled(False)
        self.locationEdit.setPlaceholderText("Location...")
        locationLayout.addWidget( self.locationEdit )

        self.browseButton = qw.QPushButton("Browse...")
        self.browseButton.hide()
        locationLayout.addWidget( self.browseButton )

        formLayout.addRow("Location:",locationLayout)

        self.fileNameLabel = qw.QLabel()
        formLayout.addRow("Filename:", self.fileNameLabel)

        self._saveButton = qw.QPushButton("Save")
        self._saveButton.setEnabled(False)
        self.buttonsLayout.addWidget( self._saveButton )
        self._cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self._cancelButton )

    def __connectEvents(self):
        self._saveButton.clicked.connect( self.accept )
        self._cancelButton.clicked.connect( self.reject )
        self.resourceEdit.textChanged.connect( self.__buildPath )
        self.extensionBox.currentIndexChanged.connect( self.__buildPath )
        self.itemSelector.currentTypeChanged.connect( self.__changeType )
        self.itemSelector.currentItemChanged.connect( self.__buildPath )
        self.browseButton.clicked.connect( self.__browse )

    def __buildPath(self):

        self.fileNameLabel.setText('')
        self._saveButton.setEnabled(False)

        if not self.__project:
            self.locationEdit.setPlaceholderText('Sorry, invalid project...')
            return

        step = self.step()
        if not step:
            self.locationEdit.setText('')
            self.locationEdit.setPlaceholderText('Sorry, invalid step...')
            return

        item = self.item()
        if not item:
            self.locationEdit.setText('')
            self.locationEdit.setPlaceholderText('Sorry, invalid item...')
            return

        if self.isAsset() or self.isShot():
            self.locationEdit.setText(item.stepFolderPath(step))

            # The filename
            nm = RamFileInfo()
            nm.project = self.__project.shortName()
            nm.ramType = item.itemType()
            nm.shortName = item.shortName()
            nm.step = step.shortName()            
            nm.extension = self.extensionBox.currentData()
            nm.resource = self.resourceEdit.text()
            itemFileName = nm.fileName()

            self.fileNameLabel.setText(itemFileName)

        else:
            if not self.__useCustomPath:
                self.locationEdit.setText(step.folderPath())

            # The filename
            nm = RamFileInfo()
            nm.project = self.__project.shortName()
            nm.ramType = ItemType.GENERAL
            nm.step = step.shortName()
            nm.shortName = item.shortName()
            nm.extension = self.extensionBox.currentData()
            nm.resource = self.resourceEdit.text()
            itemFileName = nm.fileName()

            self.fileNameLabel.setText( itemFileName )

        self._saveButton.setEnabled(True)

    def __changeType(self, itemType:ItemType):
        self.browseButton.setVisible(itemType == ItemType.GENERAL)
        self.__buildPath()

    def __browse(self):
        path = qw.QFileDialog.getExistingDirectory(self)
        if path != "":
            self.__useCustomPath = True
            self.locationEdit.setText(path)

    def isAsset(self):
        return self.itemSelector.itemType() == ItemType.ASSET

    def setAsset(self):
        self.itemSelector.setItemType(ItemType.ASSET)

    def isShot(self):
        return self.itemSelector.itemType() == ItemType.SHOT

    def setShot(self):
        self.itemSelector.setItemType(ItemType.SHOT)

    def isGeneral(self):
        return self.itemSelector.itemType() == ItemType.GENERAL

    def setGeneral(self):
        self.itemSelector.setItemType(ItemType.GENERAL)

    def setStep(self, step):
        self.itemSelector.setCurrentStep(step)

    def setItem(self, item):
        self.itemSelector.setCurrentItem(item)

    def filePath(self):
        path = self.locationEdit.text()
        if path == '':
            return ''
        fileName = self.fileNameLabel.text()
        return RamFileManager.buildPath((
            path,
            fileName
        ))

    def extension(self):
        return self.extensionBox.currentData()

    def step(self):
        return self.itemSelector.currentStep()

    def item(self):

        if self.isGeneral():
            step = self.step()
            if not step:
                return None
            return RamItem(data={"name": step.name()})

        item = self.itemSelector.currentItem()
        if not item:
            return None
        item.set("folderPath", self.locationEdit.text())
        return item

    def resource(self):
        return self.resourceEdit.text()

if __name__ == '__main__':
    dialog = RamSaveAsDialog( (
        {'extension': ".ext", 'name': "Some Type"},
        {'extension': ".other", 'name': "Another Type"},
    ) )
    ok = dialog.exec_()
    if ok == 1:
        print(dialog.filePath())
