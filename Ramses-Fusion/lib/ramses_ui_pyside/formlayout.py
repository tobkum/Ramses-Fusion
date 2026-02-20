"""A Wrapper to help layout alignments"""

try:
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc


class RamFormLayout( qw.QFormLayout ):
    """A QFormLayout Wrapper to help layout alignments"""

    def __init__(self, labelWidth:int=50, parent:qw.QWidget=None):
        super(RamFormLayout, self).__init__(parent)

        self.__labelWidth = labelWidth
        self.setHorizontalSpacing(6)
        self.setVerticalSpacing(3)
        self.setFieldGrowthPolicy( qw.QFormLayout.AllNonFixedFieldsGrow )

    def addRow(self, label, widget:qw.QWidget=None):
        """Adds a new row to the layout"""
        if isinstance(label, str):
            label = qw.QLabel(label)
        label.setFixedWidth(self.__labelWidth)
        if widget is None:
            super(RamFormLayout, self).addRow(label)
        else:
            super(RamFormLayout, self).addRow(label, widget)
