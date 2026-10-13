---
slug: yolo
type: tool
title: YOLO 模型家族
lead: 物件偵測最常用的模型家族。各版本是誰做的、模型怎麼挑、怎麼用 Ultralytics 套件辨識，以及怎麼使用官方和別人分享的權重、把模型放到其他裝置上。
meta:
  套件: Ultralytics 8.4（YOLO26）
  電腦: Windows、macOS、Linux，Python 3.13（uv）
updated: 2026-10
next: [微專題 02：簡易 AI 監控系統](monitor-esp32cam.html)
---

## YOLO 是什麼

YOLO 是 You Only Look Once（只看一次）的縮寫。早期的物件偵測要先在畫面上挑出幾千個「可能有東西」的區域，再一塊一塊判斷是什麼；YOLO 把整張畫面送進模型一次，就同時算出所有框的位置和類別，所以快到能即時處理鏡頭畫面。

課堂上常用 YOLO，是因為：

- **快**：不用顯示卡也能即時辨識。這份講義的測試筆電（Apple M4，只用 CPU）上，yolo26n 一張約 20 多毫秒。
- **好裝**：Ultralytics 套件一行指令裝好，模型第一次用的時候自動下載。
- **一個套件做好幾種事**：物件偵測、實例分割、影像分類、姿勢辨識，都是同一套寫法。
- **資料多**：網路上的教學、範例，和別人訓練好分享出來的模型都很多。

