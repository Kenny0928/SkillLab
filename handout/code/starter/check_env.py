"""
環境驗收：檢查 Python、套件、Gmail 連線、序列埠和板子，並顯示預設文字編碼
執行：uv run check_env.py [--port 序列埠]
板子要先燒好 hello 範例。輸出裡沒有帳號密碼，可以整段貼給老師或 AI。
"""

import argparse
import importlib.metadata
import locale
import platform
import re
import smtplib
import socket
import ssl
import sys
import time
from pathlib import Path

PYTHON_VERSION = (3, 13)
PACKAGES = ["pyserial", "requests", "flask"]
BAUD = 9600
WAIT_SECONDS = 6
# uv 裝的 Python 放在 cpython-3.13.16-macos-aarch64-none 這種名字的資料夾
UV_PYTHON = re.compile(r"cpython-\d+\.\d+[^/\\]*-(windows|macos|linux)-")

# USB 晶片的廠商代碼（VID）和產品代碼（PID）
CHIPS = {
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x10C4, 0xEA60): "CP2102",
}
VENDORS = {
    0x2341: "Arduino 原廠",
    0x2A03: "Arduino 原廠",
    0x1A86: "WCH（CH34x 系列）",
    0x10C4: "Silicon Labs（CP210x 系列）",
    0x0403: "FTDI",
    0x303A: "ESP32 內建 USB",
}

problems = 0


def report(ok, item, detail, fix=None):
    """ok：True 通過、None 注意、False 失敗"""
    global problems
    mark = {True: "[通過]", None: "[注意]", False: "[失敗]"}[ok]
    if ok is not True:
        problems += 1
    print(f"{mark} {item}：{detail}")
    if fix:
        print(f"       → {fix}")


def check_python():
    v = sys.version_info
    in_venv = sys.prefix != sys.base_prefix
    where = Path(sys.prefix).name if in_venv else "不在虛擬環境"
    detail = f"{v.major}.{v.minor}.{v.micro}（{where}）"
    if not in_venv:
        ok = None if (v.major, v.minor) == PYTHON_VERSION else False
        report(ok, "Python", detail, "在課程資料夾用 uv run check_env.py 執行，才會用到課程資料夾的 .venv")
    elif (v.major, v.minor) != PYTHON_VERSION:
        report(False, "Python", detail, "在課程資料夾執行 uv python pin 3.13，再執行 uv sync --managed-python")
    elif not UV_PYTHON.search(str(Path(sys.base_prefix).resolve())):
        report(None, "Python", f"{detail}，不是 uv 裝的 Python：{sys.base_prefix}",
               "刪掉課程資料夾裡的 .venv 資料夾，再執行 uv sync --managed-python")
    else:
        report(True, "Python", detail)


def check_packages():
    found, missing = [], []
    for name in PACKAGES:
        try:
            found.append(f"{name} {importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    if missing:
        report(False, "套件", "缺少 " + "、".join(missing), "在課程資料夾執行 uv add " + " ".join(missing))
    else:
        report(True, "套件", "、".join(found))


def show_encoding():
    # 中文 Windows 是 cp950，不算錯，但讀寫檔案要自己寫 encoding="utf-8"
    enc = locale.getpreferredencoding(False)
    if enc.lower().replace("-", "") == "utf8":
        print(f"預設文字編碼：{enc}")
    else:
        print(f'預設文字編碼：{enc}（讀寫檔案時要寫 encoding="utf-8"，含中文的檔案才不會出錯）')


def check_gmail():
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                              context=ssl.create_default_context(), timeout=10) as server:
            server.noop()
        report(True, "Gmail 連線", "smtp.gmail.com:465，憑證正常")
    except ssl.SSLCertVerificationError:
        report(False, "Gmail 連線", "憑證驗證失敗", "把這段輸出貼給老師")
    except (socket.gaierror, TimeoutError, OSError) as e:
        report(False, "Gmail 連線", f"連不上（{e.__class__.__name__}）",
               "確認網路；學校、公司的網路可能擋了 465 埠，換手機熱點再試一次")


def chip_name(p):
    if p.vid is None:
        return ""
    name = CHIPS.get((p.vid, p.pid)) or VENDORS.get(p.vid, "")
    return f"{name}，{p.vid:04X}:{p.pid:04X}" if name else f"{p.vid:04X}:{p.pid:04X}"


def check_board(port_arg):
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        report(False, "序列埠", "沒有 pyserial，無法檢查", "在課程資料夾執行 uv add pyserial")
        return

    # 只看 USB 裝置；macOS 的藍牙、除錯埠沒有 VID，會被排除
    ports = [p for p in serial.tools.list_ports.comports() if p.vid is not None]
    for p in ports:
        print(f"       {p.device}　{p.description}（{chip_name(p)}）")

    if port_arg:
        port = port_arg
    elif not ports:
        report(False, "序列埠", "沒有找到 USB 序列埠",
               "換一條確定能傳資料的 USB 線；再確認 USB 驅動程式有裝好")
        return
    elif len(ports) > 1:
        report(None, "序列埠", f"找到 {len(ports)} 個，不知道要用哪一個",
               "拔掉其他板子，或加上 --port 指定，例如 uv run check_env.py --port COM3")
        return
    else:
        port = ports[0].device
    report(True, "序列埠", port)

    try:
        with serial.Serial(port, BAUD, timeout=1) as ser:
            # 打開序列埠時 Uno 會重新開機，等它送出 hello
            deadline = time.time() + WAIT_SECONDS
            other = ""
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("hello"):
                    report(True, "板子", f"收到「{line}」")
                    return
                if line and not other:
                    other = line
        if other:
            report(None, "板子", f"有收到資料，但不是 hello：「{other[:40]}」",
                   "板子燒的不是 hello 範例，或範例的速率不是 9600")
        else:
            report(False, "板子", f"{WAIT_SECONDS} 秒內沒有收到資料",
                   "先在 Arduino IDE 把 hello 範例上傳到板子")
    except serial.SerialException as e:
        text = str(e)
        if any(s in text for s in ("denied", "Permission", "存取被拒", "Errno 13", "busy")):
            report(False, "板子", "序列埠打不開（被拒絕）",
                   "關掉 Arduino IDE 的序列埠監控視窗；Linux 要加入 dialout 群組後重新登入")
        else:
            report(False, "板子", f"序列埠打不開：{text}", "重新插拔 USB 線，再執行一次")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="SkillLab 環境驗收")
    parser.add_argument("--port", help="序列埠名稱，例如 COM3、/dev/ttyUSB0")
    args = parser.parse_args()

    print("SkillLab 環境驗收")
    print(f"系統：{platform.platform()}（{platform.machine()}）")
    show_encoding()
    check_python()
    check_packages()
    check_gmail()
    check_board(args.port)
    print()
    print("全部通過。" if problems == 0 else f"有 {problems} 項要處理，照 → 後面的說明做。")


if __name__ == "__main__":
    main()
