"""Windows 檔名規則：專案名稱檢查、版本名稱 -> 輸出檔名、檔名撞名判斷共用同一份定義。"""
import re

ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')   # Windows 檔名不允許的字元
RESERVED_RE = re.compile(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$")   # 保留字（含 CON.txt 這種帶副檔名的）


def is_reserved(name):
    return bool(RESERVED_RE.match(name.strip()))


def safe_filename(name):
    """名稱 -> Windows 可用的檔名（不含副檔名）：非法字元換底線、去尾端空白與點、保留字前面補底線。"""
    s = ILLEGAL_CHARS.sub("_", name).strip().rstrip(". ") or "_"
    return "_" + s if is_reserved(s) else s


def filename_key(name):
    """判斷兩個名稱會不會輸出成同一個檔案（Windows 檔名不分大小寫）。"""
    return safe_filename(name).casefold()
