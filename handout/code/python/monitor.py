"""
步驟 4、5：畫面交給 YOLO26 找人，連續幾張都有人就發 Discord 通知，附上截圖
執行：uv run monitor.py [--source 網址] [--no-window]（在課程資料夾裡執行）
  --source     http://ESP32-CAM的IP/capture，會蓋過 config.json 的 monitor.capture_url
               沒有板子時可以填 0（電腦鏡頭），先測試判斷和通知
  --no-window  不開視窗，只在終端機印訊息，按 Ctrl+C 結束
有視窗時，在畫面上按 Q 或 Esc 結束。config.json 的 discord.webhook_url 沒填，就只印出事件。
需要套件：ultralytics、requests（uv add ultralytics requests）。第一次執行會下載 yolo26n.pt。
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO

CONFIG_PATH = Path(__file__).with_name("config.json")
# config.json 範例裡的網址，還沒改掉就代表「沒填」
WEBHOOK_PLACEHOLDER = "https://discord.com/api/webhooks/貼上你的網址"

# config.json 的 monitor 沒寫到的欄位，用這裡的值
DEFAULTS = {
    "capture_url": None,     # ESP32-CAM 的 /capture 網址
    "target": "person",      # 要找的類別，COCO 80 類的英文名稱
    "conf": 0.5,             # 信心度門檻
    "hit_frames": 3,         # 連續幾張有 → 有人
    "clear_frames": 10,      # 連續幾張沒有 → 沒人
    "cooldown_seconds": 60,  # 通知後幾秒內不再通知
}
MODEL = "yolo26n.pt"         # 物件偵測，和影像辨識講義的 detect 相同
SNAPSHOT_SIZE = 800          # 截圖的長邊縮到幾像素以內再傳
FAIL_REMIND = 10             # 拿不到畫面時，每幾秒提醒一次，不要洗版


def load_config():
    """讀取同資料夾的 config.json，回傳 monitor 設定和 Webhook 網址（沒填就是 None）。"""
    if not CONFIG_PATH.exists():
        sys.exit("找不到 config.json：照講義步驟 4，在課程資料夾建立 config.json。")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        sys.exit(f"config.json 格式錯誤：{error}")
    webhook = str(cfg.get("discord", {}).get("webhook_url") or "").strip()
    if webhook in ("", WEBHOOK_PLACEHOLDER):
        webhook = None
    return DEFAULTS | cfg.get("monitor", {}), webhook


# ---------- 畫面來源 ----------

class NoFrame(Exception):
    """拿不到畫面。這和「畫面裡沒人」是兩回事。"""


class Source:
    """ESP32-CAM 的 /capture 網址，或電腦鏡頭編號（沒有板子時測試用），都用 read() 拿一張畫面。"""

    def __init__(self, src: str):
        self.url, self.cap = src, None
        if src.isdigit():
            self.cap = cv2.VideoCapture(int(src))
            if not self.cap.isOpened():
                sys.exit(f"打不開鏡頭 {src}：被別的程式用著，或編號不對")
        elif not (src.startswith("http") and src.rstrip("/").endswith("/capture")):
            sys.exit(f"看不懂的畫面來源：{src}。要填 http://板子的IP/capture，或鏡頭編號 0。")

    def read(self):
        """拿一張畫面；拿不到就丟出例外。"""
        if self.cap is not None:
            ok, frame = self.cap.read()
        else:
            r = requests.get(self.url, timeout=5)  # 每次要一張最新的
            r.raise_for_status()
            frame = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise NoFrame("沒有收到圖片")
        return frame


def why(error) -> str:
    """把連線失敗的原因整理成一句話。"""
    if isinstance(error, requests.Timeout):
        return "等太久沒有回應（timed out）"
    if isinstance(error, requests.ConnectionError):
        return "連不上（Connection refused，或網路不通）"
    return str(error)


# ---------- 辨識與通知 ----------

def detect(model, frame, target: str, conf: float):
    """辨識一張畫面，回傳（畫好框的圖, 目標有幾個, 最高信心度）。"""
    res = model(frame, conf=conf, verbose=False)[0]  # 信心度不到 conf 的框直接丟掉
    scores = [p for c, p in zip(res.boxes.cls.tolist(), res.boxes.conf.tolist())
              if res.names[int(c)] == target]
    return res.plot(), len(scores), max(scores, default=0.0)


def send_discord(url: str, text: str, image) -> bool:
    """發一則訊息到 Discord 頻道，附上截圖，成功回傳 True。"""
    # 截圖的長邊縮到 800 像素以內，存成 JPEG（畫質 80），檔案大約幾十 KB
    h, w = image.shape[:2]
    scale = SNAPSHOT_SIZE / max(h, w)
    if scale < 1:
        image = cv2.resize(image, (round(w * scale), round(h * scale)),
                           interpolation=cv2.INTER_AREA)
    jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
    # 要附檔案就不能只送 JSON：文字放在 payload_json，圖片放在 files[0]
    data = {"payload_json": json.dumps({"content": text[:2000]})}
    files = {"files[0]": ("snapshot.jpg", jpeg, "image/jpeg")}
    try:
        response = requests.post(url, data=data, files=files, timeout=15)
    except requests.RequestException as error:
        print(f"  Discord 連線失敗：{why(error)}")
        return False
    code = response.status_code
    if code in (200, 204):
        print("  已發到 Discord")
        return True
    if code == 429:
        try:
            wait = response.json().get("retry_after", "?")
        except ValueError:
            wait = "?"
        print(f"  發太快被限流，請等 {wait} 秒")
        return False
    if code in (401, 403, 404):
        print(f"  Webhook 無效（{code}）：網址可能被刪除或複製不完整，照簡易防盜系統步驟 7 重建。")
        return False
    print(f"  Discord 回應 {code}：{response.text[:200]}")
    return False


# ---------- 主程式 ----------

def clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


def pressed_quit(show: bool, ms: int) -> bool:
    """等 ms 毫秒；有視窗時順便看有沒有按 Q 或 Esc。"""
    if not show:
        time.sleep(ms / 1000)
        return False
    return (cv2.waitKey(ms) & 0xFF) in (ord("q"), ord("Q"), 27)


def main():
    parser = argparse.ArgumentParser(description="簡易 AI 監控系統")
    parser.add_argument("--source", help="ESP32-CAM 的 /capture 網址；沒有板子時填 0（電腦鏡頭）")
    parser.add_argument("--no-window", action="store_true", help="不開視窗，按 Ctrl+C 結束")
    args = parser.parse_args()

    cfg, webhook = load_config()
    source = args.source or cfg["capture_url"]
    if not source:
        sys.exit("沒有畫面來源：在 config.json 的 monitor 填 capture_url，或加上 --source 網址。")
    target, conf = cfg["target"], float(cfg["conf"])
    hit_frames, clear_frames = int(cfg["hit_frames"]), int(cfg["clear_frames"])
    cooldown = float(cfg["cooldown_seconds"])
    show = not args.no_window
    src = Source(str(source))

    print(f"載入 {MODEL}（第一次會下載）……")
    model = YOLO(MODEL)
    if target not in model.names.values():
        sys.exit(f"{MODEL} 沒有 {target} 這個類別，可以用的有：{'、'.join(model.names.values())}")
    if webhook is None:
        print("config.json 的 discord.webhook_url 還沒填：只在終端機印出事件，不發 Discord 通知。")
    print(f"開始監控 {source}：連續 {hit_frames} 張有 {target}（信心度 {conf} 以上）算有人，"
          f"連續 {clear_frames} 張沒有算人走了，通知後 {cooldown:g} 秒內不再通知。")
    print("按 Q 或 Esc 結束。" if show else "沒有視窗：發生事件才會印訊息，按 Ctrl+C 結束。")

    present = False     # 現在的狀態：False 沒人、True 有人
    hits = misses = 0   # 連續幾張有、連續幾張沒有
    last_notify = None  # 上次通知的時間（time.monotonic()，不受電腦改時間影響）
    fail_since = None   # 從什麼時候開始拿不到畫面；None 代表畫面正常
    last_remind = 0.0
    try:
        while True:
            try:
                frame = src.read()
            except (requests.RequestException, NoFrame) as error:
                # 拿不到畫面不等於沒人：計數維持原樣，等 1 秒再試
                now = time.monotonic()
                if fail_since is None:
                    fail_since = last_remind = now
                    print(f"{clock()} 拿不到畫面：{why(error)}")
                    print("  計數先不變，持續重試。檢查板子有沒有電、IP 是不是序列埠印出的那個、"
                          "電腦和板子是不是連同一個 Wi-Fi。")
                elif now - last_remind >= FAIL_REMIND:
                    last_remind = now
                    print(f"{clock()} 還是拿不到畫面（{now - fail_since:.0f} 秒了）：{why(error)}")
                if pressed_quit(show, 1000):
                    break
                continue
            if fail_since is not None:
                print(f"{clock()} 畫面恢復了（中斷 {time.monotonic() - fail_since:.0f} 秒）")
                fail_since = None

            annotated, count, best = detect(model, frame, target, conf)
            if count:  # 這張有：「連續有」加 1，「連續沒有」歸零
                hits, misses = hits + 1, 0
            else:      # 這張沒有：反過來
                hits, misses = 0, misses + 1

            if not present and hits >= hit_frames:
                present = True
                found = f"{target} ×{count}，最高信心度 {best:.2f}"
                print(f"{clock()} 有人來了（{found}）")
                now = time.monotonic()
                if last_notify is not None and now - last_notify < cooldown:
                    left = math.ceil(cooldown - (now - last_notify))
                    print(f"  冷卻中，{left} 秒內不再通知")
                else:
                    last_notify = now
                    if webhook:
                        text = (f"【AI 監控】有人來了\n時間：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
                                f"偵測：{found}")
                        send_discord(webhook, text, annotated)
            elif present and misses >= clear_frames:
                present = False
                print(f"{clock()} 人走了")

            if show:
                cv2.imshow("monitor", annotated)
            if pressed_quit(show, 1):
                break
    except KeyboardInterrupt:
        pass
    print("已結束。")
    if show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
