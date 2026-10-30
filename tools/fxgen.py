"""fxgen.py - Motor de animacion propio: crea packs LiamFX (atlas + .lfx.json) con coreografia original
para Just Dance 2014-2016 y Just Dance 4 (columnas de color, anillos/bokeh, ecualizador, sunburst, chispas...)."""
import os, sys, json, math, random, shutil
sys.path.insert(0, r"C:\Users\liamc\.gemini\antigravity\brain\5ba69886-6e95-43b6-9dcc-35499bbe77eb\scratch")
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import gen_packs as G

FPS = 60
REPO = G.REPO; LIB2 = G.LIB2

# ======================= arte del atlas =======================
def mk_col(w=64, h=256):
    im = Image.new("RGBA", (w, h)); px = im.load()
    for y in range(h):
        v = y / (h - 1); fy = min(1, v / .18) * min(1, (1 - v) / .18); fy = fy ** .8
        for x in range(w):
            u = x / (w - 1); e = min(u, 1 - u); rim = 1 + .35 * max(0, 1 - e / .08); fx = min(1, e / .03 + .15)
            px[x, y] = (255, 255, 255, int(min(1, fy * fx * rim) * 255))
    return im

def mk_glow(s=128, p=1.8):
    im = Image.new("RGBA", (s, s)); px = im.load()
    for y in range(s):
        for x in range(s):
            d = math.hypot(x - s / 2 + .5, y - s / 2 + .5) / (s / 2); px[x, y] = (255, 255, 255, int(max(0, 1 - d) ** p * 255))
    return im

def mk_ring(s=128):
    """Burbuja bokeh: disco translucido con borde brillante y reflejo (los circulos grandes de GOOD)."""
    S = 4; im = Image.new("RGBA", (s * S, s * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); R = s * S / 2 - 4 * S
    d.ellipse([s * S / 2 - R, s * S / 2 - R, s * S / 2 + R, s * S / 2 + R], fill=(255, 255, 255, 70))
    inner = Image.new("RGBA", im.size, (0, 0, 0, 0)); di = ImageDraw.Draw(inner)
    di.ellipse([s * S / 2 - R, s * S / 2 - R, s * S / 2 + R, s * S / 2 + R], outline=(255, 255, 255, 235), width=int(S * 2.6))
    hl = Image.new("RGBA", im.size, (0, 0, 0, 0)); dh = ImageDraw.Draw(hl)
    dh.ellipse([s * S * .22, s * S * .16, s * S * .56, s * S * .42], fill=(255, 255, 255, 80))
    out = Image.alpha_composite(Image.alpha_composite(im, blur(hl, S * 3)), blur(inner, S * .5))
    return out.resize((s, s), Image.Resampling.LANCZOS)

def blur(im, r): return im.filter(ImageFilter.GaussianBlur(r))

def mk_star4(s=64):
    S = 4; im = Image.new("RGBA", (s * S, s * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = s * S / 2; r = c * .96; k = .13
    d.polygon([(c, c - r), (c + r * k, c - r * k), (c + r, c), (c + r * k, c + r * k), (c, c + r), (c - r * k, c + r * k), (c - r, c), (c - r * k, c - r * k)], fill=(255, 255, 255, 255))
    g = blur(im, S * 2.2)
    return Image.alpha_composite(g, im).resize((s, s), Image.Resampling.LANCZOS)

def mk_bar(w=32, h=128):
    im = Image.new("RGBA", (w, h)); px = im.load()
    for y in range(h):
        v = abs(y / (h - 1) * 2 - 1); fy = min(1, (1 - v) / .12)
        for x in range(w):
            u = abs(x / (w - 1) * 2 - 1); core = max(0, 1 - u ** 2); px[x, y] = (255, 255, 255, int(fy * (.35 + .65 * core) * 255 * (1 - u ** 3)))
    return im

def mk_burst(s=384, n=16, width=.5, p=.75):
    S = 2; W = s * S; im = Image.new("RGBA", (W, W), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = W / 2; R = W
    for i in range(n):
        a = i * 2 * math.pi / n; wa = math.pi / n * width
        d.polygon([(c, c), (c + R * math.cos(a - wa), c + R * math.sin(a - wa)), (c + R * math.cos(a + wa), c + R * math.sin(a + wa))], fill=(255, 255, 255, 255))
    im = blur(im, 2.2 * S)
    fall = Image.new("L", (W, W)); fp = fall.load()
    for y in range(W):
        for x in range(W):
            fp[x, y] = int(255 * max(0, 1 - math.hypot(x - c, y - c) / c) ** p)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), fall))
    return im.resize((s, s), Image.Resampling.LANCZOS)

# ======================= construccion de atlas =======================
class Atlas:
    def __init__(self, size=1024): self.size = size; self.items = {}; self.regs = {}
    def add(self, name, img): self.items[name] = img.convert("RGBA")
    def pack(self):
        order = sorted(self.items, key=lambda n: -self.items[n].height)
        x = y = 2; rowh = 0; self.img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        for n in order:
            im = self.items[n]
            if x + im.width + 2 > self.size: x = 2; y += rowh + 3; rowh = 0
            self.img.paste(im, (x, y)); self.regs[n] = dict(page=0, x=x, y=y, w=im.width, h=im.height, rotate=0)
            x += im.width + 3; rowh = max(rowh, im.height)
        assert y + rowh < self.size, "atlas lleno"

# ======================= animacion =======================
def ease(name, t):
    t = max(0, min(1, t))
    if name == "outBack": c = 2.2; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
    if name == "outCubic": return 1 - (1 - t) ** 3
    if name == "outQuad": return 1 - (1 - t) ** 2
    if name == "inQuad": return t * t
    if name == "inOutSine": return -(math.cos(math.pi * t) - 1) / 2
    if name == "outElastic": return 0 if t == 0 else 1 if t == 1 else 2 ** (-10 * t) * math.sin((t * 10 - .75) * 2 * math.pi / 3) + 1
    return t

def samp(v, t):
    if not isinstance(v, list): return v
    if t <= v[0][0]: return v[0][1]
    for a, b in zip(v, v[1:]):
        if t <= b[0]:
            e = a[2] if len(a) > 2 else "linear"; u = ease(e, (t - a[0]) / max(1e-6, b[0] - a[0])); return a[1] + (b[1] - a[1]) * u
    return v[-1][1]

def hx(h): h = h.lstrip("#"); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]

