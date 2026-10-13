"""
微專題 03：簡易猜拳遊戲，兩個人一左一右同時出拳，電腦判斷誰贏
執行：uv run rps_game.py [--model 權重檔] [--source 來源]（在課程資料夾裡執行）
  --model   偵測手勢的模型（預設課程資料夾裡的 best.pt，就是自己訓練出來、複製過來的那一個）
            也可以指定其他檔案，或放講義裡備用權重的網址
  --source  0：電腦鏡頭（預設）；1：第二支鏡頭
            圖片檔的路徑：不開視窗，判斷一次就印出結果，標註圖存成 rps_result.jpg
兩個人並排在鏡頭前，各伸出一隻手（一個人玩就左右手各出一隻）。畫面上按空白鍵開始一局，
跟著倒數 3、2、1 喊「剪刀、石頭、布」，喊到「布」時出拳；按 Q 或 Esc 結束。
需要套件：ultralytics（uv add ultralytics）。
"""

import argparse
import time
from collections import Counter
from pathlib import Path

import cv2
from ultralytics import YOLO

# 模型的類別名稱 → 遊戲的手勢。自己訓練的、原始資料集的簡體中文、備用權重的手勢名稱都對到同一組，
# 所以換哪個模型都能玩。不在表上的手勢（備用權重的 like、ok……）不理它
GESTURES = {
    "rock": "rock", "paper": "paper", "scissors": "scissors",
    "石头": "rock", "布": "paper", "剪刀": "scissors",
    "fist": "rock", "palm": "paper", "peace": "scissors",
}
BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}  # 前面的贏後面的
CONF = 0.4       # 信心度門檻，低於這個值的框不算
COUNTDOWN = 3    # 倒數幾秒
SETTLE = 0.3     # 倒數完先等這麼久再開始看：手還在動，鏡頭也可能還留著倒數時的舊畫面
CAPTURE = 0.5    # 接著看幾秒的畫面，取多數
RESULT = 3       # 結果顯示幾秒
WIN = "rps"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ---------- 遊戲規則 ----------

def find_hands(model, frame):
    """偵測一張畫面，回傳（標註圖, 手的清單），每隻手是（手勢, 信心度, 框中心的 x）。"""
    # agnostic_nms：不分類別去掉重疊的框。同一隻手同時被認成 rock 和 scissors 時只留一個，
    # 不然會被當成兩位玩家
    res = model(frame, conf=CONF, agnostic_nms=True, verbose=False)[0]
    hands = []
    for c, p, box in zip(res.boxes.cls.tolist(), res.boxes.conf.tolist(), res.boxes.xywh.tolist()):
        gesture = GESTURES.get(res.names[int(c)].lower())  # 轉小寫：類別打成 Rock 也認得
        if gesture:
            hands.append((gesture, p, box[0]))  # xywh 的第一個數字就是中心的 x
    return res.plot(), hands


def left_right(hands):
    """取信心度最高的兩隻手，x 小的是左邊玩家，回傳（左, 右）的手勢；不到兩隻回傳 None。"""
    if len(hands) < 2:
        return None
    two = sorted(hands, key=lambda h: h[1], reverse=True)[:2]
    two.sort(key=lambda h: h[2])
    return two[0][0], two[1][0]


def vote(pairs):
    """幾張畫面各自的（左, 右），每位玩家取出現最多次的手勢。一張都沒看到兩隻手，回傳 None。"""
    if not pairs:
        return None
    latest = pairs[::-1]  # 從最後一張數起：次數一樣多時，取比較晚的那個，手已經停好了
    left = Counter(p[0] for p in latest).most_common(1)[0][0]
    right = Counter(p[1] for p in latest).most_common(1)[0][0]
    return left, right


def judge(left, right):
    """回傳 "left"、"right" 或 "draw"。"""
    if left == right:
        return "draw"
    return "left" if BEATS[left] == right else "right"


def settle(result, score):
    """一局結束：記分、在終端機印出結果，回傳要寫在畫面上的字。"""
    if result is None:
        print("沒看清楚，再來一次（要兩隻手都被框到）")
        return "Not clear - try again"
    left, right = result
    winner = judge(left, right)
    score[winner] += 1
    who = {"left": "左邊贏", "right": "右邊贏", "draw": "平手"}[winner]
    print(f"左邊 {left}、右邊 {right} → {who}")
    return f"{left} vs {right}: " + ("DRAW" if winner == "draw" else f"{winner.upper()} WINS")


