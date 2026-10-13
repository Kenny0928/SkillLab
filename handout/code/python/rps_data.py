"""
微專題 03 步驟 3：把標記好的照片整理成訓練用的資料集，寫出 rps.yaml
執行：uv run rps_data.py [--show [組]] [--kaggle]（在課程資料夾裡執行）
  （不加參數）  讀 photos/ 裡的照片，和 X-AnyLabeling 存在旁邊的標記（同名的 .json），
                每一類各分 8 成給 train、2 成給 valid，存到 datasets/rps/，寫出 rps.yaml
  --show        另外隨機挑 6 張，照整理好的標記畫出框和類別，存成 rps_show_1.jpg … rps_show_6.jpg
  --show valid  只從某一組挑：train 或 valid
  --kaggle      延伸挑戰：下載 Kaggle 的剪刀石頭布公開資料集（約 66 MB，不需要帳號）到 datasets/rps-kaggle/，
                寫出 rps-kaggle.yaml，和「公開資料集加上自己的照片一起訓練」的 rps-both.yaml
每次執行都從 photos/ 重新整理 datasets/rps/：在 X-AnyLabeling 改過標記，再執行一次就好。
框的類別：標成 rock、paper、scissors 的照用；標成 hand（AI 自動框出來的）就照檔名決定，
  rock_0001.jpg 裡的 hand 就是 rock。其他標籤（例如 AI 順便框到的 person、cup）不用，會列出來。
需要套件：ultralytics（uv add ultralytics，會一起裝好 OpenCV 和 PyYAML）。下載用 Python 內建的功能。
"""

import argparse
import json
import random
import shutil
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import cv2
import yaml

NAMES = ["rock", "paper", "scissors"]  # 類別編號 0、1、2，和 rps_game.py 對得上
COLORS = [(0, 0, 255), (0, 170, 0), (255, 0, 0)]  # 紅、綠、藍（OpenCV 的順序是 BGR）
PHOTOS = Path("photos")       # rps_capture.py 拍的照片，X-AnyLabeling 的標記也存在這裡
DATA_DIR = Path("datasets/rps")
VAL = 0.2                     # 每一類拿 2 成當驗證集
HAND = {"hand", "hands"}      # AI 自動框出來的標籤：類別照檔名決定
SHOW = 6

# 延伸挑戰：Kaggle 的公開資料集。原本的類別名稱是簡體中文，編號 0、1、2 剛好也是 rock、paper、scissors
KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/cubeai/rock-paper-scissors-detection-for-yolov8"
KAGGLE_DIR = Path("datasets/rps-kaggle")
KAGGLE_NAMES = ["石头", "布", "剪刀"]


# ---------- 自己的照片 ----------

def box_class(label, stem):
    """框的類別編號：標籤是 rock、paper、scissors 就照用；是 hand 就看檔名開頭。其他標籤回傳 None。"""
    name = label.strip().lower()
    if name in HAND:  # AI 只知道是手，不知道是哪個手勢：拍照時已經寫在檔名裡了
        name = stem.split("_")[0].lower()
    return NAMES.index(name) if name in NAMES else None


