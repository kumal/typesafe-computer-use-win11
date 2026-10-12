"""The Windows adapter's pure rules. Nothing here touches Windows, so it runs everywhere."""

import ctypes
import re
from types import SimpleNamespace

import pytest

from typesafe_computer_use import windows
from typesafe_computer_use.models import ROLE_WORDS, TEXT_ROLES, Missed
from typesafe_computer_use.windows import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    app_matches,
    display_name,
    key_events,
    landed,
    ocr_lines,
    pressable,
    role_for,
    unicode_events,
    wheel_delta,
)

# ------------------------------------------------------------------ roles


def test_control_types_map_onto_the_roles_the_shared_code_knows():
    assert role_for("ButtonControl") == "AXButton"
    assert role_for("HyperlinkControl") == "AXLink"
    assert role_for("EditControl") in TEXT_ROLES  # a focused edit box is a text field
    assert role_for("ComboBoxControl") in TEXT_ROLES
    assert role_for("TextControl") == "AXStaticText"  # where a list row's label is recovered from


def test_an_unknown_control_type_has_no_role():
    assert role_for("PaneControl") == ""
    assert role_for("") == ""


def test_every_mapped_control_role_has_a_word_or_is_structural():
    structural = {"AXGroup", "AXStaticText", "AXIncrementor"}
    assert {role for role in windows.CONTROL_TYPE_TO_ROLE.values()} - set(ROLE_WORDS) <= structural


# ------------------------------------------------------------------ what is pressable


def test_an_invoke_pattern_is_pressable():
    assert pressable(True, "")


def test_a_legacy_default_action_is_pressable():
    assert pressable(False, "Press")
    assert pressable(False, "Jump")


def test_the_legacy_pattern_alone_is_not_pressable():
    """Almost every element carries LegacyIAccessible; without a named action it is not a control."""
    assert not pressable(False, "")
    assert not pressable(False, "   ")


# ------------------------------------------------------------------ which window is the app


def test_an_app_matches_its_own_process_exactly():
    assert app_matches("notepad.exe", "Notepad.exe")
    assert app_matches("notepad", "notepad.exe")
    assert app_matches("OUTLOOK", "outlook.exe")


def test_a_browser_matches_by_its_product_name():
    assert app_matches("Google Chrome", "chrome.exe")
    assert app_matches("microsoft edge", "msedge.exe")


def test_no_substring_match():
    assert not app_matches("Outlook", "outlookhelper.exe")
    assert not app_matches("note", "notepad.exe")
    assert not app_matches("Google Chrome", "chromedriver.exe")


def test_a_chrome_tab_named_after_an_app_is_not_that_app():
    """The window title never counts: only the process that owns the window."""
    assert not app_matches("Outlook", "chrome.exe")


def test_a_browser_is_reported_by_its_product_name():
    assert display_name("chrome.exe") == "Google Chrome"
    assert display_name("msedge.exe") == "Microsoft Edge"
    assert display_name("notepad.exe") == "notepad.exe"
    assert app_matches(display_name("chrome.exe"), "chrome.exe")  # what is reported can be activated


# ------------------------------------------------------------------ the address bar


@pytest.mark.parametrize(
    "name",
    [
        "Address and search bar",  # Chrome and Edge, English
        "Adress- und Suchleiste",  # Chrome and Edge, German
        "Search with Google or enter address",  # Firefox, English, with its search engine
        "Search or enter address",  # Firefox without one
        "Mit Google suchen oder Adresse eingeben",  # Firefox, German, as read off a real one
        "Suchen oder Adresse eingeben",
        "address and search bar",
    ],
)
def test_the_address_bar_is_found_by_its_name_in_each_browser_and_language(name):
    # uiautomation applies RegexName with re.match, so the name must match from its first character
    assert re.match(windows.ADDRESS_BAR_NAME, name)


@pytest.mark.parametrize(
    "name", ["Email address", "Search", "Suchen", "Mit Google suchen", "Reading address book", "Enter address book", ""]
)
def test_a_field_that_only_mentions_an_address_is_not_the_address_bar(name):
    assert not re.match(windows.ADDRESS_BAR_NAME, name)


