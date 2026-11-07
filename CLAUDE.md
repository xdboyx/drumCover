# drumCover

把歌曲影片自動扒成鼓譜，合成「上方影片＋下方鼓譜＋藍色游標跟著目前該打的音符」的練習影片。

## 結構

- `tools/drumcover.py`：主流程 CLI（`download / analyze / score / render / all`）
- `tools/notation.py`：鼓譜排版器（PIL 手繪，雙聲部日系鼓譜慣例）
- `tools/evaluate.py`、`tools/gt_tools.py`：拿附有鼓譜的影片驗證扒譜準確度
- `tools/editor/`：逐小節編輯器（**擱置中的草稿，未測試**，見 `docs/future-ideas.md`）
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