class Anim:
    def __init__(self, dur): self.dur = dur; self.layers = []
    def layer(self, region, t0=0, t1=None, blend="normal", x=0, y=0, sc=1, sx=1, sy=1, rot=0, a=1, col="#ffffff", size=None):
        self.layers.append(dict(region=region, t0=t0, t1=self.dur if t1 is None else t1, blend=blend, x=x, y=y, sc=sc, sx=sx, sy=sy, rot=rot, a=a, col=col, size=size))

def build_lfx(name, atlas, anims):
    regs = atlas.regs; slots = []; atts = []; out = {}
    for an, A in anims.items():
        pass
    # un slot por (anim, capa): los slots se comparten indexando; cada animacion usa sus propios indices
    for an, A in anims.items():
        tracks = []
        for L in A.layers:
            si = len(slots); r = regs[L["region"]]
            slots.append(dict(name=f"{an}_{L['region']}_{si}", blend=L["blend"], bone="root"))
            u0, u1, v0, v1 = r["x"] / atlas.size, (r["x"] + r["w"]) / atlas.size, r["y"] / atlas.size, (r["y"] + r["h"]) / atlas.size
            ai = len(atts)
            atts.append(dict(slot=si, name=L["region"], region=L["region"], page=0, nv=4, uvs=[round(u1, 5), round(v1, 5), round(u0, 5), round(v1, 5), round(u0, 5), round(v0, 5), round(u1, 5), round(v0, 5)], tris=[1, 2, 3, 1, 3, 0]))
            bw, bh = L["size"] if L["size"] else (r["w"], r["h"])
            fr = []; n = int(round(A.dur * FPS)); prev_on = None
            for k in range(n + 1):
                t = k / FPS; on = L["t0"] <= t <= L["t1"]
                if not on:
                    if prev_on is not False: fr.append([round(t, 4), -1])
                    prev_on = False; continue
                prev_on = True
                s = samp(L["sc"], t); w = bw * s * samp(L["sx"], t); h = bh * s * samp(L["sy"], t)
                al = max(0, min(1, samp(L["a"], t))); c = hx(L["col"]) if isinstance(L["col"], str) else L["col"](t)
                rot = math.radians(samp(L["rot"], t)); cx, cy = samp(L["x"], t), samp(L["y"], t); co, si_ = math.cos(rot), math.sin(rot)
                vs = []
                for lx, ly in ((w / 2, -h / 2), (-w / 2, -h / 2), (-w / 2, h / 2), (w / 2, h / 2)):
                    vs += [round(lx * co - ly * si_ + cx, 1), round(lx * si_ + ly * co + cy, 1)]
                fr.append([round(t, 4), ai, round(c[0], 3), round(c[1], 3), round(c[2], 3), round(al, 3)] + vs)
            if prev_on: fr.append([round(A.dur + 1 / FPS, 4), -1])
            tracks.append(dict(slot=si, frames=fr))
        out[an] = dict(duration=A.dur, tracks=tracks)
    return dict(format="LiamFX", version=1, name=name, source="none.skel", spine="custom", fps=60.0, editorFps=30.0,
                pages=[dict(file=f"ScoringFX_{name}.png", w=atlas.size, h=atlas.size)], regions=regs, slots=slots, attachments=atts, animations=out)

