import ctypes
from ctypes import wintypes
import sys

WFS_SUCCESS = 0
WFS_CMD_CDM_DISPENSE = 302
WFS_CDM_CASHUNIT_ANY = 0xFFFF

class WFSVERSION(ctypes.Structure):
    _fields_ = [
        ("wVersion", wintypes.WORD),
        ("wLowVersion", wintypes.WORD),
        ("wHighVersion", wintypes.WORD),
        ("szDescription", ctypes.c_char * 257),
        ("szSystemStatus", ctypes.c_char * 257),
    ]

class WFSCDMDISPENSEITEM(ctypes.Structure):
    _fields_ = [
        ("usNumber", wintypes.USHORT),
        ("usCashUnit", wintypes.USHORT),
    ]

class WFSCDMDISPENSE(ctypes.Structure):
    _fields_ = [
        ("usNumber", wintypes.USHORT),
        ("items", WFSCDMDISPENSEITEM * 1),
        ("bPresent", wintypes.BOOL),
    ]

def dispense_cash(count=5):
    try:
        # Загружаем DLL (WinDLL безопаснее для 64-битных систем)
        xfs = ctypes.WinDLL("msxfs.dll")
    except OSError:
        return -1

    # Настраиваем типы аргументов (ОЧЕНЬ ВАЖНО для 64-бит)
    xfs.WFSStartUp.argtypes = [wintypes.DWORD, ctypes.POINTER(WFSVERSION)]
    xfs.WFSStartUp.restype = wintypes.DWORD
    
    xfs.WFSOpen.argtypes = [ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(WFSVERSION), ctypes.POINTER(wintypes.HANDLE)]
    xfs.WFSOpen.restype = wintypes.DWORD
    
    xfs.WFSExecute.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    xfs.WFSExecute.restype = wintypes.DWORD
    
    xfs.WFSClose.argtypes = [wintypes.HANDLE]
    xfs.WFSCleanUp.argtypes = []

    version = WFSVERSION()
    # Инициализация XFS (3.02.03 или 3.10)
    res = xfs.WFSStartUp(0x00030203, ctypes.byref(version))
    if res != WFS_SUCCESS:
        res = xfs.WFSStartUp(0x00031000, ctypes.byref(version))
        if res != WFS_SUCCESS:
            return -3

    hService = wintypes.HANDLE()
    service_names = [b"CDM1", b"CDM2", b"CDM3", b"CashDispenser", b"NCR_CDM"]
    opened = False
    
    for name in service_names:
        res = xfs.WFSOpen(name, 0, 0x00030203, 0, ctypes.byref(version), ctypes.byref(hService))
        if res == WFS_SUCCESS:
            opened = True
            break
            
    if not opened:
        xfs.WFSCleanUp()
        return -4

    # Команда выдачи: 5 купюр с любой кассеты
    cmd = WFSCDMDISPENSE()
    cmd.usNumber = 1
    cmd.items[0].usNumber = count 
    cmd.items[0].usCashUnit = WFS_CDM_CASHUNIT_ANY
    cmd.bPresent = True

    result_data = ctypes.c_void_p()
    res = xfs.WFSExecute(hService, WFS_CMD_CDM_DISPENSE, ctypes.byref(cmd), 10000, ctypes.byref(result_data))

    # Закрываем сессию
    xfs.WFSClose(hService)
    xfs.WFSCleanUp()

    return 0 if res == WFS_SUCCESS else -5

if __name__ == "__main__":
    # Скрываем консоль, если запущено как exe
    if getattr(sys, 'frozen', False):
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    
    # Выдаем 500 рублей (5 купюр по 100)
    dispense_cash(5)
