"""長時間工作執行器：整個伺服器只有一個，同時只跑一個工作。

工作 = 種類 + 專案 + 一串步驟 [(步驟名稱, fn(report))]。fn 用 report(0~1) 回報目前步驟的進度，
丟出例外代表失敗。狀態存在這個物件裡，跟瀏覽器分頁無關。

給之後的工作種類重用（新增專案扒譜、重新扒譜、失敗重試）：
- submit(..., start_at=i) 從第 i 步開始跑，失敗時 status()["failed_step"] 就是要重試的起點
- 步驟自己負責把中間檔寫在專案資料夾，重試時前面的步驟直接略過
"""
import threading


class Busy(Exception):
    def __init__(self, status):
        super().__init__("忙碌中：目前有工作正在執行，請等它結束再送出")
        self.status = status


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._job = None

    def status(self):
        with self._lock:
            if self._job is None:
                return {"state": "idle"}
            return {k: v for k, v in self._job.items() if not k.startswith("_")}

    def submit(self, kind, project, steps, start_at=0, output=None):
        with self._lock:
            if self._job is not None and self._job["state"] == "running":
                raise Busy({k: v for k, v in self._job.items() if not k.startswith("_")})
            self._job = {"state": "running", "kind": kind, "project": project, "step": None,
                         "step_index": start_at, "steps": [n for n, _ in steps], "progress": 0.0,
                         "error": None, "failed_step": None, "output": output}
        threading.Thread(target=self._run, args=(steps, start_at), daemon=True).start()

    def _set(self, **kw):
        with self._lock:
            self._job.update(kw)

    def _run(self, steps, start_at):
        i = start_at
        try:
            for i in range(start_at, len(steps)):
                name, fn = steps[i]
                self._set(step=name, step_index=i, progress=0.0)
                fn(lambda p: self._set(progress=round(float(p), 4)))
            self._set(state="done", step=None, progress=1.0)
        except Exception as e:   # noqa: BLE001 工作失敗一律記錄錯誤訊息
            self._set(state="error", error=str(e) or type(e).__name__, failed_step=i)
