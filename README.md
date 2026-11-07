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

## 用 Claude Code skill 使用（推薦）

這個專案的主要用法，是在 [Claude Code](https://claude.com/claude-code) 裡開啟專案資料夾，直接叫 skill 幫你跑完整流程，不用自己記指令。

1. 照上面「安裝」完成 clone 與環境建置（環境不確定時，也可以直接對 Claude 說「幫我照 README 安裝環境」）。
2. 用 Claude Code 開啟 `drumCover` 資料夾。`.claude/skills/` 底下的 skill 會自動載入。
3. 直接用口語說，或輸入 `/skill 名稱` 呼叫。

| Skill | 用途 | 怎麼叫 |
| --- | --- | --- |
| `drum-score-video` | 把歌曲影片做成鼓譜練習影片 | `/drum-score-video`，或說「幫這首歌做鼓譜影片」，直接貼 YouTube 網址也可以 |
| `drum-score-validate` | 拿附有鼓譜的影片驗證扒譜準確度、找出落差原因 | `/drum-score-validate`，或說「拿這支有譜的影片驗證」「這段過門扒得不準，幫我找原因」 |

### 範例

```text
幫這首歌做鼓譜影片 https://www.youtube.com/watch?v=XXXX
```

`drum-score-video` 會依序：
1. 先問你要不要下載（會列出影片標題與大小），以及要不要用 `%` 反覆記號。
2. 下載、分離鼓聲、辨識、量化成譜，並先檢查 `score_preview.png`。
3. 先輸出 20 秒試片確認同步與版面，沒問題再輸出整首。

成品在 `projects/<名稱>/out.mp4`。

已有本地影片的話，放成 `projects/<名稱>/video.mp4`，再對 Claude 說「用這支影片做鼓譜影片」即可。

## 手動用法（不透過 skill）

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

## 授權與致謝

- 扒鼓模型使用 [ADTOF](https://github.com/MZehren/ADTOF)（Zehren、Alunno、Bientinesi 等人），其內容採用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)（需署名、**禁止商業使用**、衍生作品須以相同方式授權）。
- PyTorch 移植版為 [xavriley/ADTOF-pytorch](https://github.com/xavriley/ADTOF-pytorch)，以 git submodule 引入，本 repo 不包含它的程式碼與權重。該 repo 目前沒有明確的 LICENSE，其模型權重轉換自上述 ADTOF，請比照 ADTOF 的授權條件使用。
- 因此，**本工具僅限個人學習、練習等非商業用途**。若要商業使用，請先向原作者確認授權。
- 另外使用 [Demucs](https://github.com/facebookresearch/demucs)、[beat_this](https://github.com/CPJKU/beat_this)、[yt-dlp](https://github.com/yt-dlp/yt-dlp) 等開源套件，各自依其授權。
