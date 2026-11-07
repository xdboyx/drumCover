"""鼓譜排版：把小節畫成一行一行的 PNG，並回傳每個音符事件的 x 座標供游標使用。

記譜慣例（對照一般日系鼓譜）：
- 雙聲部：手（hi-hat / 小鼓 / tom / 銅鈸）符桿朝上，腳（大鼓 / hi-hat 踏）符桿朝下，各自有休止符
- 時間位置用 tick（每拍 12）：16 分音符 = 3 tick、8 分三連音 = 4 tick
- staff step：五線譜最上面那條線為 0，往下每半格 +1（線 = 偶數、間 = 奇數）
"""
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont

TICKS = 12

# 樂器 -> (staff step, 符頭種類, 聲部)
INSTRUMENTS = {
    "CR": (-1, "ox", "up"),    # Crash ⊗
    "HH": (-1, "x", "up"),     # Hi-hat 閉
    "HO": (-1, "xo", "up"),    # Hi-hat 開（上方加 o）
    "HHO": (-1, "xo", "up"),
    "RD": (0, "x", "up"),      # Ride
    "TH": (1, "fill", "up"),   # High tom
    "TM": (2, "fill", "up"),   # Mid tom
    "SD": (3, "fill", "up"),   # Snare
    "XS": (3, "tri", "up"),    # Cross-stick ▲
    "TF": (5, "fill", "up"),   # Floor tom
    "BD": (7, "fill", "down"),  # Bass drum
    "HF": (9, "x", "down"),    # Hi-hat 踏
}
ACCENTED = {"CR"}               # 一律加重音記號的樂器

TEXT_FONT = r"C:\Windows\Fonts\arial.ttf"
SERIF_BOLD = r"C:\Windows\Fonts\timesbd.ttf"
SERIF_ITALIC = r"C:\Windows\Fonts\timesi.ttf"
SYMBOL_FONT = r"C:\Windows\Fonts\seguisym.ttf"
BLACK = (0, 0, 0)


@dataclass
class Layout:
    width: int = 1920
    height: int = 280
    sp: int = 20                 # 線距
    margin_l: int = 40
    margin_r: int = 40
    clef_w: int = 60
    header_w: int = 60           # 第一行的拍號寬度
    bar_pad_l: int = 34
    bar_pad_r: int = 30
    bars_per_line: int = 4
    staff_top: int = 0

    def __post_init__(self):
        self.staff_top = int(self.height * 0.40)

    def y(self, step):
        return self.staff_top + step * self.sp / 2


def voice_of(name):
    return INSTRUMENTS[name][2]


