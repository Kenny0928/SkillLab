"""
步驟 8：網頁儀表板（Uno 燒步驟 5 的主程式）
執行：uv run dashboard.py [--port 序列埠] [--web-port 8000]（在課程資料夾裡執行）
需要套件：pyserial、flask、requests
"""

import argparse
import json
import logging
import math
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports
from flask import Flask, jsonify, request

# 通知功能來自步驟 6、7（放在同一個資料夾）。匯入失敗就當作沒有這個通知。
try:
    from gmail_alert import alarm_message, test_message, send_gmail
except Exception:
    send_gmail = None
try:
    from discord_alert import alarm_text, test_text, send_discord
except Exception:
    send_discord = None

CONFIG_PATH = Path(__file__).with_name("config.json")

# config.example.json 裡的範例值，還沒改掉就代表「沒填」
PLACEHOLDERS = {
    "gmail.sender": "your.alarm@gmail.com",
    "gmail.app_password": "abcd efgh ijkl mnop",
    "gmail.to": "you@example.com",
    "discord.webhook_url": "https://discord.com/api/webhooks/貼上你的網址",
}

STATE_TEXT = {
    "DISARMED": "撤防",
    "EXIT": "離開倒數",
    "ARMED": "布防",
    "ENTRY": "進入倒數",
    "ALARM": "警報",
    "TEST": "測試模式",
}
COMMANDS = ("ARM", "DISARM", "MUTE", "STATUS", "TEST", "MODE,TEST", "MODE,DETECT")

# 測試通知的冷卻時間，避免連按洗版
TEST_COOLDOWN = 10

