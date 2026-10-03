"""
步驟 6：用 Python 寄 Gmail（Uno 燒步驟 5 的主程式）
執行：uv run gmail_alert.py [--port 序列埠] [--mode detect|test|check]（在課程資料夾裡執行）
不加 --mode 會先問要用哪一種模式。
需要套件：pyserial
"""

import argparse
import json
import math
import smtplib
import ssl
import sys
import threading
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import serial
import serial.tools.list_ports

CONFIG_PATH = Path(__file__).with_name("config.json")

# config.example.json 裡的範例值，還沒改掉就代表「沒填」
PLACEHOLDERS = {
    "gmail.sender": "your.alarm@gmail.com",
    "gmail.app_password": "abcd efgh ijkl mnop",
    "gmail.to": "you@example.com",
    "discord.webhook_url": "https://discord.com/api/webhooks/貼上你的網址",
}

TEST_SUBJECT = "【防盜系統】測試信"
TEST_BODY = "這是一封測試信，收到代表 Gmail 設定正確。"
# 測試通知的冷卻時間，避免連按洗版
TEST_COOLDOWN = 10

# Uno 在測試模式送來的 TEST,xxx 對應的說明
TEST_WHAT = {
    "TEST,PING": "收到 TEST 指令",
    "TEST,DIST": "超音波偵測到物體",
    "TEST,LIGHT": "光敏電阻變亮",
}


# ---------- 三支程式共用的小工具（內容都一樣）----------

def get_field(cfg: dict, name: str):
    """用 "gmail.sender" 這種寫法取出設定值，找不到就回傳 None。"""
    value = cfg
    for key in name.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def missing_fields(cfg: dict, names) -> list:
    """回傳還沒填（空的或還是範例值）的欄位名稱。"""
    missing = []
    for name in names:
        value = get_field(cfg, name)
        if value is None or str(value).strip() == "" or value == PLACEHOLDERS.get(name):
            missing.append(name)
    return missing


def load_config(required=()) -> dict:
    """讀取同資料夾的 config.json，必要欄位沒填就結束程式。"""
    if not CONFIG_PATH.exists():
        print("找不到 config.json：請把 config.example.json 複製一份改名為 config.json，"
              "再填入你的資料。")
        sys.exit(1)
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"config.json 格式錯誤：{error}")
        sys.exit(1)
    for name in missing_fields(cfg, required):
        print(f"config.json 的 {name} 還沒填")
        sys.exit(1)
    return cfg


def wait_for_boot(ser, timeout: float = 5.0) -> bool:
    """Uno 開機會先送出 STATE,DISARMED；等到它（或已經在跑的 READ）才送指令，指令才不會遺失。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("STATE,") or line.startswith("READ,"):
            return True
    return False


def open_serial(port: str):
    """開啟序列埠，並等 Uno 開機完成（開啟序列埠時 Uno 會重新開機）。"""
    try:
        ser = serial.Serial(port, 9600, timeout=1)
    except (serial.SerialException, OSError) as error:
        print(error)
        print("可用的序列埠：")
        for item in serial.tools.list_ports.comports():
            print(item.device)
        print("Arduino IDE 的序列埠監控視窗開著的話，要先關掉。")
        if sys.platform.startswith("linux") and "Permission denied" in str(error):
            print("Linux 要先把帳號加入 dialout 群組：sudo usermod -a -G dialout $USER，"
                  "登出再登入後生效。")
        sys.exit(1)
    print("序列埠已開啟，等 Uno 開機…")
    if not wait_for_boot(ser):
        print("5 秒內沒有收到 Uno 的訊息：確認板子已燒錄步驟 5 的主程式。")
        ser.close()
        sys.exit(1)
    return ser


def is_alarm(line: str) -> bool:
    """步驟 5 的主程式進入警報時會送出 STATE,ALARM。"""
    return line == "STATE,ALARM"


# ---------- 寄信 ----------

def alarm_message(line: str) -> tuple:
    """警報信的主旨與內容。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "【防盜系統】偵測到入侵", f"時間：{now}\n訊息：{line}"


