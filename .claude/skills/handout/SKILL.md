---
name: handout
description: SkillLab 講義的製作流程：先用 Markdown 寫初稿（content/handout/<slug>.md），使用者審閱後用 tools/md2html.mjs 轉成網頁；也規定子 agent 怎麼分工。寫新講義、修改用 md 寫的講義、或使用者說「上網頁」時使用。
---

# 講義製作流程

新講義一律先寫 Markdown，md 是來源，網頁由 `tools/md2html.mjs` 產生。標記寫法見 [markup.md](markup.md)。

已經手寫成 HTML 的講義（setup、controller、alarm-uno、alarm-esp32、vision、esp32-cam）不補 md，照舊直接改 HTML。產生出來的 HTML 第一行註解寫著「由 content/handout/… 產生」，這種檔案不要手改，改 md 再轉。

## 流程

| 步驟 | 誰 | 做什麼 |
|---|---|---|
| 1. 大綱 | Claude → 使用者確認 | 講義類型、slug、每一節的標題和重點、要查證的事、要寫的程式。在對話裡給，確認後才寫 |
| 2. 初稿 | Claude（子 agent 平行查證、寫程式） | 寫 `content/handout/<slug>.md`；程式放 `handout/code/`，要編譯或執行過；沒把握的寫 `[待查]` |
| 3. 預覽 | Claude | `node tools/md2html.mjs <slug> --preview` 產生 `handout/_preview-<slug>.html`（不進 git），用 check-layout 看過再交給使用者 |
| 4. 審閱 | 使用者 | 直接改 md；要 Claude 處理的留 `<!-- 給 Claude：… -->`；改好說「上網頁」 |
| 5. 上網頁 | Claude（子 agent 平行檢查） | 見下面的清單 |
| 6. 回報 | Claude | 改了哪些檔、檢查結果、沒測到的部分 |

### 上網頁

1. 處理 md 裡每一個 `<!-- 給 Claude：… -->` 和 `[待查]`，處理完刪掉。
2. 畫 `:::diagram` 要的圖，存成 `assets/handout/fig/<slug>/<id>.html`（見 markup.md 的「圖」）。
3. 第一次上網頁：照 CLAUDE.md 在 `handout.html` 對應的組加卡片（卡片連到 `handout/<slug>.html`）。
4. `node tools/md2html.mjs <slug>`：寫出 `handout/<slug>.html`、填程式區塊、同步選單卡片的「更新於」和「撰寫中」。有問題會列出來並拒絕寫檔。
5. 更新其他頁的 `doc-end` 和「製作中」說明（手寫的 HTML 頁直接改；md 頁改 md 的 `next:` 再轉）。
6. 排版和連結檢查（子 agent），有問題改 md 或 CSS 後重轉。

之後改內容：改 md → `node tools/md2html.mjs <slug>` → 截圖檢查。內容有實質更新時改檔頭的 `updated:`。

## 子 agent 分工

- 講義文字由主 agent 寫和改，不拆給子 agent，語氣和用字才一致。
- 子 agent 做能獨立完成、結果能驗證的工作，平行跑，回報給主 agent 整合。
- 小事（查一個版本號、改一行程式）主 agent 直接做，不開子 agent。
- 子 agent 不 commit、不改講義內文（md 和 HTML），只改交代的檔案。

| 階段 | 子 agent | 做什麼 | 能改的檔案 | 回報 |
|---|---|---|---|---|
| 初稿 | 查證 | 版本、規格、價格、網址、服務還在不在 | 不改檔 | 每題：答案、來源網址、查證日期、把握程度 |
| 初稿 | 程式 | 寫範例程式並實際編譯或執行 | `handout/code/` 下指定的檔案 | 檔案清單、編譯或執行的輸出、沒測到的部分 |
| 初稿寫完 | 試讀 | 用學生的角度讀 md，找跳步、沒解釋的名詞、照著做會卡住的地方 | 不改檔 | 行號和問題 |
| 上網頁後 | 排版 | 用 check-layout 截 1440／900／390，對照 CLAUDE.md 的視覺風格 | 不改檔 | 問題、寬度、截圖路徑 |
| 上網頁後 | 連結 | 站內連結和錨點都存在、外部連結打得開 | 不改檔 | 壞掉的連結 |

### 交代子 agent 時寫清楚

1. **目標**：要做出什麼，給講義 md 的路徑讓它讀相關段落。
2. **範圍**：能改哪些檔案；其他檔案只能讀。
3. **限制**：不 commit；不改講義內文；程式的註解和輸出用繁體中文（台灣用語）；照 CLAUDE.md。
4. **怎麼驗證**：
   - Arduino：用 Arduino IDE 內建的 arduino-cli 編譯，`"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile -b <FQBN> <資料夾>`（ESP32-CAM 是 `esp32:esp32:esp32cam`）。沒有實機就說沒有實機測過。
   - Python：在 scratchpad 建 uv 環境（Python 3.13，套件和講義相同）實際執行；需要硬體或網路服務時，用本機的假伺服器模擬。不能開視窗、不能用真的鏡頭。
5. **回報格式**：精簡；列出檔案、測試情境和輸出摘要、沒測到的部分、要問作者的問題。
