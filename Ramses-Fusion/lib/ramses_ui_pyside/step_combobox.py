# -*- coding: utf-8 -*-
"""
A ComboBox for selecting steps
"""

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc

from ramses import RAMSES, StepType, RamStep, RamObject
from .object_combobox import RamObjectBox

class RamStepBox(RamObjectBox):
    """
    A ComboBox for selecting steps
    """

    currentStepChanged = qc.Signal(RamStep)

    # <== CONSTRUCTOR ==>

    def __init__(self, parent=None): # pylint: disable=useless-super-delegation
        super(RamStepBox, self).__init__(parent)
        self.currentObjectChanged.connect(self.__changeObject)

    @qc.Slot(RamObject)
    def __changeObject(self, obj):
        self.currentStepChanged.emit(obj)

    # <== PUBLIC ==>

    def currentStep(self):
        return self.currentObject()

    @qc.Slot(RamStep)
    def setCurrentStep(self, step):
        if isinstance(step, RamStep):
            self.setCurrentObject(step)
            return
        else:
            for i in range(self.count()):
                if self.itemData(i, qc.Qt.UserRole).shortName() == step:
                    self.setCurrentIndex(i)
                    return
            self.setCurrentIndex(-1)

    def loadSteps(self, stepType:str=StepType.ALL):
        project = RAMSES.project()
        if not project:
            return
        self.setObjects(project.steps(stepType, lazyLoading=False))