class _Control:
    def __init__(self, value=None):
        self.value = value

    def Exists(self, *_):
        return self.value is not None


def _window_with(edit=None, combo=None):
    """A browser window as uiautomation shows it: which control kinds carry the address bar's name."""
    asked = []

    def find(kind, control):
        def look(**kwargs):
            asked.append((kind, kwargs["RegexName"]))
            return control or _Control()

        return look

    window = SimpleNamespace(EditControl=find("edit", edit), ComboBoxControl=find("combo", combo))
    return window, asked


def _browser_url_with(monkeypatch, window, first_read=False):
    """windows.browser_url against a fake window. By default the process has read once already, so
    the read searches once; `first_read` is the process's first, which waits for the bar."""
    monkeypatch.setattr(windows, "_find_window", lambda app: 1)
    monkeypatch.setattr(windows, "auto", SimpleNamespace(ControlFromHandle=lambda hwnd: window))
    monkeypatch.setattr(windows, "_ui_value", lambda control: control.value)
    monkeypatch.setattr(windows, "_bar_warmup_spent", not first_read)
    return windows.browser_url("Firefox")


class _Clock:
    """A clock the wait runs on instead of the real one: sleeping moves it, nothing waits."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _AppearsLater(_Control):
    """A bar that a cold browser shows only from the n-th search on."""

    def __init__(self, value, after):
        super().__init__(value)
        self.after = after
        self.searches = 0

    def Exists(self, *_):
        self.searches += 1
        return self.searches > self.after


def test_the_url_comes_from_an_edit_in_chrome_and_edge(monkeypatch):
    window, asked = _window_with(edit=_Control("example.com/page"))
    assert _browser_url_with(monkeypatch, window) == "example.com/page"
    assert asked == [("edit", windows.ADDRESS_BAR_NAME)]


def test_the_url_comes_from_a_combo_box_in_firefox(monkeypatch):
    window, asked = _window_with(combo=_Control("https://example.com/page"))
    assert _browser_url_with(monkeypatch, window) == "https://example.com/page"
    assert [kind for kind, _ in asked] == ["edit", "combo"]


def test_no_address_bar_has_no_url(monkeypatch):
    window, _ = _window_with()
    assert _browser_url_with(monkeypatch, window) is None


def test_an_address_bar_without_a_value_has_no_url(monkeypatch):
    window, _ = _window_with(edit=_Control(""), combo=_Control(""))
    assert _browser_url_with(monkeypatch, window) is None


def test_the_first_read_waits_for_a_cold_browser_to_show_its_address_bar(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    bar = _AppearsLater("www.temu.com/ch/stuhl", after=3)  # nothing for three searches, then there
    window, _ = _window_with(combo=bar)
    assert _browser_url_with(monkeypatch, window, first_read=True) == "www.temu.com/ch/stuhl"
    assert bar.searches == 4
    assert 0 < clock.now < windows.ADDRESS_BAR_WARMUP_SECONDS  # it waited, and stopped when it saw the bar


def test_a_first_read_that_never_sees_a_bar_gives_up_after_the_warmup(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    window, _ = _window_with()
    assert _browser_url_with(monkeypatch, window, first_read=True) is None
    assert windows.ADDRESS_BAR_WARMUP_SECONDS <= clock.now < windows.ADDRESS_BAR_WARMUP_SECONDS + 1


def test_the_wait_is_spent_once_per_process(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    window, _ = _window_with()
    assert _browser_url_with(monkeypatch, window, first_read=True) is None
    spent = clock.now
    assert windows.browser_url("Firefox") is None  # a window with no recognised bar, a second time
    assert clock.now == spent  # one search, no waiting


def test_a_bar_found_at_once_is_read_without_waiting(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    window, _ = _window_with(combo=_Control("example.com/page"))
    assert _browser_url_with(monkeypatch, window, first_read=True) == "example.com/page"
    assert clock.now == 0.0


def test_a_draft_in_a_found_bar_is_not_waited_for(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    window, _ = _window_with(combo=_Control("test suche"))
    assert _browser_url_with(monkeypatch, window, first_read=True) is None
    assert clock.now == 0.0  # the bar was there; its text just is not an address


def test_no_browser_window_uses_up_no_wait(monkeypatch):
    monkeypatch.setattr(windows, "_find_window", lambda app: None)
    monkeypatch.setattr(windows, "_bar_warmup_spent", False)
    assert windows.browser_url("Firefox") is None
    assert windows._bar_warmup_spent is False  # the first window that does exist still gets it


def test_the_escape_hatch_works_while_the_first_read_waits(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(windows, "time", clock)
    monkeypatch.setattr(windows, "mouse_location", lambda: (0.0, 0.0))  # the abort corner
    window, _ = _window_with()
    with pytest.raises(windows.Abort):
        _browser_url_with(monkeypatch, window, first_read=True)


def test_a_draft_in_the_address_bar_is_not_the_pages_url(monkeypatch):
    window, _ = _window_with(combo=_Control("test suche"))  # read off a real Firefox on a new tab
    assert _browser_url_with(monkeypatch, window) is None


def test_a_url_read_off_firefox_comes_back_without_the_scheme(monkeypatch):
    window, _ = _window_with(combo=_Control("www.youtube.com/shorts/F0iPaYngwX4"))  # a real read
    assert _browser_url_with(monkeypatch, window) == "www.youtube.com/shorts/F0iPaYngwX4"


def test_a_url_with_spaces_in_its_query_is_still_the_pages_url(monkeypatch):
    # Firefox shows the address decoded: this is the shape a real Temu page's address bar read back
    url = "www.temu.com/?_p_rfs=1&_x_ns_iradname=Online Tracking Link&_x_ns_irmpname=Firefox Browser - adMarketplace&_x=1"
    window, _ = _window_with(combo=_Control(url))
    assert _browser_url_with(monkeypatch, window) == url


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("www.youtube.com/shorts/F0iPaYngwX4", True),
        ("https://example.com/a%20b?q=1#x", True),
        ("about:preferences", True),
        ("example.com/my file.html", True),  # decoded %20 in the path
        ("example.com/?q=Online Tracking Link&x=1", True),  # decoded %20 in the query
        ("example.com#a section", True),
        ("test suche", False),  # read off a real Firefox on a new tab
        ("how to cook rice", False),
        ("what is 1/2 cup", False),  # a slash after the first word does not make it an address
        ("example.com now", False),
        ("", False),
        ("   ", False),
    ],
)
def test_a_url_may_hold_spaces_once_its_host_and_path_have_begun(text, expected):
    assert windows.is_url_text(text) is expected


# ------------------------------------------------------------------ input events


def test_a_plain_key_is_down_then_up():
    assert key_events("return") == [(0x0D, 0), (0x0D, KEYEVENTF_KEYUP)]


def test_command_becomes_control_held_around_the_key():
    assert key_events("a", command=True) == [(0x11, 0), (0x41, 0), (0x41, KEYEVENTF_KEYUP), (0x11, KEYEVENTF_KEYUP)]


def test_command_bracket_is_alt_left_the_windows_back():
    ext = KEYEVENTF_EXTENDEDKEY
    assert key_events("[", command=True) == [(0x12, 0), (0x25, ext), (0x25, ext | KEYEVENTF_KEYUP), (0x12, KEYEVENTF_KEYUP)]


def test_delete_is_an_extended_key():
    assert key_events("delete") == [(0x2E, KEYEVENTF_EXTENDEDKEY), (0x2E, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)]


def test_text_is_typed_as_unicode_characters_not_keys():
    down, up = KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    assert unicode_events("aé") == [(ord("a"), down), (ord("a"), up), (0xE9, down), (0xE9, up)]


def test_text_outside_ascii_survives():
    """pyautogui.typewrite dropped every one of these."""
    text = "Zoë, 東京, Ω"
    units = [unit for unit, flags in unicode_events(text) if not flags & KEYEVENTF_KEYUP]
    assert "".join(map(chr, units)) == text


def test_a_character_outside_the_bmp_is_a_surrogate_pair():
    units = [unit for unit, flags in unicode_events("😀") if not flags & KEYEVENTF_KEYUP]
    assert units == [0xD83D, 0xDE00]


def test_the_scroll_the_actions_ask_for_is_whole_notches_in_the_macos_direction():
    assert wheel_delta(10) > 0 and wheel_delta(-10) < 0  # positive scrolls up on both
    assert wheel_delta(-10) == -400  # ten lines at three a notch
    assert wheel_delta(3) == windows.WHEEL_DELTA


def test_the_input_record_has_the_size_windows_expects():
    """SendInput rejects a record of the wrong size, so the union must be as wide as MOUSEINPUT."""
    pointer = ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(windows._Input) == (40 if pointer == 8 else 28)


# ------------------------------------------------------------------ a click that reads back


def test_a_click_lands_only_where_the_cursor_went():
    assert landed((100, 200), (100.0, 200.0))
    assert landed((100, 200), (101.0, 199.0))
    assert not landed((100, 200), (0.0, 0.0))  # another desktop has the input
    assert not landed((100, 200), (100.0, 260.0))


def test_a_click_that_did_not_land_presses_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(windows, "_move", lambda point: None)
    monkeypatch.setattr(windows, "mouse_location", lambda: (0.0, 0.0))
    monkeypatch.setattr(windows, "_send", sent.append)
    with pytest.raises(Missed, match="not \\(640, 480\\)"):
        windows.click_at((640.0, 480.0))
    assert sent == []


def test_a_click_that_landed_presses_and_releases(monkeypatch):
    sent = []
    monkeypatch.setattr(windows, "_move", lambda point: None)
    monkeypatch.setattr(windows, "mouse_location", lambda: (640.0, 480.0))
    monkeypatch.setattr(windows, "_send", sent.append)
    windows.click_at((640.4, 479.6))
    assert [event.u.mi.dwFlags for event in sent] == [windows.MOUSEEVENTF_LEFTDOWN, windows.MOUSEEVENTF_LEFTUP]


# ------------------------------------------------------------------ OCR


def test_ocr_lines_box_the_words_and_report_full_confidence():
    result = {
        "text": "Sign in",
        "lines": [
            {
                "text": "Sign in",
                "words": [
                    {"text": "Sign", "bounding_rect": {"x": 10, "y": 20, "width": 30, "height": 12}},
                    {"text": "in", "bounding_rect": {"x": 45, "y": 18, "width": 12, "height": 16}},
                ],
            },
            {"text": "", "words": []},
        ],
    }
    assert ocr_lines(result) == [("Sign in", windows.OCR_CONFIDENCE, (10.0, 18.0, 57.0, 34.0))]
    assert windows.OCR_CONFIDENCE == 1.0  # Windows.Media.Ocr reports none


def test_ocr_reads_english_unless_told_otherwise(monkeypatch):
    monkeypatch.delenv("CLICKER_OCR_LANGUAGE", raising=False)
    assert windows.ocr_language() == "en"
    assert windows.OCR_LANGUAGE == "en"


def test_the_ocr_language_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("CLICKER_OCR_LANGUAGE", "de")
    assert windows.ocr_language() == "de"
    monkeypatch.setenv("CLICKER_OCR_LANGUAGE", " de-DE \n")
    assert windows.ocr_language() == "de-DE"  # a stray space from a .env line is not part of the tag


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_ocr_language_falls_back_to_the_default(monkeypatch, value):
    monkeypatch.setenv("CLICKER_OCR_LANGUAGE", value)
    assert windows.ocr_language() == windows.OCR_LANGUAGE


def test_recognition_asks_the_engine_for_the_chosen_language(monkeypatch):
    asked = []

    def recognize(image, language):
        asked.append(language)
        return {"lines": []}

    monkeypatch.setattr(windows, "winocr", SimpleNamespace(recognize_pil_sync=recognize))
    monkeypatch.delenv("CLICKER_OCR_LANGUAGE", raising=False)
    assert windows.recognize_text(object()) == []
    monkeypatch.setenv("CLICKER_OCR_LANGUAGE", "de")
    assert windows.recognize_text(object()) == []
    assert asked == ["en", "de"]