# ======================= coreografias =======================
def rise_sparks(A, rng, n, t0, spread, y0, rise, life=(.35, .6), size=(18, 40), col="#ffffff", region="star4", blend="additive", amax=1):
    for i in range(n):
        s = t0 + rng.random() * .22; l = rng.uniform(*life); x = rng.uniform(-spread, spread); sz = rng.uniform(*size)
        dx = rng.uniform(-25, 25); y1 = y0 + rise * rng.uniform(.5, 1)
        A.layer(region, s, s + l, blend, x=[(s, x), (s + l, x + dx)], y=[(s, y0 + rng.uniform(-60, 40)), (s + l, y1)], sc=[(s, 0, "outQuad"), (s + l * .3, sz / 64), (s + l, 0)] if region == "star4" else [(s, sz / 128, "outQuad"), (s + l, sz / 128 * .3)], rot=rng.uniform(0, 90), a=[(s, 0), (s + l * .2, amax), (s + l, 0)], col=col)

def radial(A, rng, n, t0, r0, r1, life=(.3, .5), size=(14, 30), col="#fff", region="star4", blend="additive"):
    for i in range(n):
        s = t0 + rng.random() * .06; l = rng.uniform(*life); ang = rng.random() * 2 * math.pi; rr = rng.uniform(r0, r1); sz = rng.uniform(*size)
        A.layer(region, s, s + l, blend, x=[(s, math.cos(ang) * r0, "outCubic"), (s + l, math.cos(ang) * rr)], y=[(s, math.sin(ang) * r0, "outCubic"), (s + l, math.sin(ang) * rr)],
                sc=[(s, sz / 64 if region == "star4" else sz / 128, "outQuad"), (s + l, 0)], rot=rng.uniform(0, 180), a=[(s, 1), (s + l, 0)], col=col)

def text_layers(A, name, col, style, dur, tilt=0, glow_a=.5, glow_col=None, rise=14, big=1.0):
    """Texto: pop-in elastico, leve flotacion y salida. En JD14 se anade rebote de rotacion."""
    sc_in = (1.38 * big) if style == "jd14" else (1.28 * big)
    scale = [(0, .0, "outBack"), (.14, sc_in * 1.12, "outQuad"), (.24, sc_in), (dur - .24, sc_in * 1.03), (dur, sc_in * .9)] if style == "jd14" else [(0, .35, "outBack"), (.16, sc_in * 1.08, "outQuad"), (.26, sc_in), (dur - .22, sc_in * 1.02), (dur, sc_in * .94)]
    alpha = [(0, 0), (.05, 1), (dur - .2, 1), (dur, 0)]
    yy = [(0, -10, "outCubic"), (.3, 0), (dur, rise)]
    wob = [(0, -6 if tilt == 0 else -6, "outQuad"), (.16, 3, "outQuad"), (.3, 0)] if style == "jd14" else [(0, 0)]
    A.layer(name, 0, dur, "additive", y=yy, sc=[(t, v * 1.07) if len(k) == 2 else (t, v * 1.07, k[2]) for k in scale for (t, v) in [(k[0], k[1])]], rot=wob, a=[(t, v * glow_a) for t, v in alpha], col=glow_col or col)
    A.layer(name, 0, dur, "normal", y=yy, sc=scale, rot=wob, a=alpha)

