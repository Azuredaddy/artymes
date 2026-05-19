"""
Standalone input test — run this directly to test if typing works at all.
Usage:  python test_input.py
Open Notepad before running.
"""
import time
import sys

print("=== ARTY Input Test ===")
print()

# ── Test 1: pyautogui available? ──────────────────────────────────────────────
try:
    import pyautogui
    print("[OK] pyautogui imported")
except ImportError as e:
    print(f"[FAIL] pyautogui: {e}")
    sys.exit(1)

# ── Test 2: pyperclip available? ─────────────────────────────────────────────
try:
    import pyperclip
    print("[OK] pyperclip imported")
    HAS_CLIP = True
except ImportError:
    print("[WARN] pyperclip not found — will use typewrite")
    HAS_CLIP = False

# ── Test 3: win32gui available? ───────────────────────────────────────────────
try:
    import win32gui, win32con
    print("[OK] win32gui imported")
    HAS_WIN32 = True
except ImportError:
    print("[WARN] win32gui not found (pywin32 not installed)")
    HAS_WIN32 = False

print()

# ── Test 4: find Notepad ──────────────────────────────────────────────────────
notepad_hwnd = 0
if HAS_WIN32:
    result = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                print(f"  visible window: {t}")
            if "notepad" in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    if result:
        notepad_hwnd = result[0]
        title = win32gui.GetWindowText(notepad_hwnd)
        print(f"\n[OK] Found Notepad: '{title}' hwnd={notepad_hwnd}")
    else:
        print("\n[WARN] Notepad not found in window list — open Notepad first!")

print()

# ── Test 5: click into Notepad and paste ─────────────────────────────────────
if notepad_hwnd and HAS_WIN32:
    rect = win32gui.GetWindowRect(notepad_hwnd)
    left, top, right, bottom = rect
    cx = (left + right) // 2
    cy = top + 80 + (bottom - top - 80) // 2
    print(f"Window rect: {rect}")
    print(f"Will click content area at: ({cx}, {cy})")
    print("Focusing and clicking in 2 seconds...")
    time.sleep(2)

    import win32api, win32con
    win32gui.ShowWindow(notepad_hwnd, 9)
    # Alt-key trick: unlocks Windows foreground-lock so SetForegroundWindow works reliably
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32gui.SetForegroundWindow(notepad_hwnd)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.6)
    pyautogui.click(cx, cy)
    time.sleep(0.4)

    if HAS_CLIP:
        pyperclip.copy("ARTY typing test - clipboard paste")
        pyautogui.hotkey("ctrl", "v")
        print("[OK] Clipboard paste sent")
    else:
        pyautogui.typewrite("ARTY typing test", interval=0.05)
        print("[OK] typewrite sent")

    time.sleep(0.5)
    # Also try pressing Enter then typing one more line
    pyautogui.press("enter")
    if HAS_CLIP:
        pyperclip.copy("Line 2 from ARTY")
        pyautogui.hotkey("ctrl", "v")

elif not HAS_WIN32:
    print("Trying without win32 — clicking at screen center in 2 seconds...")
    print("Manually click into Notepad NOW then wait...")
    time.sleep(4)
    if HAS_CLIP:
        pyperclip.copy("ARTY typing test - no win32")
        pyautogui.hotkey("ctrl", "v")
        print("[OK] Clipboard paste sent")

print()
print("=== Done — did text appear in Notepad? ===")
input("Press Enter to exit...")
