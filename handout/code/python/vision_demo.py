"""
影像辨識試驗台：同一個畫面，試六種辨識方法
執行：uv run vision_demo.py [--source 來源] [--task 方法]（在課程資料夾裡執行）
  --source  0：電腦鏡頭（預設）；1：第二支鏡頭
            http://ESP32-CAM的IP/capture：ESP32-CAM（範例 3 的程式）
            圖片或影片檔的路徑
  --task    hsv、classify、detect、segment、semantic、pose（預設 detect）
畫面上按 1–6 切換方法，按 Q 或 Esc 結束。
HSV 模式：用 HSV 視窗的滑桿調範圍；在畫面上點一下，終端機會印出那一點的 HSV。
需要套件：ultralytics（uv add ultralytics）。每種方法第一次用，會自動下載模型到課程資料夾。
"""

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO

WIN = "vision"
HSV_WIN = "HSV"
TASKS = ["hsv", "classify", "detect", "segment", "semantic", "pose"]  # 對應按鍵 1–6

# 每種方法用的模型：Ultralytics YOLO26 最小的 n 版，一般筆電不用顯示卡也跑得動
MODELS = {
    "classify": "yolo26n-cls.pt",  # 影像分類：ImageNet 1000 類，整張圖一個答案
    "detect": "yolo26n.pt",        # 物件偵測：COCO 80 類，每個物體一個框
    "segment": "yolo26n-seg.pt",   # 實例分割：COCO 80 類，每個物體描出輪廓
    "semantic": "yolo26n-sem.pt",  # 語意分割：Cityscapes 19 類（街景），每個像素一個類別
    "pose": "yolo26n-pose.pt",     # 姿勢辨識：每個人 17 個關節點
}
CONF = 0.4  # 信心度低於這個值的結果不畫

# HSV 滑桿的初始值：橘色乒乓球。OpenCV 的 H 是 0–179（色相角度除以 2），S、V 是 0–255
HSV_START = {"H min": 5, "H max": 20, "S min": 120, "V min": 120}
HSV_MAX = {"H min": 179, "H max": 179, "S min": 255, "V min": 255}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

models = {}               # 載入過的模型，切回來不用重新載入
last = {"frame": None}    # 最新的原始畫面，給滑鼠點擊查 HSV 用


# ---------- 畫面來源 ----------

class Source:
    """電腦鏡頭、ESP32-CAM 網址、圖片、影片，都用 read() 拿一張畫面。"""

    def __init__(self, src: str):
        self.cap = None
        self.url = None
        self.image = None
        if src.isdigit():
            self.cap = cv2.VideoCapture(int(src))
        elif src.startswith("http") and src.rstrip("/").endswith("/capture"):
            self.url = src  # 每次要一張最新的
        elif Path(src).suffix.lower() in IMAGE_EXT:
            self.image = cv2.imread(src)
            if self.image is None:
                raise SystemExit(f"讀不到圖片：{src}")
        else:
            self.cap = cv2.VideoCapture(src)  # 影片檔，或 ESP32-CAM 的 :81/stream
        if self.cap is not None and not self.cap.isOpened():
            raise SystemExit(f"打不開 {src}：鏡頭被別的程式用著、編號不對、檔案不存在，或網址打錯")

    def read(self):
        if self.image is not None:
            return self.image.copy()
        if self.url:
            try:
                r = requests.get(self.url, timeout=5)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"拿不到畫面：{e}")
                return None
            return cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        if self.cap is not None:
            self.cap.release()


# ---------- 傳統方法：HSV 顏色篩選 ----------