def fx_anims(style):
    """style: 'jd14' | 'jd4' | 'scratch'. Devuelve dict de Anim."""
    rng = random.Random(11 if style == "jd14" else 29)
    P = dict(
        jd14=dict(perfect="#5BF52A", perfect2="#B9FF5A", super="#A9E8FF", good="#17B6FF", ok="#D81CFF", gold="#FFC21A", bad="#FF2A2A"),
        jd4=dict(perfect="#9CE82A", perfect2="#E4FF6A", super="#A5E9FF", good="#2F8BFF", ok="#9A28E0", gold="#FFC21A", bad="#FF2050"),
    )[style]
    anims = {}
    COLW, COLH = 330, 620
    # ---------- PERFECT ----------
    d = .95; A = Anim(d)
    A.layer("col", 0, d, "normal", sx=520, sy=COLH, size=(1, 1), a=[(0, 0), (.08, .9), (d - .3, .8), (d, 0)], col=P["perfect"], sc=1)
    if style == "jd14":
        A.layer("glow", 0, d, "additive", sc=[(0, 1.5), (d, 4.2)], size=(128, 128), a=[(0, 0), (.1, .55), (d, 0)], col=P["perfect"], sx=2.2)
        for i in range(11):  # barras tipo ecualizador laser
            x = -135 + i * 27; t0 = .02 + i * .006
            hs = [(0, 0.05)]; t = t0
            while t < d - .15:
                t += .06; hs.append((t, rng.uniform(.25, 1.0), "outQuad"))
            hs += [(d - .05, .05)]
            A.layer("bar", t0, d - .05, "additive", x=x, y=0, size=(26, 420), sy=hs, a=[(t0, 0), (t0 + .08, .85), (d - .25, .7), (d - .05, 0)], col=P["perfect2"])
        A.layer("burst16", 0, d, "additive", sc=[(0, .6), (d, 2.4, "outCubic")], rot=[(0, 0), (d, 45)], a=[(0, 0), (.1, .5), (d, 0)], col=P["perfect"])
        rise_sparks(A, rng, 22, .05, 150, -80, 360, size=(14, 34), col=P["perfect2"])
    else:
        A.layer("burst16", 0, d, "additive", x=-170, y=130, size=(900, 900), sc=[(0, .5), (d, 1.0, "outCubic")], rot=[(0, 0), (d, 28)], a=[(0, 0), (.1, .95), (d - .3, .7), (d, 0)], col=P["perfect2"])
        A.layer("glow", 0, d, "additive", x=-90, y=70, size=(128, 128), sc=[(0, 2), (d, 5)], a=[(0, 0), (.1, .7), (d, 0)], col=P["perfect2"])
        rise_sparks(A, rng, 16, .05, 140, -60, 300, size=(12, 28), col="#EFFFB0")
    text_layers(A, "PERFECT", P["perfect"], style, d, glow_a=.45)
    anims["Perfect"] = A
    # ---------- SUPER (variante celeste claro) ----------
    d = .95; A = Anim(d)
    A.layer("col", 0, d, "normal", sx=460, sy=COLH, size=(1, 1), a=[(0, 0), (.08, .8), (d - .3, .7), (d, 0)], col="#6FD6FF", sc=1)
    A.layer("burst8", 0, d, "additive", sc=[(0, .5), (d, 2.1, "outCubic")], rot=[(0, 0), (d, -60)], a=[(0, 0), (.1, .55), (d, 0)], col="#E6F8FF")
    A.layer("glow", 0, d, "additive", size=(128, 128), sc=[(0, 1.5), (d, 4.5)], sx=2, a=[(0, 0), (.1, .5), (d, 0)], col=P["super"])
    for i in range(6):
        s = .05 + i * .035; l = .6; x = rng.uniform(-130, 130); A.layer("ring", s, s + l, "additive", x=x, y=[(s, -90), (s + l, 130)], sc=[(s, .3), (s + l, rng.uniform(.9, 1.5), "outQuad")], a=[(s, 0), (s + .1, .6), (s + l, 0)], col="#DFF6FF")
    rise_sparks(A, rng, 26, .04, 150, -80, 380, size=(14, 36), col="#F2FCFF")
    text_layers(A, "SUPER", P["super"], style, d, glow_a=.55, glow_col="#D8F5FF")
    anims["Super"] = A
    # ---------- GOOD ----------
    d = .85; A = Anim(d)
    A.layer("col", 0, d, "normal", sx=420, sy=COLH, size=(1, 1), a=[(0, 0), (.08, .75 if style == "jd14" else .65), (d - .28, .6), (d, 0)], col=P["good"], sc=1)
    A.layer("glow", 0, d, "additive", size=(128, 128), sc=[(0, 1.2), (d, 3.6)], sx=2, a=[(0, 0), (.1, .45), (d, 0)], col=P["good"])
    n = 9 if style == "jd4" else 7
    for i in range(n):  # circulos grandes translucidos alrededor
        ang = rng.uniform(0, 2 * math.pi); rr = rng.uniform(60, 200); s = .02 + rng.random() * .12; l = rng.uniform(.55, .75); big_ = rng.uniform(1.0, 2.2)
        cx, cy = math.cos(ang) * rr, math.sin(ang) * rr * 1.2
        A.layer("ring", s, s + l, "additive", x=[(s, cx), (s + l, cx + rng.uniform(-30, 30))], y=[(s, cy), (s + l, cy + rng.uniform(40, 110))], sc=[(s, big_ * .45, "outBack"), (s + l, big_ * 1.0, "outQuad")], a=[(s, 0), (s + .1, .8), (s + l, 0)], col="#CFEFFF" if style == "jd4" else "#9EE6FF")
    for i in range(10):
        s = .05 + rng.random() * .15; l = rng.uniform(.35, .55); x = rng.uniform(-150, 150)
        A.layer("dot", s, s + l, "additive", x=x, y=[(s, rng.uniform(-80, 0)), (s + l, rng.uniform(80, 200))], sc=[(s, rng.uniform(.6, 1.3)), (s + l, 0)], a=[(s, 0), (s + .08, 1), (s + l, 0)], col="#FFFFFF")
    text_layers(A, "GOOD", P["good"], style, d, glow_a=.45)
    anims["Good"] = A
    # ---------- OK ----------
    d = .7; A = Anim(d)
    A.layer("col", 0, d, "normal", sx=300, sy=COLH, size=(1, 1), a=[(0, 0), (.07, .92), (d - .22, .8), (d, 0)], col=P["ok"], sc=1)
    A.layer("glow", 0, d, "additive", size=(128, 128), sc=[(0, 1.4), (d, 3.8)], sx=1.8, a=[(0, 0), (.08, .6), (d, 0)], col=P["ok"])
    if style == "jd14":
        radial(A, rng, 8, .03, 40, 190, life=(.3, .45), size=(40, 70), col="#FF7BFF", region="glow", blend="additive")
        A.layer("ring", .0, .45, "additive", sc=[(0, .6), (.45, 3.0, "outCubic")], a=[(0, .55), (.45, 0)], col="#FF8CFF")
    text_layers(A, "OK", P["ok"], style, d, glow_a=.4)
    anims["Ok"] = A
    # ---------- YEAH (Gold) ----------
    d = .95; A = Anim(d)
    A.layer("col", 0, d, "normal", sx=460, sy=COLH, size=(1, 1), a=[(0, 0), (.08, .85), (d - .3, .7), (d, 0)], col="#E39A00", sc=1)
    A.layer("burst16", 0, d, "additive", sc=[(0, .6), (d, 2.8, "outCubic")], rot=[(0, 0), (d, 70)], a=[(0, 0), (.08, .95), (d - .35, .7), (d, 0)], col="#FFD24A")
    A.layer("burst16", 0, d, "additive", sc=[(0, .4), (d, 2.0, "outCubic")], rot=[(0, 0), (d, -40)], a=[(0, 0), (.1, .5), (d, 0)], col="#FFF0B0")
    A.layer("ring", 0, .6, "additive", sc=[(0, .5), (.6, 4.2, "outCubic")], a=[(0, .9), (.6, 0)], col="#FFE07A")
    radial(A, rng, 24, .02, 60, 320, life=(.4, .7), size=(20, 46), col="#FFF4C0")
    text_layers(A, "YEAH", "#FFC21A", style, d, glow_a=.55, glow_col="#FFE07A", big=1.05)
    anims["Gold"] = A
    # ---------- MISS ----------
    for an, col, region in (("Bad", P["bad"], "MISS"), ("GoldMiss", "#FFC21A", "GOLDMISS")):
        d = .6; A = Anim(d)
        A.layer("col", 0, d, "normal", sx=COLW * .8, sy=COLH * .75, size=(1, 1), a=[(0, 0), (.06, .45), (d - .2, .3), (d, 0)], col=col, sc=1)
        A.layer("glow", 0, d, "additive", size=(128, 128), sc=[(0, 1.2), (.2, 3.2, "outCubic"), (d, 3.6)], a=[(0, 0), (.06, .7), (d, 0)], col=col)
        A.layer("ring", 0, .4, "additive", sc=[(0, .6), (.4, 2.4, "outCubic")], a=[(0, .5), (.4, 0)], col=col)
        shake = [(0, 0), (.1, -14), (.17, 12), (.24, -8), (.31, 5), (.4, 0)]
        sc = [(0, .1, "outBack"), (.12, 1.55, "outQuad"), (.22, 1.38), (d - .18, 1.38), (d, 1.1)]; al = [(0, 0), (.04, 1), (d - .18, 1), (d, 0)]
        A.layer(region, 0, d, "additive", x=shake, sc=[(t, v * 1.08) for t, v in [(k[0], k[1]) for k in sc]], a=[(t, v * .4) for t, v in al], col=col)
        A.layer(region, 0, d, "normal", x=shake, sc=sc, a=al)
        anims[an] = A
    return anims