> [!NOTE]
> 物件偵測、分割這些任務在做什麼，辨識結果的類別、信心度、框怎麼看，在[影像辨識](vision.html#s3)講義。這份講義不重講，只講 YOLO 怎麼挑、怎麼用。

### 先讀

- [環境安裝](setup.html#s3)：裝好 uv，建好課程資料夾。
- [影像辨識](vision.html)：第 03、04 節。

## 版本年表

> 「YOLO26 是第 26 版嗎？YOLOv12 比 YOLO11 新，所以比較好嗎？」

都不是。YOLO 的版本號不是同一個團隊一路往上加：原作者做到 v3 就停了，之後各家公司和研究團隊都用 YOLO 這個名字發表自己的版本。號碼有時候接在別人後面，有時候跳號：v13 之後，Ultralytics 直接跳到 26，官方沒有說明這個數字怎麼來的。

:::diagram 版本時間軸 {#timeline}
橫軸是 2015 到 2026 年。分成四排，每排一個團隊：原作者 Redmon（v1 2015、v2 2016、v3 2018）、中研院王建堯和廖弘源（v4 2020、v7 2022、v9 2024）、Ultralytics 公司（v5 2020、v8 2023、11 2024、26 2026，27 已宣布但還沒釋出，用虛線）、其他團隊（v6 2022 美團、v10 2024 清華、v12 2025 水牛城大學等、v13 2025 清華）。每個版本是排上的一個點，標版本號。一眼要看得出來：號碼不是在同一排裡連續往上加。
:::

| 版本 | 年份 | 誰做的 | 特色 |
|---|---|---|---|
| v1–v3 | 2015–2018 | Joseph Redmon 等（華盛頓大學） | 開創「整張畫面只看一次」的做法 |
| v4 | 2020 | Alexey Bochkovskiy、王建堯、廖弘源 | 整理並加入大量訓練技巧，例如把四張照片拼成一張來訓練 |
| v5 | 2020 | Ultralytics | 改用 PyTorch（現在最常用的深度學習套件），好裝好用；沒有發表論文 |
| v6 | 2022 | 美團 | 為工業應用的部署設計 |
| v7 | 2022 | 王建堯、Bochkovskiy、廖弘源 | 改良模型結構和訓練方法，同樣速度下更準 |
| v8 | 2023 | Ultralytics | 同一個套件做偵測、分割、分類、姿勢 |
| v9 | 2024 | 王建堯、廖弘源等 | 改善深層網路訓練時資訊流失的問題 |
| v10 | 2024 | 清華大學 | 第一個主打不需要 NMS 的 YOLO |
| 11 | 2024 | Ultralytics | 參數更少、更準：YOLO11m 比 YOLOv8m 少兩成參數 |
| v12 | 2025 | 水牛城大學、中國科學院大學 | 以注意力機制為核心 |
| v13 | 2025 | 清華大學 | 用新的方法找出畫面各部分之間的關聯 |
| 26 | 2026 | Ultralytics | 不需要 NMS，為 CPU 和小型裝置設計；yolo26n 在 CPU 上比 YOLO11n 快最多 43% |
| 27 | 2026 年 9 月宣布 | Ultralytics | 還沒釋出 |

- **NMS**：模型對同一個東西常常給出好幾個重疊的框，NMS 是最後只留下最好那一個的步驟。省掉這一步，速度比較快，畫面裡東西多的時候也不會變慢。
- **v4、v7、v9**：都有台灣中央研究院資訊科學研究所的王建堯、廖弘源參與。
- **v12、v13**：學術團隊發表的版本。Ultralytics 的文件說 YOLO12 訓練可能不穩、在 CPU 上比較慢，不建議正式使用。

### 原作者為什麼停下來

原作者 Joseph Redmon 在 [2020 年 2 月的推文](https://x.com/pjreddie/status/1230524770350817280)裡說，他停止了電腦視覺的研究：「我看到了自己的研究造成的影響。我很喜歡這份工作，但軍事用途和隱私問題，最後讓我無法再忽視。」

同一套技術可以拿來數車流、找走失的寵物，也可以拿來監看別人。微專題 02 的[什麼情況下會失效](monitor-esp32cam.html#s5)一節，最後一組就是在練習想這件事。

### 其他做同一件事的模型

還有一些沒有編號、或名字裡沒有 YOLO 的模型也做物件偵測，例如曠視的 YOLOX、百度的 RT-DETR、Roboflow 的 RF-DETR。看到「比 YOLO 更準」的新模型，先看它比的是哪一版、在什麼裝置上量的。

## 看懂模型檔名

`yolo26n-seg.pt` 拆開來是四個部分：

| 部分 | 意思 |
|---|---|
| `yolo26` | 版本 |
| `n` | 大小：n、s、m、l、x，越後面越大 |
| `-seg` | 任務：這個是實例分割。沒有字尾的是物件偵測 |
| `.pt` | 檔案格式：PyTorch |

檔案裡存的是模型的**權重**，也就是訓練時學到的幾百萬個數字。「下載模型」「分享權重」說的都是這個檔案。

### 大小：n、s、m、l、x

YOLO26 物件偵測的官方數字（2026-10 的[官方文件](https://docs.ultralytics.com/models/yolo26/)）：

| 大小 | 參數量 | 準確度 | CPU 每張 |
|---|---|---|---|
| n（nano） | 2.4M | 40.9 | 38.9 ms |
| s（small） | 9.5M | 48.6 | 87.2 ms |
| m（medium） | 20.4M | 53.1 | 220.0 ms |
| l（large） | 24.8M | 55.0 | 286.2 ms |
| x（extra large） | 55.7M | 57.5 | 525.8 ms |

- **參數量**：權重有幾個數字，M 是百萬。越多，檔案越大、算得越久。
- **準確度**：在 COCO（常用的公開資料集，80 類日常物品，見[影像辨識](vision.html#s5)講義第 05 節）驗證照片上的分數（mAP50-95），0 到 100，越高越準。只有在同一份照片上量的分數才能比。
- **CPU 每張**：官方的測試電腦用 CPU、ONNX 格式（第 07 節）量的時間。你的電腦不一樣，第 05 節自己量。

從 n 到 x，參數量多了 23 倍、時間多了 13 倍，準確度從 40.9 進步到 57.5。

### 任務：字尾

| 字尾 | 任務 | 訓練用的公開資料集 |
|---|---|---|
| 沒有 | 物件偵測 | COCO，80 類 |
| `-seg` | 實例分割 | COCO，80 類 |
| `-cls` | 影像分類 | ImageNet，1000 類 |
| `-pose` | 姿勢辨識 | COCO，人體 17 個關節點 |
| `-obb` | 旋轉框偵測 | DOTA，空拍照片 15 類 |
| `-sem` | 語意分割 | Cityscapes，街景 19 類 |
| `-sem-ade20k` | 語意分割 | ADE20K，室內外場景 150 類 |
| `-depth` | 深度估計 | 約 219 萬張照片 |

- **旋轉框偵測**：框可以斜著放，用在空拍照片裡斜停的船、車這類東西。
- **深度估計**：估計畫面裡每一點離鏡頭多遠。
- 檔名開頭是 `yoloe-26` 的是開放詞彙模型：用文字告訴它要找什麼，不限於 80 類。

## 用 Ultralytics 跑起來

### 安裝

在課程資料夾的終端機執行。做過影像辨識講義第 07 節的話，已經裝好了。

```sh
uv add ultralytics
```

ultralytics 會一起裝 PyTorch 和 OpenCV，裝好約 1&nbsp;GB，下載要好幾分鐘，請在上課前裝好。

### 用指令

```sh
uv run yolo predict model=yolo26n.pt source=https://ultralytics.com/images/bus.jpg
```

- 第一次會自動下載 yolo26n.pt（約 5&nbsp;MB），放在目前的資料夾。
- 終端機印出 `4 persons, 1 bus`；畫好框的圖存在 runs/detect/predict。再跑一次會存到 predict-2、predict-3……
- 改成 `source=0 show=True` 就是用網路攝影機即時辨識，在終端機按 Ctrl+C 結束。打不開鏡頭，照[影像辨識](vision.html#s7)講義第 07 節允許終端機使用相機；沒有鏡頭就繼續用圖片網址。

### 用 Python

存成課程資料夾裡的 detect_bus.py，執行 `uv run detect_bus.py`：

```py
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model("https://ultralytics.com/images/bus.jpg")
for box in results[0].boxes:
    print(model.names[int(box.cls)], round(float(box.conf), 2))
```

印出 `bus 0.88`、`person 0.87`……每個框一行。`model.names` 是類別編號對名稱的對照表，yolo26n.pt 有 80 類。

用 Python 時預設不存圖；要存的話加 `save=True`。

### 來源

| 寫法 | 來源 |
|---|---|
| `bus.jpg` | 一張圖片；也可以是圖片網址 |
| `照片/` | 資料夾裡的所有圖片 |
| `影片.mp4` | 影片檔 |
| `0` | 網路攝影機；第二支是 `1` |

ESP32-CAM 的畫面，用影像辨識講義的 [vision_demo.py](vision.html#s7) 加 `--source` 網址。

### 常用參數

指令寫成 `conf=0.5`，Python 寫成 `model("bus.jpg", conf=0.5)`。

| 參數 | 意思 | 例子 |
|---|---|---|
| `conf` | 信心度門檻，低於這個的不算 | `conf=0.5` |
| `classes` | 只要某幾類，寫類別編號 | `classes=0`：只要 person |
| `imgsz` | 送進模型前縮成多大，小一點比較快 | `imgsz=320` |
| `device` | 用什麼硬體算 | `cpu`、`0`：第一張 NVIDIA 顯示卡、`mps`：Mac 的 GPU |
| `save` | 存下畫好框的結果 | `save=True` |
| `show` | 開視窗顯示 | `show=True` |

## 怎麼挑

| 情況 | 建議 |
|---|---|
| 第一次用，一般筆電 | `yolo26n.pt` |
| n 常常漏掉小東西或認錯 | 換 `yolo26s.pt`，速度慢 2 倍左右 |
| 有 NVIDIA 顯示卡 | s 或 m，加上 `device=0` |
| 樹莓派 5 | n，匯出成 NCNN（第 07 節）。官方在 Pi 5 上量，一張從 299 ms 變成 67 ms |
| 照著網路上的教學做，教學用 YOLOv8 或 YOLO11 | 先照教學用同一版，跑通再換。在 Ultralytics 套件裡只要改檔名 |
| 看到論文說 v12、v13 比較準 | 先用 YOLO26 或 YOLO11，原因見第 02 節 |

原則：先用 n 把整個流程跑通，不夠準再換大一號。

### 自己量量看

yolo_compare.py 用同一張畫面跑好幾個大小的模型，印出每個花多久、找到什麼。存成課程資料夾裡的 yolo_compare.py：

@code python/yolo_compare.py

```sh
uv run yolo_compare.py
uv run yolo_compare.py --source bus.jpg --save
```

- 第一行用網路攝影機拍一張來比；第二行用照片。bus.jpg 是第 04 節用指令辨識時，Ultralytics 下載到資料夾裡的範例照片。
- 沒有下載過的模型，第一次會自動下載：s 約 20&nbsp;MB，m 約 44&nbsp;MB。

測試筆電（Apple M4，只用 CPU）跑 bus.jpg 的結果：

```text
模型        參數量  平均毫秒  偵測數  前 3 個（類別 信心值）
yolo26n.pt  2.4M    22.5      5       bus 0.88、person 0.87、person 0.86
yolo26s.pt  9.5M    43.1      5       bus 0.92、person 0.92、person 0.90
yolo26m.pt  20.4M   87.8      5       person 0.94、person 0.94、bus 0.92
```

三個都找到 4 個人和 1 台公車，大的信心度高一點，但時間是 2 倍、4 倍。這張照片很清楚，小模型就夠了；換成光線差、東西小的照片再比一次，差距會比較明顯。

## 用別人分享的權重

> 「我要偵測的東西不在 COCO 的 80 類裡，一定要自己訓練嗎？」

不一定，先找找看有沒有人訓練好、分享出來。COCO 沒有「臉」和「手」，但網路上有很多人分享偵測臉、手、車牌、安全帽的權重。

### 去哪裡找

| 地方 | 怎麼找 | 注意 |
|---|---|---|
| [Hugging Face](https://huggingface.co/models?library=ultralytics) | 模型頁篩選 Ultralytics | 數量最多，品質不一；看下載數和說明頁 |
| [Ultralytics Platform](https://platform.ultralytics.com) | Explore 頁 | 別人公開的模型可以下載 .pt，也有匯出好的其他格式 |
| [Kaggle](https://www.kaggle.com/models) | 搜尋 YOLO | Ultralytics 官方也放了 YOLO26、YOLO11 |
| GitHub | 專案的 Releases 頁面 | 通常跟著論文或專案一起發布 |
| Roboflow Universe | 搜尋資料集 | 主要是資料集；別人的模型多半要註冊帳號、用它的服務執行 |

### 用之前先檢查

- **載得進來嗎**：說明頁寫的是哪一版 YOLO、用什麼程式訓練的。用原版 YOLOv5、YOLOv7 專案訓練的權重，Ultralytics 載不進來，會出現 `NOT forwards compatible` 的錯誤。
- **認得哪些類別**：載入以後 `print(model.names)`。
- **用什麼照片訓練的**：照片跟你的場地差越多（角度、光線、背景），越容易認錯。說明頁沒寫訓練資料的，要自己多測。
- **授權**：能不能用在你的作品，見第 08 節。
- **來源信得過嗎**：見下一段。

### .pt 檔可以執行程式

.pt 檔用 Python 的 pickle 格式存，這種格式在載入時，可以執行檔案裡夾帶的任何程式碼。Ultralytics 預設沒有關掉這個功能；檔案裡寫到的套件沒裝，它還會試著自動安裝。所以載入一個陌生人的 .pt，跟執行一支陌生人寫的程式一樣。

- **只用信得過的來源**：官方、下載數多、說明頁完整、作者有其他作品。
- **下載前看掃描結果**：Hugging Face 會掃描 .pt 檔，在檔案頁列出它載入時會用到的程式。Ultralytics 的權重會用到 ultralytics 套件自己的程式，所以官方權重也會標成要注意（caution）；標成危險（dangerous）的不要用。掃描不是百分之百準，不能取代「來源信得過」。
- **用比較保險的載法**：在程式最前面加上這兩行，Ultralytics 就只載入正常權重會用到的東西，也不會自動安裝套件。Ultralytics 官方的權重和下面的範例都能這樣載入。

```py
import os
os.environ["ULTRALYTICS_SAFE_LOAD"] = "1"   # 要寫在 from ultralytics import YOLO 之前
```

用指令時，macOS、Linux 在指令前面加上 `ULTRALYTICS_SAFE_LOAD=1`；Windows 的 PowerShell 先執行 `$env:ULTRALYTICS_SAFE_LOAD="1"`，同一個視窗裡之後的指令都有效。

- **有 ONNX 版本的可以用 ONNX**：它只存運算步驟和數字，不是 pickle 格式。不過匯出的格式只能拿來辨識，不能接著訓練。

這和[環境安裝](setup.html#s6)講義「AI 建議的套件先查」是同一件事：從網路上拿來、會在你電腦上執行的東西，都要先確認來源。

### 範例：偵測手

Hugging Face 上的 [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) 分享了偵測臉和手的權重，下載數很多，說明頁標示 Apache-2.0 授權。`model=` 後面直接放權重的網址：

```sh
uv run yolo predict model=https://huggingface.co/Bingsu/adetailer/resolve/main/hand_yolov8n.pt source=0 show=True
```

- 第一次會把權重下載到目前資料夾的 weights/hand_yolov8n.pt（約 6&nbsp;MB），之後直接用。
- 它只認一類：`model.names` 是 `{0: 'hand'}`。檔名 yolov8n 表示這是用 YOLOv8 的 n 訓練的，Ultralytics 套件一樣能載入。
- 網址要用檔案頁的「下載」連結，中間是 `/resolve/`。直接複製瀏覽器網址列會是 `/blob/`，下載到的是網頁，會出現 `invalid load key, '<'` 的錯誤。

> [!NOTE]
> 這份權重是從 Ultralytics 的 YOLOv8 繼續訓練來的，Ultralytics 的授權是 AGPL-3.0。這種情況授權怎麼算，說法不一；用在上課沒問題，要做成產品前先查清楚。

想認的東西真的沒有人分享，就要自己訓練，見[微專題 03：簡易猜拳遊戲](rps-webcam.html)。

## 匯出到其他裝置

.pt 要裝了 PyTorch 才能用。要放到手機、樹莓派、瀏覽器上，或想在電腦上跑快一點，先匯出成那個裝置用的格式。最常用的是 ONNX：一種通用的模型格式，很多程式和裝置都讀得懂，不需要 PyTorch。

```sh
uv add onnx onnxruntime onnxslim
uv run yolo export model=yolo26n.pt format=onnx
```

- 第一行裝匯出 ONNX 要用的套件，只要裝一次。Ultralytics 本來會自己裝，但在 uv 建的環境裡常常裝不起來，所以先手動裝。
- 匯出的 yolo26n.onnx 和 yolo26n.pt 放在同一個資料夾，一樣用 `YOLO("yolo26n.onnx")` 或 `model=yolo26n.onnx` 載入。
- ONNX 約 10&nbsp;MB，比 .pt 的 5&nbsp;MB 大：.pt 每個數字用的位數是 ONNX 的一半。這只影響檔案大小，辨識結果幾乎一樣。
- 在測試筆電上，同一張照片 .pt 約 25 毫秒，ONNX 約 19 毫秒。

| 格式 | format= | 適合 |
|---|---|---|
| ONNX | `onnx` | 通用，Windows、macOS、Linux 都能跑 |
| OpenVINO | `openvino` | Intel 的 CPU |
| TensorRT | `engine` | NVIDIA 顯示卡、Jetson |
| Core&nbsp;ML | `coreml` | iPhone、Mac |
| LiteRT | `litert` | Android 手機；瀏覽器用 LiteRT.js 執行 |
| NCNN | `ncnn` | 樹莓派、Android 手機 |

舊教學寫的 `format=tflite`、`format=tfjs`，新版會自動改成 `litert`；`int8=True`、`half=True` 改成 `quantize=8`、`quantize=16`。完整清單見[官方文件](https://docs.ultralytics.com/modes/export/)。


### ESP32-CAM 為什麼跑不動

ESP32-CAM 的晶片是經典款 ESP32。樂鑫（Espressif）的 AI 函式庫 [ESP-DL](https://github.com/espressif/esp-dl) 有在新一代晶片上跑 YOLO26n 的範例，速度是這樣：

| 晶片 | 輸入大小 | 一張要多久 |
|---|---|---|
| ESP32-P4 | 512 | 約 2 秒 |
| ESP32-S3 | 512 | 約 8 秒 |
| ESP32（ESP32-CAM） | — | 範例沒有提供 |

官方文件說，新晶片的運算有專用的加速指令，經典款 ESP32 只能用一般的 C 程式算，會慢很多；範例也還沒附這顆晶片的設定。樂鑫另外做了更小的偵測模型 [ESPDet-Pico](https://github.com/espressif/esp-detection)，輸入縮到 224，ESP32-S3 每秒能跑 7 張以上，官方有貓、狗、手、臉、行人的範例。

所以微專題 02 讓 ESP32-CAM 負責拍、電腦負責辨識。各種板子能跑什麼，見[影像辨識](vision.html#s6)和[選擇控制器](controller.html)講義。

## 授權

> 「我用 YOLO 做的作品，可以拿去比賽、拿去賣嗎？」

Ultralytics 的套件和模型（v5、v8、11、26）用 AGPL-3.0 授權。[官方的授權頁](https://www.ultralytics.com/license)把用途分成兩種：

| 用途 | 可以嗎 |
|---|---|
| 上課、研究、自己練習 | 可以 |
| 專題放到 GitHub 開源 | 可以，整個專案（程式、設定，可能也包括訓練出來的權重）都要用 AGPL-3.0 公開 |
| 做成產品，或做成網路服務、API 給別人用，但不公開程式碼 | 要買 Ultralytics 的企業授權 |

官方的常見問題還說，用 Ultralytics 訓練出來的權重預設也是 AGPL-3.0，只在公司內部使用也一樣。這是 Ultralytics 自己的說法，比一般對 AGPL 的解讀更寬；要做成產品之前，先找懂授權的人確認。

其他版本的授權不一樣：

| 授權 | 版本 | 白話 |
|---|---|---|
| 公有領域 | v1–v4（Darknet） | 不限制怎麼用 |
| Apache-2.0 | YOLOX、RT-DETR（百度原版）、RF-DETR（N 到 L） | 寬鬆：保留授權聲明就能用，包括做成產品 |
| GPL-3.0 | v6、v7、v9 | 把軟體散布出去，要連程式碼一起公開 |
| AGPL-3.0 | v5、v8、v10、11、v12、v13、26 | 除了散布，做成網路服務給別人用也要公開程式碼 |

同一個模型可能有不同授權：Ultralytics 套件裡的 RT-DETR 是 AGPL-3.0；YOLO-NAS 的程式是 Apache-2.0，權重卻不能商用。

> [!NOTE]
> 以各專案的 LICENSE 檔和官方說明為準。要用在比賽或產品上，先看清楚規定。

## 常見問題

- **第一次執行很久沒反應**：正在下載模型檔，n 約 5&nbsp;MB，s 約 20&nbsp;MB，m 約 44&nbsp;MB。
- **No module named 'ultralytics'**：不在課程資料夾，或沒有用 uv run 執行。
- **網路上的 YOLOv5 程式跑不起來**：很多舊教學用原版 YOLOv5 專案（`python detect.py`、`torch.hub.load`），寫法和 Ultralytics 套件不同。改用第 04 節的寫法，模型換成 YOLO26 或 YOLO11。
- **有 NVIDIA 顯示卡，還是很慢**：沒有加 `device=0`，或裝到只能用 CPU 的 PyTorch。照 [uv 的 PyTorch 說明](https://docs.astral.sh/uv/guides/integration/pytorch/)改裝支援 CUDA（NVIDIA 顯示卡的運算平台）的版本。
- **Mac 要怎麼用 GPU**：加 `device=mps`。測試筆電上，yolo26n 一張從 23 毫秒變成 6 毫秒；第一張要準備，會慢半秒。
- **匯出 ONNX 出現 No module named 'onnx'**：先執行第 07 節的第一行，裝好匯出要用的套件。
- **載入權重出現 invalid load key, '<'**：下載到的是網頁，不是權重。Hugging Face 的網址要用 `/resolve/`，不是 `/blob/`。

### 請 AI 幫你找

```prompt
我用 Python 和 ultralytics 套件（用 uv 管理），想用網路攝影機偵測「＿＿＿」，COCO 的 80 類裡沒有這個東西。
請幫我：
1. 找 Hugging Face 上能用 ultralytics 載入的模型，列出網址、下載數、授權、用什麼照片訓練。
2. 說明下載前要檢查什麼，.pt 檔有什麼安全風險。
3. 寫一段程式用網路攝影機測試，信心度 0.5 以上才畫框。用 uv run 執行，不要用 pip。
```

拿到答案後，先自己打開每個網址：AI 可能編出不存在的模型，授權也要到模型頁自己看。