def read_xlabel(path: Path):
    """讀 X-AnyLabeling 的標記檔，回傳（框的清單, 看不懂的標籤）。框是「類別 x中心 y中心 寬 高」，都是 0–1 的比例。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    w, h = data["imageWidth"], data["imageHeight"]
    rows, unknown = [], []
    for shape in data["shapes"]:
        if shape.get("shape_type") != "rectangle":  # 多邊形、點這些不是物件偵測的框
            continue
        c = box_class(shape["label"], path.stem)
        if c is None:
            unknown.append(shape["label"])
            continue
        xs = [p[0] for p in shape["points"]]
        ys = [p[1] for p in shape["points"]]
        x1, x2 = max(min(xs), 0), min(max(xs), w)  # 拉到照片外面的部分切掉
        y1, y2 = max(min(ys), 0), min(max(ys), h)
        if x2 - x1 < 2 or y2 - y1 < 2:  # 不小心點一下產生的小框
            continue
        rows.append((c, (x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h))
    return rows, unknown


def build():
    """photos/ → datasets/rps/train、valid，每一類各自隨機分。"""
    photos = sorted(PHOTOS.glob("*.jpg"))
    if not photos:
        raise SystemExit(f"{PHOTOS.resolve()} 裡沒有照片：先用 rps_capture.py 拍照")
    groups, unlabeled, empty, unknown = {n: [] for n in NAMES}, [], [], Counter()
    for photo in photos:
        label_file = photo.with_suffix(".json")
        if not label_file.exists():
            unlabeled.append(photo.name)
            continue
        rows, bad = read_xlabel(label_file)
        unknown.update(bad)
        if not rows:
            empty.append(photo.name)
            continue
        groups[NAMES[rows[0][0]]].append((photo, rows))  # 照第一個框的類別分組，分 train／valid 時每一類比例才一樣

    rng = random.Random(0)  # 固定的亂數：沒改照片的話，每次分法都一樣
    splits = {"train": [], "valid": []}
    for items in groups.values():
        rng.shuffle(items)
        n_val = round(len(items) * VAL) if len(items) >= 5 else 0
        splits["valid"] += items[:n_val]
        splits["train"] += items[n_val:]
    if not splits["valid"]:  # 先檢查再刪舊的：照片不夠時，上一次整理好的資料集還在
        raise SystemExit("標好的照片太少：每一類至少要 5 張，才分得出驗證集。")

    if DATA_DIR.exists():  # 每次重新整理
        try:
            shutil.rmtree(DATA_DIR)
        except OSError as e:  # 刪不乾淨就停下來，舊照片才不會混進新的資料集
            raise SystemExit(f"刪不掉舊的 {DATA_DIR}：{e}\n關掉開著裡面照片的程式，再執行一次。")
    for split, items in splits.items():
        (DATA_DIR / split / "images").mkdir(parents=True)
        (DATA_DIR / split / "labels").mkdir(parents=True)
        for photo, rows in items:
            shutil.copy2(photo, DATA_DIR / split / "images" / photo.name)
            lines = [f"{c} {x:.6f} {y:.6f} {bw:.6f} {bh:.6f}" for c, x, y, bw, bh in rows]
            (DATA_DIR / split / "labels" / f"{photo.stem}.txt").write_text("\n".join(lines) + "\n")

    print(f"photos/ 裡有 {len(photos)} 張照片")
    if unlabeled:
        print(f"  {len(unlabeled)} 張還沒標記（沒有 .json），這次不用：{'、'.join(unlabeled[:5])}……")
    if empty:
        print(f"  {len(empty)} 張的標記裡沒有能用的框，這次不用；照片裡有手的話，回 X-AnyLabeling 補框：{'、'.join(empty[:5])}……")
    if unknown:
        print(f"  沒用到的標籤 {dict(unknown)}：不是手的框可以刪掉；是手的話改成 rock、paper、scissors 或 hand")
    if not all(groups.values()):
        print(f"  注意：{'、'.join(n for n in NAMES if not groups[n])} 一張都沒有，模型學不會")
    few = [n for n in NAMES if 0 < len(groups[n]) < 5]
    if few:
        print(f"  注意：{'、'.join(few)} 不到 5 張，沒有分到驗證集，看不出模型這一類學得怎樣")
    write_yaml("rps.yaml", path=DATA_DIR, train="train/images", val="valid/images")


def write_yaml(filename, **paths):
    """寫出訓練要用的 yaml：照片在哪裡、每個編號是什麼類別。路徑用絕對路徑，從哪個資料夾開始訓練都找得到。"""
    lines = []
    for key, value in paths.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines += [f'  - "{Path(v).resolve().as_posix()}"' for v in value]
        else:
            lines.append(f'{key}: "{value if key != "path" else Path(value).resolve().as_posix()}"')
    lines += ["names:"] + [f"  {i}: {name}" for i, name in enumerate(NAMES)]
    Path(filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已寫出 {filename}")


# ---------- 檢查 ----------

def label_path(image: Path) -> Path:
    """圖片對應的標記檔：images 換成 labels、副檔名換成 .txt。YOLO 也是這樣找的。"""
    return image.parent.parent / "labels" / f"{image.stem}.txt"


def read_labels(image: Path):
    """讀 YOLO 的標記檔，每行是「類別 x中心 y中心 寬 高」，後四個是 0–1 的比例。"""
    rows = []
    for line in label_path(image).read_text().splitlines():
        if line.strip():
            c, *xywh = line.split()
            rows.append((int(c), *map(float, xywh)))
    return rows


def count(data_dir, splits):
    """印出每個 split 有幾張圖、每一類有幾個框。"""
    print(f"\n{data_dir} 每一組的圖片數，和每一類有幾個框：")
    for split in splits:
        images = sorted((data_dir / split / "images").glob("*.jpg"))
        boxes = [0] * len(NAMES)
        for image in images:
            for c, *_ in read_labels(image):
                boxes[c] += 1
        detail = "  ".join(f"{name} {n:>3}" for name, n in zip(NAMES, boxes))
        print(f"  {split:<6}{len(images):>5} 張  框 {sum(boxes):>4} 個：{detail}")


def label(img, text, org):
    """寫字：先畫黑色粗字當外框，再畫白字。"""
    for color, thick in (((0, 0, 0), 5), ((255, 255, 255), 2)):
        cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, thick, cv2.LINE_AA)


def show(n, split):
    """隨機挑 n 張圖，照標記檔畫框，存成 rps_show_1.jpg……，順便印出標記檔的內容。"""
    images = sorted(DATA_DIR.glob(f"{'*' if split == 'all' else split}/images/*.jpg"))
    where = "兩組" if split == "all" else f" {split} "
    print(f"\n從{where}隨機挑 {min(n, len(images))} 張，照標記檔畫框（整張圖的寬、高都當作 1）：")
    for i, image in enumerate(random.sample(images, min(n, len(images))), 1):
        img = cv2.imread(str(image))
        h, w = img.shape[:2]
        out = f"rps_show_{i}.jpg"
        print(f"{out} ← {image.relative_to(DATA_DIR)}（{w}×{h}）")
        for c, x, y, bw, bh in read_labels(image):
            print(f"  {c} {x:.3f} {y:.3f} {bw:.3f} {bh:.3f} → {NAMES[c]}，"
                  f"中心在 ({x:.2f}, {y:.2f})，寬 {bw:.2f}、高 {bh:.2f}")
            # 比例乘上圖片的寬高換成像素；中心減掉一半的寬高，就是左上角
            x1, y1 = round((x - bw / 2) * w), round((y - bh / 2) * h)
            x2, y2 = round((x + bw / 2) * w), round((y + bh / 2) * h)
            cv2.rectangle(img, (x1, y1), (x2, y2), COLORS[c], 3)
            cv2.circle(img, (round(x * w), round(y * h)), 6, COLORS[c], -1)  # 框的中心
            label(img, f"{c} {NAMES[c]}", (max(x1, 0) + 8, max(y1, 0) + 32))
        cv2.imwrite(out, img)


# ---------- 延伸挑戰：公開資料集 ----------

def kaggle():
    """下載 Kaggle 的資料集，寫出 rps-kaggle.yaml 和 rps-both.yaml。已經有就不重新下載。"""
    if not all((KAGGLE_DIR / s / "labels").is_dir() for s in ("train", "valid", "test")):
        zip_path = KAGGLE_DIR.with_suffix(".zip")
        KAGGLE_DIR.parent.mkdir(exist_ok=True)
        if not zip_path.exists():  # 用瀏覽器下載的 zip 改名放在這裡，就不用再下載
            print("下載公開資料集（約 66 MB）……")
            part = zip_path.with_suffix(".part")  # 下載完才改名，中斷的話不會留下壞掉的 zip
            try:
                urllib.request.urlretrieve(KAGGLE_URL, part)
            except OSError as error:  # 連不上、斷線、逾時
                raise SystemExit(f"下載失敗：{error}\n再執行一次；還是不行，用瀏覽器打開 {KAGGLE_URL}，"
                                 f"下載的 zip 改名成 {zip_path.name} 放進 datasets 資料夾。")
            part.rename(zip_path)
        tmp = KAGGLE_DIR.with_name("rps-kaggle-tmp")  # 先解到暫存資料夾，全部完成才改名
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        shutil.rmtree(KAGGLE_DIR, ignore_errors=True)
        tmp.rename(KAGGLE_DIR)
        zip_path.unlink()
    names = yaml.safe_load((KAGGLE_DIR / "data.yaml").read_text(encoding="utf-8"))["names"]
    if names != KAGGLE_NAMES:
        raise SystemExit(f"公開資料集的類別變了：{names}，和程式預期的 {KAGGLE_NAMES} 不同，先別訓練。")
    write_yaml("rps-kaggle.yaml", path=KAGGLE_DIR, train="train/images", val="valid/images", test="test/images")
    # 兩份一起訓練，但驗證只用自己的照片：要知道的是「在自己的教室準不準」
    write_yaml("rps-both.yaml", train=[DATA_DIR / "train/images", KAGGLE_DIR / "train/images"],
               val=str((DATA_DIR / "valid/images").resolve().as_posix()))
    count(KAGGLE_DIR, ["train", "valid", "test"])


def main():
    parser = argparse.ArgumentParser(description="整理剪刀石頭布的資料集")
    parser.add_argument("--show", nargs="?", const="all", choices=["all", "train", "valid"],
                        help=f"隨機挑 {SHOW} 張畫出標記，存成圖片；後面可以指定 train 或 valid")
    parser.add_argument("--kaggle", action="store_true", help="延伸挑戰：另外下載 Kaggle 的公開資料集")
    args = parser.parse_args()

    build()
    count(DATA_DIR, ["train", "valid"])
    if args.show:
        show(SHOW, args.show)
    if args.kaggle:
        kaggle()
    print("\n下一步：訓練。指令和參數見講義。")


if __name__ == "__main__":
    main()
