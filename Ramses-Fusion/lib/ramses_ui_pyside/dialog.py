"""! @brief The base Dialog class for all dialogs
 @file dialog.py
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

import os
import yaml

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
    from PySide2 import QtGui as qg
    QAction = qw.QAction
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc
    from PySide6 import QtGui as qg
    QAction = qg.QAction

from ramses_ui_pyside.about_dialog import RamAboutDialog
from ramses_ui_pyside.utils import (
    openHelp,
    aboutRamses,
    donate,
    openApiReference,
    checkUpdate,
    openGeneralHelp,
)

class RamDialog( qw.QDialog ):
    """!
    @brief The base Dialog class for all dialogs

    ## Inheritances : 
        - Implements qw.QDialog => [description]
    """

    def __init__(self, parent:qw.QWidget=None):
        super(RamDialog, self).__init__(parent)

        self.__preset_folder = ""

        self.__dialog_setup_ui()
        self.__dialog_setup_menu()
        self.__dialog_connect_events()
        self.setWindowTitle("Ramses")

    def __dialog_setup_ui(self):

        self.uberLayout = qw.QVBoxLayout(self)
        self.uberLayout.setContentsMargins(16,0,16,16)
        self.uberLayout.setSpacing(10)

        self.menuLayout = qw.QHBoxLayout(self)
        self.menuLayout.setContentsMargins(0,16,0,0)
        self.menuLayout.setSpacing(3)
        self.uberLayout.addLayout(self.menuLayout)

        self.mainWidget = qw.QWidget()
        self.uberLayout.addWidget(self.mainWidget)

        self.mainLayout = qw.QVBoxLayout(self.mainWidget)
        self.mainLayout.setSpacing(10)

        self.buttonsLayout = qw.QHBoxLayout()
        self.buttonsLayout.setSpacing(2)
        self.uberLayout.addLayout( self.buttonsLayout )

    def __dialog_setup_menu(self):

        self.titleLabel = qw.QLabel()
        self.menuLayout.addWidget(self.titleLabel)

        self.presetButton = qw.QToolButton()
        self.presetButton.setText("Presets...")
        self.presetButton.setPopupMode(qw.QToolButton.InstantPopup)
        self.presetButton.hide()
        self.menuLayout.insertWidget(1, self.presetButton , stretch=0)

        self.presetMenu = qw.QMenu()
        self.presetButton.setMenu(self.presetMenu)

        self.savePresetAction = self.presetMenu.addAction("Save preset...")
        self.loadPresetAction = self.presetMenu.addAction("Load preset...")
        self.presetMenu.addSeparator()

        self.presetFilesMenu = qw.QMenu("Presets")
        self.presetMenu.addMenu(self.presetFilesMenu)

        self.helpButton = qw.QToolButton()
        self.helpButton.setText("Help...")
        self.helpButton.setPopupMode(qw.QToolButton.InstantPopup)
        self.menuLayout.addWidget(self.helpButton)

        self.helpMenu = qw.QMenu()
        self.helpAction = self.helpMenu.addAction("Ramses Add-on help...")
        self.generalHelpAction = self.helpMenu.addAction("Ramses general help...")
        self.apiReferenceAction = self.helpMenu.addAction("Ramses API reference...")
        self.helpMenu.addSeparator()
        self.updateAction = self.helpMenu.addAction("Check for update")
        self.donateAction = self.helpMenu.addAction("Donate...")
        self.helpMenu.addSeparator()
        self.aboutAction = self.helpMenu.addAction("About...")
        self.helpAction.setShortcut(qg.QKeySequence("F1"))
        self.helpButton.setMenu(self.helpMenu)

        self.menuLayout.setStretch(0,100)
        self.menuLayout.setStretch(1,0)

    def __dialog_connect_events(self):
        self.savePresetAction.triggered.connect( self.savePreset )
        self.loadPresetAction.triggered.connect( self.loadPreset )
        self.presetFilesMenu.triggered.connect( self.__presetActionTriggered )

        self.helpAction.triggered.connect( openHelp )
        self.generalHelpAction.triggered.connect( openGeneralHelp )
        self.apiReferenceAction.triggered.connect( openApiReference )
        self.updateAction.triggered.connect( checkUpdate )
        self.aboutAction.triggered.connect( self.showAbout )
        self.donateAction.triggered.connect( donate )

    def __reloadPresets(self):

        if not os.path.isdir(self.__preset_folder):
            return

        # Remove previous presets
        self.presetFilesMenu.clear()

        # List files in the folder
        for file_name in os.listdir(self.__preset_folder):
            name, ext = os.path.splitext(file_name)
            ext = ext.lower()
            if ext in ('.yaml','.yml'):
                p = self.__preset_folder + file_name
                presetAction = QAction(name, self)
                presetAction.setData(p)
                self.presetFilesMenu.addAction(presetAction)

    @qc.Slot(QAction)
    def __presetActionTriggered(self, action):
        self.loadPresetFile(action.data())

    def _load_enum_preset(self, data, comboBox:qw.QComboBox):
        if data is not None:
            for i in range(comboBox.count()):
                itemData = comboBox.itemData(i, qc.Qt.UserRole)
                if itemData == data:
                    comboBox.setCurrentIndex(i)
                    return
        comboBox.setCurrentIndex(-1)

    @qc.Slot()
    def loadPreset(self):
        """Prompts the user to select a preset file to load"""
        open_file = qw.QFileDialog.getOpenFileName(self, "Load preset...", self.__preset_folder, "Yaml (*.yml *.yaml)")[0]
        if open_file != "":
            self.loadPresetFile(open_file)

    @qc.Slot()
    def savePreset(self):
        """Saves the current options as a preset file"""
        saveFile = qw.QFileDialog.getSaveFileName(self, "Save settings as preset...", self.__preset_folder, "Yaml (*.yml *.yaml)")[0]
        if saveFile != "":
            options = self.getOptions()
            with open(saveFile, "w", encoding='utf-8') as file:
                yaml.dump(options, file)

        self.__reloadPresets()

    def getPreset(self) -> str:
        """Returns the current options as a yaml string"""
        return yaml.dump(self.getOptions())

    def loadPresetFile(self, filePath):
        """Loads a preset file"""
        if not os.path.isfile(filePath):
            return

        with open(filePath, 'r', encoding='utf-8') as file:
            options = yaml.safe_load(file.read())
            if options:
                self.setOptions(options)

    def getOptions(self):
        """Returns the options as a dict. This is a virtual method"""
        raise NotImplementedError

    def setOptions(self, options):
        """Loads the options. This is a virtual method"""
        raise NotImplementedError

    def setPresetFolder(self, folderPath:str):
        """Sets the default folder for loading/saving presets"""
        self.__preset_folder = folderPath
        self.__reloadPresets()

    def showPresetMenu(self):
        """Shows the preset menu"""
        self.presetButton.show()

    def setWindowTitle(self, title:str):
        """Overrides QDialog.setWindowTitle to set the title on the label"""
        super(RamDialog, self).setWindowTitle(title)
        self.titleLabel.setText(title)

    def showAbout(self):
        """Shows the Ramses about dialog"""
        d = RamAboutDialog()
        d.exec_()
