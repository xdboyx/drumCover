---
name: drum-score-video
description: 把一支歌曲影片（YouTube 網址或本地 mp4）自動扒鼓譜，合成「上方影片、下方一行 4 小節鼓譜 + 藍色游標跟著目前該打的音符」的練習影片。當使用者說「幫這首歌做鼓譜影片」「扒鼓譜做影片」「drum cover 影片加譜」「像之前那樣做一支鼓譜影片」，或貼一個 YouTube 網址要做鼓譜時使用。
---

# 鼓譜影片流水線

成品樣式：1920x1080，上方影片（裁切成 1920x800），下方 280px 白底鼓譜條，一次顯示 4 小節，
藍色游標跳到目前擊打的音符，整行打完換下一行。記譜採日系鼓譜慣例：雙聲部（手朝上、大鼓朝下）、
Crash 用 ⊗ 加重音、三連音括號、與前一小節相同用 %、連續 4 個以上空小節合併成多小節休止。

## 程式位置

- `tools/drumcover.py`：CLI，子指令 `download / analyze / score / render / all`
- `tools/notation.py`：鼓譜排版器（PIL 手繪）
- `tools/evaluate.py`、`tools/gt_tools.py`：驗證用（見 drum-score-validate skill）
- 中間檔與成品都在 `projects/<name>/`；一律用專案 venv：`.venv/Scripts/python.exe`

## 步驟

1. **一開始就用 `AskUserQuestion` 一次問完**（讓使用者用選項選，不要用文字問）：
   - 下載確認：問題裡寫出影片標題、來源、預估大小（先用 `yt_dlp --no-download --print` 查）。
     有版權的官方影片要提醒僅供自用練習。選項：「開始下載」／「先不要」。
   - 反覆記號：選項「用 % 反覆記號（Recommended）」（版面精簡）／
     「每小節都寫出來（--no-simile）」（照著打比較好讀）。
   後面第 5、6 步的 render 都要照這個選擇加不加 `--no-simile`。
2. 下載＋抽音訊：`... tools/drumcover.py download <name> --url "<url>"`
   本地影片：直接放成 `projects/<name>/video.mp4`。
3. 分析：`... analyze <name>`
   - Demucs htdemucs_ft 分離鼓聲 → `drums.wav`
   - ADTOF 逐幀機率分別跑鼓聲音軌與完整混音 → `act_drums.npy`、`act_mix.npy`
   - beat_this 拍點/小節線 → `beats.json`
   已存在的中間檔會跳過；要重做某一步就刪掉對應檔。
4. 量化成譜：`... score <name>` → `score.json` 與整份譜 `score_preview.png`。
   **先看 score_preview.png**（裁幾段用 Read 看）。
5. 先出 20 秒試片確認同步與版面：`... render <name> --start 30 --dur 20`，抽幾張畫面確認。
6. 輸出整首：`... render <name>` → `projects/<name>/out.mp4`

## render 常用參數

- `--crop-y 0.5`：上方影片的垂直裁切位置（0 保留頂部、1 保留底部）。
  **原影片底部若已有字幕/譜，用 `--crop-y 0`。**
- `--no-simile`：不用 % 反覆記號，每小節都寫出來（照著打時比較好讀）
- `--lead 0.0`：游標提早量（秒）；`--codec libx264`：沒有 NVIDIA GPU 時

## 扒譜演算法重點（score 步驟，都在 drumcover.py）

- `repair_beats()`：beat_this 常在半速/倍速段出錯（例如只有第 1、3 拍打 crash 的段落），
  以全曲主要拍距修補：拍距≈2T 補中間拍、<0.65T 丟掉；再局部線性回歸平滑。
- `downbeat_phase()`：小節起點用滑動多數決，避免單一小節亂跳。
- `grid_offset()`：ADTOF 擊打點比 beat_this 格線系統性早 ~11ms，量化前先修正。
- `HYBRID_SOURCE`：hi-hat 用完整混音的機率（分離會弄弱輕的 hi-hat），其他用鼓聲音軌。
- `OFFBEAT16_PENALTY` + 不衝突才吸附：8 分反拍常拖拍 30~60ms，量化時優先記成 8 分音符，
  但該 8 分格已有同樂器時（真的 16 分音符節奏）不吸附。
- `triplet_beats()`：拍內非 hi-hat 的音明確落在 1/3、2/3 才判為三連音拍（tick：每拍 12）。
- `fill_from_context()`：hi-hat 被 crash 餘音或大鼓蓋住時，前後 4 小節有 ≥3 小節同位置有 hi-hat，
  且本小節是 8 分律動或緊接 crash，才用低門檻補回。
- `detect_cross_stick()` + `tidy()`：鼓身低頻比例 <0.075 且頻譜峰 >600Hz 的「小鼓」判為 cross-stick（▲）；
  同小節 cross-stick 佔多數時其餘小鼓也改成 cross-stick。
- `split_toms()`：tom 依擊打瞬間低頻主頻率分 TH/TM/TF；cymbal 同小節 ≥4 次判 ride，否則 crash。

## 已知限制

- Hi-hat 開/閉、重音（crash 以外）目前偵測不到。
- 樂譜常省略的輕音（ghost note）與伴奏音軌裡的 hi-hat 會被抓到（「多抓」的主要來源）。
- 驗證成績（KICK BACK，162 小節）：整體 F1 95.6%、完全正確小節 54.9%；大鼓 97.9%、小鼓 96.5%、hi-hat 94.4%。

## 環境（新機器才需要）

```
python -m venv .venv
.venv/Scripts/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
.venv/Scripts/pip install yt-dlp imageio-ffmpeg demucs soundfile librosa pillow numpy scipy mido pretty_midi rotary-embedding-torch beat-this
git clone https://github.com/xavriley/ADTOF-pytorch.git third_party/ADTOF-pytorch
.venv/Scripts/pip install -e third_party/ADTOF-pytorch
```

beat_this 的權重伺服器（cloud.cp.jku.at）在 Python certifi 下會報憑證過期，但 Windows 系統憑證庫驗證正常。
解法：用 curl 下載到 torch 快取（不要關閉 SSL 驗證）：
`curl -sSfL -o ~/.cache/torch/hub/checkpoints/beat_this-final0.ckpt https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt`