def test_message(line: str) -> tuple:
    """測試信的主旨與內容（不是警報）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    what = TEST_WHAT.get(",".join(line.split(",")[:2]), "測試")
    return (f"【防盜系統・測試】{what}",
            f"這是測試信，不是警報。\n時間：{now}\n來源：{what}\n訊息：{line}")


def send_gmail(cfg: dict, subject: str, body: str) -> bool:
    """寄一封信，成功回傳 True。"""
    gmail = cfg["gmail"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = gmail["sender"]
    msg["To"] = gmail["to"]
    msg.set_content(body)
    # Google 把應用程式密碼顯示成 4 組，中間有空格，登入時要去掉
    password = gmail["app_password"].replace(" ", "")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                              context=ssl.create_default_context(), timeout=20) as server:
            server.login(gmail["sender"], password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print("登入失敗：請確認用的是「應用程式密碼」而不是 Gmail 密碼，"
              "且帳號已開啟兩步驟驗證。")
        return False
    except ssl.SSLCertVerificationError:
        print("憑證驗證失敗：在課程資料夾用 uv run 執行，才會用到 uv 裝的 Python。")
        return False
    except Exception as error:
        print(f"寄信失敗：{error}")
        return False
    print("已寄出 Gmail")
    return True


# ---------- 主程式 ----------

MENU = """選擇模式：
  1 偵測模式：自動布防，警報時寄信
  2 測試模式：輸入 TEST 或觸發感測器，就寄一封【測試】信
  3 只檢查帳號：不用接板子，寄一封測試信"""
MODES = {"1": "detect", "2": "test", "3": "check"}


def choose_mode() -> str:
    """顯示選單，一直問到答案是 1、2 或 3。"""
    print(MENU)
    while True:
        try:
            answer = input("請輸入 1、2 或 3：").strip()
        except EOFError:
            sys.exit(1)
        if answer in MODES:
            return MODES[answer]


def keyboard_loop(ser, write_lock, stop):
    """背景執行緒：讀鍵盤，輸入 Q 就結束，其他文字原樣送給 Uno。"""
    while True:
        try:
            text = input().strip()
        except EOFError:
            return
        if not text:
            continue
        if text.lower() == "q":
            stop.set()
            return
        try:
            with write_lock:
                ser.write(f"{text}\n".encode())
        except (serial.SerialException, OSError) as error:
            print(error)
            stop.set()
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="序列埠，會蓋過 config.json 的 serial_port")
    parser.add_argument("--mode", choices=["detect", "test", "check"],
                        help="跳過選單，直接選模式")
    args = parser.parse_args()
    mode = args.mode or choose_mode()

    required = ["gmail.sender", "gmail.app_password", "gmail.to"]
    if mode == "check":
        cfg = load_config(required)
        sys.exit(0 if send_gmail(cfg, TEST_SUBJECT, TEST_BODY) else 1)

    if not args.port:
        required.append("serial_port")
    cfg = load_config(required)
    cooldown = cfg.get("cooldown_seconds", 60)
    ser = open_serial(args.port or cfg["serial_port"])
    write_lock = threading.Lock()
    stop = threading.Event()
    last_alarm = None  # 上次寄出警報的時間
    last_test = None   # 上次寄出測試的時間

    def send_command(cmd: str):
        with write_lock:
            ser.write(f"{cmd}\n".encode())

    try:
        if mode == "test":
            send_command("MODE,TEST")
            print("測試模式：Uno 亮紫燈、蜂鳴器不響。輸入 TEST，或手靠近超音波、照亮光敏電阻，"
                  "就會寄出測試信。輸入 Q 結束。")
        else:
            send_command("ARM")
            print("已送出 ARM：10 秒後開始偵測。可以輸入 DISARM、MUTE、STATUS，輸入 Q 結束。")
        threading.Thread(target=keyboard_loop, args=(ser, write_lock, stop),
                         daemon=True).start()

        while not stop.is_set():
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if not line.startswith("READ,"):  # READ 每 0.25 秒一行，印出來會洗版
                print(f"{datetime.now():%H:%M:%S} {line}")
            if line == "ERR,TEST":
                print("TEST 只能在測試模式使用：重新執行並選 2。")
            elif is_alarm(line):
                if last_alarm is not None and time.monotonic() - last_alarm < cooldown:
                    left = math.ceil(cooldown - (time.monotonic() - last_alarm))
                    print(f"冷卻中，{left} 秒內不再通知")
                    continue
                subject, body = alarm_message(line)
                if send_gmail(cfg, subject, body):
                    last_alarm = time.monotonic()
            elif line.startswith("TEST,"):
                if last_test is not None and time.monotonic() - last_test < TEST_COOLDOWN:
                    left = math.ceil(TEST_COOLDOWN - (time.monotonic() - last_test))
                    print(f"冷卻中，{left} 秒內不再寄測試信")
                    continue
                subject, body = test_message(line)
                if send_gmail(cfg, subject, body):
                    last_test = time.monotonic()
        print("已結束。")
    except KeyboardInterrupt:
        print("已結束。")
    except serial.SerialException as error:
        print(error)
        sys.exit(1)
    finally:
        if mode == "test":  # 不要讓板子一直停在安靜的測試模式
            try:
                send_command("MODE,DETECT")
            except Exception:
                pass
        ser.close()


if __name__ == "__main__":
    main()
