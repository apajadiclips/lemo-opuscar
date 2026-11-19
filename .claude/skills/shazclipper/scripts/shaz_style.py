"""@shazclipper house style: normal 9:16 layout (facecam top, gameplay full to the bottom), plain subtitles,
important moments in Titan One light green. Only text has to sit in the safe zone; pictures run full frame.

Safe zone (TikTok / Reels / Shorts, 1080x1920): x 60-940, y 210-1470 (top bar, bottom caption/nav, right buttons)."""
import math, os, re
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
W, H = 1080, 1920
SAFE = (60, 210, 940, 1470)
SAFE_CX = (SAFE[0] + SAFE[2]) / 2                 # 500: text is centred in the safe column
CAM_H, DIV_H = 760, 76
DIV_Y = CAM_H; GAME_Y = CAM_H + DIV_H; GAME_H = H - GAME_Y
SUB_Y = GAME_Y + 120                              # plain subtitles: first line centre (inside the safe zone)
CHANNEL = "@shazclipper"
PLAIN = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"     # plain subtitles (OFL)
MOMENT = f"{SKILL}/fonts/TitanOne-Regular.ttf"                     # important moments (OFL, commercial use allowed)
WHT, BLK, RED, YEL = (255, 255, 255), (0, 0, 0), (235, 40, 40), (255, 214, 0)
MINT = (150, 255, 160)                            # "hijau cair": the moment colour
GREY = (225, 225, 230)
MAXW = 840

def clamp(x, a, b): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a), 0, 1)
def lerp(a, b, k): return a + (b - a) * k
def eo(k): return 1 - (1 - k) ** 3
def eio(k): return 4 * k ** 3 if k < .5 else 1 - (-2 * k + 2) ** 3 / 2
def back(k, s=2.2): return 1 + (s + 1) * (k - 1) ** 3 + s * (k - 1) ** 2

@lru_cache(maxsize=96)
def F(sz, path=PLAIN): return ImageFont.truetype(path, max(8, int(sz)))

# important words (both languages): drawn in Titan One mint, a little bigger, with a pop
MOMENT_WORDS = r"rampok|merompak|curi|mencuri|maling|kabur|angkut|cekik|mayat|bunuh|tumbang"
def is_moment(w): return bool(re.search(MOMENT_WORDS, re.sub(r"[^a-z]", "", w.lower())))
def clean(w): return re.sub(r"[.,]", "", w).upper()

def panel(img, box, w, h, sharp=1.6, sat=1.1):
    x0, y0, x1, y1 = box; bw, bh = x1 - x0, y1 - y0
    if bw / bh > w / h: nb = bh * w / h; x0 += (bw - nb) / 2; x1 = x0 + nb
    else: nb = bw * h / w; y0 += (bh - nb) / 2; y1 = y0 + nb
    im = img.crop((int(x0), int(y0), int(x1), int(y1))).resize((w, h), Image.LANCZOS)
    return ImageEnhance.Sharpness(ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.07)).enhance(sat)).enhance(sharp)

STREAMER = "Windah Basudara"                      # set per clip: S.STREAMER = spec["streamer"]

def compose(cam_img, game_img, channel_in_divider=True):
    im = Image.new("RGB", (W, H)); im.paste(cam_img, (0, 0)); im.paste(game_img, (0, GAME_Y))
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle((0, DIV_Y, W, GAME_Y), fill=(10, 10, 12)); d.rectangle((0, DIV_Y, W, DIV_Y + 6), fill=MINT)
    cy = DIV_Y + 41
    d.text((SAFE[0] + 10, cy), "▶", font=F(28), fill=RED, anchor="lm")
    d.text((SAFE[0] + 48, cy), STREAMER, font=F(32), fill=WHT, anchor="lm")
    if channel_in_divider:
        x1 = SAFE[2] - 10; tw = d.textlength(CHANNEL, font=F(34))
        d.text((x1, cy), CHANNEL, font=F(34), fill=WHT, anchor="rm")
        d.ellipse((x1 - tw - 58, cy - 22, x1 - tw - 14, cy + 22), fill=MINT); d.text((x1 - tw - 36, cy + 1), "S", font=F(28), fill=BLK, anchor="mm")
    return im

