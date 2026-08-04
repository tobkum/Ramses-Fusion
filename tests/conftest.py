# -*- coding: utf-8 -*-
"""Test-suite hygiene guards.

Unit tests must never touch the real filesystem.

The specific mistake this catches actually happened and cost a long
investigation: ``test_createNewComp_save_failure`` stubbed a path resolver with
``"D:/test.comp"``. Its parent is a *drive root*, so the code under test
created real ``D:\\_versions`` and ``D:\\_published`` directories on the
developer's disk every time the suite ran. Because they appeared during
working sessions, they looked like a plugin bug rather than a test artifact —
a colleague running the same build never saw them, because he never ran the
tests.

The check belongs here rather than in the plugin: it is a property of the test
suite, so guarding it at runtime would be shipping code to defend against our
own fixtures.
"""

import os
import string
import sys

import pytest

# --- import paths -----------------------------------------------------------
# Set here rather than in each test module so every module is runnable on its
# own. They used to do it individually and one of them (test_integration) got
# it wrong, pointing at a directory that does not exist; it only passed in a
# full run because an alphabetically earlier module had already appended the
# correct path. Running that file alone gave 8 failures, and which SDK patches
# were live depended on collection order.
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
_APP_DIR = os.path.join(_PROJECT_ROOT, "Ramses-Fusion")
_LIB_DIR = os.path.join(_APP_DIR, "lib")

for _path in (_LIB_DIR, _APP_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# NOTE: the SDK patches are deliberately NOT applied here. Several test
# modules replace entries in sys.modules at import time, and importing the
# ramses package from conftest (before they get the chance) changes what they
# end up mocking. A module that depends on patched SDK behaviour applies the
# patches itself; see test_integration.py.

# Any directory created at a drive root is a test artefact. The check used to
# look only for these three names, which is why a fixture rendering to
# "D:/Previews/Shot_Preview.mov" quietly created D:\Previews on every run: the
# folder simply wasn't on the list. Kept only to name the usual suspects in
# the failure message.
_PIPELINE_FOLDERS = ("_versions", "_published", "_preview")


@pytest.fixture(scope="session")
def _drive_roots():
    """Existing drive roots, probed once (a per-test scan would be slow)."""
    return [
        "%s:\\" % letter
        for letter in string.ascii_uppercase
        if os.path.isdir("%s:\\" % letter)
    ]


def _dirs_at(roots):
    """Every top-level directory at each drive root.

    Deliberately name-agnostic: a test has no business creating *any*
    directory at a drive root, and an allow-list only catches the names
    somebody already thought of.
    """
    found = set()
    for root in roots:
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir():
                            found.add(entry.path)
                    except OSError:
                        continue  # vanished or permission-denied mid-scan
        except OSError:
            continue  # unreadable root (empty removable drive, etc.)
    return found


@pytest.fixture(autouse=True)
def no_drive_root_dirs(request, _drive_roots):
    """Fails the individual test that creates any directory at a drive root.

    Cleans up what it finds (only if empty) so one offending test cannot cascade
    into failures for every test that follows it.
    """
    before = _dirs_at(_drive_roots)
    yield
    created = sorted(_dirs_at(_drive_roots) - before)

    for path in created:
        try:
            os.rmdir(path)  # empty-only by design: never delete real content
        except OSError:
            pass

    if created:
        pytest.fail(
            "%s created %s at a drive root.\n"
            "Either a fixture path's parent is a drive root (e.g. 'D:/test.comp'"
            " -> 'D:/'), or a fixture renders to a made-up absolute path such as"
            " 'D:/Previews/x.mov'. Use tmp_path/tempfile, or patch os.makedirs "
            "so the test cannot touch the filesystem.\n"
            "(Pipeline folders %s at a root are the classic case.)"
            % (request.node.nodeid, created, list(_PIPELINE_FOLDERS))
        )


@pytest.fixture(autouse=True)
def no_leaked_comp_pin():
    """Fails any test that leaves FusionHost pinned to a composition.

    `FusionHost._pinned_comp` is class-level state that makes `host.comp`
    return one fixed composition for the duration of a publish or preview.
    If a test leaves it set, every later test in the run silently talks to
    that stale comp instead of its own fixture — the same failure the
    `Ramses.online()` singleton caused before it was reset per test, where
    one offline test quietly disabled every @requires_connection handler in
    the suite and the tests still passed.

    Reset before, asserted after, so a leak is attributed to the test that
    caused it rather than to whichever one runs next.
    """
    try:
        from fusion_host import FusionHost
    except Exception:  # pragma: no cover - fusion_host not importable here
        yield
        return

    FusionHost._pinned_comp = None
    yield
    leaked = FusionHost._pinned_comp
    FusionHost._pinned_comp = None
    assert leaked is None, (
        "test finished with FusionHost._pinned_comp still set (%r) - a "
        "pinned comp must always be released in a finally" % (leaked,)
    )
