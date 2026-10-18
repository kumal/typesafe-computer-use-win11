"""The guard in conftest.py stands in front of every call that reaches the machine the suite runs on.

Nothing here calls one of them: a call that slipped through would take the machine over. Each is
checked by being the guard's refusal and not the real function.
"""

import os
import subprocess
import webbrowser

import pytest
from conftest import OS_LAUNCHES, REAL_WINDOWS, WEBBROWSER_CALLS, raw_windows_calls
from PIL import ImageGrab

from typesafe_computer_use import macos, windows


def refused(function) -> bool:
    return "refuse" in getattr(function, "__qualname__", "")


@pytest.mark.parametrize("name", ["_post", "osascript", "screenshot", "open_path"])
def test_the_macos_calls_that_reach_the_machine_are_refused(name):
    assert refused(getattr(macos, name))


@pytest.mark.parametrize(
    "name",
    ["_send", "_move", "_user32", "screenshot", "activate", "open_url", "open_path", "ax_press", "ax_focus", "ax_set_value"],
)
def test_the_windows_calls_that_reach_the_machine_are_refused(name):
    assert refused(getattr(windows, name))


def test_the_guard_also_stands_below_the_adapters_own_functions():
    assert refused(ImageGrab.grab)
    assert refused(subprocess.Popen)
    assert all(refused(getattr(webbrowser, name)) for name in WEBBROWSER_CALLS)
    assert all(refused(getattr(os, name)) for name in OS_LAUNCHES if hasattr(os, name))


@pytest.mark.skipif(not REAL_WINDOWS, reason="the Windows packages are not installed here")
def test_the_raw_windows_input_focus_and_launch_calls_are_refused():
    guarded = {(owner.__name__, name) for owner, name in raw_windows_calls()}
    for expected in [
        ("win32api", "SetCursorPos"),
        ("win32gui", "SetForegroundWindow"),
        ("win32gui", "ShowWindow"),
        ("uiautomation", "SendKeys"),
        ("InvokePattern", "Invoke"),
        ("ValuePattern", "SetValue"),
        ("LegacyIAccessiblePattern", "DoDefaultAction"),
    ]:
        assert expected in guarded
    for owner, name in raw_windows_calls():
        assert refused(getattr(owner, name)), f"{owner.__name__}.{name}"