def make_pack(name, style, title):
    R, _ = (G.pack_jd2014() if style == "jd14" else G.pack_jd4())
    at = Atlas()
    for k in ("PERFECT", "SUPER", "GOOD", "OK", "YEAH", "MISS", "GOLDMISS"): at.add(k, R[k])
    at.add("col", mk_col()); at.add("glow", mk_glow()); at.add("ring", mk_ring()); at.add("star4", mk_star4()); at.add("dot", mk_glow(32, 1.2))
    at.add("bar", mk_bar()); at.add("burst16", mk_burst(384, 16, .5)); at.add("burst8", mk_burst(256, 8, .35))
    at.pack()
    lfx = build_lfx(name, at, fx_anims(style))
    # miniatura
    th = Image.new("RGBA", (256, 256), (12, 8, 26, 255))
    colr = {"jd14": (0, 160, 255), "jd4": (150, 70, 230)}[style]
    colimg = Image.new("RGBA", (256, 256), colr + (0,)); cm = mk_col(256, 256).resize((120, 256)); tint = Image.new("RGBA", cm.size, colr + (255,)); tint.putalpha(cm.getchannel("A").point(lambda v: int(v * .7)))
    th.alpha_composite(tint, (68, 0))
    for im, (w, h), pos in ((R["PERFECT"], (236, 62), (10, 40)), (R["SUPER"], (180, 52), (38, 105)), (R["GOOD"], (150, 48), (10, 165)), (R["OK"], (84, 48), (162, 165))):
        s = G.fit(im, w, h); th.alpha_composite(s, pos)
    ImageDraw.Draw(th).text((128, 12), title, font=ImageFont.truetype(G.F_BOLD, 22), fill=(255, 255, 255, 255), anchor="mt")
    lfx["source"] = f"ScoringFX_{name}.skel"
    for base in (REPO, LIB2):
        out = os.path.join(base, name); os.makedirs(out, exist_ok=True)
        at.img.save(out + f"\\ScoringFX_{name}.png"); th.save(out + f"\\ScoringFX_Thumbnail_{name}.png")
        json.dump(lfx, open(out + f"\\{name}.lfx.json", "w", encoding="utf-8"), separators=(",", ":"))
        al = [f"ScoringFX_{name}.png", f"size:{at.size},{at.size}", "filter:Linear,Linear"]
        for rn, rr in at.regs.items():
            al += [rn, f"bounds:{rr['x']},{rr['y']},{rr['w']},{rr['h']}"]
            if rr.get("rotate"): al += ["rotate:90"]
        open(out + f"\\ScoringFX_{name}.atlas", "w", encoding="utf-8").write("\n".join(al) + "\n")
        shutil.copy2(G.BASIC + r"\ScoringFX_Basic.skel", out + f"\\ScoringFX_{name}.skel")
        p_idx = base + r"\library_index.json"; idx = json.load(open(p_idx, encoding="utf-8")); idx = [i for i in idx if i["name"] != name]
        idx.insert(0, dict(name=name, file=f"{name}/{name}.lfx.json", animations=sorted(lfx["animations"]), group="classic", thumb=f"{name}/ScoringFX_Thumbnail_{name}.png"))
        json.dump(idx, open(p_idx, "w", encoding="utf-8"), indent=2)
    print("OK", name, os.path.getsize(os.path.join(REPO, name, name + ".lfx.json")) // 1024, "KB")

if __name__ == "__main__":
    make_pack("JD2014_2016", "jd14", "JD 2014-2016"); make_pack("JD4", "jd4", "JUST DANCE 4")
