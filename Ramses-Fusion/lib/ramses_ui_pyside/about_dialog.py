"""! @brief The Add-on about dialog.
 @file about_dialog.py
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
    from PySide2 import QtWidgets as qw
    from PySide2 import QtCore as qc
except:  # pylint: disable=bare-except
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc

from ramses_ui_pyside.utils import (
    donate
)

from ramses import (
    RAMSES,
    RamHost,
    log,
    LogLevel,
)

class RamAboutDialog(qw.QDialog):
    """The about dialog"""

    def __init__(self, parent=None):
        super(RamAboutDialog, self).__init__(parent)

        host = RAMSES.host
        if not host or host.version == "0.0.0":
            log("Host is not implemented", LogLevel.Critical)
            host = RamHost()

        self.setWindowTitle("About " + host.name)

        # DCC host panels use WindowStaysOnTopHint; match it so this dialog
        # appears above them. Set before exec() so Qt applies it at first show.
        self.setWindowFlags(self.windowFlags() | qc.Qt.WindowStaysOnTopHint)

        l = qw.QVBoxLayout()
        l.setContentsMargins(6,6,6,6)
        l.setSpacing(6)
        self.setLayout(l)

        l.addWidget(qw.QLabel( "<strong>" + host.name + "</strong> by " + host.vendorName + "<br />"
            "<i>v" + host.version + "</i><br />"
            "This is an Add-on to integrate the<br/>Ramses Asset Management System in " + host.hostName
        ))

        l.addWidget(qw.QLabel("<p>Licensed under the GNU General Public License v3</p>"
                              "<p>Please make a donation if you like this!</p>" ))

        self.donateButton = qw.QPushButton("💟 Donate ")
        l.addWidget(self.donateButton)

        self.donateButton.clicked.connect(donate)

if __name__ == "__main__":
    app = qw.QApplication.instance() or qw.QApplication()
    d = RamAboutDialog()
    d.exec_()