def beat_items(positions, unit, per_beat):
    """一拍內某聲部的音符/休止符序列。positions: 拍內位置（tick），unit: 3（16 分）或 4（三連音）。
    回傳 [(pos, dur_units, is_note)]，dur_units 以 unit 為單位。"""
    occ = sorted(positions)
    n = per_beat // unit
    items = []
    if not occ:
        return [(0, n, False)]
    if occ[0] > 0:
        items.append((0, occ[0] // unit, False))
    for i, p in enumerate(occ):
        nxt = occ[i + 1] if i + 1 < len(occ) else per_beat
        dur = (nxt - p) // unit
        if unit == 4 and dur == 2 and i + 1 < len(occ):
            # 三連音裡佔兩格的音照慣例寫成「8 分音符 + 8 分休止符」
            items += [(p, 1, True), (p + unit, 1, False)]
        else:
            items.append((p, dur, True))
    return items


class LineRenderer:
    def __init__(self, layout: Layout = None):
        self.L = layout or Layout()
        sp = self.L.sp
        self.f_num = ImageFont.truetype(TEXT_FONT, int(sp * 0.9))
        self.f_tsig = ImageFont.truetype(SERIF_BOLD, int(sp * 2.3))
        self.f_tempo = ImageFont.truetype(SERIF_BOLD, int(sp * 1.25))
        self.f_tri = ImageFont.truetype(SERIF_ITALIC, int(sp * 1.0))
        self.f_multi = ImageFont.truetype(SERIF_BOLD, int(sp * 1.6))
        self.f_note = ImageFont.truetype(SYMBOL_FONT, int(sp * 1.6))

    # ------------------------------------------------------------ 基本元件
    def _staff(self, d, x0, x1):
        for k in range(5):
            y = self.L.y(2 * k)
            d.line([(x0, y), (x1, y)], fill=BLACK, width=2)

    def _barline(self, d, x, final=False):
        y0, y1 = self.L.y(0), self.L.y(8)
        if final:
            d.line([(x - 9, y0), (x - 9, y1)], fill=BLACK, width=2)
            d.rectangle([x - 4, y0, x + 1, y1], fill=BLACK)
        else:
            d.line([(x, y0), (x, y1)], fill=BLACK, width=2)

    def _clef(self, d, x):
        y0, y1 = self.L.y(2), self.L.y(6)
        w = self.L.sp * 0.32
        d.rectangle([x, y0, x + w, y1], fill=BLACK)
        d.rectangle([x + w * 2.2, y0, x + w * 3.2, y1], fill=BLACK)

    def _notehead(self, d, x, step, kind):
        sp = self.L.sp
        y = self.L.y(step)
        if step <= -2 or step >= 10:   # 加線
            for s in (range(-2, step - 1, -2) if step < 0 else range(10, step + 1, 2)):
                d.line([(x - sp * 0.95, self.L.y(s)), (x + sp * 0.95, self.L.y(s))], fill=BLACK, width=2)
        if kind == "fill":
            w, h = sp * 0.66, sp * 0.47
            d.ellipse([x - w, y - h, x + w, y + h], fill=BLACK)
        elif kind == "tri":
            r = sp * 0.6
            d.polygon([(x - r, y + r * 0.55), (x + r, y + r * 0.55), (x, y - r * 0.75)], fill=BLACK)
        elif kind == "ox":
            r = sp * 0.55
            d.ellipse([x - r, y - r, x + r, y + r], outline=BLACK, width=2)
            q = r * 0.7
            d.line([(x - q, y - q), (x + q, y + q)], fill=BLACK, width=2)
            d.line([(x - q, y + q), (x + q, y - q)], fill=BLACK, width=2)
        else:
            r = sp * 0.42
            d.line([(x - r, y - r), (x + r, y + r)], fill=BLACK, width=3)
            d.line([(x - r, y + r), (x + r, y - r)], fill=BLACK, width=3)

    def _dot(self, d, x, step):
        y = self.L.y(step if step % 2 else step - 1)
        r = self.L.sp * 0.16
        d.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)

    def _rest(self, d, x, units, unit, voice):
        """units * unit = 長度（tick）。上聲部休止符放高一點、下聲部放低一點。"""
        sp, L = self.L.sp, self.L
        ticks = units * unit
        dy = -sp * 1.0 if voice == "up" else sp * 1.1
        k = 0.62                         # 休止符縮小比例（以第 2 間為中心）
        y = lambda s: L.y(4 + (s - 4) * k) + dy
        if ticks >= TICKS * 4:          # 全休止符
            d.rectangle([x - sp * 0.65, L.y(2), x + sp * 0.65, L.y(2) + sp * 0.5], fill=BLACK)
        elif ticks >= TICKS * 2:        # 二分休止符
            yy = L.y(4) + (dy if voice == "down" else -sp * 0.2)
            d.rectangle([x - sp * 0.65, yy - sp * 0.5, x + sp * 0.65, yy], fill=BLACK)
        elif ticks >= TICKS:            # 四分休止符
            pts = [(x - sp * 0.1, y(1.4)), (x + sp * 0.3, y(2.9)), (x - sp * 0.12, y(4.3)), (x + sp * 0.28, y(5.6))]
            d.line(pts, fill=BLACK, width=int(sp * 0.24), joint="curve")
            d.arc([x - sp * 0.4, y(5.2), x + sp * 0.25, y(6.6)], 110, 300, fill=BLACK, width=int(sp * 0.17))
        else:                           # 八分 / 十六分休止符
            n = 2 if ticks <= 3 else 1
            top = y(3)
            d.line([(x + sp * 0.4, top), (x - sp * 0.1, y(6 if n == 1 else 7))], fill=BLACK, width=3)
            for k in range(n):
                cx = x - sp * 0.35 - k * sp * 0.2
                cy = top + k * sp
                r = sp * 0.22
                d.ellipse([cx - r, cy - r + sp * 0.1, cx + r, cy + r + sp * 0.1], fill=BLACK)
                d.line([(cx, cy + sp * 0.3), (x + sp * 0.4 - k * sp * 0.2, cy)], fill=BLACK, width=3)
            if ticks == 9:               # 附點八分休止符
                self._dot(d, x + sp * 0.85, 3 if voice == "up" else 7)

    def _flag(self, d, sx, tip, k, up):
        sp = self.L.sp
        s = 1 if up else -1
        fy = tip + s * k * sp * 0.75
        pts = [(sx, fy), (sx + sp * 0.35, fy + s * sp * 0.55), (sx + sp * 0.85, fy + s * sp * 1.0),
               (sx + sp * 0.8, fy + s * sp * 1.8)]
        d.line(pts, fill=BLACK, width=int(sp * 0.22), joint="curve")

    # ------------------------------------------------------------ 一行
    def render_line(self, measures, show_header=False, is_last_line=False, tempo=None):
        """measures: list of dict
             {"kind": "bar", "no": 小節號, "ticks": 48, "events": [{tick, notes, idx}]}
             {"kind": "repeat", "no", "ticks", "events"}   與前一小節相同（畫 %，游標照比例移動）
             {"kind": "multirest", "no", "count"}          連續休止小節
        回傳 (PIL.Image, {event_idx: x})"""
        L = self.L
        img = Image.new("RGB", (L.width, L.height), (255, 255, 255))
        d = ImageDraw.Draw(img)
        x0, x1 = L.margin_l, L.width - L.margin_r
        self._staff(d, x0, x1)
        x = x0 + 8
        self._clef(d, x)
        x += L.clef_w
        if show_header:
            for yy in (L.y(2), L.y(6)):
                d.text((x + L.header_w * 0.35, yy), "4", font=self.f_tsig, fill=BLACK, anchor="mm")
            x += L.header_w
            if tempo:
                d.text((x0, L.y(-9.5)), "\u2669", font=self.f_note, fill=BLACK, anchor="ls")
                d.text((x0 + L.sp * 1.1, L.y(-9.5)), f"= {tempo}", font=self.f_tempo, fill=BLACK, anchor="ls")
        if measures:
            d.text((x0, L.y(-5.2)), str(measures[0]["no"]), font=self.f_num, fill=BLACK, anchor="ls")

        n = L.bars_per_line
        bar_w = (x1 - x) / n
        xs = {}
        for bi in range(n):
            bx0 = x + bi * bar_w
            if bi < len(measures):
                m = measures[bi]
                if m["kind"] == "bar":
                    xs.update(self._render_bar(d, m, bx0, bar_w))
                elif m["kind"] == "repeat":
                    self._repeat_sign(d, bx0 + bar_w / 2)
                    xs.update({e["idx"]: self.tick_x(bx0, bar_w, e["tick"], m["ticks"]) for e in m["events"]})
                else:
                    self._multirest(d, bx0, bar_w, m["count"])
            self._barline(d, bx0 + bar_w, final=is_last_line and bi == n - 1)
        return img, xs

    def _repeat_sign(self, d, cx):
        sp, L = self.L.sp, self.L
        cy = L.y(4)
        d.polygon([(cx - sp * 0.9, cy + sp * 0.9), (cx - sp * 0.45, cy + sp * 0.9),
                   (cx + sp * 0.9, cy - sp * 0.9), (cx + sp * 0.45, cy - sp * 0.9)], fill=BLACK)
        r = sp * 0.17
        for dx, dy in ((-0.6, -0.45), (0.6, 0.45)):
            d.ellipse([cx + dx * sp - r, cy + dy * sp - r, cx + dx * sp + r, cy + dy * sp + r], fill=BLACK)

    def _multirest(self, d, bx0, bar_w, count):
        sp, L = self.L.sp, self.L
        a, b = bx0 + sp * 1.2, bx0 + bar_w - sp * 1.2
        d.rectangle([a, L.y(3), b, L.y(5)], fill=BLACK)
        d.line([(a, L.y(2)), (a, L.y(6))], fill=BLACK, width=2)
        d.line([(b, L.y(2)), (b, L.y(6))], fill=BLACK, width=2)
        d.text(((a + b) / 2, L.y(-1.5)), str(count), font=self.f_multi, fill=BLACK, anchor="ms")

    def tick_x(self, bx0, bar_w, tick, ticks):
        L = self.L
        inner = bar_w - L.bar_pad_l - L.bar_pad_r
        return bx0 + L.bar_pad_l + inner * tick / ticks

    # ------------------------------------------------------------ 一小節
    def _render_bar(self, d, bar, bx0, bar_w):
        ticks = bar["ticks"]
        n_beats = ticks // TICKS
        voices = {"up": {}, "down": {}}
        for e in bar["events"]:
            for nm in e["notes"]:
                voices[voice_of(nm)].setdefault(e["tick"], {"notes": [], "idx": e["idx"]})["notes"].append(nm)
        xs = {e["idx"]: self.tick_x(bx0, bar_w, e["tick"], ticks) for e in bar["events"]}
        if not voices["up"] and not voices["down"]:
            self._rest(d, bx0 + bar_w / 2, 4, TICKS, "up")
            return xs
        for v, evs in voices.items():
            if not evs:
                continue            # 整小節沒有這個聲部就不畫（影片譜的慣例）
            b = 0
            while b < n_beats:
                local = {t - b * TICKS: ev for t, ev in evs.items() if b * TICKS <= t < (b + 1) * TICKS}
                # 連續兩拍空白（第 1-2 或 3-4 拍）合併成二分休止符
                if not local and b % 2 == 0 and b + 1 < n_beats and \
                        not any((b + 1) * TICKS <= t < (b + 2) * TICKS for t in evs):
                    self._rest(d, self.tick_x(bx0, bar_w, b * TICKS + TICKS // 2, ticks), 2, TICKS, v)
                    b += 2
                    continue
                self._render_beat(d, local, b, v, bx0, bar_w, ticks)
                b += 1
        return xs

    def _render_beat(self, d, local, b, voice, bx0, bar_w, ticks):
        L, sp = self.L, self.L.sp
        up = voice == "up"
        unit = 4 if any(t % 3 for t in local) else 3
        items = beat_items(list(local), unit, TICKS)
        stems = []
        for pos, units, is_note in items:
            x = self.tick_x(bx0, bar_w, b * TICKS + pos, ticks)
            if not is_note:
                self._rest(d, x, units, unit, voice)
                continue
            names = sorted(local[pos]["notes"], key=lambda n: INSTRUMENTS[n][0])
            steps = [INSTRUMENTS[n][0] for n in names]
            prev = None
            for nm in names:
                st, kind, _ = INSTRUMENTS[nm]
                dx = sp * 1.25 if (prev is not None and st - prev == 1) else 0
                self._notehead(d, x + dx, st, kind)
                if kind == "xo":
                    yo = L.y(-4.6)
                    r = sp * 0.3
                    d.ellipse([x - r, yo - r, x + r, yo + r], outline=BLACK, width=2)
                prev = st if dx == 0 else None
            if any(n in ACCENTED for n in names):
                ya = L.y(steps[0]) - sp * 3.2 - sp * 0.9
                d.line([(x - sp * 0.55, ya - sp * 0.35), (x + sp * 0.45, ya), (x - sp * 0.55, ya + sp * 0.35)],
                       fill=BLACK, width=2)
            if unit == 3 and units == 3:          # 附點八分
                self._dot(d, x + sp * 1.2, steps[-1] if up else steps[0])
            stems.append((x, L.y(steps[0]), L.y(steps[-1]), units))

        if not stems:
            return
        full = TICKS // unit                     # 一整拍的長度（units）
        beamed = [s for s in stems if s[3] < full]
        sdx = sp * 0.6 if up else -sp * 0.6
        length = sp * 3.2
        if len(beamed) >= 2:
            beam_y = (min(s[1] for s in beamed) - length) if up else (max(s[2] for s in beamed) + length)
        for x, y_hi, y_lo, units in stems:
            sx = x + sdx
            start = y_lo if up else y_hi
            if units >= full or len(beamed) < 2:
                tip = (y_hi - length) if up else (y_lo + length)
            else:
                tip = beam_y
            d.line([(sx, start), (sx, tip)], fill=BLACK, width=2)
            if units < full and len(beamed) < 2 and not (unit == 4 and units == 2):   # 單獨的八分/十六分 -> 旗子
                for k in range(2 if (unit == 3 and units == 1) else 1):
                    self._flag(d, sx, tip, k, up)

        if len(beamed) >= 2:
            th = int(sp * 0.42)
            s = 1 if up else -1
            xb = [bm[0] + sdx for bm in beamed]
            y0 = beam_y if up else beam_y - th
            d.rectangle([xb[0], y0, xb[-1], y0 + th], fill=BLACK)
            if unit == 3:   # 第二條符槓（十六分音符）
                y2 = y0 + s * sp * 0.72
                for i, bm in enumerate(beamed):
                    if bm[3] != 1 or (i > 0 and beamed[i - 1][3] == 1):
                        continue
                    if i + 1 < len(beamed) and beamed[i + 1][3] == 1:
                        j = i
                        while j + 1 < len(beamed) and beamed[j + 1][3] == 1:
                            j += 1
                        a, bb = xb[i], xb[j]
                    elif i + 1 < len(beamed):
                        a, bb = xb[i], xb[i] + sp * 0.9
                    else:
                        a, bb = xb[i] - sp * 0.9, xb[i]
                    d.rectangle([a, y2, bb, y2 + th], fill=BLACK)
        if unit == 4:        # 三連音記號
            x_first = self.tick_x(bx0, bar_w, b * TICKS, ticks) + sdx
            x_last = self.tick_x(bx0, bar_w, b * TICKS + 8, ticks) + sdx
            if up:
                yb = min(s[1] for s in stems) - length - sp * 0.9
            else:
                yb = max(s[2] for s in stems) + length + sp * 0.9
            hook = sp * 0.35 if up else -sp * 0.35
            d.line([(x_first, yb + hook), (x_first, yb), (x_last, yb), (x_last, yb + hook)], fill=BLACK, width=1)
            cx = (x_first + x_last) / 2
            d.rectangle([cx - sp * 0.4, yb - sp * 0.5, cx + sp * 0.4, yb + sp * 0.5], fill=(255, 255, 255))
            d.text((cx, yb), "3", font=self.f_tri, fill=BLACK, anchor="mm")


def render_cursor(strip, x, color=(110, 185, 255), layout=None):
    """在 numpy 陣列 (H,W,3) 上就地畫游標（色彩相乘：白底變藍、黑色音符維持黑）。"""
    L = layout or Layout()
    w = int(L.sp * 1.6)
    x0 = max(0, int(x - w / 2 + L.sp * 0.15))
    x1 = min(strip.shape[1], x0 + w)
    y0 = int(L.y(-7.5))
    y1 = int(L.y(13))
    region = strip[y0:y1, x0:x1].astype("uint16")
    for c in range(3):
        region[..., c] = region[..., c] * color[c] // 255
    strip[y0:y1, x0:x1] = region.astype("uint8")


# ---------------------------------------------------------------- 整頁排版（A4 直式，供 PDF / PNG 輸出）
A4_PX = (1240, 1754)             # A4 直式 150 dpi
CJK_FONTS = [r"C:\Windows\Fonts\msjh.ttc", r"C:\Windows\Fonts\msjhbd.ttc", r"C:\Windows\Fonts\mingliu.ttc",
             r"C:\Windows\Fonts\kaiu.ttf"]


def _cjk_font(size):
    for f in CJK_FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_sheet(measures, title, version_name, bpm, page_px=A4_PX, per_line=4):
    """把一整份鼓譜排成多頁 A4 直式。measures 同 render_line（每項 kind=bar/repeat/multirest）。
    每行 4 小節；第一頁上方有歌名、版本名稱與 BPM。回傳 PIL.Image 的 list（每頁一張）。"""
    pw, ph = page_px
    margin_top, margin_bottom = 100, 90
    line_h = 200
    lay = Layout(width=pw, height=line_h, sp=15, margin_l=60, margin_r=60, bars_per_line=per_line)
    r = LineRenderer(lay)
    lines = [measures[i:i + per_line] for i in range(0, len(measures), per_line)] or [[]]

    f_title, f_sub = _cjk_font(46), _cjk_font(26)
    title_h = 150
    pages, y, d, page = [], 0, None, None
    for li, ms in enumerate(lines):
        if page is None or y + line_h > ph - margin_bottom:
            page = Image.new("RGB", (pw, ph), (255, 255, 255))
            pages.append(page)
            d = ImageDraw.Draw(page)
            y = margin_top
            if len(pages) == 1:
                d.text((lay.margin_l, y), title, font=f_title, fill=BLACK)
                d.text((lay.margin_l, y + 66), f"{version_name}    BPM {int(round(bpm))}", font=f_sub, fill=BLACK)
                y += title_h
        img, _ = r.render_line(ms, show_header=li == 0, is_last_line=li == len(lines) - 1,
                               tempo=None)
        page.paste(img, (0, y))
        y += line_h
    return pages
