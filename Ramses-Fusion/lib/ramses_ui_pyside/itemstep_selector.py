"""Widget to select a working file"""

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

from ramses import ItemType, StepType, RamItem, RamStep, RAMSES

from ramses_ui_pyside.step_combobox import RamStepBox
from ramses_ui_pyside.item_selector import RamItemSelectWidget
from ramses_ui_pyside.formlayout import RamFormLayout

class RamItemStepSelectWidget( qw.QWidget ):
    """Widget to select a working file"""

    currentItemChanged = qc.Signal(RamItem)
    currentTypeChanged = qc.Signal(ItemType)
    currentStepChanged = qc.Signal(RamStep)

    def __init__(self, parent:qw.QWidget=None):
        """A Widget to select a file"""

        super(RamItemStepSelectWidget, self).__init__(parent)

        self.__widget_setupUi()
        self.__widget_connectEvents()

        # Init
        if RAMSES.project():
            self.__typeChanged()

    def __widget_setupUi(self):

        layout = RamFormLayout(parent=self)
        layout.setContentsMargins(0,0,0,0)

        self.typeBox = qw.QComboBox()
        self.typeBox.addItem("Asset", ItemType.ASSET)
        self.typeBox.addItem("Shot", ItemType.SHOT)
        self.typeBox.addItem("Other", ItemType.GENERAL)
        layout.addRow("Type:", self.typeBox)

        self.stepBox = RamStepBox()
        layout.addRow("Step:", self.stepBox)

        """self.itemLayout = qw.QStackedLayout()
        self.itemLayout.setContentsMargins(0,0,0,0)"""

        self.itemSelector = RamItemSelectWidget()
        #self.itemLayout.addWidget(self.itemSelector)

        """self.itemNameEdit = qw.QLineEdit()
        self.itemNameEdit.setPlaceholderText("Item name")
        self.itemNameEdit.setMaximumHeight(24)
        self.itemLayout.addWidget(self.itemNameEdit)"""

        self.itemLabel = qw.QLabel("Item:")
        layout.addRow(self.itemLabel, self.itemSelector)

    def __widget_connectEvents(self):
        self.typeBox.currentIndexChanged.connect( self.__typeChanged )
        self.stepBox.currentStepChanged.connect( self.__stepChanged )
        self.itemSelector.currentItemChanged.connect( self.__itemChanged )
        #self.itemNameEdit.textChanged.connect( self.__itemChanged )

    @qc.Slot()
    def __typeChanged(self):

        itemType = self.itemType()

        # Load steps

        if itemType == ItemType.ASSET:
            self.stepBox.loadSteps( StepType.ASSET_PRODUCTION )
            self.itemLabel.setText("Asset:")
            self.itemLabel.show()
            self.itemSelector.show()
            #self.itemLayout.setCurrentIndex(0)
        elif itemType == ItemType.SHOT:
            self.stepBox.loadSteps( StepType.SHOT_PRODUCTION )
            self.itemLabel.setText("Shot:")
            self.itemLabel.show()
            self.itemSelector.show()
            #self.itemLayout.setCurrentIndex(0)
        else:
            self.stepBox.loadSteps( )
            self.itemLabel.setText("Name:")
            self.itemLabel.hide()
            self.itemSelector.hide()

        # Update item list
        self.itemSelector.setType(itemType)

        self.currentTypeChanged.emit(itemType)

    @qc.Slot()
    def __stepChanged(self, step):
        self.currentStepChanged.emit(step)

    @qc.Slot()
    def __itemChanged(self, item:RamItem):
        self.currentItemChanged.emit(item)

    def itemType(self) -> ItemType:
        """Get the current item type"""
        return self.typeBox.currentData()

    def setItemType(self, itemType:ItemType):
        """Set the type"""
        if itemType == ItemType.ASSET:
            self.typeBox.setCurrentIndex(0)
        elif itemType == ItemType.SHOT:
            self.typeBox.setCurrentIndex(1)
        else:
            self.typeBox.setCurrentIndex(2)

    def currentStep(self):
        """The selected step"""
        return self.stepBox.currentObject()

    def setCurrentStep(self, step:RamStep):
        """Set the step"""
        if step:
            stepType = step.stepType()
            if stepType == StepType.ASSET_PRODUCTION:
                self.setItemType(ItemType.ASSET)
            elif stepType == StepType.SHOT_PRODUCTION:
                self.setItemType(ItemType.SHOT)
            else:
                self.setItemType(ItemType.GENERAL)
        self.stepBox.setCurrentStep(step)
        self.__stepChanged(step)

    def currentItem(self):
        """The selected item"""
        #if self.itemType() == ItemType.GENERAL:
        #    return RamItem(data={"shortName":self.itemNameEdit.text()})
        
        return self.itemSelector.currentItem()

    def setCurrentItem(self, item):
        """Set the item"""
        if item:
            self.setItemType(item.itemType())
        self.itemSelector.setGroup(None)
        self.itemSelector.setCurrentItem(item)

if __name__ == "__main__":

    w = RamItemStepSelectWidget()
    w.show()
