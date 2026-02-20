"""! @brief Import/Replace item Dialog
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
    from PySide2 import QtGui as qg
    QAction = qw.QAction
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc
    from PySide6 import QtGui as qg
    QAction = qg.QAction

from ramses import (
    RamFileManager,
    RAMSES,
    RamFileInfo,
    RamItem,
    RamStep,
    log,
    LogLevel
    )

from ramses_ui_pyside.dialog import RamDialog
from ramses_ui_pyside.itemstep_selector import RamItemStepSelectWidget
from ramses_ui_pyside.search_list import RamSearchListWidget

class RamImportDialog(RamDialog):
    """Import item Dialog"""

    def __init__(self, parent:qw.QWidget=None, openExtensions:list[str]=(), hideExtensions:list[str]=()):
        super(RamImportDialog, self).__init__(parent)
        self.__setup_menu()
        self.__setup_ui()
        self.__connectEvents()
        self.__openExtensions = openExtensions
        self.__hideExtensions = hideExtensions

        if not RAMSES.project():
            log( "Project not available: You must log in Ramses first!", LogLevel.Critical)
            self.uberLayout.addWidget( qw.QLabel("Project not available: You must log in Ramses first!") )
            self.mainWidget.setEnabled(False)
            self.openButton.setEnabled(False)

    def __setup_menu(self):
        SETTINGS = RAMSES.settings()
        by_version = SETTINGS.userSettings.get('sort_publish_by_version', True)
        asc = SETTINGS.userSettings.get('sort_publish_ascending', False)
        recent_items = SETTINGS.recentImport

        i = 1

        if len(recent_items) > 0:
            self.recentButton = qw.QToolButton()
            self.recentButton.setText("Recent items...")
            self.recentButton.setPopupMode(qw.QToolButton.InstantPopup)
            self.menuLayout.insertWidget(i, self.recentButton , stretch=0)
            i += 1
            self.recentMenu = qw.QMenu()
            self.recentButton.setMenu(self.recentMenu)
            for import_data in recent_items:
                item = RamItem(import_data['item'], objectType = import_data['itemType'])
                step = RamStep(import_data['step'])
                a = QAction( item.name() + ' | ' + step.name(), self )
                a.setData(import_data)
                self.recentMenu.addAction(a)
            self.recentMenu.triggered.connect(self.__get_recent)


        self.optionsButton = qw.QToolButton()
        self.optionsButton.setText("Options...")
        self.optionsButton.setPopupMode(qw.QToolButton.InstantPopup)
        self.menuLayout.insertWidget(i, self.optionsButton , stretch=0)
        i += 1

        self.optionsMenu = qw.QMenu()
        self.optionsButton.setMenu(self.optionsMenu)

        self.sortByVersion = QAction("Sort by version", self)
        self.sortByVersion.setCheckable( True )
        self.sortByVersion.setChecked( by_version )
        self.optionsMenu.addAction(self.sortByVersion)

        self.sortByResource = QAction("Sort by resource", self)
        self.sortByResource.setCheckable(True)
        self.sortByResource.setChecked( not by_version )
        self.sortByResource.setParent(self)
        self.optionsMenu.addAction(self.sortByResource)

        self.optionsMenu.addSeparator()

        self.sortAsc = QAction("Sort ascending", self)
        self.sortAsc.setCheckable(True)
        self.sortAsc.setChecked( asc )
        self.optionsMenu.addAction(self.sortAsc)

        self.sortDesc = QAction("Sort descending", self)
        self.sortDesc.setCheckable(True)
        self.sortDesc.setChecked(not asc )
        self.optionsMenu.addAction(self.sortDesc)

        self.optionsMenu.addSeparator()

        self.showSettingsUI = QAction("Edit import settings", self)
        self.showSettingsUI.setCheckable(True)
        self.showSettingsUI.setChecked( False )
        self.optionsMenu.addAction(self.showSettingsUI)

    def __setup_ui(self):
        self.setWindowTitle( "Import item..." )
        self.setMinimumWidth(400)

        layout = qw.QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(6)
        self.mainLayout.addLayout(layout)

        self.itemSelector = RamItemStepSelectWidget()
        self.itemSelector.setCurrentStep(None) # Force to manually set a step
        layout.addWidget(self.itemSelector)

        versionLayout = qw.QVBoxLayout()
        versionLayout.setContentsMargins(0,0,0,0)
        versionLayout.setSpacing(3)
        layout.addLayout(versionLayout)

        versionLayout.addWidget(qw.QLabel("Version:"))

        self.versionBox = qw.QComboBox()
        versionLayout.addWidget(self.versionBox)

        self.versionList = qw.QListWidget()
        self.versionList.setSelectionMode(qw.QAbstractItemView.ExtendedSelection)
        versionLayout.addWidget(RamSearchListWidget(self.versionList))

        self.openButton = qw.QPushButton("Import")
        self.openButton.setEnabled(False)
        self.buttonsLayout.addWidget( self.openButton )
        self.cancelButton = qw.QPushButton("Cancel")
        self.buttonsLayout.addWidget( self.cancelButton )

        # Select the previous import step
        settings = RAMSES.settings()
        step_uuid = settings.userSettings.get('lastImportStep', '')
        step = RamStep(step_uuid)
        self.itemSelector.setCurrentStep(step)

    def __connectEvents(self):
        self.sortByVersion.toggled.connect( self.__change_sort_publish_by_version )
        self.sortByResource.toggled.connect( self.__change_sort_publish_by_resource )
        self.sortAsc.toggled.connect( self.__change_sort_publish_asc )
        self.sortDesc.toggled.connect( self.__change_sort_publish_desc )

        self.openButton.clicked.connect(self.__onOpen)
        self.cancelButton.clicked.connect(self.reject)
        self.itemSelector.currentStepChanged.connect(self.__changeItem)
        self.itemSelector.currentItemChanged.connect(self.__changeItem)
        self.versionBox.currentIndexChanged.connect(self.__update_published_files)
        self.versionList.itemSelectionChanged.connect( self.__check )

    @qc.Slot()
    def __onOpen(self):
        # Save the item type and step
        settings = RAMSES.settings()
        step = self.currentStep()
        if step:
            settings.userSettings['lastImportStep'] = step.uuid()
            settings.save()
        self.accept()

    @qc.Slot(bool)
    def __change_sort_publish_by_version(self, checked):
        SETTINGS = RAMSES.settings()
        self.sortByVersion.setChecked( checked )
        self.sortByResource.setChecked( not checked )
        SETTINGS.userSettings['sort_publish_by_version'] = checked
        SETTINGS.save()
        self.__changeItem()

    @qc.Slot(bool)
    def __change_sort_publish_by_resource(self, checked):
        SETTINGS = RAMSES.settings()
        self.sortByVersion.setChecked( not checked )
        self.sortByResource.setChecked( checked )
        SETTINGS.userSettings['sort_publish_by_version'] = not checked
        SETTINGS.save()
        self.__changeItem()

    @qc.Slot(bool)
    def __change_sort_publish_asc(self, checked):
        SETTINGS = RAMSES.settings()
        self.sortAsc.setChecked( checked )
        self.sortDesc.setChecked( not checked )
        SETTINGS.userSettings['sort_publish_ascending'] = checked
        SETTINGS.save()
        self.__changeItem()

    @qc.Slot(bool)
    def __change_sort_publish_desc(self, checked):
        SETTINGS = RAMSES.settings()
        self.sortAsc.setChecked( not checked )
        self.sortDesc.setChecked( checked )
        SETTINGS.userSettings['sort_publish_ascending'] = not checked
        SETTINGS.save()
        self.__changeItem()

    @qc.Slot()
    def __check(self):
        self.openButton.setEnabled(
            len(self.filePaths()) > 0
        )

    @qc.Slot()
    def __changeItem(self, item=None):

        # Ensure we have the actual item, not a step passed by a signal
        from ramses import RamItem
        if not isinstance(item, RamItem):
            item = self.itemSelector.currentItem()
        
        self.versionList.clear()
        self.versionBox.clear()
        if not item:
            self.__check()
            return

        step = self.itemSelector.currentStep()
        folders = item.publishedVersionFolderPaths(
            step,
            sortByVersion=self.sortByVersion.isChecked(),
            sortDescending=self.sortDesc.isChecked()
            )

        for f in folders:
            folderName = os.path.basename( f )
            folderName = folderName.split("_")
            title = ""

            # Test length to know what we've got
            if len(folderName) == 3: # resource, version, state
                title = folderName[0] + " | v" + folderName[1] + " | " + folderName[2]
            elif len(folderName) < 3: # version (state)
                # naming could be faulty
                try:
                    n = int(folderName[0])
                except ValueError:
                    n = 0
                if n != 0:
                    title = "v" + " | ".join(folderName)
            else:
                title = " | ".join(folderName)

            self.versionBox.addItem(title, f)
            self.__update_published_files()

        # Save the step to restore it next time
        SETTINGS = RAMSES.settings()
        SETTINGS.userSettings['last_import_step'] = step.shortName()
        SETTINGS.save()

        self.__check()

    @qc.Slot(QAction)
    def __get_recent(self, action):
        import_data = action.data()
        item = RamItem(import_data['item'], objectType = import_data['itemType'])
        step = RamStep(import_data['step'])
        self.setCurrentItem(item)
        self.setCurrentStep(step)
        self.__changeItem(item)

    @qc.Slot()
    def __update_published_files(self):
        self.versionList.clear()
        # List available files
        folder = self.versionBox.currentData()
        files = RamFileManager.getRamsesFiles( folder )
        for f in files:
            nm = RamFileInfo()
            fileName = os.path.basename(f)
            if not nm.setFileName(fileName):
                continue
            resource = nm.resource
            if nm.isBackup:
                continue
            if len(self.__openExtensions) > 0 and not nm.extension in self.__openExtensions:
                continue
            if len(self.__hideExtensions) > 0 and nm.extension in self.__hideExtensions:
                continue
            
            # Main files have empty resource strings. 
            # We display them as "Main" to be consistent with the Ramses UI.
            title = resource if resource != "" else "Main"
            title = title + " (" + nm.extension + ")"
            item = qw.QListWidgetItem( title )
            item.setData(qc.Qt.UserRole, f)
            item.setToolTip(fileName)
            self.versionList.addItem(item)

    def setSingleSelection(self, single:bool=True):
        """Set the selection mode of the files to single or multiple (extended selection)"""
        if single:
            self.versionList.setSelectionMode(qw.QAbstractItemView.SingleSelection)
        else:
            self.versionList.setSelectionMode(qw.QAbstractItemView.ExtendedSelection)

    def filePaths(self) -> list:
        """The selected file paths"""
        if self.versionList.count() == 0:
            return ()

        items = self.versionList.selectedItems()
        files = []
        for item in items:
            files.append( item.data(qc.Qt.UserRole) )
        return files

    def currentItem(self) -> RamItem:
        """The selected item"""
        return self.itemSelector.currentItem()

    def setCurrentItem(self, item:RamItem):
        """Preselects a specific item"""
        self.itemSelector.setCurrentItem(item)

    def currentStep(self) -> RamStep:
        """The selected step"""
        return self.itemSelector.currentStep()

    def setCurrentStep(self, step:RamStep):
        """Preselects a specific step"""
        self.itemSelector.setCurrentStep(step)

    def currentResource(self) -> str:
        """The selected resource"""

    def showImportOptions(self) -> bool:
        """Whether a dialog to edit the import settings must be shown before import"""
        return self.showSettingsUI.isChecked()

if __name__ == "__main__":
    d = RamImportDialog()
    d.resetLastStep()
    if d.exec_():
        print(d.filePaths())
