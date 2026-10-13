"""
YOLO 模型大小比較：同一張畫面給大小不同的模型各跑幾次，看「越大越準、但越慢」
執行：uv run yolo_compare.py [--source 來源] [--models 模型 …] [--runs 次數] [--save]（在課程資料夾裡執行）
  --source  0：電腦鏡頭（預設，抓一張畫面來比）；1：第二支鏡頭
            圖片或影片檔的路徑（影片取第一張畫面）
  --models  要比的模型，用空白隔開（預設 yolo26n.pt yolo26s.pt yolo26m.pt）
            也可以放匯出的 .onnx，或從 Hugging Face 下載的 .pt
  --runs    每個模型跑幾次取平均（預設 5；另外先暖機一次，不算在內）
  --save    把每個模型的標註圖存成 compare_1_模型名.jpg、compare_2_…，可以並排比較
毫秒數每台電腦差很多，要看的是模型之間差幾倍。
需要套件：ultralytics（uv add ultralytics）。每個模型第一次用，會自動下載到課程資料夾。
"""

import argparse
import time
import unicodedata
from pathlib import Path

import cv2
from ultralytics import YOLO

DEFAULT_MODELS = ["yolo26n.pt", "yolo26s.pt", "yolo26m.pt"]  # n、s、m：由小到大
CONF = 0.25  # 信心度門檻，和 yolo predict 的預設一樣；每個模型用同一個值才公平
TOP = 3      # 表格列出信心度最高的前幾個
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def grab_frame(src: str):
    """圖片直接讀；鏡頭或影片抓一張畫面。每個模型都用這同一張，比較才公平。"""
    if Path(src).suffix.lower() in IMAGE_EXT:
        frame = cv2.imread(src)
    else:
        cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
        # 鏡頭剛打開時自動曝光還沒調好，前幾張偏暗，多讀幾張再用最後一張
        for _ in range(10 if src.isdigit() else 1):
            _, frame = cap.read()
        cap.release()
    if frame is None:
        raise SystemExit(f"拿不到畫面：{src}（檔案不存在、鏡頭編號不對，或鏡頭被別的程式用著）")
    return frame


def count_params(model):
    """參數量，單位百萬（M）。ONNX 等匯出的格式數不到，顯示 -。"""
    try:
        # 官網表格是把 Conv 和 BatchNorm 合併（fuse）之後才數的，這裡照做，數字才對得上
        model.fuse(verbose=False)
    except TypeError:
        return "-"
    return f"{sum(p.numel() for p in model.model.parameters()) / 1e6:.1f}M"


def top_results(res):
    """信心度最高的前 TOP 個，寫成「類別 信心值」。"""
    found = sorted(zip(res.boxes.conf.tolist(), res.boxes.cls.tolist()), reverse=True)[:TOP]
    return "、".join(f"{res.names[int(c)]} {p:.2f}" for p, c in found) or "沒有偵測到"


def cell(text, width):
    """補空白讓欄位對齊。中文字在終端機佔兩格，要算兩個寬。"""
    w = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)
    return text + " " * max(width - w, 1)


def label(img, text):
    """左上角寫字：先畫黑色粗字當外框，再畫白字。"""
    for color, thick in (((0, 0, 0), 5), ((255, 255, 255), 2)):
        cv2.putText(img, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, thick, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="YOLO 模型大小比較")
    parser.add_argument("--source", default="0", help="0、1、圖片或影片檔")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="要比的模型")
    parser.add_argument("--runs", type=int, default=5, help="每個模型跑幾次取平均")
    parser.add_argument("--save", action="store_true", help="把每個模型的標註圖存成檔案")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs 至少要 1")

    frame = grab_frame(args.source)
    print(f"畫面 {frame.shape[1]}×{frame.shape[0]}，每個模型先暖機 1 次，再跑 {args.runs} 次取平均")

    rows = []
    for i, name in enumerate(args.models, 1):
        short = Path(name).name  # 只留檔名，路徑太長表格會亂
        print(f"載入 {name}（第一次會下載）……")
        model = YOLO(name)
        res = model(frame, conf=CONF, verbose=False)[0]  # 暖機：第一次要配置記憶體，特別慢，不算
        if res.boxes is None:
            raise SystemExit(f"{name} 不是偵測模型，沒有框可以比")
        start = time.perf_counter()
        for _ in range(args.runs):
            res = model(frame, conf=CONF, verbose=False)[0]
        ms = (time.perf_counter() - start) / args.runs * 1000  # 含前處理和後處理，就是實際用起來的時間
        rows.append([short, count_params(model), f"{ms:.1f}", str(len(res.boxes)), top_results(res)])
        if args.save:
            out = res.plot()
            label(out, f"{short}  {ms:.0f} ms")
            path = f"compare_{i}_{Path(name).stem}.jpg"  # 加編號：同名的 .pt 和 .onnx 才不會互蓋
            cv2.imwrite(path, out)
            print(f"  存檔：{path}")

    widths = [max(len(r[0]) for r in rows) + 2, 8, 10, 8]  # 最後一欄不用對齊
    print()
    for row in [["模型", "參數量", "平均毫秒", "偵測數", f"前 {TOP} 個（類別 信心值）"]] + rows:
        print("".join(cell(text, w) for text, w in zip(row, widths)) + row[-1])


if __name__ == "__main__":
    main()
