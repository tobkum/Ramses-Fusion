# -*- coding: utf-8 -*-
import os
import re
import json
import threading
import glob
from ramses import (
    RamHost,
    RamItem,
    RamStep,
    RamStatus,
    RamFileInfo,
    LogLevel,
    ItemType,
    RAMSES,
    RAM_SETTINGS,
    RamMetaDataManager,
    RamState,
    RamDaemonInterface,
)

try:
    import ramses.yaml as yaml
except ImportError:
    import yaml
from fusion_config import FusionConfig

__all__ = ["FusionHost"]

# =============================================================================
# RENDER FORMAT CONSTANTS
# =============================================================================
FORMAT_QUICKTIME = "QuickTimeMovies"
CODEC_PRORES_422 = "Apple ProRes 422_apcn"
CODEC_PRORES_422_HQ = "Apple ProRes 422 HQ_apch"

# =============================================================================
# MONKEY-PATCHING RAMSES API (Fixes critical environment bugs only)
# =============================================================================

from ramses import RamFileManager

# Use a flag to ensure patches are only applied once
if not hasattr(RamFileManager, "_fusion_patched"):
    RamFileManager._fusion_patched = True

    # 1. Fix Race Condition: Disable background threads for copies.
    original_copy = RamFileManager.copy

    def _patched_copy(originPath, destinationPath, separateThread=False):
        """Forces synchronous file copying to prevent race conditions in Fusion's environment."""
        return original_copy(originPath, destinationPath, separateThread)

    RamFileManager.copy = staticmethod(_patched_copy)

    # 2. Fix Case Sensitivity and robust matching for version files on Windows.
    def _patched_getLatestVersionFilePath(filePath, previous=False):
        """Resolves the latest version file path using a robust, case-insensitive identity match."""
        fileName = os.path.basename(filePath)
        # Strip extension and any existing version block (_v001, _WIP001, etc)
        name_no_ext = fileName.split(".")[0]
        clean_name = re.sub(r"_[a-zA-Z]*\d+$", "", name_no_ext)
        base_id = clean_name.lower() + "_"

        versionsFolder = RamFileManager.getVersionFolder(filePath)
        if not os.path.isdir(versionsFolder):
            return ""

        candidates = []
        for f in os.listdir(versionsFolder):
            if not f.lower().startswith(base_id):
                continue
            path = os.path.join(versionsFolder, f)
            if not os.path.isfile(path):
                continue

            # Extract version from the end: ...STATE001.comp
            m = re.search(r"(\d+)\.[^.]+$", f)
            if m:
                version = int(m.group(1))
                candidates.append((version, path))

        if not candidates:
            return ""
        candidates.sort()  # Sort by version number

        if previous:
            return candidates[-2][1] if len(candidates) > 1 else ""
        return candidates[-1][1]

    def _patched_getVersionFilePaths(filePath):
        """Returns a list of all version files associated with the current composition's identity."""
        fileName = os.path.basename(filePath)
        name_no_ext = fileName.split(".")[0]
        clean_name = re.sub(r"_[a-zA-Z]*\d+$", "", name_no_ext)
        base_id = clean_name.lower() + "_"

        versionsFolder = RamFileManager.getVersionFolder(filePath)
        if not os.path.isdir(versionsFolder):
            return []

        candidates = []
        for f in os.listdir(versionsFolder):
            if not f.lower().startswith(base_id):
                continue
            path = os.path.join(versionsFolder, f)
            if not os.path.isfile(path):
                continue

            m = re.search(r"(\d+)\.[^.]+$", f)
            if m:
                version = int(m.group(1))
                candidates.append((version, path))

        candidates.sort()
        return [c[1] for c in candidates]

    RamFileManager.getLatestVersionFilePath = staticmethod(
        _patched_getLatestVersionFilePath
    )
    RamFileManager.getVersionFilePaths = staticmethod(_patched_getVersionFilePaths)

    # 3. Thread-Safe Socket Communication for RamDaemonInterface
    # We add a lock to the Singleton instance
    daemon = RamDaemonInterface.instance()
    if not hasattr(daemon, "_lock"):
        daemon._lock = threading.Lock()

    original_post = getattr(daemon, "_RamDaemonInterface__post")

    def _patched_post(self, query, bufsize=0):
        with self._lock:
            # We must use the original method which handles the actual socket logic
            # Since it's a private method, we call it via the mangled name on the instance
            return original_post(query, bufsize)

    # Apply the patch to the class method (handling private name mangling)
    RamDaemonInterface._RamDaemonInterface__post = _patched_post

    # 4. Fix Metadata Deletion in RamMetaDataManager
    # The API's auto-deletion logic is prone to race conditions and path mismatches.
    def _patched_getMetaData(folderPath):
        meta_file = RamMetaDataManager.getMetaDataFile(folderPath)
        if not os.path.exists(meta_file):
            return {}
        try:
            with open(meta_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _patched_getFileMetaData(filePath):
        data = RamMetaDataManager.getMetaData(os.path.dirname(filePath))
        return data.get(os.path.basename(filePath), {})

    RamMetaDataManager.getMetaData = staticmethod(_patched_getMetaData)
    RamMetaDataManager.getFileMetaData = staticmethod(_patched_getFileMetaData)

    # 5. Fix Side-Effect: Prevent automatic directory creation during path resolution.
    # The API's default behavior creates _versions and _published folders just by
    # checking paths, which clutters the filesystem during UI refreshes.
    def _patched_getVersionFolder(filePath):
        """Resolves the versions subfolder path without automatically creating it."""
        fileFolder = os.path.dirname(filePath)
        from ramses import RAM_SETTINGS

        versionsFolderName = RAM_SETTINGS.folderNames.versions
        if RamFileManager.inVersionsFolder(filePath):
            return fileFolder
        elif RamFileManager.inPublishFolder(filePath) or RamFileManager.inPreviewFolder(
            filePath
        ):
            return os.path.join(
                os.path.dirname(fileFolder), versionsFolderName
            ).replace("\\", "/")
        return os.path.join(fileFolder, versionsFolderName).replace("\\", "/")

    def _patched_getPublishFolder(filePath):
        """Resolves the published subfolder path without automatically creating it."""
        fileFolder = os.path.dirname(filePath)
        from ramses import RAM_SETTINGS

        publishFolderName = RAM_SETTINGS.folderNames.publish
        if RamFileManager.inPublishFolder(filePath):
            return fileFolder
        elif RamFileManager.inVersionsFolder(
            filePath
        ) or RamFileManager.inPreviewFolder(filePath):
            return os.path.join(os.path.dirname(fileFolder), publishFolderName).replace(
                "\\", "/"
            )
        return os.path.join(fileFolder, publishFolderName).replace("\\", "/")

    def _patched_getPublishInfo(filePath):
        """Resolves publish metadata for a file without creating any directories on disk."""
        if not os.path.isfile(filePath):
            return RamFileInfo()
        fileInfo = RamFileInfo()
        fileInfo.setFilePath(filePath)
        publishFolder = RamFileManager.getPublishFolder(filePath)
        versionInfo = RamFileManager.getLatestVersionInfo(filePath)
        versionFolder = ""
        if versionInfo.resource != "":
            versionFolder = versionInfo.resource + "_"
        from ramses.utils import intToStr

        versionFolder += intToStr(max(1, versionInfo.version))
        if versionInfo.state != "" and versionInfo.state.lower() != "v":
            versionFolder += "_" + versionInfo.state
        newFilePath = os.path.join(
            publishFolder, versionFolder, fileInfo.fileName()
        ).replace("\\", "/")
        publishedInfo = RamFileInfo()
        publishedInfo.setFilePath(newFilePath)
        publishedInfo.date = fileInfo.date
        publishedInfo.version = versionInfo.version
        if versionInfo.state != "" and versionInfo.state.lower() != "v":
            publishedInfo.state = versionInfo.state
        return publishedInfo

    RamFileManager.getVersionFolder = staticmethod(_patched_getVersionFolder)
    RamFileManager.getPublishFolder = staticmethod(_patched_getPublishFolder)
    RamFileManager.getPublishInfo = staticmethod(_patched_getPublishInfo)

    # 6. Fix State Reversion: Allow passing target state to publish process.
    def _patched_publish(
        self,
        forceShowPublishUI=False,
        incrementVersion=True,
        publishOptions=None,
        state=None,
    ):
        """Extended publish process that supports state propagation to prevent archive status reversion."""
        item = self.currentItem()
        step = self.currentStep()
        if not item or not step:
            return False

        # Save with correct state to prevent reversion
        state_short = state.shortName() if state else None
        self._RamHost__save(
            self.saveFilePath(), comment="Published", newStateShortName=state_short
        )

        publishInfo = self.publishInfo()
        if not publishOptions:
            publishOptions = step.publishSettings("yaml")
        publishOptions = self._publishOptions(publishOptions, forceShowPublishUI)
        if publishOptions is False or publishOptions is None:
            return False

        ramPublishOptions = publishOptions.get("ramsesPublishOptions", {})
        if ramPublishOptions.get("useTempFile", False):
            self.createTempWorkingFile()

        if not self._RamHost__runUserScripts(
            "before_pre_publish", publishInfo, publishOptions, item, step
        ):
            return False
        publishOptions = self._prePublish(publishInfo, publishOptions)
        if publishOptions is False or publishOptions is None:
            return False

        if ramPublishOptions.get("backupFile", False):
            self._RamHost__backupPublishedFile(publishInfo)
        if not self._RamHost__runUserScripts(
            "before_publish", publishInfo, item, step, publishOptions
        ):
            return False

        published_files = self._publish(publishInfo, publishOptions)
        if not published_files:
            return False
        for file in published_files:
            self._RamHost__setPublishMetadata(file, publishInfo)
        if not self._RamHost__runUserScripts(
            "on_publish", published_files, publishInfo, item, step, publishOptions
        ):
            return False

        status = self.currentStatus()
        if status:
            status.setPublished(True)
        self.closeTempWorkingFile()

        if incrementVersion:
            self._RamHost__save(
                self.saveFilePath(),
                incrementVersion=True,
                newStateShortName=state_short,
            )
        return True

    RamHost.publish = _patched_publish

# =============================================================================


class FusionHost(RamHost):
    """
    Ramses Host implementation for Blackmagic Fusion.
    """

    LOG_PREFIXES = {
        LogLevel.Info: "INFO",
        LogLevel.Warning: "WARNING",
        LogLevel.Critical: "ERROR",
        LogLevel.Debug: "DEBUG",
    }

    def __init__(self, fusion_obj: object) -> None:
        super().__init__()
        self.fusion = fusion_obj
        self.hostName = "Fusion"
        self._status_cache = None  # Used for UI badge caching

        try:
            self.hostVersion = str(
                self.fusion.GetAttrs().get("FUSION_Version", "Unknown")
            )
        except Exception:
            self.hostVersion = "Unknown"

    @staticmethod
    def normalizePath(path: object) -> str:
        """Centralized path normalization for Fusion (forward slashes).

        Args:
            path (object): The file path to normalize.

        Returns:
            str: The normalized path with forward slashes, or empty string if input is None/empty.
        """
        if not path:
            return ""
        return str(path).replace("\\", "/")

    @property
    def comp(self) -> object:
        """Gets the currently active Fusion composition.

        Returns:
            object: The active Fusion composition object, or None if not available.
        """
        return self.fusion.GetCurrentComp()

    def currentFilePath(self) -> str:
        """Gets the file path of the current composition.

        Returns:
            str: The normalized full path to the current composition file, or empty string if not saved.
        """
        if not self.comp:
            return ""
        path = self.comp.GetAttrs().get("COMPS_FileName", "")
        return self.normalizePath(path)

    def _isDirty(self) -> bool:
        """Checks if the current composition has unsaved changes.

        Returns:
            bool: True if the composition is modified (dirty), False otherwise.
        """
        if not self.comp:
            return False
        return self.comp.GetAttrs().get("COMPB_Modified", False)

    def _log(self, message: str, level: int) -> None:
        """Logs a message to the Fusion console (internal helper).

        Args:
            message (str): The message to log.
            level (int): The severity level (from Ramses LogLevel).
                         Levels below Info are ignored.
        """
        # Silence anything below Info level (0=Debug, -1=DataSent, -2=DataReceived)
        if level < LogLevel.Info:
            return

        prefix = self.LOG_PREFIXES.get(level, "LOG")
        print(f"[Ramses][{prefix}] {str(message)}")

    @staticmethod
    def _sanitizeNodeName(name: str) -> str:
        """Ensures a string is a valid Fusion node name.

        Fusion node names must be alphanumeric (underscores allowed) and cannot start with a digit.

        Args:
            name (str): The proposed name.

        Returns:
            str: A sanitized, valid node name.
        """
        if not name:
            return ""
        # Remove invalid chars (keep only alphanumeric and underscore)
        safe_name = "".join([c if c.isalnum() else "_" for c in name])
        # Fusion nodes cannot start with a digit
        if safe_name and safe_name[0].isdigit():
            safe_name = "R_" + safe_name
        return safe_name

    def currentStatus(self) -> RamStatus:
        """Gets the current status, with safety guards for non-pipeline files.

        Returns:
            RamStatus: The current status or None.
        """
        item = self.currentItem()
        step = self.currentStep()
        if not item or not step:
            return None

        # Only query if we have a valid item/step pair to avoid API crashes
        try:
            return item.currentStatus(step)
        except Exception as e:
            self._log(f"Failed to get status for {item}: {e}", LogLevel.Debug)
            return None

    def currentItem(self) -> RamItem:
        """Gets the current working Item, prioritizing DB-registered path first,
        then falling back to Metadata UUID if the path is unregistered (moved file).
        """
        if not self.comp:
            return None

        # 1. Try Path-based resolution first (Standard API behavior)
        # This returns a correctly typed RamShot/RamAsset if the path is in the DB.
        # If not, it returns a 'virtual' item based on filename.
        item = super().currentItem()

        # 2. If the item is virtual (not in DB), try to recover identity from Metadata
        if item and item.virtual():
            item_uuid = self.comp.GetData("Ramses.ItemUUID")
            if item_uuid:
                from ramses import RamShot, RamAsset, ItemType

                # Use the virtual item's type as a hint for the real object
                try:
                    target_type = item.itemType()
                    if target_type == ItemType.SHOT:
                        real_item = RamShot(item_uuid)
                    elif target_type == ItemType.ASSET:
                        real_item = RamAsset(item_uuid)
                    else:
                        real_item = RamItem(item_uuid)

                    # Verify the real item actually exists in DB by checking shortName
                    if real_item.shortName() != "Unknown":
                        return real_item
                except Exception as e:
                    self._log(f"Metadata UUID recovery failed: {e}", LogLevel.Debug)

        return item

    def currentStep(self) -> RamStep:
        """Gets the current working Step, prioritizing path-based resolution."""
        if not self.comp:
            return None

        # Standard API behavior (path-based)
        step = super().currentStep()

        # Note: If the file is moved, step will be None.
        # In the future, we could store StepUUID in metadata to resolve this.

        return step

    def isFusionStep(self, step: RamStep) -> bool:
        """Determines if a given Step is configured for Fusion.

        Checks:
        1. Linked Applications (via Ramses Daemon).
        2. Software-specific metadata/settings.
        3. Step naming conventions.

        Args:
            step (RamStep): The step to check.

        Returns:
            bool: True if it's a Fusion-related step.
        """
        if not step:
            return False

        daemon = RAMSES.daemonInterface()
        s_data = step.data()

        # 1. Linked Applications
        apps = s_data.get("applications", [])
        if isinstance(apps, list):
            for app_uuid in apps:
                app_data = daemon.getData(str(app_uuid), "RamApplication")
                app_name = str(app_data.get("name", "")).upper()
                if "FUSION" in app_name or "BMF" in app_name:
                    return True

        # 2. Metadata / Legacy Settings
        for key in ["application", "software", "app", "dcc"]:
            val = str(s_data.get(key, "")).upper()
            if "FUSION" in val or "BMF" in val:
                return True

        # 3. Step Naming
        if "FUSION" in step.shortName().upper():
            return True

        # 4. YAML General Settings
        stgs = step.generalSettings("yaml")
        if isinstance(stgs, dict):
            stg_val = str(stgs.get("application", "")).upper()
            if "FUSION" in stg_val or "BMF" in stg_val:
                return True

        return False

    def collectItemSettings(self, item: RamItem) -> dict:
        """Collects resolution and timing settings for the given item.

        Optimized version of base class `__collectItemSettings`.
        Uses API methods to handle overrides correctly while benefiting from DAEMON caching.
        Specifically handles Sequence-level overrides for Shot items.

        Args:
            item (RamItem): The item to collect settings for.

        Returns:
            dict: A dictionary containing 'width', 'height', 'framerate', 'duration',
                  'pixelAspectRatio', and optionally 'frames'.
        """
        if not item:
            return {}

        # STRICT MODE: Always use the Daemon's active project
        project = RAMSES.project()

        if not project:
            return {}

        settings = {
            "width": int(project.width() or 1920),
            "height": int(project.height() or 1080),
            "framerate": float(project.framerate() or 24.0),
            "duration": 0.0,
            "pixelAspectRatio": float(project.pixelAspectRatio() or 1.0),
        }

        if item and item.itemType() == ItemType.SHOT:
            # Use the sequence object to benefit from API override logic
            from ramses import RamShot

            shot = item if isinstance(item, RamShot) else RamShot(item.uuid())

            settings["duration"] = float(shot.duration())
            # Calculate frames manually using Project FPS (currently in settings['framerate'])
            # We use round() to avoid truncation errors present in the API's shot.frames() which uses int()
            settings["frames"] = int(
                round(settings["duration"] * settings["framerate"])
            )

            seq = shot.sequence()
            if seq:
                settings["width"] = int(seq.width())
                settings["height"] = int(seq.height())
                settings["framerate"] = float(seq.framerate())
                settings["pixelAspectRatio"] = float(seq.pixelAspectRatio())

        return settings

    def _get_fusion_settings(self, step) -> dict:
        """Helper to safely retrieve Fusion settings from a Step.

        The Ramses API 'publishSettings("yaml")' automatically parses the stored
        YAML string into a Python dictionary.
        """
        if not step:
            return {}
        try:
            data = step.publishSettings("yaml")
            if isinstance(data, dict):
                return data.get("fusion", {})
        except Exception as e:
            self.log(f"Error retrieving Step settings: {e}", LogLevel.Warning)

        return {}

    def _get_preset_settings(self, preset_name: str) -> tuple:
        """Resolves extension and sequence settings for a given preset.

        Returns:
            tuple: (extension: str, is_sequence: bool)
        """
        ext = "mov"
        is_sequence = False

        step = self.currentStep()
        fusion_cfg = self._get_fusion_settings(step)
        preset_cfg = fusion_cfg.get(preset_name, {})

        if preset_cfg:
            fmt = preset_cfg.get("format", "")
            if fmt:
                custom_ext = FusionConfig.get_extension(fmt)
                if custom_ext:
                    ext = custom_ext

            is_sequence = preset_cfg.get("image_sequence", False)

        return ext, is_sequence

    def _calculate_padding_str(self) -> str:
        """Calculates the sequence padding string (zeroes) based on the shot range."""
        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        item = self.currentItem()
        frames = 0
        if item:
            settings = self.collectItemSettings(item)
            frames = settings.get("frames", 0)

        end = start + max(0, frames - 1)
        padding = max(4, len(str(end)))
        return "0" * padding

    def resolvePreviewPath(self) -> str:
        """Resolves the designated preview file path for the current shot.

        Constructs the path using the project's preview folder and the Ramses naming convention.
        Respects custom format/sequence settings from the Step configuration.
        Uses zeroes (0) for frame padding if an image sequence is configured.

        Returns:
            str: The normalized absolute path for the preview file, or empty string on failure.
        """
        try:
            ext, is_sequence = self._get_preset_settings("preview")

            # Determine target folder: Project Preview Folder or Step Publish Folder fallback
            preview_folder = self.previewPath()
            if not preview_folder:
                # Fallback to standard Ramses publish path logic
                fallback_path = self.publishFilePath(ext, "")
                preview_folder = os.path.dirname(fallback_path)

            # Previews are typically non-versioned "Masters"
            pub_info = self.publishInfo()
            preview_info = pub_info.copy()
            preview_info.version = -1
            preview_info.state = ""
            preview_info.resource = ""
            preview_info.extension = ""  # Exclude from base filename for sequence logic

            base_filename = preview_info.fileName().rstrip(".")

            if is_sequence:
                padding_str = self._calculate_padding_str()
                # Fusion sequence format: name.0000.ext
                filename = f"{base_filename}.{padding_str}.{ext}"
                # Sequence subfolder logic
                preview_folder = os.path.join(preview_folder, base_filename)
            else:
                filename = f"{base_filename}.{ext}"

            return self.normalizePath(os.path.join(preview_folder, filename))
        except Exception as e:
            self._log(f"Failed to resolve preview path: {e}", LogLevel.Debug)
            return ""

    def resolveFinalPath(self) -> str:
        """Resolves the designated master export path for the current shot.

        Attempts to use the project's export path. If not set, falls back to the standard
        publish file path. Respects custom format/sequence settings from the Step configuration.
        Uses zeroes (0) for frame padding if an image sequence is configured.

        Returns:
            str: The normalized absolute path for the final export file, or empty string on failure.
        """
        try:
            # STRICT MODE: Rely on the Daemon's active project
            project = RAMSES.project()
            if not project:
                return ""

            ext, is_sequence = self._get_preset_settings("final")

            export_folder = project.exportPath()

            # 1. Resolve Base Filename and Target Directory
            pub_info = self.publishInfo()

            if export_folder:
                # Master Render (No versioning in filename)
                master_info = pub_info.copy()
                master_info.version = -1
                master_info.extension = ""
                base_filename = master_info.fileName().rstrip(".")
                target_dir = export_folder
            else:
                # Archival Render (Versioned fallback)
                # We get the path from Ramses, then strip extension for our own sequence logic
                archival_path = self.publishFilePath(ext, "")
                base_filename = os.path.splitext(os.path.basename(archival_path))[0]
                target_dir = os.path.dirname(archival_path)

            # 2. Handle Sequence Logic
            if is_sequence:
                padding_str = self._calculate_padding_str()
                # Fusion sequence format: name.0000.ext
                filename = f"{base_filename}.{padding_str}.{ext}"
                # Sequence subfolder
                target_dir = os.path.join(target_dir, base_filename)
            else:
                filename = f"{base_filename}.{ext}"

            return self.normalizePath(os.path.join(target_dir, filename))

        except Exception as e:
            self._log(f"Failed to resolve final path: {e}", LogLevel.Debug)
            return ""

    def _saveAs(
        self,
        filePath: str,
        item: RamItem,
        step: RamStep,
        version: int,
        comment: str,
        incremented: bool,
    ) -> bool:
        """Internal implementation to save the composition to a specific path.

        Args:
            filePath (str): The target file path.
            item (RamItem): The item being saved (unused by Fusion implementation).
            step (RamStep): The step context (unused by Fusion implementation).
            version (int): The version number (unused by Fusion implementation).
            comment (str): The comment (unused by Fusion implementation).
            incremented (bool): Whether this is an increment (unused by Fusion implementation).

        Returns:
            bool: True on success, False on failure.
        """
        if not self.comp:
            return False
        # Normalize path for Fusion
        filePath = self.normalizePath(filePath)
        try:
            self.comp.Save(filePath)
            return True
        except Exception as e:
            self.log(f"Failed to save: {e}", LogLevel.Critical)
            return False

    def _open(self, filePath: str, item: RamItem, step: RamStep) -> bool:
        """Internal implementation to open a composition file.

        Args:
            filePath (str): The file path to open.
            item (RamItem): The item context (unused).
            step (RamStep): The step context (unused).

        Returns:
            bool: True if file exists and opened, False otherwise.
        """
        if os.path.exists(filePath):
            # Normalize path for Fusion
            self.fusion.LoadComp(self.normalizePath(filePath))
            return True
        return False

    def _setFileName(self, fileName: str) -> bool:
        """Sets the internal file name of the composition without saving to disk.

        Args:
            fileName (str): The new file name/path.

        Returns:
            bool: True on success, False if no composition is active.
        """
        if not self.comp:
            return False
        return self.comp.SetAttrs({"COMPS_FileName": self.normalizePath(fileName)})

    def save(
        self,
        incremental: bool = False,
        comment: str = None,
        setupFile: bool = True,
        state: RamState = None,
    ) -> bool:
        """Saves the current file, optionally creating a new version or setting up the scene.

        Overridden to bypass the base class implementation of `__collectItemSettings` which
        is less efficient for Fusion. Instead, it calls `_setupCurrentFile` directly with
        optimized settings collection if `setupFile` is True.

        Args:
            incremental (bool, optional): If True, increments the version number. Defaults to False.
            comment (str, optional): Note describing the version changes. Defaults to None.
            setupFile (bool, optional): If True, applies project settings (FPS, res) to the comp. Defaults to True.
            state (RamState, optional): The target state for the version name. Ensures the archived
                                        filename matches the database status immediately.

        Returns:
            bool: True on success, False on failure.
        """
        if setupFile:
            item = self.currentItem()
            if item:
                settings = self.collectItemSettings(item)
                self._setupCurrentFile(item, self.currentStep(), settings)

        # When setupFile=False, persist metadata here (setupFile=True handles it via _setupCurrentFile)
        if not setupFile:
            item = self.currentItem()
            if item:
                self._store_ramses_metadata(item)

        # We call the internal __save method directly if we have a state override,
        # otherwise we fallback to the super().save() which handles default logic.
        if state or incremental or comment:
            saveFilePath = self.saveFilePath()
            if saveFilePath == "":
                from ramses import Log

                self.log(Log.MalformedName, LogLevel.Critical)
                return self.saveAs()

            # Name mangling for private method in parent class
            state_short = state.shortName() if state else None
            return self._RamHost__save(saveFilePath, incremental, comment, state_short)

        return super(FusionHost, self).save(
            incremental=incremental, comment=comment, setupFile=False
        )

    # -------------------------------------------------------------------------
    # UI Implementation helpers using UIManager
    # -------------------------------------------------------------------------

    def _request_input(
        self, title: str, fields: list, ok_text: str = "OK", cancel_text: str = "Cancel"
    ) -> dict:
        """Shows a custom modal dialog to request user input.

        Uses the Fusion UIManager to create a dynamic form based on the `fields` definition.
        Handles window events and result collection.

        Args:
            title (str): The title of the dialog window.
            fields (list of dict): A list of field definitions. Each dict must contain:
                - 'id' (str): Unique identifier for the field.
                - 'label' (str): Display text for the label.
                - 'type' (str): One of 'text', 'line', 'combo', 'slider', 'checkbox', 'label'.
                - 'default' (any): Default value.
                - 'options' (dict, optional): For 'combo' types, mapping index to label.
                - 'lines' (int, optional): For 'text' types, number of lines.
            ok_text (str): Label for the primary action button.
            cancel_text (str): Label for the secondary button (hidden if None/empty).

        Returns:
            dict: A dictionary mapping field IDs to their values if the user clicks OK,
                  or None if the user cancels.
        """
        ui = self.fusion.UIManager
        disp = bmd.UIDispatcher(ui)

        # Use a more unique ID to avoid dispatcher conflicts
        win_id = f"RamsesDlg_{int(os.getpid())}_{id(fields)}"

        # Modal behavior: Disable main window if it exists
        main_win = None
        if hasattr(self, "app") and hasattr(self.app, "dlg"):
            main_win = self.app.dlg

        if main_win:
            main_win.Enabled = False

        rows = []
        total_height = 80  # Buttons + Margins

        for f in fields:
            label = ui.Label(
                {
                    "Text": f["label"],
                    "Weight": 0.25,
                    "Alignment": {"AlignTop": True, "AlignRight": True},
                }
            )
            ctrl, height = self._create_ui_element(ui, f)
            total_height += height + 5  # Add small padding between rows
            rows.append(ui.HGroup([label, ctrl]))

        # Build Button Group
        buttons = [ui.HGap(0, 1)]
        buttons.append(
            ui.Button(
                {"ID": "OkBtn", "Text": ok_text, "Weight": 0, "MinimumSize": [120, 30]}
            )
        )
        if cancel_text:
            buttons.append(
                ui.Button(
                    {
                        "ID": "CancelBtn",
                        "Text": cancel_text,
                        "Weight": 0,
                        "MinimumSize": [120, 30],
                    }
                )
            )

        dlg = disp.AddWindow(
            {
                "WindowTitle": title,
                "ID": win_id,
                "Geometry": [400, 400, 500, total_height],
                "MaximumSize": [800, 1000],  # Prevent crazy growth
            },
            ui.VGroup(
                [
                    ui.VGroup({"Spacing": 5, "Weight": 0}, rows),
                    ui.VGap(
                        0, 1
                    ),  # Stretch gap to push buttons down and keep rows tight
                    ui.VGap(10),
                    ui.HGroup({"Weight": 0}, buttons),
                ]
            ),
        )

        results = {}
        # Track if the user actually clicked OK
        confirmed = [False]

        def on_ok(ev):
            confirmed[0] = True
            items = dlg.GetItems()
            for f in fields:
                if f["type"] == "label":
                    continue  # Skip data collection for labels

                ctrl = items[f["id"]]
                if f["type"] == "text":
                    results[f["id"]] = ctrl.PlainText
                elif f["type"] == "line":
                    results[f["id"]] = ctrl.Text
                elif f["type"] == "combo":
                    results[f["id"]] = int(ctrl.CurrentIndex)
                elif f["type"] == "slider":
                    results[f["id"]] = int(ctrl.Value)
                elif f["type"] == "checkbox":
                    results[f["id"]] = bool(ctrl.Checked)

            # Stop the loop
            disp.ExitLoop()

        def on_cancel(ev):
            disp.ExitLoop()

        # Bind handlers
        dlg.On.OkBtn.Clicked = on_ok
        if cancel_text:
            dlg.On.CancelBtn.Clicked = on_cancel
        dlg.On[win_id].Close = on_cancel

        try:
            dlg.Show()
            disp.RunLoop()
        finally:
            # Cleanup handlers safely
            try:
                dlg.On.OkBtn.Clicked = None
                dlg.On.CancelBtn.Clicked = None
                dlg.On[win_id].Close = None
            except Exception:
                pass

            dlg.Hide()
            # Re-enable main window
            if main_win:
                main_win.Enabled = True

        return results if confirmed[0] else None

    def _create_ui_element(self, ui: object, field_def: dict) -> tuple:
        """Creates a specific UI control based on the field definition.

        Args:
            ui (UIManager): The Fusion UIManager instance.
            field_def (dict): The field configuration (type, id, default, etc.).

        Returns:
            tuple: (control_object, height_int)
        """
        f_type = field_def["type"]
        f_id = field_def["id"]
        default = field_def.get("default", "")

        if f_type == "text":
            h = field_def.get("lines", 1) * 25 + 20
            return ui.TextEdit(
                {
                    "ID": f_id,
                    "Text": str(default),
                    "Weight": 0.75,
                    "MinimumSize": [200, h],
                }
            ), h

        if f_type == "line":
            return ui.LineEdit({"ID": f_id, "Text": str(default), "Weight": 0.75}), 30

        if f_type == "combo":
            ctrl = ui.ComboBox({"ID": f_id, "Weight": 0.75})
            options = field_def.get("options", {})
            for i in range(len(options)):
                val = options.get(str(i))
                if val:
                    ctrl.AddItem(str(val))
            ctrl.CurrentIndex = int(field_def.get("default", 0))
            return ctrl, 30

        if f_type == "slider":
            return ui.Slider(
                {
                    "ID": f_id,
                    "Value": float(default),
                    "Minimum": 0,
                    "Maximum": 100,
                    "Weight": 0.75,
                }
            ), 30

        if f_type == "checkbox":
            return ui.CheckBox(
                {"ID": f_id, "Checked": bool(default), "Text": "", "Weight": 0.75}
            ), 30

        if f_type == "label":
            # Calculate height based on characters (generous estimation)
            text_len = len(str(default))
            h = max(40, (text_len // 50 + 1) * 22)
            return ui.Label(
                {
                    "ID": f_id,
                    "Text": str(default),
                    "Weight": 0.75,
                    "WordWrap": True,
                    "Alignment": {"AlignTop": True, "AlignLeft": True},
                    "MinimumSize": [200, h],
                }
            ), h

        return ui.Label({"Text": "Unknown Field"}), 30

    # -------------------------------------------------------------------------
    # Pipeline Implementation
    # -------------------------------------------------------------------------

    def _import(
        self,
        filePaths: list,
        item: RamItem,
        step: RamStep,
        importOptions: list,
        forceShowImportUI: bool,
    ) -> bool:
        """Imports the specified files as Loader nodes into the current composition.

        Logic:
        1. Determines a grid location below the currently active tool.
        2. Iterates through file paths, creating a Loader node for each.
        3. Staggers nodes horizontally.
        4. Renames nodes based on the Item/Step naming convention (`Item_Step`), sanitizing names to be Fusion-safe.
        5. Sets the Global Start time to match the project start.

        Args:
            filePaths (list): List of absolute file paths to import.
            item (RamItem): The source item associated with the files.
            step (RamStep): The source step associated with the files.
            importOptions (list): (Unused) Import options.
            forceShowImportUI (bool): (Unused) Whether to force UI.

        Returns:
            bool: True on success, False if no composition is open.
        """
        if not self.comp:
            return False
        self.comp.Lock()

        # Get start frame for alignment
        start_frame = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)

        # Determine Reference Position (Grid Units)
        flow = self.comp.CurrentFrame.FlowView
        start_x, start_y = 0, 0

        active = self.comp.ActiveTool
        if active and flow:
            pos = flow.GetPosTable(active)
            # Fusion returns {1.0: x, 2.0: y} in Grid Units
            if pos:
                start_x = pos[1]
                start_y = pos[2] + 1  # Start one unit below active tool

        for i, path in enumerate(filePaths):
            # Stagger horizontally
            target_x = start_x + i
            target_y = start_y

            loader = self.comp.AddTool("Loader", target_x, target_y)
            if loader:
                # Explicitly set the clip path with forward slashes for cross-platform safety
                loader.Clip[1] = self.normalizePath(path)

                # Smart Naming with safety fallback
                if item:
                    raw_name = (
                        f"{item.shortName()}_{step.shortName()}"
                        if step
                        else item.shortName()
                    )
                else:
                    # Fallback to sanitized base filename
                    raw_name = os.path.splitext(os.path.basename(path))[0]

                name = self._sanitizeNodeName(raw_name)

                if name:
                    # Prevent name collisions by checking if node exists and appending counter
                    final_name = name
                    counter = 1
                    while self.comp.FindTool(final_name):
                        final_name = f"{name}_{counter}"
                        counter += 1
                    loader.SetAttrs({"TOOLS_Name": final_name})

                # Automatic Alignment
                loader.GlobalIn[1] = float(start_frame)

        self.comp.Unlock()
        return True

    def _importUI(self, item: RamItem, step: RamStep) -> dict:
        """Shows the native Fusion file request dialog for importing.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            dict: {'filePaths': [path]} or None if cancelled.
        """
        path = self.fusion.RequestFile()
        return {"filePaths": [path]} if path else None

    def _openUI(self, item: RamItem = None, step: RamStep = None) -> dict:
        """Shows the native Fusion file request dialog for opening a composition.

        Args:
            item (RamItem, optional): Context item.
            step (RamStep, optional): Context step.

        Returns:
            dict: {'filePath': path} or None if cancelled.
        """
        path = self.fusion.RequestFile()
        return {"filePath": path} if path else None

    def _preview(
        self,
        previewFolderPath: str,
        previewFileBaseName: str,
        item: RamItem,
        step: RamStep,
    ) -> list:
        """Renders a preview using the `_PREVIEW` Saver anchor.

        Locates the specific `_PREVIEW` node in the flow, sets its output path,
        applies the preview render preset, triggers the render,
        and verifies the output file.

        Args:
            previewFolderPath (str): Target directory for the preview.
            previewFileBaseName (str): Base filename.
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            list: List of generated file paths (usually just one), or empty list on failure.
        """
        if not self.comp:
            return []

        # 1. Find the Preview Anchor
        preview_node = self.comp.FindTool("_PREVIEW")
        if not preview_node:
            self.log(
                "Preview anchor (_PREVIEW) not found in Flow. Use 'Setup Scene' to add one.",
                LogLevel.Warning,
            )
            return []

        # 2. Resolve the final path using centralized logic (Respects Step Config)
        dst = self.resolvePreviewPath()
        if not dst:
            self.log("Could not resolve preview path.", LogLevel.Critical)
            return []

        # 3. Armed for render
        self.log(f"Starting preview render to: {dst}", LogLevel.Info)

        # Ensure directory exists
        prev_dir = os.path.dirname(dst)
        if not os.path.exists(prev_dir):
            os.makedirs(prev_dir)

        preview_node.Clip[1] = dst
        self.apply_render_preset(preview_node, "preview")
        preview_node.SetAttrs({"TOOLB_PassThrough": False})

        try:
            # 4. Trigger Fusion Render
            if self.comp.Render(True):
                # 5. Verify the output
                if self._verify_render_output(dst):
                    # Disarm immediately after render
                    preview_node.SetAttrs({"TOOLB_PassThrough": True})

                    # Save after render to ensure comp is clean and context is preserved
                    src = self.currentFilePath()
                    if src:
                        self.comp.Save(src)
                    return [dst]
                else:
                    self.log(
                        f"Preview render produced an invalid file: {dst}",
                        LogLevel.Critical,
                    )
            return []
        except Exception as e:
            self.log(f"Preview render failed: {e}", LogLevel.Critical)
            return []
        finally:
            # 6. Always disarm (redundant safety)
            if preview_node:
                preview_node.SetAttrs({"TOOLB_PassThrough": True})

    def _publishOptions(
        self, proposedOptions: dict, showPublishUI: bool = False
    ) -> dict:
        """Returns the publish options, optionally showing a UI.

        Currently just passes through default options.

        Args:
            proposedOptions (dict): Default options from the Step configuration.
            showPublishUI (bool): Whether to force a UI dialog.

        Returns:
            dict: The final publish options.
        """
        # If the UI is forced, we could show a dialog here.
        # For now, we return the options to ensure the process continues.
        return proposedOptions or {}

    def _prePublish(self, publishInfo: RamFileInfo, publishOptions: dict) -> dict:
        """Hook called before the publish process begins.

        Args:
            publishInfo (RamFileInfo): Info about the file to be published.
            publishOptions (dict): Options for the publish process.

        Returns:
            dict: Potentially modified publish options.
        """
        return publishOptions or {}

    def _verify_render_output(self, path: str) -> bool:
        """Verifies that a render output exists and is valid.
        Handles image sequences by checking for wildcard matches if the exact path
        contains padding placeholders (e.g., .0000. or .####.).

        Args:
            path (str): The path to verify.

        Returns:
            bool: True if file(s) exist and size > 0, False otherwise.
        """
        if not path:
            return False

        # 1. Direct check (for movies or single frames)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True

        # 2. Sequence check (for paths with 0000, ####, etc.)
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            return False

        filename = os.path.basename(path)
        # Identify common padding patterns between dots: .0000. , .####. , .%04d.
        # Uses lookbehind/lookahead to preserve the surrounding dots.
        # Matches: sequences of zeros, hash symbols, or printf-style %d formats.
        wildcard_name = re.sub(r"(?<=\.)(0+|#+|%\d*d)(?=\.)", "*", filename)

        if "*" in wildcard_name:
            matches = glob.glob(
                os.path.join(directory, wildcard_name).replace("\\", "/")
            )
            for m in matches:
                if os.path.isfile(m) and os.path.getsize(m) > 0:
                    return True

        return False

    def publish(
        self,
        forceShowPublishUI: bool = False,
        incrementVersion: bool = True,
        publishOptions: dict = None,
        state: RamState = None,
    ) -> bool:
        """Publishes the current item, ensuring the version file reflects the correct state.

        Overridden to propagate the target state during the publish render cycle,
        preventing archived versions from reverting to legacy state names.

        Args:
            forceShowPublishUI (bool): Whether to force the UI.
            incrementVersion (bool): Whether to increment the version after publish.
            publishOptions (dict): Custom options.
            state (RamState, optional): Target state for the version name.
                                        If None, fetches the current state from DB.

        Returns:
            bool: True on success.
        """
        # If no state provided, use the current one from the DB
        if not state:
            status = self.currentStatus()
            state = status.state() if status else None

        return super(FusionHost, self).publish(
            forceShowPublishUI=forceShowPublishUI,
            incrementVersion=incrementVersion,
            publishOptions=publishOptions,
            state=state,
        )

    def saveAs(self, setupFile: bool = True, state: RamState = None) -> bool:
        """Saves the current file as a new Item-Step, propagating state to the first version.

        Args:
            setupFile (bool): Whether to apply project settings.
            state (RamState, optional): Target state for the initial version.

        Returns:
            bool: True on success.
        """
        # We handle setupFile ourselves to use optimized Fusion logic
        if setupFile:
            res = self._saveAsUI()  # Base API shows UI
            if not res:
                return False

            # Re-apply the logic from save() but for the new context
            item, step = res.get("item"), res.get("step")
            if item:
                settings = self.collectItemSettings(item)
                self._setupCurrentFile(item, step, settings)
                self._store_ramses_metadata(item)

        # Call base saveAs - it will eventually call our _saveAs and copyToVersion
        # Note: RamHost.saveAs doesn't support state propagation, so we manually
        # increment the version after save if a state is provided.
        success = super().saveAs(setupFile=False)

        if success and state:
            # Force a correctly named version immediately
            self.save(incremental=False, state=state, setupFile=False)

        return success

    def updateStatus(
        self,
        state: RamState = None,
        comment: str = "",
        completionRatio: int = 50,
        savePreview: bool = False,
        publish: bool = False,
        showPublishUI: bool = False,
    ) -> bool:
        """Updates the item status in the database, optionally publishing and creating previews.

        Implements an atomic-like transaction:
        1. Saves and increments the version (on disk).
        2. Tries to publish (if requested).
        3. Updates the database status ONLY if publish succeeds (or wasn't requested).
        4. Generates a preview (optional).

                Args:
                    state (RamState, optional): The target state. If None, shows UI.
                    comment (str, optional): Note describing the version changes.
                    completionRatio (int, optional): Progress percentage (0-100).            savePreview (bool, optional): Whether to generate a preview render.
            publish (bool, optional): Whether to publish the file.
            showPublishUI (bool, optional): Whether to force the publish UI.

        Returns:
            bool: True on success, False on failure or cancellation.
        """
        # 1. Basic checks
        if not self.testDaemonConnection():
            return False

        # Ensure we are saved at least once as a Ramses item
        if not self.currentItem() and not self.save():
            return False

        # 2. Collect user input if parameters are missing
        if state is None:
            newStatusDict = self._statusUI(self.currentStatus())
            if not newStatusDict:
                return False

            publish = newStatusDict.get("publish", False)
            savePreview = newStatusDict.get("savePreview", False)
            comment = newStatusDict.get("note", "")
            completionRatio = newStatusDict.get("completionRatio", 50)
            state = newStatusDict.get("state", RAMSES.defaultState)
            showPublishUI = newStatusDict.get("showPublishUI", False)

        # 3. Step 1 of Transaction: Save and Increment Version
        # This creates the physical version on disk that we will either publish or keep as WIP.
        # We pass the state to ensure the filename matches the new status.
        save_comment = comment if comment else "Status change"
        if not self.save(incremental=True, comment=save_comment, state=state):
            self.log("Failed to save new version for status update.", LogLevel.Critical)
            return False

        # 4. Step 2 of Transaction: Publish (if requested)
        # If publish fails (render fails), we abort the database update.
        if publish:
            # We pass the state to publish() so the 'Published' save uses the correct name.
            if not self.publish(showPublishUI, incrementVersion=False, state=state):
                self.log(
                    "Publish failed. STATUS UPDATE ABORTED.",
                    LogLevel.Critical,
                )
                self.log(
                    "CRITICAL: A new version was saved to disk, but the database remains unchanged. "
                    "Please update status manually to fix the desync.",
                    LogLevel.Warning,
                )
                return False

        # 5. Step 3 of Transaction: Update the Database
        # Only reached if Publish succeeded OR was not requested.
        status = self.currentStatus()
        if status:
            status.setComment(comment)
            status.setCompletionRatio(completionRatio)
            status.setState(state)
            status.setVersion(self.currentVersion())

        # 6. Preview (Non-critical, doesn't abort the status update if it fails)
        if savePreview:
            try:
                self.savePreview()
            except Exception as e:
                self.log(f"Optional preview generation failed: {e}", LogLevel.Warning)

        return True

    def _publish(self, publishInfo: RamFileInfo, publishOptions: dict) -> list:
        """Executes the publish process: Final Render + Comp Backup.

        Implements a "Split Publish":
        1. Render: If `_FINAL` anchor exists, renders it to the Project Export folder.
        2. Backup: Saves a copy of the `.comp` file to the Step Publish folder (`_published`).

        If the render fails, the entire process is aborted.

        Args:
            publishInfo (RamFileInfo): Info about the file to be published.
            publishOptions (dict): Options for the publish process.

        Returns:
            list: List of published file paths (rendered file + backup file).
        """
        if not self.comp:
            return []

        src = self.currentFilePath()
        if not src:
            self.log(
                "Cannot publish: current composition has no saved path.",
                LogLevel.Critical,
            )
            return []

        # Ensure publishInfo has the correct extension for the comp backup
        ext = os.path.splitext(src)[1].lstrip(".")

        # Use the standard naming logic to get the correct publish path
        # 0. Sync Render Anchors (Critical for path validity)
        # Note: Handled by caller (RamsesFusionApp) or here?
        # App calls _sync_render_anchors() before save(), so we assume paths are correct.

        # 1. Store Internal Metadata (Project/Item UUID consistency)
        # This ensures we can identify the file's project even if paths are ambiguous.
        item = self.currentItem()
        if item:
            self._store_ramses_metadata(item)

        self.log(f"Publishing SRC: {src}", LogLevel.Info)

        published_files = []

        try:
            # 1. Automated Final Render
            # Find the _FINAL anchor node
            final_node = self.comp.FindTool("_FINAL")
            if not final_node:
                self.log(
                    "Publish ABORTED: No _FINAL anchor found. Use 'Setup Scene' to add one.",
                    LogLevel.Critical,
                )
                return []

            self.log("Starting final master render...", LogLevel.Info)
            # Enable the node
            final_node.SetAttrs({"TOOLB_PassThrough": False})
            render_success = False

            # Resolve and create directory before render
            render_path = self.normalizePath(final_node.Clip[1])
            render_dir = os.path.dirname(render_path)
            if render_dir and not os.path.exists(render_dir):
                os.makedirs(render_dir)

            try:
                # Execute render - comp.Render returns True only on success
                if self.comp.Render(True):
                    # Secondary Verification: Check file existence and size
                    if self._verify_render_output(render_path):
                        self.log(
                            f"Final render complete and verified: {render_path}",
                            LogLevel.Info,
                        )
                        render_success = True
                        published_files.append(render_path)
                    else:
                        self.log(
                            f"Final render produced an invalid file: {render_path}",
                            LogLevel.Critical,
                        )
                else:
                    self.log(
                        "Final render failed or was cancelled by user.",
                        LogLevel.Warning,
                    )
            finally:
                # Always disarm
                final_node.SetAttrs({"TOOLB_PassThrough": True})

            # GATEKEEPER: If render failed or was invalid, abort everything
            if not render_success:
                self.log(
                    "Publish ABORTED: Render failed. No files will be published.",
                    LogLevel.Critical,
                )
                return []

            # 2. Perform Comp File Backup (standard Ramses publish)
            # This only happens if final_node render succeeded.
            # We use RamFileManager.copy instead of _saveAs to avoid switching Fusion's context
            # to the published folder. This ensures the user stays in the working file.
            try:
                # Use publishInfo directly for the comp backup to follow API standards
                comp_publish_info = publishInfo.copy()
                comp_publish_info.extension = ext
                dst_comp = self.normalizePath(comp_publish_info.filePath())

                # Ensure directory exists (monkey-patched API no longer creates it automatically)
                comp_dir = os.path.dirname(dst_comp)
                if not os.path.exists(comp_dir):
                    os.makedirs(comp_dir)

                # src is our current working file, which was just saved by RamHost.publish()
                RamFileManager.copy(src, dst_comp, separateThread=False)
                self.log(f"Comp backup published to: {dst_comp}", LogLevel.Info)
                published_files.append(dst_comp)
            except Exception as e:
                self.log(f"Failed to copy comp backup: {e}", LogLevel.Warning)

            return published_files
        except Exception as e:
            self.log(f"Publish failed during process: {e}", LogLevel.Critical)
            return []

    def _replace(
        self,
        filePaths: list,
        item: RamItem,
        step: RamStep,
        importOptions: list,
        forceShowImportUI: bool,
    ) -> bool:
        """Replaces the selected Loader node's clip with the specified file.

        Also updates the node name if it was using a generic name.

        Args:
            filePaths (list): List containing the new file path (only first is used).
            item (RamItem): Context item (for naming).
            step (RamStep): Context step (for naming).
            importOptions (list): (Unused).
            forceShowImportUI (bool): (Unused).

        Returns:
            bool: True on success, False if no valid Loader selected.
        """
        if not self.comp:
            return False
        active = self.comp.ActiveTool
        if not active or active.GetAttrs()["TOOLS_RegID"] != "Loader":
            self.log("Please select a Loader node to replace.", LogLevel.Warning)
            return False

        if filePaths:
            active.Clip[1] = self.normalizePath(filePaths[0])
            # Rename if it was a generic name
            if "Loader" in active.GetAttrs()["TOOLS_Name"]:
                raw_name = (
                    f"{item.shortName()}_{step.shortName()}"
                    if step
                    else item.shortName()
                )
                name = self._sanitizeNodeName(raw_name)

                active.SetAttrs({"TOOLS_Name": name})
            return True
        return False

    def _replaceUI(self, item: RamItem, step: RamStep) -> dict:
        """Shows the native Fusion file request dialog for replacing.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.

        Returns:
            dict: {'filePaths': [path]} or None if cancelled.
        """
        res = self._openUI(item, step)
        if res:
            return {"filePaths": [res["filePath"]]}
        return None

    def _restoreVersionUI(self, versionFiles: list) -> str:
        """Shows a UI to select a version to restore.

        Args:
            versionFiles (list): List of file paths to previous versions.

        Returns:
            str: The selected file path, or empty string if cancelled.
        """
        if not versionFiles:
            return ""

        # Enrich options with comments from metadata
        opts = {}
        for i, f in enumerate(versionFiles):
            comment = RamMetaDataManager.getComment(f)
            basename = os.path.basename(f)
            label = f"{basename} - [{comment}]" if comment else basename
            opts[str(i)] = label

        res = self._request_input(
            "Restore Version",
            [
                {
                    "id": "Idx",
                    "label": "Select Version:",
                    "type": "combo",
                    "options": opts,
                }
            ],
        )
        return versionFiles[res["Idx"]] if res else ""

    def _saveAsUI(self) -> dict:
        """Shows the native Fusion file request dialog for 'Save As'.

        Parsing the selected path to reconstruct Ramses Item/Step context.

        Returns:
            dict: Dictionary with 'item', 'step', 'extension', 'resource', or None if cancelled.
        """
        path = self.fusion.RequestFile()
        if not path:
            return None

        # Use API to parse the selected path and instantiate the correctly typed object
        item = RamItem.fromPath(path, virtualIfNotFound=True)
        nm = RamFileInfo()
        nm.setFilePath(path)

        if not nm.project:
            self.log(
                "The selected path does not seem to belong to a Ramses project. This may cause pipeline issues.",
                LogLevel.Warning,
            )

        if not item:
            item = RamItem(
                data={
                    "name": nm.shortName or "New",
                    "shortName": nm.shortName or "New",
                },
                create=False,
            )

        step = RamStep.fromPath(path)
        # Ensure we have a valid Ramses step
        if not step:
            step = RamStep(
                data={"name": nm.step or "New", "shortName": nm.step or "New"},
                create=False,
            )

        return {
            "item": item,
            "step": step,
            "extension": os.path.splitext(path)[1].lstrip("."),
            "resource": nm.resource,
        }

    def _saveChangesUI(self) -> str:
        """Shows a dialog asking to save changes before closing/opening.

        Returns:
            str: 'save', 'discard', or 'cancel'.
        """
        res = self._request_input(
            "Save Changes?",
            [
                {
                    "id": "Mode",
                    "label": "Current file is modified. Action:",
                    "type": "combo",
                    "options": {
                        "0": "Save and Continue",
                        "1": "Discard and Continue",
                        "2": "Cancel",
                    },
                }
            ],
        )
        if not res:
            return "cancel"
        modes = {0: "save", 1: "discard", 2: "cancel"}
        return modes.get(res["Mode"], "cancel")

    def apply_render_preset(self, node, preset_name: str = "preview") -> None:
        """Applies standard pipeline settings (codec, format) to a Saver node.

        Optimized to avoid dirtying the composition if settings already match.
        Checks for Step-specific overrides in the Ramses Project Settings (YAML).

        Args:
            node (Tool): The Saver node to modify.
            preset_name (str, optional): 'preview' or 'final'. Defaults to "preview".
        """
        if not node:
            return

        # 1. Check for Step Overrides
        try:
            step = self.currentStep()
            fusion_cfg = self._get_fusion_settings(step)
            target_cfg = fusion_cfg.get(preset_name, {})

            if target_cfg:
                # Apply custom configuration
                FusionConfig.apply_config(node, target_cfg)
                return

        except Exception as e:
            self.log(f"Failed to apply Step Render Preset: {e}", LogLevel.Warning)

        # 2. Fallback to Hardcoded Defaults (ProRes)
        if node.GetInput("OutputFormat") != FORMAT_QUICKTIME:
            node.SetInput("OutputFormat", FORMAT_QUICKTIME, 0)

        compression_key = f"{FORMAT_QUICKTIME}.Compression"
        if preset_name == "preview":
            if node.GetInput(compression_key) != CODEC_PRORES_422:
                node.SetInput(compression_key, CODEC_PRORES_422, 0)
        else:
            # Final / default: Apple ProRes 422 HQ
            if node.GetInput(compression_key) != CODEC_PRORES_422_HQ:
                node.SetInput(compression_key, CODEC_PRORES_422_HQ, 0)

    def _store_ramses_metadata(self, item: RamItem) -> None:
        """Embeds Ramses identity (Project/Item UUIDs) into Fusion composition metadata.

        Optimized to only write data if it differs from current metadata.

        Args:
            item (RamItem): The item whose identity to store.
        """
        if not self.comp or not item:
            return

        try:
            item_uuid = str(item.uuid())
            if self.comp.GetData("Ramses.ItemUUID") != item_uuid:
                self.comp.SetData("Ramses.ItemUUID", item_uuid)

            # Store Project UUID (Resolves cross-project ambiguity)
            project = item.project() or RAMSES.project()
            if project:
                proj_uuid = str(project.uuid())
                if self.comp.GetData("Ramses.ProjectUUID") != proj_uuid:
                    self.comp.SetData("Ramses.ProjectUUID", proj_uuid)

            self.log(f"Embedded Ramses Metadata: {item.name()}", LogLevel.Debug)
        except Exception as e:
            self.log(f"Failed to embed metadata: {e}", LogLevel.Warning)

    def _setupCurrentFile(
        self, item: RamItem, step: RamStep, setupOptions: dict
    ) -> bool:
        """Applies Ramses settings (resolution, FPS, ranges) to the current composition.

        Updates Fusion Preferences (FrameFormat) and Attributes (Timeline/Render ranges).
        Persists identity metadata.

        Args:
            item (RamItem): Context item.
            step (RamStep): Context step.
            setupOptions (dict): Dictionary with 'width', 'height', 'framerate', 'frames', etc.

        Returns:
            bool: True on success.
        """
        if not self.comp:
            return False

        # Get duration from options or fallback to item
        fps = setupOptions.get("framerate", 24.0)
        duration = setupOptions.get("duration", 0.0)

        # If duration is 0, try to get it directly from item if it's a shot
        if duration <= 0 and item and item.itemType() == ItemType.SHOT:
            try:
                duration = float(item.duration())
            except (ValueError, TypeError, AttributeError):
                # Duration may be None or invalid, use default
                duration = 5.0

        # Fallback to a default if still 0
        if duration <= 0:
            duration = 5.0

        # If we have an explicit frame count from Ramses, use it.
        # Otherwise calculate from duration and (potentially overridden) FPS.
        if setupOptions.get("frames", 0) > 0:
            total_frames = int(setupOptions["frames"])
        else:
            total_frames = int(round(duration * fps))

        start = RAM_SETTINGS.userSettings.get("compStartFrame", 1001)
        end = start + total_frames - 1

        width = setupOptions.get("width", 1920)
        height = setupOptions.get("height", 1080)
        pa = setupOptions.get("pixelAspectRatio", 1.0)

        # Check if changes are actually needed (avoid dirtying the comp)
        curr_prefs = self.comp.GetPrefs("Comp.FrameFormat") or {}
        curr_w = int(curr_prefs.get("Width", 0))
        curr_h = int(curr_prefs.get("Height", 0))
        curr_fps = float(curr_prefs.get("Rate", 24.0))
        curr_pa_x = float(curr_prefs.get("AspectX", 1.0))
        curr_pa_y = float(curr_prefs.get("AspectY", 1.0))

        # Apply Resolution, Rate and Aspect Ratio via Prefs (batched for efficiency)
        new_prefs = {}
        # Use a small tolerance (0.1) for resolution to avoid sub-pixel dirtying
        if abs(curr_w - int(width)) > 0.1:
            new_prefs["Comp.FrameFormat.Width"] = int(width)
        if abs(curr_h - int(height)) > 0.1:
            new_prefs["Comp.FrameFormat.Height"] = int(height)
        if abs(curr_fps - float(fps)) > 0.001:
            new_prefs["Comp.FrameFormat.Rate"] = float(fps)
        if abs(curr_pa_x - float(pa)) > 0.001:
            new_prefs["Comp.FrameFormat.AspectX"] = float(pa)
        if abs(curr_pa_y - 1.0) > 0.001:
            new_prefs["Comp.FrameFormat.AspectY"] = 1.0

        if new_prefs:
            self.comp.SetPrefs(new_prefs)

        # Apply Timeline Ranges via Attrs (Immediate and more reliable)
        attrs = self.comp.GetAttrs()
        new_attrs = {}

        if attrs.get("COMPN_GlobalStart") != float(start):
            new_attrs["COMPN_GlobalStart"] = float(start)
        if attrs.get("COMPN_GlobalEnd") != float(end):
            new_attrs["COMPN_GlobalEnd"] = float(end)
        if attrs.get("COMPN_RenderStart") != float(start):
            new_attrs["COMPN_RenderStart"] = float(start)
        if attrs.get("COMPN_RenderEnd") != float(end):
            new_attrs["COMPN_RenderEnd"] = float(end)

        if new_attrs:
            self.comp.SetAttrs(new_attrs)

        # Persist Identity Metadata
        self._store_ramses_metadata(item)

        return True

    def _statusUI(self, currentStatus: RamStatus = None) -> dict:
        """Shows the dialog to update status, note, and publish settings.

        Args:
            currentStatus (RamStatus, optional): The current status object.

        Returns:
            dict: Dictionary with keys 'note', 'completionRatio', 'publish', 'state', 'showPublishUI', 'savePreview'.
                  Returns None if cancelled.
        """
        states = RAMSES.states()
        if not states:
            return None
        state_opts = {str(i): s.name() for i, s in enumerate(states)}

        cur_note = currentStatus.comment() if currentStatus else ""
        cur_short = currentStatus.state().shortName() if currentStatus else "WIP"
        def_idx = next(
            (i for i, s in enumerate(states) if s.shortName() == cur_short), 0
        )

        res = self._request_input(
            "Update Status",
            [
                {
                    "id": "Comment",
                    "label": "Note:",
                    "type": "text",
                    "default": cur_note,
                    "lines": 6,
                },
                {
                    "id": "State",
                    "label": "New State:",
                    "type": "combo",
                    "options": state_opts,
                    "default": def_idx,
                },
                {
                    "id": "Publish",
                    "label": "Publish Final:",
                    "type": "checkbox",
                    "default": False,
                },
            ],
        )

        if res is None:
            return None

        selected_state = states[res["State"]]

        return {
            "note": res["Comment"],
            "completionRatio": int(selected_state.completionRatio()),
            "publish": res["Publish"],
            "state": selected_state,
            "showPublishUI": False,
            "savePreview": False,
        }