# Uno 在測試模式送來的 TEST,xxx 對應的說明
TEST_WHAT_TEXT = {
    "PING": "收到 TEST 指令",
    "DIST": "超音波偵測到物體",
    "LIGHT": "光敏電阻變亮",
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


# ---------- 解析 Uno 傳來的一行 ----------

def parse_line(line: str):
    """把一行文字變成 dict；看不懂或數字壞掉就回傳 None。"""
    parts = line.strip().split(",")
    kind = parts[0]
    try:
        if kind == "READ" and len(parts) == 5:
            return {"type": "read", "dist": int(parts[1]), "light": int(parts[2]),
                    "threshold": int(parts[3]), "state": parts[4]}
        if kind == "STATE" and len(parts) == 2:
            return {"type": "state", "state": parts[1]}
        if kind == "DETECT" and len(parts) == 2 and parts[1] in ("DIST", "LIGHT"):
            return {"type": "detect", "what": parts[1]}
        if kind == "TEST" and len(parts) == 4 and parts[1] == "PING":
            return {"type": "test", "what": "PING", "dist": int(parts[2]),
                    "light": int(parts[3])}
        if kind == "TEST" and len(parts) == 3 and parts[1] == "DIST":
            return {"type": "test", "what": "DIST", "dist": int(parts[2])}
        if kind == "TEST" and len(parts) == 3 and parts[1] == "LIGHT":
            return {"type": "test", "what": "LIGHT", "light": int(parts[2])}
        if kind == "ERR" and len(parts) >= 2:
            return {"type": "err", "text": ",".join(parts[1:])}
    except ValueError:
        return None
    return None


# ---------- 共用狀態 ----------

class Board:
    """存放最新的資料。讀序列埠的執行緒和網頁會同時用，所以要上鎖。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.dist = None
        self.light = None
        self.threshold = None
        self.state = None
        self.last_seen = None  # 最後一次收到有效資料的時間
        self.events = deque(maxlen=50)

    def add_event(self, text: str):
        with self.lock:
            self._add_event(text)

    def _add_event(self, text: str):
        self.events.append({"time": datetime.now().strftime("%H:%M:%S"), "text": text})

    def update(self, msg: dict):
        """套用一筆資料。狀態剛變成警報回傳 "alarm"，收到測試訊息回傳 "test"，其他回傳 None。"""
        with self.lock:
            self.last_seen = time.monotonic()
            old_state = self.state
            if msg["type"] == "read":
                self.dist = msg["dist"]
                self.light = msg["light"]
                self.threshold = msg["threshold"]
                self.state = msg["state"]
            elif msg["type"] == "state":
                self.state = msg["state"]
            elif msg["type"] == "detect":
                if msg["what"] == "DIST":
                    self._add_event("偵測到：距離變近")
                else:
                    self._add_event("偵測到：盒子被打開")
            elif msg["type"] == "test":
                self._add_event(f"測試：{TEST_WHAT_TEXT[msg['what']]}")
                return "test"
            elif msg["type"] == "err":
                self._add_event(f"Uno 回報錯誤：{msg['text']}")
            if self.state != old_state:
                self._add_event(f"狀態：{STATE_TEXT.get(self.state, self.state)}")
            if self.state == "ALARM" and old_state != "ALARM":
                return "alarm"
            return None

    def snapshot(self, notify: str = "") -> dict:
        with self.lock:
            online = self.last_seen is not None and time.monotonic() - self.last_seen < 3
            return {
                "online": online,
                "dist": self.dist,
                "light": self.light,
                "threshold": self.threshold,
                "state": self.state,
                "state_text": STATE_TEXT.get(self.state, "—"),
                "notify": notify,
                "events": list(self.events)[::-1],  # 最新的排最前面
            }


# ---------- 警報通知 ----------

class Notifier:
    """狀態變成警報、或收到測試訊息時，在背景執行緒寄 Gmail、發 Discord。"""

    def __init__(self, cfg: dict, board: Board):
        self.cfg = cfg
        self.board = board
        self.cooldowns = {"alarm": cfg.get("cooldown_seconds", 60), "test": TEST_COOLDOWN}
        self.last_sent = {"alarm": None, "test": None}
        self.use_gmail = send_gmail is not None and not missing_fields(
            cfg, ["gmail.sender", "gmail.app_password", "gmail.to"])
        self.use_discord = send_discord is not None and not missing_fields(
            cfg, ["discord.webhook_url"])

    def describe(self) -> str:
        gmail = "開啟" if self.use_gmail else "關閉"
        discord = "開啟" if self.use_discord else "關閉"
        return f"通知：Gmail {gmail}、Discord {discord}"

    def trigger(self, kind: str, line: str):
        """kind 是 "alarm" 或 "test"。回傳背景執行緒（沒有要通知就回傳 None）。"""
        if not (self.use_gmail or self.use_discord):
            if kind == "test":
                self.board.add_event("測試：沒有設定 Gmail 或 Discord，沒有送出通知")
            return None
        now = time.monotonic()
        last = self.last_sent[kind]
        cooldown = self.cooldowns[kind]
        if last is not None and now - last < cooldown:
            what = "通知" if kind == "alarm" else "測試通知"
            text = f"冷卻中，{math.ceil(cooldown - (now - last))} 秒內不再{what}"
            print(text)
            self.board.add_event(text)
            return None
        self.last_sent[kind] = now
        thread = threading.Thread(target=self.send_all, args=(kind, line), daemon=True)
        thread.start()
        return thread

    def send_all(self, kind: str, line: str):
        is_test = kind == "test"
        if self.use_gmail:
            subject, body = test_message(line) if is_test else alarm_message(line)
            ok = send_gmail(self.cfg, subject, body)
            if is_test:
                self.board.add_event("已寄出測試信（Gmail）" if ok else "測試失敗：Gmail")
            else:
                self.board.add_event("已寄出 Gmail" if ok else "通知失敗：Gmail")
        if self.use_discord:
            ok = send_discord(self.cfg, test_text(line) if is_test else alarm_text(line))
            if is_test:
                self.board.add_event("已發出測試訊息（Discord）" if ok else "測試失敗：Discord")
            else:
                self.board.add_event("已發到 Discord" if ok else "通知失敗：Discord")


# ---------- 序列埠 ----------

board = Board()
notifier = None  # main() 會建立
ser = None  # main() 會開啟
write_lock = threading.Lock()
stopping = threading.Event()  # main() 結束前設定


def handle_line(line: str):
    if not line.startswith("READ"):  # READ 每 0.25 秒一行，印出來會洗版
        print(f"{datetime.now():%H:%M:%S} {line}")
    msg = parse_line(line)
    if msg is None:
        return
    kind = board.update(msg)
    if kind and notifier is not None:
        notifier.trigger(kind, line)


def reader_loop(port):
    """背景執行緒：一直讀序列埠，每一行交給 handle_line。"""
    while True:
        try:
            raw = port.readline()
        except Exception as error:
            if not stopping.is_set():  # 結束程式時序列埠已經關掉，不用印錯誤
                print(error)
            return
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            handle_line(line)


def send_command(cmd: str):
    with write_lock:
        ser.write(f"{cmd}\n".encode())


# ---------- 網頁 ----------

app = Flask(__name__)
# 網頁每 0.5 秒查詢一次，關掉 Flask 每個請求一行的紀錄
logging.getLogger("werkzeug").setLevel(logging.ERROR)

PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>防盜系統儀表板</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #fbfaf8; color: #17181a;
         font-family: system-ui, -apple-system, "Segoe UI", "Microsoft JhengHei",
                      sans-serif; }
  main { max-width: 640px; margin: 0 auto; padding: 24px 16px; }
  #badge { padding: 24px; border-radius: 4px; text-align: center; color: #fff;
           font-size: 40px; font-weight: 700; background: #8a8a85; }
  .DISARMED { background: #2e7d32 !important; }
  .EXIT, .ENTRY { background: #b26a00 !important; }
  .ARMED { background: #1f5fbf !important; }
  .ALARM { background: #c62828 !important; }
  .TEST { background: #6a3fb5 !important; }
  #offline { margin-top: 16px; padding: 12px; border: 1px solid #e4572e;
             border-radius: 4px; color: #e4572e; display: none; }
  .nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
          margin: 16px 0; }
  .num { padding: 16px 8px; border: 1px solid #e2e0db; border-radius: 4px;
         text-align: center; }
  .num b { display: block; font-size: 40px; font-variant-numeric: tabular-nums; }
  .num span { font-size: 14px; }
  .btns { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  button { padding: 16px; font-size: 18px; border: 1px solid #e2e0db;
           border-radius: 4px; background: #fff; color: #17181a; cursor: pointer; }
  .btns button:first-child { background: #e4572e; border-color: #e4572e; color: #fff; }
  .modes { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
           margin-bottom: 12px; }
  .modes button.on { background: #17181a; border-color: #17181a; color: #fff; }
  .btns.one { grid-template-columns: 1fr; }
  #notify { margin-top: 8px; font-size: 14px; color: #6b6b66; text-align: center; }
  button:disabled { opacity: .4; cursor: not-allowed; }
  h2 { font-size: 16px; margin: 24px 0 8px; }
  ul { list-style: none; margin: 0; padding: 0; border: 1px solid #e2e0db;
       border-radius: 4px; }
  li { padding: 8px 12px; border-bottom: 1px solid #e2e0db; }
  li:last-child { border-bottom: 0; }
  li time { margin-right: 12px; color: #6b6b66; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<main>
  <div id="badge">—</div>
  <div id="notify"></div>
  <div id="offline">板子離線：超過 3 秒沒有收到資料</div>
  <div class="nums">
    <div class="num"><b id="dist">—</b><span>距離（cm）</span></div>
    <div class="num"><b id="light">—</b><span>亮度</span></div>
    <div class="num"><b id="threshold">—</b><span>觸發距離（cm）</span></div>
  </div>
  <div class="modes">
    <button id="m-detect" data-cmd="MODE,DETECT">偵測模式</button>
    <button id="m-test" data-cmd="MODE,TEST">測試模式</button>
  </div>
  <div class="btns" id="detect">
    <button data-cmd="ARM">布防</button>
    <button data-cmd="DISARM">撤防</button>
    <button data-cmd="MUTE">靜音</button>
  </div>
  <div class="btns one" id="testbtns" style="display: none">
    <button data-cmd="TEST">送出測試通知</button>
  </div>
  <h2>事件紀錄</h2>
  <ul id="events"></ul>
</main>
<script>
  const $ = (id) => document.getElementById(id);
  const num = (v, hideNegative) => (v === null || (hideNegative && v < 0)) ? "—" : v;

  function render(s) {
    $("badge").textContent = s.state_text;
    $("badge").className = s.state || "";
    $("dist").textContent = num(s.dist, true);
    $("light").textContent = num(s.light, false);
    $("threshold").textContent = num(s.threshold, false);
    $("notify").textContent = s.notify || "";
    const test = s.state === "TEST";
    $("m-detect").className = test ? "" : "on";
    $("m-test").className = test ? "on" : "";
    $("detect").style.display = test ? "none" : "grid";
    $("testbtns").style.display = test ? "grid" : "none";
    $("offline").style.display = s.online ? "none" : "block";
    document.querySelectorAll("button").forEach((b) => (b.disabled = !s.online));
    const list = $("events");
    list.innerHTML = "";
    for (const e of s.events) {
      const li = document.createElement("li");
      const t = document.createElement("time");
      t.textContent = e.time;
      li.append(t, e.text);
      list.append(li);
    }
  }

  async function refresh() {
    try {
      render(await (await fetch("/api/state")).json());
    } catch (error) {
      $("offline").style.display = "block";
      document.querySelectorAll("button").forEach((b) => (b.disabled = true));
    }
  }

  document.querySelectorAll("button").forEach((b) => {
    b.onclick = () => fetch("/api/cmd", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd: b.dataset.cmd }),
    });
  });

  refresh();
  setInterval(refresh, 500);
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return PAGE


@app.get("/api/state")
def api_state():
    return jsonify(board.snapshot(notifier.describe() if notifier is not None else ""))


@app.post("/api/cmd")
def api_cmd():
    data = request.get_json(silent=True) or {}
    cmd = data.get("cmd")
    if cmd not in COMMANDS:
        return jsonify({"error": "不支援的指令"}), 400
    try:
        send_command(cmd)
    except Exception as error:
        return jsonify({"error": str(error)}), 500
    return jsonify({"ok": True})


# ---------- 主程式 ----------

def main():
    global ser, notifier
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="序列埠，會蓋過 config.json 的 serial_port")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--web-port", type=int, default=8000)
    args = parser.parse_args()

    cfg = load_config([] if args.port else ["serial_port"])
    ser = open_serial(args.port or cfg["serial_port"])
    notifier = Notifier(cfg, board)
    print(notifier.describe())
    threading.Thread(target=reader_loop, args=(ser,), daemon=True).start()

    print(f"儀表板：http://{args.host}:{args.web_port}")
    try:
        # debug 模式的 reloader 會把程式啟動兩次，序列埠就會被開兩次，所以要關掉
        app.run(host=args.host, port=args.web_port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    print("已結束。")
    if board.state == "TEST":  # 不要讓板子一直停在安靜的測試模式
        try:
            send_command("MODE,DETECT")
        except Exception:
            pass
    stopping.set()
    ser.close()


if __name__ == "__main__":
    main()
