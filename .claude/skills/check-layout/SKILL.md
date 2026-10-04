---
name: check-layout
description: 截圖檢查 SkillLab 頁面的排版與視覺（1440／900／390 三種寬度）。改了 HTML 或 CSS 之後、或使用者要檢視頁面視覺問題時使用。
---

# 檢查排版

1. 截圖（腳本自己起伺服器，三種寬度一次跑完，輸出到 scratchpad）：

   ```sh
   node .claude/skills/check-layout/shot.mjs handout.html --out <scratchpad>
   ```

   - 只看某個區塊：`--selector ".doc-head"`
   - 只要某些寬度：`--widths 390`
   - 要量數值：`--eval "JS 表達式"`。例如卡片高度 `[...document.querySelectorAll('.card')].map(c => c.offsetHeight)`；點擊目標 `document.elementFromPoint(x, y).className`
   - 頁面出現水平捲動時，輸出會標 ⚠

2. 用 Read 看截圖。長頁面先用 `--selector` 截局部，或用 PIL 裁切，不要整張縮小看細節。

3. 對照 CLAUDE.md 的「視覺風格」逐項檢查，並特別注意：
   - 手機上產品名稱斷行（用 `&nbsp;`）
   - 同一列的卡片是否等高
   - 新加的顏色和文字對比
   - 改動是否波及其他頁（共用的 class 要截其他頁確認）

4. 回報時附上看到的問題和寬度；改完再截一次確認。
