"""! @brief Open item Dialog
 @file open_dialog.py
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

import os

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
    QAction = qw.QAction
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc
    from PySide6 import QtGui as qg
    QAction = qg.QAction

from ramses import (
    RAMSES,
    RamMetaDataManager,
    RamFileInfo,
    RamItem,
    RamStep,
    log,
    LogLevel,
    ItemType
    )

from ramses_ui_pyside.dialog import RamDialog
from ramses_ui_pyside.itemstep_selector import RamItemStepSelectWidget
from ramses_ui_pyside.search_list import RamSearchListWidget

class RamOpenDialog(RamDialog):
    """Open item Dialog"""

    def __init__(self, fileTypes:list, parent:qw.QWidget=None):
        super(RamOpenDialog, self).__init__(parent)
        self.__fileTypes = fileTypes
        self.__selected_recent_path = ''
        self.__setup_menu()
        self.__setup_ui()
        self.__connectEvents()

        if not RAMSES.project():
            log( "Project not available: You must log in Ramses first!", LogLevel.Critical)
            self.uberLayout.addWidget( qw.QLabel("Project not available: You must log in Ramses first!") )
            self.mainWidget.setEnabled(False)
            self.openButton.setEnabled(False)

    def __setup_menu(self):
        SETTINGS = RAMSES.settings()
        recent_files = SETTINGS.recentFiles

        if len(recent_files) == 0:
            return

        self.recentButton = qw.QToolButton()
        self.recentButton.setText("Recent files...")
        self.recentButton.setPopupMode(qw.QToolButton.InstantPopup)
        self.menuLayout.insertWidget(1, self.recentButton , stretch=0)

        self.recentMenu = qw.QMenu()
        self.recentButton.setMenu(self.recentMenu)

        for file in recent_files:

            if not os.path.isfile(file):
                recent_files.remove(file)
                continue

            item = RamItem.fromPath(file)
            if not item:
                a = QAction( os.path.basename(file), self )
                a.setData( file )
                self.recentMenu.addAction(a)
                continue

            nm = RamFileInfo()
            nm.setFilePath(file)

            res = nm.resource

            if nm.isRestoredVersion:
                if res != '':
                    res = res + " | "
                res = res + "v" + str(nm.restoredVersion) + " (restored)"

            itemName = ""
            if nm.project != "":
                itemName = nm.project + " | "
            itemName = itemName + str(item)
            if nm.step != "":
                itemName = itemName + " | " + nm.step
            if res != "":
                itemName = itemName + " | " + res


            a = QAction( itemName, self )
            a.setData( file )
            a.setToolTip( os.path.basename(file) )
            self.recentMenu.addAction(a)

        # We may have removed old files not available anymore,
        # Re-set the list
        SETTINGS.recentFiles = recent_files
        # And connect the menu
        self.recentMenu.triggered.connect(self.__open_recent)

    def __setup_ui(self):
        self.setWindowTitle( "Open item..." )
        self.setMinimumWidth(400)

        layout = qw.QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(6)
        self.mainLayout.addLayout(layout)

        self.itemSelector = RamItemStepSelectWidget()
        self.itemSelector.setCurrentStep(None) # Force to manually set a step
        layout.addWidget(self.itemSelector)

        resourceLayout = qw.QVBoxLayout()
        layout.addLayout(resourceLayout)

        resourceLayout.addWidget(qw.QLabel("Resource:"))

        self.resourceList = qw.QListWidget()
        resourceLayout.addWidget(self.resourceList)

        versionLayout = qw.QVBoxLayout()
        layout.addLayout(versionLayout)

        versionLayout.addWidget(qw.QLabel("Version:"))
        self.versionList = qw.QListWidget()
        versionLayout.addWidget(RamSearchListWidget(self.versionList))

        self.openButton = qw.QPushButton("Open")
        self.openButton.setEnabled(False)
        self.buttonsLayout.addWidget( self.openButton )
        self.cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self.cancelButton )

        # Select the previous open step
        settings = RAMSES.settings()
        step_uuid = settings.userSettings.get('lastOpenStep', '')
        step = RamStep(step_uuid)
        self.itemSelector.setCurrentStep(step)

    def __connectEvents(self):
        self.openButton.clicked.connect(self.__onOpen)
        self.cancelButton.clicked.connect(self.reject)
        self.itemSelector.currentStepChanged.connect(self.__changeItem)
        self.itemSelector.currentItemChanged.connect(self.__changeItem)
        self.resourceList.currentItemChanged.connect(self.__changeResource)

    @qc.Slot()
    def __onOpen(self):
        # Save the item type and step
        settings = RAMSES.settings()
        step = self.currentStep()
        if step:
            settings.userSettings['lastOpenStep'] = step.uuid()
            settings.save()
        self.accept()

    @qc.Slot(QAction)
    def __open_recent(self, action):
        self.__selected_recent_path = action.data()
        self.accept()

    @qc.Slot()
    def __check(self):
        filePath = self.filePath()
        self.openButton.setEnabled( filePath  != "" )

    @qc.Slot()
    def __changeItem(self):
        item = self.itemSelector.currentItem()

        self.resourceList.clear()
        self.versionList.clear()

        step = self.itemSelector.currentStep()
        itemType = self.itemSelector.itemType()

        if itemType == ItemType.GENERAL:
            # List files in the step folder
            stepFolder = step.folderPath()
            for f in os.listdir(stepFolder):
                filePath = os.path.join(stepFolder, f)

                nm = self.__validateFile(filePath)
                if not nm:
                    continue

                n = nm.shortName
                r = nm.resource
                if r != "":
                    n = n + "(" + r + ")"
                if n == '':
                    n = 'Main'

                listItem = qw.QListWidgetItem( n )
                listItem.setData( qc.Qt.UserRole, filePath )
                listItem.setToolTip( os.path.basename(filePath) )
                self.resourceList.addItem( listItem )
            self.__check()
            return

        if not item:
            self.__check()
            return
        files = item.stepFilePaths(step)
        for file in files:
            nm = self.__validateFile(file)
            if not nm:
                continue

            res = nm.resource

            if nm.isRestoredVersion:
                if res != '':
                    res = res + " | "
                res = res + "v" + str(nm.restoredVersion) + " (restored)"

            if res == "":
                res = "Main (" + nm.extension + ")"

            listItem = qw.QListWidgetItem( res )
            listItem.setData( qc.Qt.UserRole, file )
            listItem.setToolTip( os.path.basename(file) )
            self.resourceList.addItem( listItem )

        self.__check()

    @qc.Slot()
    def __changeResource(self):

        self.versionList.clear()

        item = self.currentItem()
        if not item:
            self.__check()
            return

        # Add current
        resourceItem = self.resourceList.currentItem()
        if resourceItem:
            listItem = qw.QListWidgetItem("Current version")
            listItem.setData(qc.Qt.UserRole, resourceItem.data(qc.Qt.UserRole))
            self.versionList.addItem(listItem)

        versionFiles = item.versionFilePaths( self.currentResource(), self.currentStep() )
        versionFiles.reverse()

        # Add other versions
        for v in versionFiles:
            fileName = os.path.basename( v )
            nm = RamFileInfo()
            if not nm.setFileName( fileName ):
                continue
            if not nm.extension in self.__fileTypes:
                continue
            comment = RamMetaDataManager.getComment( v )
            itemText = nm.state + ' | ' + str( nm.version )
            if comment != "":
                itemText = itemText + ' | ' + comment
            item = qw.QListWidgetItem( itemText )
            item.setData(qc.Qt.UserRole, v)
            self.versionList.addItem(item)

        self.__check()

    def __validateFile(self, filePath:str):
        nm = RamFileInfo()
        nm.setFilePath(filePath)
        if nm.project == '':
            return None
        if not nm.extension.lower() in self.__fileTypes:
            return None
        return nm

    def currentItem(self):
        "The selected item if  any"
        return self.itemSelector.currentItem()

    def setCurrentItem(self, item):
        """Selects the current item"""
        self.itemSelector.setCurrentItem(item)

    def currentStep(self):
        "The selected step, if any"
        return self.itemSelector.currentStep()

    def setCurrentStep(self, step):
        """Selects the current step"""
        self.itemSelector.setCurrentStep(step)

    def currentResource(self):
        """The selected resource string, if any"""
        nm = RamFileInfo()
        nm.setFilePath(self.filePath())
        return nm.resource

    def filePath(self):
        """The selected file path"""

        # if we're opening a recent file
        if self.__selected_recent_path != '':
            return self.__selected_recent_path

        # if a version is selected
        versionItem = self.versionList.currentItem()
        if versionItem:
            return versionItem.data(qc.Qt.UserRole)

        # if a resource is selected
        resourceItem = self.resourceList.currentItem()
        if resourceItem:
            return resourceItem.data(qc.Qt.UserRole)

        # Check the item and step
        item = self.currentItem()
        if not item:
            return ""

        step = self.currentStep()

        for ext in self.__fileTypes:
            fp = item.stepFilePath(extension=ext, step=step)
            if fp != "":
                return fp

        return ""

if __name__ == '__main__':
    dialog = RamOpenDialog( ("ma", "mb") )
    if dialog.exec_():
        print(dialog.filePath())
    else:
        print("Cancelled")
