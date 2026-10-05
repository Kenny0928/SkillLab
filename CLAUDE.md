# SkillLab

純靜態網站，GitHub Pages 從 `main` 根目錄發布。`index.html` 的 `build:*` 區段由 `node tools/build.mjs` 產生，不要手改。

## 內容定位

- 網站以教育為目的。專題是概念雛形，不要寫得像能實際使用的產品：標題加上「簡易」這類字眼（例如「簡易防盜系統」），頁首用 `<p class="scope">` 框說明這是學習用的雛形，並保留「什麼情況下會失效」一節。
- 避免「保護」「防止」這類暗示有實際防護效果的用字，改用「偵測」「練習情境」。

## 檢查排版

改了 HTML／CSS 就用 `check-layout` skill 截圖確認（1440／900／390）。不要另寫截圖工具。

## 視覺風格

- 顏色只用 `assets/style.css` 的 token：底色 `--paper`，卡片 `--face`，文字 `--ink`／`--ink-2`，線 `--rule`，強調色 `--accent`（圖形）／`--accent-text`（小字）。`--ink-3` 對比不足，只能當裝飾。唯一另外的顏色是講義類型色。
- 字型：Inter + Noto Sans TC；編號、程式碼、規格用 `--mono`。字重只用 400／500／600。
- 平面風格：1px `--rule` 邊框，圓角 4px（程式碼區塊 6px）。不用陰影、漸層，選單卡片不放照片。
- 版寬：內文欄 760px，頁面最寬 1120px，左右留白 24px（寬度 < 400px 時 16px）。斷點 600／760／1100。
- 文字對比至少 4.5:1；可點區域高度至少 40px；手機不能出現水平捲動；產品名稱用 `&nbsp;` 連起來（`VS&nbsp;Code`），有連字號的名稱包 `<span class="nw">`（`ESP32-CAM`、`Wi-Fi`），數字和單位用 `&nbsp;`（`5&nbsp;MB`）；`tools/lib/nobreak.mjs` 可以一次處理整頁。行內 `<code>` 不換行，長指令用程式區塊。
- 內文連結不加 class，會自動變成橘色底線並加上 ↗／↓。導覽和卡片連結一定要加 class。

## 講義分類

| `data-type` | 標籤 | 內容 | |
|---|---|---|---|
| `tool` | 工具 | 軟體環境、開發工具 | |
| `hardware` | 硬體 | 控制器、感測器、模組 | |
| `concept` | 觀念 | 電路、訊號、序列埠、影像等原理 | |
| `project` | 微專題 NN | 小型專題，編號兩位數 | |
| `advanced` | 進階專題 | 大型專題 | 預留 |
| `resource` | 學習資源 | 外部資源整理 | 預留 |

- 不用「基礎」：內容會隨時間改變，新舊交給「更新於」表達。寫「微專題」，不寫「微專案」。
- 新類型先問使用者。顏色加在 `handout.css` 的 course types：`--t` 對白底至少 3:1，`--t-ink` 對 `--t-bg` 至少 4.5:1。

## 講義選單與內頁

- `handout.html`：依類型分組，組的順序照上表，組內依閱讀順序排列；頂端的跳轉列連到每一組。新卡片放進對應的組，照現有卡片的結構複製；某個類型的第一篇要連同組和跳轉連結一起加。
- 一個專題一張卡，各版本放在 `card-vers`，`card-link` 指向完成度最高的版本。未完成的版本加 `<span class="st">撰寫中</span>`，等內頁的 `badge` 拿掉時一起拿掉。
- 「更新於 YYYY-MM」是手寫的，講義內容有實質更新時要同步改。
- 內頁 kicker 格式為 `<p class="kicker" data-type="project"><span class="type-tag">微專題 01</span>Arduino Uno 版</p>`，類型和文字要跟卡片一致。
- 新增講義：寫 md → 使用者審閱 → 在選單加卡片 → 轉成網頁 → 更新其他頁的 `doc-end` 和「製作中」說明。

## 講義製作流程

- 新講義先寫 Markdown（`content/handout/<slug>.md`），使用者看過、說「上網頁」，再用 `node tools/md2html.mjs <slug>` 轉成 `handout/<slug>.html`。md 是來源，改內容就改 md 再轉。
- 流程、標記寫法、子 agent 怎麼分工，見 `handout` skill。
- md 產生的 HTML 不要手改。已經手寫成 HTML 的講義不補 md，照舊直接改 HTML。