def hsv_mask(frame, h_min, h_max, s_min, v_min):
    """回傳黑白遮罩：顏色在範圍內的像素是白色（255）。"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    if h_min <= h_max:
        mask = cv2.inRange(hsv, (h_min, s_min, v_min), (h_max, 255, 255))
    else:
        # 紅色跨過 0：H ≥ h_min 或 H ≤ h_max 都算
        mask = (cv2.inRange(hsv, (h_min, s_min, v_min), (179, 255, 255))
                | cv2.inRange(hsv, (0, s_min, v_min), (h_max, 255, 255)))
    # 先縮再脹，去掉零星的雜點
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def run_hsv(frame, h_min, h_max, s_min, v_min):
    mask = hsv_mask(frame, h_min, h_max, s_min, v_min)
    out = (frame * 0.3).astype(np.uint8)  # 不符合的地方變暗
    out[mask > 0] = frame[mask > 0]
    summary = "沒有找到這個顏色"
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        biggest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(biggest)
        if area > 200:  # 太小的當作雜訊
            x, y, w, h = cv2.boundingRect(biggest)
            cx, cy = x + w // 2, y + h // 2
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(out, (cx, cy), 5, (0, 0, 255), -1)
            summary = f"最大的一塊：中心 ({cx}, {cy})，面積 {int(area)} 像素"
    return out, mask, summary


def read_sliders():
    return [cv2.getTrackbarPos(name, HSV_WIN) for name in HSV_START]


def open_hsv_window():
    cv2.namedWindow(HSV_WIN)
    for name, value in HSV_START.items():
        cv2.createTrackbar(name, HSV_WIN, value, HSV_MAX[name], lambda v: None)


def on_click(event, x, y, flags, param):
    frame = last["frame"]
    if event == cv2.EVENT_LBUTTONDOWN and frame is not None:
        h, s, v = cv2.cvtColor(frame[y:y + 1, x:x + 1], cv2.COLOR_BGR2HSV)[0, 0]
        print(f"({x}, {y}) 的 HSV：H={h} S={s} V={v}")


# ---------- AI 方法：YOLO26 ----------

def get_model(task):
    if task not in models:
        print(f"載入 {MODELS[task]}（第一次會下載）……")
        models[task] = YOLO(MODELS[task])
    return models[task]


def summarize(task, res):
    """把辨識結果整理成一行文字。"""
    names = res.names
    if task == "classify":
        top = res.probs.top5[:3]
        return "、".join(f"{names[i]} {float(res.probs.data[i]):.2f}" for i in top)
    if task == "semantic":
        classes, counts = np.unique(res.semantic_mask.data.cpu().numpy(), return_counts=True)
        share = sorted(zip(counts, classes), reverse=True)[:3]
        total = counts.sum()
        return "、".join(f"{names[int(c)]} {n / total:.0%}" for n, c in share)
    if res.boxes is None or len(res.boxes) == 0:
        return "沒有偵測到"
    found = {}
    for c in res.boxes.cls.tolist():
        found[names[int(c)]] = found.get(names[int(c)], 0) + 1
    text = "、".join(f"{name} ×{n}" for name, n in found.items())
    if task == "pose":
        text += f"（每人 {res.keypoints.shape[1]} 個關節點）"
    return text


def run_model(task, frame):
    res = get_model(task)(frame, conf=CONF, verbose=False)[0]
    return res.plot(), summarize(task, res)


# ---------- 主程式 ----------

def label(img, text):
    """左上角寫字：先畫黑色粗字當外框，再畫白字。"""
    for color, thick in (((0, 0, 0), 5), ((255, 255, 255), 2)):
        cv2.putText(img, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, thick, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="影像辨識試驗台")
    parser.add_argument("--source", default="0", help="0、1、ESP32-CAM 的 /capture 網址、圖片或影片檔")
    parser.add_argument("--task", default="detect", choices=TASKS)
    args = parser.parse_args()

    src = Source(args.source)
    task = args.task
    cv2.namedWindow(WIN)
    cv2.setMouseCallback(WIN, on_click)
    if task == "hsv":
        open_hsv_window()
    print("按 1–6 切換：1 HSV、2 分類、3 偵測、4 實例分割、5 語意分割、6 姿勢。按 Q 結束。")

    fails = 0
    last_print = 0.0
    while True:
        frame = src.read()
        if frame is None:
            fails += 1
            if fails >= 10:
                print("連續 10 次沒有畫面，結束")
                break
            time.sleep(0.5)
            continue
        fails = 0
        last["frame"] = frame

        start = time.perf_counter()
        if task == "hsv":
            out, mask, summary = run_hsv(frame, *read_sliders())
            cv2.imshow(HSV_WIN, mask)
        else:
            out, summary = run_model(task, frame)
        fps = 1 / max(time.perf_counter() - start, 1e-6)

        label(out, f"[{TASKS.index(task) + 1}] {task}  {fps:.1f} fps")
        cv2.imshow(WIN, out)
        if time.time() - last_print >= 1:  # 每秒印一次結果
            print(f"{task}：{summary}")
            last_print = time.time()

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if ord("1") <= key <= ord("6"):
            new_task = TASKS[key - ord("1")]
            if new_task == "hsv" and task != "hsv":
                open_hsv_window()
            elif task == "hsv" and new_task != "hsv":
                cv2.destroyWindow(HSV_WIN)
            task = new_task

    src.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
