"""
微專題 03 步驟 1：用網路攝影機拍剪刀石頭布的照片，之後用 X-AnyLabeling 標記
執行：uv run rps_capture.py [--source 來源]（在課程資料夾裡執行）
  --source  0：電腦鏡頭（預設）；1：第二支鏡頭
畫面上按 1（rock）、2（paper）、3（scissors）開始連拍：先倒數 2 秒讓手就位，
接著每 0.5 秒存一張，共 10 張。連拍時一直比同一個手勢，邊拍邊換左右手、角度、遠近、位置。
按 Q 或 Esc 結束。
照片存在課程資料夾的 photos/，檔名是 rock_0001.jpg、paper_0001.jpg……
已經有的照片不會被蓋掉，編號接著往下，所以可以分好幾次、換好幾個人拍。
需要套件：ultralytics（uv add ultralytics，會一起裝好 OpenCV）。
"""

import argparse
import re
import time
from collections import Counter
from pathlib import Path

import cv2

KEYS = {ord("1"): "rock", ord("2"): "paper", ord("3"): "scissors"}
PHOTOS = Path("photos")  # 相對於課程資料夾
READY = 2      # 按下去以後倒數幾秒才開始拍
EVERY = 0.5    # 每隔幾秒拍一張
BURST = 10     # 一次連拍幾張
GOAL = 50      # 每一類建議至少拍幾張（而且要好幾個人）
WIN = "capture"


def existing():
    """photos/ 裡每一類已經有幾張、最大的編號是多少。"""
    count, last = Counter(), Counter()
    for path in PHOTOS.glob("*.jpg"):
        m = re.fullmatch(r"(rock|paper|scissors)_(\d+)", path.stem)
        if m:
            count[m[1]] += 1
            last[m[1]] = max(last[m[1]], int(m[2]))
    return count, last


def next_path(label, last):
    """下一張照片的檔名。已經有同名的檔（例如副檔名是大寫的 .JPG）就跳過那個編號，不蓋掉。"""
    while True:
        last[label] += 1
        path = PHOTOS / f"{label}_{last[label]:04d}.jpg"
        if not path.exists():
            return path


def text(img, s, y, scale=0.8, center=False):
    """寫字：先畫黑色粗字當外框，再畫白字。center=True 時左右置中。"""
    x = 12
    if center:
        x = (img.shape[1] - cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0][0]) // 2
    for color, thick in (((0, 0, 0), round(scale * 6)), ((255, 255, 255), round(scale * 2.5))):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def capture(source):
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise SystemExit(f"打不開 {source}：鏡頭被別的程式用著，或編號不對")
    PHOTOS.mkdir(exist_ok=True)
    count, last = existing()
    print(f"photos/ 裡已經有：rock {count['rock']}、paper {count['paper']}、scissors {count['scissors']} 張")
    print("按 1 rock、2 paper、3 scissors 開始連拍；按 Q 或 Esc 結束。")
    label, t0, taken, next_shot = None, 0.0, 0, 0.0  # label 不是 None 時正在連拍
    while True:
        ok, frame = cap.read()
        if not ok:
            print("拿不到畫面，結束")
            break
        # 左右翻轉成鏡像，和 rps_game.py 一樣：拍下來的照片就是玩遊戲時模型看到的樣子
        frame = cv2.flip(frame, 1)
        out = frame.copy()  # 字寫在 out 上；存檔用 frame，照片裡才不會有字
        now = time.monotonic()

        if label and now - t0 < READY:
            text(out, f"{label}: {READY - int(now - t0)}", 120, 3, center=True)
        elif label:
            if now >= next_shot:
                path = next_path(label, last)
                if not cv2.imwrite(str(path), frame):  # 存失敗不會跳錯誤，只會回傳 False
                    print(f"存不了 {path}：photos/ 不能寫入，或磁碟滿了")
                    break
                count[label] += 1
                taken += 1
                next_shot = now + EVERY
            text(out, f"REC {label} {taken}/{BURST}", 50, 1.2, center=True)
            cv2.rectangle(out, (0, 0), (out.shape[1] - 1, out.shape[0] - 1), (0, 0, 255), 8)
            if taken >= BURST:
                print(f"{label}：這次拍了 {taken} 張，共 {count[label]} 張")
                label = None
        else:
            text(out, "1 rock   2 paper   3 scissors   Q quit", 32)
        status = "   ".join(f"{name} {count[name]}/{GOAL}" for name in KEYS.values())
        text(out, status, out.shape[0] - 16, 0.7)
        cv2.imshow(WIN, out)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in KEYS and label is None:  # 連拍中按別的鍵不理它
            label, t0, taken = KEYS[key], now, 0
            next_shot = now + READY
    cap.release()
    cv2.destroyAllWindows()
    print(f"照片在 {PHOTOS.resolve()}：rock {count['rock']}、paper {count['paper']}、scissors {count['scissors']} 張")


def main():
    parser = argparse.ArgumentParser(description="拍剪刀石頭布的照片")
    parser.add_argument("--source", default="0", help="0、1，或影片檔")
    args = parser.parse_args()
    capture(args.source)


if __name__ == "__main__":
    main()
