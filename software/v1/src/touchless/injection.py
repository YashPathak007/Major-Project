"""Input injection — PLAN.md §9, §4 E10.

The injector is the ONLY path from gesture code to the OS cursor.
Two safety rules live here:

1. Never force focus. Injection targets whatever window is in the
   foreground; the controller never calls SetForegroundWindow.
2. Never inject into an elevated / secure window (UIPI). On Windows
   the foreground process integrity level is checked with ctypes; an
   elevated target produces E10 ("Can't control this window") instead
   of a silent no-op. On other platforms the check reports
   not-elevated (documented; the real check runs on Windows).

PyAutoGUI is imported lazily inside PyAutoGUIBackend so the core
modules import cleanly on machines without a display (tests use
FakeBackend). FAILSAFE is disabled deliberately: this program IS the
mouse, and its kill-switch is Esc / tray Quit — a corner-triggered
failsafe would fire whenever the user gestures into the top-left
corner. PAUSE is set to 0 for the §6 latency budget.
"""

from __future__ import annotations

import ctypes
import sys

E10_MESSAGE = (
    "Can't control this window — it needs higher permission. "
    "Use your mouse and keyboard here."
)


class InjectionBlocked(Exception):
    """Raised when injection is refused (E10). Carries the HUD message."""

    def __init__(self, message: str = E10_MESSAGE):
        super().__init__(message)
        self.message = message


class InjectionBackend:
    """Interface: move / click / drag / scroll / release."""

    def move(self, x: float, y: float) -> None:
        raise NotImplementedError

    def click(self) -> None:
        raise NotImplementedError

    def mouse_down(self) -> None:
        raise NotImplementedError

    def mouse_up(self) -> None:
        raise NotImplementedError

    def scroll(self, lines: int) -> None:
        raise NotImplementedError

    def screen_size(self) -> tuple[int, int]:
        raise NotImplementedError


class FakeBackend(InjectionBackend):
    """Recording backend for tests (and dry runs)."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.calls: list[tuple] = []
        self._size = (width, height)
        self.button_held = False

    def move(self, x: float, y: float) -> None:
        self.calls.append(("move", round(x, 1), round(y, 1)))

    def click(self) -> None:
        self.calls.append(("click",))

    def mouse_down(self) -> None:
        self.button_held = True
        self.calls.append(("mouse_down",))

    def mouse_up(self) -> None:
        self.button_held = False
        self.calls.append(("mouse_up",))

    def scroll(self, lines: int) -> None:
        self.calls.append(("scroll", lines))

    def screen_size(self) -> tuple[int, int]:
        return self._size


class PyAutoGUIBackend(InjectionBackend):
    """Real Windows backend. Imported lazily (needs a display)."""

    def __init__(self):
        import pyautogui  # noqa: PLC0415 (lazy: display required)
        pyautogui.FAILSAFE = False  # this program IS the mouse (see above)
        pyautogui.PAUSE = 0
        self._pg = pyautogui

    def move(self, x: float, y: float) -> None:
        self._pg.moveTo(int(x), int(y), duration=0)

    def click(self) -> None:
        self._pg.click()

    def mouse_down(self) -> None:
        self._pg.mouseDown()

    def mouse_up(self) -> None:
        self._pg.mouseUp()

    def scroll(self, lines: int) -> None:
        self._pg.scroll(lines)

    def screen_size(self) -> tuple[int, int]:
        size = self._pg.size()
        return int(size.width), int(size.height)


class ElevationChecker:
    """Reports whether the foreground window is elevated (Windows)."""

    def is_foreground_elevated(self) -> bool:
        if not sys.platform.startswith("win"):
            return False
        try:
            return _windows_foreground_elevated()
        except Exception:
            return False  # on any check failure, do not block input silently


def _windows_foreground_elevated() -> bool:
    """UIPI check via ctypes: foreground process integrity level."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return False
    try:
        token = ctypes.c_void_p(0)
        if not advapi32.OpenProcessToken(handle, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            return False
        try:
            TOKEN_INTEGRITY_LEVEL = 25
            needed = ctypes.c_ulong(0)
            advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(needed))
            buf = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, buf, needed, ctypes.byref(needed)):
                return False
            # TOKEN_MANDATORY_LABEL: SID at offset 4 (after 4-byte revision/authority count layout
            # the RID is the last sub-authority). Read the RID directly.
            sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
            # SID structure: revision(1) + sub_authority_count(1) + authority(6) + sub_authorities(4 each)
            count = sid[1]
            rid_offset = 8 + (count - 1) * 4
            rid = int.from_bytes(bytes(sid[rid_offset:rid_offset + 4]), "little")
            SECURITY_MANDATORY_HIGH_RID = 0x3000
            return rid >= SECURITY_MANDATORY_HIGH_RID
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.CloseHandle(handle)


class Injector:
    """Gatekeeper: every injection passes the E10 check first."""

    def __init__(self, backend: InjectionBackend,
                 elevation: ElevationChecker | None = None):
        self.backend = backend
        self.elevation = elevation or ElevationChecker()

    def _check(self) -> None:
        if self.elevation.is_foreground_elevated():
            raise InjectionBlocked()

    def move(self, x: float, y: float) -> None:
        self._check()
        self.backend.move(x, y)

    def click(self) -> None:
        self._check()
        self.backend.click()

    def mouse_down(self) -> None:
        self._check()
        self.backend.mouse_down()

    def mouse_up(self) -> None:
        """Button-up is ALWAYS allowed (quit/drag-cancel safety, §2 J6).

        Releasing a held button must never be blocked by the E10
        check — a stuck drag after quit is a catastrophic defect.
        """
        self.backend.mouse_up()

    def scroll(self, lines: int) -> None:
        self._check()
        self.backend.scroll(lines)

    def release_all(self) -> None:
        """Quit/drag-cancel path: unconditional button-up."""
        try:
            self.backend.mouse_up()
        except Exception:
            pass

    def screen_size(self) -> tuple[int, int]:
        return self.backend.screen_size()
