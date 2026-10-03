"""
步驟 7：用 Python 發 Discord 訊息（Uno 燒步驟 5 的主程式）
執行：uv run discord_alert.py [--port 序列埠] [--mode detect|test|check]（在課程資料夾裡執行）
不加 --mode 會先問要用哪一種模式。
需要套件：pyserial、requests
"""

import argparse
import json
import math
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
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

TEST_TEXT = "【防盜系統】測試訊息：收到代表 Discord 設定正確。"
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


# ---------- 發訊息 ----------

def alarm_text(line: str) -> str:
    """警報訊息的內容。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"【防盜系統】偵測到入侵\n時間：{now}\n訊息：{line}"


def test_text(line: str) -> str:
    """測試訊息的內容（不是警報）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    what = TEST_WHAT.get(",".join(line.split(",")[:2]), "測試")
    return f"【防盜系統・測試】{what}\n這是測試訊息，不是警報。\n時間：{now}\n訊息：{line}"


def send_discord(cfg: dict, text: str) -> bool:
    """發一則訊息到 Discord 頻道，成功回傳 True。"""
    url = cfg["discord"]["webhook_url"]
    try:
        # 這裡用 requests，不用內建的 urllib：
        # urllib 沒帶 User-Agent，會被 Discord 前面的 Cloudflare 擋下（403 / error 1010）
        response = requests.post(url, json={"content": text[:2000]}, timeout=10)
    except requests.RequestException as error:
        print(f"連線失敗：{error}")
        return False

    code = response.status_code
    if code in (200, 204):
        print("已發到 Discord")
        return True
    if code == 429:
        try:
            wait = response.json().get("retry_after", "?")
        except ValueError:
            wait = "?"
        print(f"發太快被限流，請等 {wait} 秒")
        return False
    if code in (401, 403, 404):
        print(f"Webhook 無效（{code}）：網址可能被刪除或複製不完整。")
        return False
    print(f"Discord 回應 {code}：{response.text[:200]}")
    return False


# ---------- 主程式 ----------

MENU = """選擇模式：
  1 偵測模式：自動布防，警報時發訊息
  2 測試模式：輸入 TEST 或觸發感測器，就發一則【測試】訊息
  3 只檢查帳號：不用接板子，發一則測試訊息"""
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

    required = ["discord.webhook_url"]
    if mode == "check":
        cfg = load_config(required)
        sys.exit(0 if send_discord(cfg, TEST_TEXT) else 1)

    if not args.port:
        required.append("serial_port")
    cfg = load_config(required)
    cooldown = cfg.get("cooldown_seconds", 60)
    ser = open_serial(args.port or cfg["serial_port"])
    write_lock = threading.Lock()
    stop = threading.Event()
    last_alarm = None  # 上次發出警報的時間
    last_test = None   # 上次發出測試的時間

    def send_command(cmd: str):
        with write_lock:
            ser.write(f"{cmd}\n".encode())

    try:
        if mode == "test":
            send_command("MODE,TEST")
            print("測試模式：Uno 亮紫燈、蜂鳴器不響。輸入 TEST，或手靠近超音波、照亮光敏電阻，"
                  "就會發出測試訊息。輸入 Q 結束。")
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
                if send_discord(cfg, alarm_text(line)):
                    last_alarm = time.monotonic()
            elif line.startswith("TEST,"):
                if last_test is not None and time.monotonic() - last_test < TEST_COOLDOWN:
                    left = math.ceil(TEST_COOLDOWN - (time.monotonic() - last_test))
                    print(f"冷卻中，{left} 秒內不再發測試訊息")
                    continue
                if send_discord(cfg, test_text(line)):
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
