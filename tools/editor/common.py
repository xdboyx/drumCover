"""編輯器各模組共用的東西：HTTP 錯誤、設定、長時間工作執行器、扒譜流程。"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import pipeline as real_pipeline   # noqa: E402
from jobs import JobRunner         # noqa: E402


class HttpError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


class Settings:
    """啟動時由命令列參數設定；各模組一律讀屬性，不要複製值。"""
    projects_root = ROOT / "projects"   # --projects-root
    web_dist = HERE / "web" / "dist"    # --web-dist（React build 產物）


settings = Settings()
runner = JobRunner()   # 整個伺服器唯一的長時間工作執行器


def pipeline():
    """扒譜流程：預設是真的 drumcover；環境變數 DRUMCOVER_PIPELINE 可指到另一個 .py（測試用假流程）。"""
    path = os.environ.get("DRUMCOVER_PIPELINE")
    if not path:
        return real_pipeline
    spec = importlib.util.spec_from_file_location("drumcover_fake_pipeline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
