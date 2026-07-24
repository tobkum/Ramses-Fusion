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

import pytest

# Created inside a step folder in real use — never at the root of a drive.
_PIPELINE_FOLDERS = ("_versions", "_published", "_preview")


@pytest.fixture(scope="session")
def _drive_roots():
    """Existing drive roots, probed once (a per-test scan would be slow)."""
    return [
        "%s:\\" % letter
        for letter in string.ascii_uppercase
        if os.path.isdir("%s:\\" % letter)
    ]


def _pipeline_dirs_at(roots):
    return {
        os.path.join(root, name)
        for root in roots
        for name in _PIPELINE_FOLDERS
        if os.path.isdir(os.path.join(root, name))
    }


@pytest.fixture(autouse=True)
def no_drive_root_pipeline_dirs(request, _drive_roots):
    """Fails the individual test that creates a pipeline folder at a drive root.

    Cleans up what it finds (only if empty) so one offending test cannot cascade
    into failures for every test that follows it.
    """
    before = _pipeline_dirs_at(_drive_roots)
    yield
    created = sorted(_pipeline_dirs_at(_drive_roots) - before)

    for path in created:
        try:
            os.rmdir(path)  # empty-only by design: never delete real content
        except OSError:
            pass

    if created:
        pytest.fail(
            "%s created %s at a drive root.\n"
            "A fixture path's parent is a drive root (e.g. 'D:/test.comp' -> "
            "'D:/'). Use a realistic nested path and patch os.makedirs so the "
            "test cannot touch the filesystem." % (request.node.nodeid, created)
        )