def channel_badge(im, y=SAFE[3] - 60):
    """The channel as a badge low in the frame, its bottom edge still inside the safe zone."""
    d = ImageDraw.Draw(im, "RGBA"); f = F(38); tw = d.textlength(CHANNEL, font=f); bw = tw + 96
    x0 = SAFE[0] + 10                       # bottom-left of the safe zone: clear of the subject in the middle
    d.rounded_rectangle((x0, y - 34, x0 + bw, y + 34), 34, fill=(0, 0, 0, 150))
    d.ellipse((x0 + 12, y - 24, x0 + 60, y + 24), fill=MINT); d.text((x0 + 36, y + 1), "S", font=F(30), fill=BLK, anchor="mm")
    d.text((x0 + 74, y + 1), CHANNEL, font=f, fill=WHT, anchor="lm")

def watermark(im):
    d = ImageDraw.Draw(im, "RGBA"); d.text((SAFE_CX, SAFE[3] - 28), CHANNEL, font=F(36), fill=(255, 255, 255, 95), anchor="mm")

def word_img(w, sz, col, path=PLAIN, scale=1.0, sw_k=.13, shadow=True):
    sw = max(2, int(sz * scale * sw_k)); f = F(sz * scale, path); bb = f.getbbox(w, stroke_width=sw)
    L = Image.new("RGBA", (bb[2] - bb[0] + 40, bb[3] - bb[1] + 46), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    if shadow: d.text((20 - bb[0] + 4, 20 - bb[1] + 7), w, font=f, fill=(0, 0, 0, 130), stroke_width=sw, stroke_fill=(0, 0, 0, 130))
    d.text((20 - bb[0], 20 - bb[1]), w, font=f, fill=col + (255,), stroke_width=sw, stroke_fill=(10, 10, 14, 255))
    return L

def _layout(words, sz, big):
    """Word widths (moment words in Titan One, bigger) and greedy lines within MAXW."""
    sp = F(sz).getlength(" ")
    ws = [F(sz * big, MOMENT).getlength(clean(w)) if is_moment(w) else F(sz).getlength(clean(w)) for w in words]
    lines, cur, cw = [], [], 0.0
    for i, w in enumerate(ws):
        add = w + (sp if cur else 0)
        if cur and cw + add > MAXW: lines.append(cur); cur, cw = [i], w
        else: cur.append(i); cw += add
    lines.append(cur); return lines, ws, sp

def line_words(base, t, words, y, sz, col, big=1.3, t_on=None, times=None):
    """Draw a phrase centred in the safe column. Plain words white; moment words Titan One mint and bigger,
    popping in at their own time (times[i]) or at t_on."""
    lines, ws, sp = _layout(words, sz, big)
    for li, idx in enumerate(lines):
        lw = sum(ws[i] for i in idx) + sp * (len(idx) - 1); x = SAFE_CX - lw / 2; yy = y + li * sz * 1.3
        for i in idx:
            w = words[i]
            if is_moment(w):
                t0 = times[i] if times else (t_on or 0)
                if t >= t0 - .05:
                    k = seg(t, t0 - .05, t0 + .14); s = lerp(1.5, 1, back(k))
                    L = word_img(clean(w), sz * big, MINT, MOMENT, s, .16)
                    base.alpha_composite(L, (int(x + ws[i] / 2 - L.width / 2), int(yy + sz * .08 - L.height / 2)))
            else:
                L = word_img(clean(w), sz, col)
                base.alpha_composite(L, (int(x + ws[i] / 2 - L.width / 2), int(yy - L.height / 2)))
            x += ws[i] + sp
    return y + len(lines) * sz * 1.3

def subtitle(base, t, first, second=None, y=SUB_Y, sz=62, sz2=40, times=None, t_on=None):
    """Plain two-language subtitle: first language white (sz), second smaller and grey under it."""
    y2 = line_words(base, t, first.split(), y, sz, WHT, times=times, t_on=t_on)
    if second: line_words(base, t, second.split(), y2 - sz * .2, sz2, GREY, t_on=t_on)

def moment(base, s, y, sz, scale=1.0, col=MINT):
    """A whole line in the moment style (hook, reaction, end card), centred in the safe column.
    Too wide for the safe column? It shrinks to fit (MAXW), so it never runs under the app UI."""
    full = F(sz, MOMENT).getlength(s) * 1.06
    if full > MAXW: sz = sz * MAXW / full
    L = word_img(s, sz, col, MOMENT, scale, .16); base.alpha_composite(L, (int(SAFE_CX - L.width / 2), int(y - L.height / 2)))

def safe_overlay(im):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for r in ((0, 0, W, SAFE[1]), (0, SAFE[3], W, H), (SAFE[2], SAFE[1], W, SAFE[3]), (0, SAFE[1], SAFE[0], SAFE[3])):
        d.rectangle(r, fill=(255, 0, 0, 70))
    d.rectangle(SAFE, outline=(0, 255, 120, 255), width=4)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
