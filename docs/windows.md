# Windows (experimental)

`windows.py` provides the same adapter over UI Automation, Win32 `SendInput`, and
Windows.Media.Ocr, and `uv sync` installs its packages in place of the macOS ones. It is
untested on Windows: CI runs only its pure rules, on macOS and Linux. Expect it to break, and
please report what you see. Install the English OCR language once, from an elevated PowerShell:

```powershell
Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"
```

No permission prompt is needed. What differs from macOS:

- OCR reads English unless `CLICKER_OCR_LANGUAGE` names another language tag, such as `de`. It
  reports no confidence, so every line counts as certain. Windows.Media.Ocr reads one language
  per run, and that language's pack must be installed, from an elevated PowerShell, in the same
  way as the English one: `Language.OCR~~~de-DE~0.0.1.0` for `de`. A language without its pack
  fails the first recognition, and the message it prints always names the English pack.
- An app is its process: `activate` matches the executable name exactly (`notepad.exe`), or a
  known browser by its product name (`Google Chrome` is `chrome.exe`). Window titles never count.
- A click reads the cursor back first, and refuses to press, ending the run, when the cursor did
  not reach the target (a UAC prompt or the lock screen has the input).
- The browser URL is read off the address bar, which Chrome and Edge show without the scheme.
- Only the primary monitor is captured. Command-[ (back) is Alt-Left.
- When a policy blocks the installed `clicker.exe`, run `uv run python -m typesafe_computer_use`
  with the same arguments, or `... typesafe_computer_use inspect` for `clicker-inspect`.
