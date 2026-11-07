---
name: drum-score-validate
description: 用「本身附有鼓譜的打鼓影片」驗證並改進自動扒鼓譜的準確度：擷取影片上的譜當標準答案、逐格比對、找出落差原因、修正演算法、重新量化評分。當使用者說「拿這支有譜的影片驗證」「比對我扒的譜跟影片上的譜」「過門/某段扒得不準，幫我找原因」「扒譜準確度多少」時使用。
---

# 鼓譜扒譜驗證流程

前提：已依 drum-score-video skill 跑完 download / analyze / score（下載前要先徵得使用者同意）。

## 1. 擷取影片上的譜

```
.venv/Scripts/python.exe tools/gt_tools.py extract <name> [--y0 860 --y1 1080]
```
- 先抽一張影格看譜條在畫面哪個高度，調整 `--y0/--y1`（1080p 座標）。
- 產出 `projects/<name>/gt/line_XXX.png`（每次換行一張）、`half_XXX.png`（左右兩半放大，抄譜用）、`lines.json`（每行出現時間）。
- 轉場時會有重複或全黑的行，抄譜時跳過即可。

## 2. 手抄成標準答案 `projects/<name>/gt/gt.txt`

逐張 Read `half_XXX.png` 抄寫。格式（範例見 `projects/kickback/gt/gt.txt`）：
```
9: CR 1; BD 1 3&; SD 2 4; HH 1& 2 2& 3 3& 4 4&
10: HH8; SD 2 3e 4; BD 1 3&
12: =10            # 與第 10 小節相同（% 記號也這樣抄）
43: rest           # 整小節休止；多小節休止要展開成每小節一行
41: SD 3 3T3 4T2 4T3   # 三連音：T2 = 拍 + 1/3，T3 = 拍 + 2/3
```
- 位置：`1 1e 1& 1a … 4a`；`HH8` = 8 個 8 分音符 hi-hat。
- 樂器：CR crash(⊗)、HH、HO 開 hi-hat、RD、XS cross-stick（小鼓位置的 ▲）、SD、TH/TM/TF、BD、HF hi-hat 踏。
- 讀音高：上下聲部分開讀；先用下聲部（大鼓）的休止符算出每拍 x 座標，再對上聲部。不確定的小節用 PIL 裁切放大 2 倍再看。
- 小節編號以影片第一個有音的小節為 1；用 `lines.json` 的時間對照 `score.json` 各小節 t0 確認沒有錯位。

## 3. 評分與對照

```
.venv/Scripts/python.exe tools/evaluate.py <name> --detail     # 各樂器精確率/召回率/F1 + 每小節差異
.venv/Scripts/python.exe tools/gt_tools.py compare <name>      # gt/cmp_XX.png：上影片譜、下自動扒譜
```
差異符號：`+3e` 多抓、`-2&` 漏抓。

## 4. 找原因的套路（依過去經驗由大到小）

1. **整段錯位/節奏全亂** → 拍點：檢查 `beats.json` 拍距是否在某段變 2 倍或一半（`repair_beats`）。
2. **固定早/晚一格** → 量測 ADTOF 峰值相對格線的偏移（`grid_offset`），或演奏律動拖拍（`OFFBEAT16_PENALTY`）。
3. **某樂器系統性漏抓** → 比較 `act_drums.npy` 與 `act_mix.npy` 哪個來源較準（`HYBRID_SOURCE`）；印出該小節每格機率看是「低於門檻」還是「完全沒反應」。
4. **樂器分類錯**（▲ 被當小鼓、tom/大鼓混淆）→ 在 drums.wav 擊打瞬間取頻譜特徵（低頻比例、峰值頻率、平坦度），比較兩群分佈再訂規則。
5. **三連音/特殊節奏** → 印出拍內擊打點的小數位置（0.33/0.67 vs 0.25/0.5/0.75）。
- 調門檻前先掃描看曲線：曲線平代表門檻不是瓶頸，不要硬調以免過度擬合單一首歌。
- 每次修改後重跑 `score` + `evaluate`，確認整體 F1 與「完全正確小節」都沒有退步。

## 5. 回報

給使用者：修正前後的數字對照表、每類落差的原因與對應修正、仍無法修正的部分（例如譜上省略的 ghost note、伴奏音軌的 hi-hat、開/閉 hi-hat）。