# ---------- 畫面 ----------

def text(img, s, y, scale=0.8, center=False):
    """寫字：先畫黑色粗字當外框，再畫白字。center=True 時左右置中。"""
    x = 12
    if center:
        x = (img.shape[1] - cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0][0]) // 2
    for color, thick in (((0, 0, 0), round(scale * 6)), ((255, 255, 255), round(scale * 2.5))):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def play(model, source):
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise SystemExit(f"打不開 {source}：鏡頭被別的程式用著，或編號不對")
    score = Counter()
    state, t0, pairs, message = "wait", 0.0, [], ""
    print("兩個人並排在鏡頭前，按空白鍵開始一局，按 Q 或 Esc 結束。")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("拿不到畫面，結束")
            break
        # 左右翻轉成鏡像：玩家看螢幕就像照鏡子，站在左邊的人出現在畫面左邊，就是「左邊玩家」。
        # 不翻的話，鏡頭看到的左右和玩家自己的左右相反，容易搞混。
        # 手勢左右翻轉還是同一個手勢，訓練時 YOLO 也會隨機左右翻轉圖片，所以不影響辨識。
        frame = cv2.flip(frame, 1)
        out, hands = find_hands(model, frame)
        now = time.monotonic()

        if state == "count" and now - t0 >= COUNTDOWN:
            state, t0, pairs = "capture", now, []
        if state == "count":
            text(out, str(COUNTDOWN - int(now - t0)), 120, 4, center=True)  # 放上方，不擋到手
        elif state == "capture":
            pair = left_right(hands)
            if pair and now - t0 >= SETTLE:  # 先等手停好，才開始算
                pairs.append(pair)
            text(out, "GO!", 120, 4, center=True)
            if now - t0 >= SETTLE + CAPTURE:
                message = settle(vote(pairs), score)
                print(f"  比數 左 {score['left']} : {score['right']} 右，平手 {score['draw']} 次")
                state, t0 = "result", now
        elif state == "result":
            text(out, message, 60, 0.9, center=True)
            if now - t0 >= RESULT:
                state = "wait"
        else:
            text(out, "SPACE: start   Q: quit", 32)
        text(out, f"LEFT {score['left']} : {score['right']} RIGHT   draw {score['draw']}",
             out.shape[0] - 16)
        cv2.imshow(WIN, out)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key == ord(" ") and state == "wait":
            state, t0 = "count", now
    cap.release()
    cv2.destroyAllWindows()


def photo(model, path):
    """照片只判斷一次，不開視窗。照片不翻轉：照片左邊的手就是左邊玩家。"""
    frame = cv2.imread(path)
    if frame is None:
        raise SystemExit(f"讀不到圖片：{path}")
    out, hands = find_hands(model, frame)
    found = "、".join(f"{g} {p:.2f}（x={x:.0f}）" for g, p, x in sorted(hands, key=lambda h: h[2]))
    print(f"偵測到 {len(hands)} 隻手：{found or '沒有'}")
    pair = left_right(hands)
    settle(vote([pair] if pair else []), Counter())
    cv2.imwrite("rps_result.jpg", out)
    print("標註圖存成 rps_result.jpg")


def main():
    parser = argparse.ArgumentParser(description="簡易猜拳遊戲")
    parser.add_argument("--model", default="best.pt", help="權重檔或網址")
    parser.add_argument("--source", default="0", help="0、1，或圖片檔")
    args = parser.parse_args()

    # 網址交給 Ultralytics 下載；本機的檔案先檢查在不在
    if not args.model.startswith(("http://", "https://")) and not Path(args.model).exists():
        raise SystemExit(f"找不到 {args.model}：把訓練結果資料夾裡的 weights/best.pt 複製到課程資料夾，"
                         f"或用 --model 指定權重檔")
    model = YOLO(args.model)
    usable = sorted({GESTURES[n.lower()] for n in model.names.values() if n.lower() in GESTURES})
    if not usable:
        raise SystemExit(f"{args.model} 沒有剪刀石頭布的類別，它的類別是：{'、'.join(model.names.values())}")
    print(f"模型認得的手勢：{'、'.join(usable)}")

    if Path(args.source).suffix.lower() in IMAGE_EXT:
        photo(model, args.source)
    else:
        play(model, args.source)


if __name__ == "__main__":
    main()
