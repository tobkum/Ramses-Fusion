"""! @brief Utilitaries
 @file utils.py
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

from time import time

try:
    from PySide2 import QtGui as qg
    from PySide2 import QtCore as qc
    from PySide2 import QtWidgets as qw
except:  # pylint: disable=bare-except
    from PySide6 import QtGui as qg
    from PySide6 import QtCore as qc
    from PySide6 import QtWidgets as qw

from ramses import (
    RAMSES,
    RAM_SETTINGS,
    log
)

from ramses_ui_pyside.update_dialog import RamUpdateDialog

@qc.Slot()
def openHelp():
    """Opens the online help for the addon"""
    if not RAMSES.host:
        return
    qg.QDesktopServices.openUrl( qc.QUrl( RAMSES.host.helpURL ) )

@qc.Slot()
def openGeneralHelp():
    """Opens the online help"""
    if not RAMSES.host:
        return
    qg.QDesktopServices.openUrl( qc.QUrl( RAM_SETTINGS.generalHelpUrl ) )

@qc.Slot()
def aboutRamses():
    """Opens the web page about Ramses"""
    qg.QDesktopServices.openUrl( qc.QUrl( RAM_SETTINGS.aboutRamsesURL ) )

@qc.Slot()
def donate():
    """Opens the donation page"""
    qg.QDesktopServices.openUrl( qc.QUrl( RAM_SETTINGS.donateURL ) )

@qc.Slot()
def openApiReference():
    """Opens the online API reference"""
    qg.QDesktopServices.openUrl( qc.QUrl( RAM_SETTINGS.apiReferenceUrl ) )

@qc.Slot()
def checkUpdate( discreet=False ):
    """Checks if an update is available for the tool"""

    if not RAMSES.host:
        return

    # if discreet and not debug, only once a day
    if discreet and not RAM_SETTINGS.debugMode:
        now = time()
        latest = RAM_SETTINGS.lastUpdateCheck
        if now - latest < 86400:
            return

    response = RAMSES.host.checkAddOnUpdate()
    info = response.get("data", {})

    RAM_SETTINGS.lastUpdateCheck = time()
    RAM_SETTINGS.save()

    if not info.get('update', False):
        log(RAMSES.host.name + " is up-to-date (" + RAMSES.host.version + ").")
        if not discreet:
            qw.QMessageBox.information(
                None,
                RAMSES.host.name,
                RAMSES.host.name + " is up-to-date (" + RAMSES.host.version + ")!"
            )
        return

    dialog = RamUpdateDialog( response, RAMSES.host.name, RAMSES.host.version)
    dialog.exec_()
