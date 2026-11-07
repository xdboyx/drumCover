# drumCover

把歌曲影片自動扒成鼓譜，合成「上方影片＋下方鼓譜＋藍色游標跟著目前該打的音符」的練習影片。

## 結構

- `tools/drumcover.py`：主流程 CLI（`download / analyze / score / render / all`）
- `tools/notation.py`：鼓譜排版器（PIL 手繪，雙聲部日系鼓譜慣例）
- `tools/evaluate.py`、`tools/gt_tools.py`：拿附有鼓譜的影片驗證扒譜準確度
- `tools/editor/`：本機網頁操作介面（扒譜、預覽、編輯版本、輸出；第一版已實作，規劃脈絡見 `docs/future-ideas.md` 第 1 節）
  - `server.py`：HTTP 伺服器（只接受本機 Host／Origin）、專案與版本 API
  - `jobs.py`：長時間工作執行器（同時只跑一個、可從失敗步驟重試）；`pipeline.py`：扒譜流程（呼叫 drumcover.py 子行程）
  - `render_job.py`：輸出練習影片；`sheet_export.py`：輸出鼓譜圖檔（PDF／PNG）
  - `home.html`：首頁（專案清單、新增專案）；`index.html`：編輯畫面
- `tests/`：編輯器的 HTTP 測試（`.venv/Scripts/python.exe -m pytest tests`），以子行程啟動伺服器，扒譜流程用假的 pipeline 取代
- `啟動操作介面.bat`：雙擊啟動編輯器伺服器並開瀏覽器
- `projects/<name>/`：每首歌的中間檔與成品（video.mp4、score.json、out.mp4…）
- `third_party/ADTOF-pytorch/`：扒鼓模型
- 一律使用專案 venv：`.venv/Scripts/python.exe`

## Skills（`.claude/skills/`）

- `drum-score-video`：做鼓譜影片的完整流程與演算法重點
- `drum-score-validate`：用附譜影片驗證、找落差原因、修正的流程

## 未來想法

擱置中或還沒做的想法，以及已經規劃好的做法，都記在 **[docs/future-ideas.md](docs/future-ideas.md)**。
- 開始新功能前先看這份文件，可能已經有規劃
- 使用者說「先擱置」「之後再做」的想法，要把想法和已規劃的做法寫進這份文件，之後不用重新想

## Agent skills

### Issue tracker

Issues 放在 GitHub Issues（`xdboyx/drumCover`，用 `gh` CLI）。See `docs/agents/issue-tracker.md`.

### Triage labels

使用預設五個標籤（`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`）。See `docs/agents/triage-labels.md`.

### Domain docs

single-context（根目錄 `GLOSSARY.md` + `docs/adr/`）。See `docs/agents/domain.md`.
