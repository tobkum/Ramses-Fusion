"""
A ComboBox for selecting states
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
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtCore as qc

from ramses import RAMSES, RamState, RamObject
from .object_combobox import RamObjectBox

class RamStateBox(RamObjectBox):
    """
    A ComboBox for selecting states
    """

    currentStateChanged = qc.Signal(RamState)

    # <== CONSTRUCTOR ==>

    def __init__(self, parent=None): # pylint: disable=useless-super-delegation
        super(RamStateBox, self).__init__(parent)
        self.currentObjectChanged.connect(self.__changeObject)

        # Populate states from Ramses
        self.setObjects( RAMSES.states() )
        self.setCurrentState( RAMSES.defaultState() )

    @qc.Slot(RamObject)
    def __changeObject(self, obj):
        self.currentStateChanged.emit(obj)

    # <== PUBLIC ==>

    def currentState(self):
        """The selected state"""
        return self.currentObject()

    @qc.Slot(RamState)
    def setCurrentState(self, state):
        """Select a state"""
        if isinstance(state, RamState):
            self.setCurrentObject(state)
            return
        else:
            for i in range(self.count()):
                if self.itemData(i, qc.Qt.UserRole).shortName() == state:
                    self.setCurrentIndex(i)
                    return
            self.setCurrentIndex(-1)
