# drumCover

把歌曲影片自動扒成鼓譜，合成「上方影片＋下方鼓譜＋藍色游標跟著目前該打的音符」的練習影片。

## 流程

1. 下載影片、抽出音訊（yt-dlp）
2. Demucs 分離鼓聲，ADTOF 辨識每個鼓件的擊打時間，beat_this 偵測拍點與小節線
3. 量化成譜，輸出日系雙聲部鼓譜（手朝上、大鼓朝下）
4. 把譜與影片合成一支練習影片

## 安裝

需要 Python 3.10 以上。建議有 NVIDIA 顯卡（分離與輸出影片都會快很多）。

```bash
git clone --recurse-submodules https://github.com/xdboyx/drumCover.git
cd drumCover
```

如果 clone 時忘了加 `--recurse-submodules`，補抓：

```bash
git submodule update --init --recursive
```

建立虛擬環境並安裝套件（Windows）：

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install -e third_party/ADTOF-pytorch
.venv/Scripts/python.exe -m pip install git+https://github.com/CPJKU/beat_this.git
```

沒有 NVIDIA 顯卡時，torch 改裝 CPU 版，輸出影片時加 `--codec libx264`。

## 基本用法

所有指令都用專案 venv 執行，格式是 `drumcover.py <指令> <專案名稱> [選項]`，中間檔與成品都放在 `projects/<專案名稱>/`。

一次跑完整流程：

```bash
.venv/Scripts/python.exe tools/drumcover.py all mysong --url "https://www.youtube.com/watch?v=XXXX"
```

也可以分步驟：

```bash
.venv/Scripts/python.exe tools/drumcover.py download mysong --url "<網址>"
.venv/Scripts/python.exe tools/drumcover.py analyze mysong
.venv/Scripts/python.exe tools/drumcover.py score mysong
.venv/Scripts/python.exe tools/drumcover.py render mysong
```

已有本地影片時，直接放成 `projects/mysong/video.mp4`，從 `analyze` 開始。

先輸出 20 秒試片確認同步與版面：

```bash
.venv/Scripts/python.exe tools/drumcover.py render mysong --start 30 --dur 20
```

### 常用選項

| 選項 | 說明 |
| --- | --- |
| `--start` / `--dur` | 只輸出某一段（秒） |
| `--lead` | 游標提早量（秒） |
| `--crop-y` | 影片上下裁切位置，0 保留頂部、1 保留底部 |
| `--strip-h` | 鼓譜條高度（預設 280） |
| `--no-simile` | 不用 `%` 反覆記號，每小節都寫出來 |
| `--source` | ADTOF 機率來源：`drums` / `mix` / `max` / `hybrid`（預設） |
| `--codec` | 影片編碼器，預設 `h264_nvenc`，無 NVIDIA 顯卡用 `libx264` |

## 專案結構

- `tools/drumcover.py`：主流程 CLI
- `tools/notation.py`：鼓譜排版器
- `tools/evaluate.py`、`tools/gt_tools.py`：拿附有鼓譜的影片驗證準確度
- `tools/editor/`：逐小節編輯器（草稿，未測試）
- `projects/`：每首歌的 `score.json`、`beats.json`（影片、音訊等大檔不納入版控）
- `third_party/ADTOF-pytorch`：扒鼓模型（git submodule）
- `.claude/skills/`：給 Claude Code 用的流程說明
- `docs/future-ideas.md`：未來想法

## 注意

- 下載的影片多半有版權，產出的練習影片僅供個人練習，請勿公開散布。
- 自動扒譜不是 100% 準確，輸出前建議先看 `score_preview.png`。
