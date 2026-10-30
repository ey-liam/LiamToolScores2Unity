"""gen_packs.py - Genera los packs JD2014_2016, JD4 y Custom_Scratch (mismo esqueleto/animaciones de Classic, arte y colores propios)."""
import os, json, math, random, shutil, colorsys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = r"C:\Users\liamc\Downloads\JD Modding"
BASIC = ROOT + r"\ScoringFX\Library\Basic"
HD = ROOT + r"\ScoringFX\Recreations\JD2014_2016\Individual_Textures"
REPO = r"C:\Users\liamc\Documents\LiamToolScores2Unity\Library"
LIB2 = ROOT + r"\ScoringFX\Library"
F_BOLD = ROOT + r"\Just Dance Bold.ttf"
F_LIT = ROOT + r"\litera-regular.ttf"
F_REG = ROOT + r"\Just Dance Font Regular.ttf"
F_PRESS = ROOT + r"\PressGothic.otf"
random.seed(7)

# ---------- atlas ----------
def parse_atlas(p):
    L = [l.strip() for l in open(p, encoding="utf-8")]
    regs = {}; i = 0
    while i < len(L):
        l = L[i]
        if l.endswith(".png") or l.startswith(("size:", "filter:")) or not l:
            i += 1; continue
        n = l; i += 1
        x, y, w, h = [int(v) for v in L[i].replace("bounds:", "").split(",")]; i += 1
        rot = False
        if i < len(L) and L[i].startswith("rotate:"): rot = True; i += 1
        regs[n] = dict(x=x, y=y, w=w, h=h, rot=rot)
    return regs
REGS = parse_atlas(BASIC + r"\ScoringFX_Basic.atlas")
BASIC_IMG = Image.open(BASIC + r"\ScoringFX_Basic.png").convert("RGBA")

def basic_region(n):
    r = REGS[n]
    if r["rot"]: return BASIC_IMG.crop((r["x"], r["y"], r["x"] + r["h"], r["y"] + r["w"])).transpose(Image.Transpose.ROTATE_270)
    return BASIC_IMG.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))

def hexc(h, a=255):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def fit(img, w, h, pad=3):
    bb = img.getbbox()
    if bb: img = img.crop(bb)
    s = min((w - 2 * pad) / img.width, (h - 2 * pad) / img.height)
    img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, ((w - img.width) // 2, (h - img.height) // 2), img)
    return out

# ---------- generadores ----------
def blur(im, r): return im.filter(ImageFilter.GaussianBlur(r))

def text_img(txt, font, size, fill, stroke, glow, glow_r=10, stroke_w=3, spacing=0, rot=0, shear=0, w=500, h=136, inner=None):
    S = 3
    fnt = ImageFont.truetype(font, size * S)
    # medir con espaciado
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    adv = []; tw = 0
    for c in txt:
        a = d0.textlength(c, font=fnt) + spacing * S; adv.append(a); tw += a
    tw -= spacing * S
    asc, desc = fnt.getmetrics()
    W = int(tw + 140 * S); H = int((asc + desc) + 140 * S)
    def layer(**kw):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 70 * S
        for c, a in zip(txt, adv):
            d.text((x, 70 * S), c, font=fnt, **kw); x += a
        return im
    g = blur(layer(fill=glow, stroke_width=int((glow_r * .8) * S), stroke_fill=glow), glow_r * S)
    g2 = blur(layer(fill=glow, stroke_width=int(glow_r * .35 * S), stroke_fill=glow), glow_r * .4 * S)
    st = layer(fill=stroke, stroke_width=int(stroke_w * S), stroke_fill=stroke)
    core = layer(fill=fill)
    im = Image.alpha_composite(Image.alpha_composite(Image.alpha_composite(g, g2), st), core)
    if inner:  # relleno interior suave (como las letras huecas de JD14)
        pass
    if shear:
        m = math.tan(math.radians(shear))
        im = im.transform(im.size, Image.Transform.AFFINE, (1, m, -m * im.height / 2, 0, 1, 0), Image.Resampling.BICUBIC)
    if rot: im = im.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
    im = im.resize((im.width // S, im.height // S), Image.Resampling.LANCZOS)
    return fit(im, w, h, pad=2)

def cross_img(color, glow, w, h, white=True, tilt=0):
    S = 4; W, H = w * S, h * S
    def ln(col, wd):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); r = int(W * .27); c = W // 2
        d.line([(c - r, c - r), (c + r, c + r)], fill=col, width=wd); d.line([(c - r, c + r), (c + r, c - r)], fill=col, width=wd)
        for p in [(c - r, c - r), (c + r, c + r), (c - r, c + r), (c + r, c - r)]:
            d.ellipse([p[0] - wd // 2, p[1] - wd // 2, p[0] + wd // 2, p[1] + wd // 2], fill=col)
        return im
    g = blur(ln(glow, int(W * .2)), W * .06)
    im = Image.alpha_composite(g, ln(color, int(W * .17)))
    if white: im = Image.alpha_composite(im, ln((255, 255, 255, 255), int(W * .11)))
    return im.resize((w, h), Image.Resampling.LANCZOS)

def soft_blob(w, h, col=(255, 255, 255), sparks=30):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); px = im.load()
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2)); a = max(0, 1 - d) ** 1.6
            px[x, y] = col + (int(a * 200),)
    d = ImageDraw.Draw(im)
    for _ in range(sparks):
        x, y = random.randint(w // 5, w * 4 // 5), random.randint(h // 5, h * 4 // 5); r = random.choice([1, 1, 2])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
    return im

def stripes(w, h):
    """Barras verticales tipo ecualizador laser (PERFECT JD2014)."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    n = 11; bw = w / (n * 1.6)
    for i in range(n):
        x = int(w * .08 + i * (w * .84 / n)); hh = int(h * random.uniform(.45, .95)); a = random.randint(150, 255)
        d.rectangle([x, h // 2 - hh // 2, x + int(bw), h // 2 + hh // 2], fill=(255, 255, 255, a))
    im = Image.alpha_composite(blur(im, 5), blur(im, 1.2))
    return im

def rays(w, h, n=16, cx=.5, cy=.5):
    S = 3; W, H = w * S, h * S; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = (W * cx, H * cy); R = max(W, H)
    for i in range(n):
        a = i * 2 * math.pi / n; wa = math.pi / n * .55
        d.polygon([c, (c[0] + R * math.cos(a - wa), c[1] + R * math.sin(a - wa)), (c[0] + R * math.cos(a + wa), c[1] + R * math.sin(a + wa))], fill=(255, 255, 255, 235))
    im = blur(im, 3 * S)
    fall = Image.new("L", (W, H)); px = fall.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = int(255 * max(0, 1 - math.hypot((x - c[0]) / (W * .5), (y - c[1]) / (H * .5))) ** .7)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), fall))
    return im.resize((w, h), Image.Resampling.LANCZOS)

def bokeh(w, h, n=14):
    S = 3; W, H = w * S, h * S; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(n):
        r = random.randint(int(W * .05), int(W * .2)); x = random.randint(r, W - r); y = random.randint(r, H - r)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, random.randint(40, 90)), outline=(255, 255, 255, 190), width=max(2, S))
    return blur(im, S * .7).resize((w, h), Image.Resampling.LANCZOS)

def sparkle_field(w, h, n=26):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = random.randint(8, w - 8), random.randint(8, h - 8); r = random.choice([3, 4, 6, 8, 11])
        d.polygon([(x, y - r), (x + r * .25, y - r * .25), (x + r, y), (x + r * .25, y + r * .25), (x, y + r), (x - r * .25, y + r * .25), (x - r, y), (x - r * .25, y - r * .25)], fill=(255, 255, 255, 255))
    return Image.alpha_composite(blur(im, 2.5), im)

def radial_ring(w, h):
    S = 3; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([w * S * .12, h * S * .12, w * S * .88, h * S * .88], outline=(255, 255, 255, 255), width=int(w * S * .09))
    return blur(im, S * 3).resize((w, h), Image.Resampling.LANCZOS)

# ---------- retintado de animaciones ----------
def retint(lfx, targets):
    for an, tgt in targets.items():
        t = [v / 255 for v in hexc(tgt)[:3]]; mt = max(t)
        for tr in lfx["animations"][an]["tracks"]:
            for f in tr["frames"]:
                if len(f) < 6 or f[1] < 0: continue
                r, g, b = f[2:5]
                if max(r, g, b) - min(r, g, b) > .2:
                    k = max(r, g, b) / mt
                    f[2], f[3], f[4] = [min(1, round(c * k, 3)) for c in t]

# ---------- definicion de packs ----------
def pack_jd2014():
    o = lambda n: Image.open(HD + "\\" + n).convert("RGBA")
    TILT = 8
    def tilted(im, w, h): return fit(im.rotate(TILT, resample=Image.Resampling.BICUBIC, expand=True), w, h)
    R = {}
    R["PERFECT"] = tilted(o("01_PERFECT_Original_HD.png"), 495, 136)
    R["GOOD"] = tilted(o("03_GOOD_Original_HD.png"), 368, 136)
    R["OK"] = tilted(o("04_OK_Original_HD.png"), 201, 136)
    R["YEAH"] = tilted(o("06_YEAH_Original_HD.png"), 327, 136)
    R["MISS"] = fit(o("05_MISS_Original_HD.png"), 127, 126)
    R["GOLDMISS"] = fit(o("07_GOLDMISS_Original_HD.png"), 127, 126)
    # SUPER: mismo estilo (letras blancas, contorno + resplandor celeste claro), inclinado 8 grados
    R["SUPER"] = text_img("SUPER", F_BOLD, 92, (255, 255, 255, 255), hexc("#8FE3FF"), hexc("#B8F0FF", 255), glow_r=9, stroke_w=3, spacing=9, rot=TILT, w=380, h=136)
    R["green_group"] = stripes(161, 159)
    R["super_group"] = Image.alpha_composite(blur(rays(168, 192, 12, .5, .55), 1), sparkle_field(168, 192, 14))
    colors = dict(Perfect="#5BF52A", Super="#A9E8FF", Good="#17B6FF", Ok="#D81CFF", Gold="#FFC21A", Bad="#FF2A2A", GoldMiss="#FFC21A")
    return R, colors

def pack_jd4():
    W = (255, 255, 255, 255)
    def t(txt, col, w, h, size=84): return text_img(txt, F_LIT, size, W, W, hexc(col), glow_r=10, stroke_w=3.2, spacing=2, w=w, h=h)
    R = {}
    R["PERFECT"] = t("PERFECT", "#B6F020", 495, 136); R["SUPER"] = t("SUPER", "#9FE6FF", 380, 136)
    R["GOOD"] = t("GOOD", "#3FA8FF", 368, 136); R["OK"] = t("OK", "#C040FF", 201, 136); R["YEAH"] = t("YEAH", "#FFC21A", 327, 136)
    R["MISS"] = cross_img(hexc("#FF5C7A"), hexc("#FF2050"), 127, 126)
    R["GOLDMISS"] = cross_img(hexc("#FFC21A"), hexc("#FF9A00"), 127, 126)
    R["green_group"] = rays(161, 159, 14, .5, .5)  # rayos radiales verde-amarillo de PERFECT en JD4
    R["good_particles"] = bokeh(123, 124, 12)
    R["super_group"] = Image.alpha_composite(bokeh(168, 192, 8), sparkle_field(168, 192, 16))
    colors = dict(Perfect="#B6F020", Super="#A5E9FF", Good="#2F8BFF", Ok="#A81CE8", Gold="#FFC21A", Bad="#FF2050", GoldMiss="#FFC21A")
    return R, colors

def pack_scratch():
    W = (255, 255, 255, 255)
    def t(txt, w, h): return text_img(txt, F_BOLD, 90, W, hexc("#FFFFFF"), hexc("#FFFFFF"), glow_r=8, stroke_w=2, spacing=4, w=w, h=h)
    R = {"PERFECT": t("PERFECT", 495, 136), "SUPER": t("SUPER", 380, 136), "GOOD": t("GOOD", 368, 136), "OK": t("OK", 201, 136), "YEAH": t("YEAH", 327, 136),
         "MISS": cross_img(hexc("#DDDDDD"), hexc("#FFFFFF"), 127, 126), "GOLDMISS": cross_img(hexc("#DDDDDD"), hexc("#FFFFFF"), 127, 126)}
    colors = dict(Perfect="#6CFF6C", Super="#A5E9FF", Good="#4FB0FF", Ok="#D060FF", Gold="#FFD040", Bad="#FF4060", GoldMiss="#FFD040")
    return R, colors

def build(name, R, colors, title, thumb_fx):
    atlas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    for n, r in REGS.items():
        img = R.get(n)
        img = fit(img, r["w"], r["h"], 0) if (img is not None and img.size != (r["w"], r["h"])) else (img if img is not None else basic_region(n))
        img = img.convert("RGBA")
        atlas.paste(img.transpose(Image.Transpose.ROTATE_90) if r["rot"] else img, (r["x"], r["y"]))
    lfx = json.load(open(BASIC + r"\Basic.lfx.json", encoding="utf-8"))
    lfx["name"] = name; lfx["source"] = f"ScoringFX_{name}.skel"; lfx["pages"] = [dict(file=f"ScoringFX_{name}.png", w=1024, h=1024)]
    retint(lfx, colors)
    # thumbnail
    th = Image.new("RGBA", (256, 256), (14, 10, 30, 255)); d = ImageDraw.Draw(th)
    sc = fit(R["PERFECT"], 236, 70); th.paste(sc, (10, 40), sc)
    sc = fit(R["SUPER"], 190, 56); th.paste(sc, (33, 108), sc)
    sc = fit(R["GOOD"], 150, 50); th.paste(sc, (12, 170), sc); sc = fit(R["OK"], 90, 50); th.paste(sc, (160, 170), sc)
    d.text((128, 12), title, font=ImageFont.truetype(F_BOLD, 22), fill=(255, 255, 255, 255), anchor="mt")
    for base in (REPO, LIB2):
        out = os.path.join(base, name); os.makedirs(out, exist_ok=True)
        atlas.save(out + f"\\ScoringFX_{name}.png"); th.save(out + f"\\ScoringFX_Thumbnail_{name}.png")
        shutil.copy2(BASIC + r"\ScoringFX_Basic.skel", out + f"\\ScoringFX_{name}.skel")
        al = [f"ScoringFX_{name}.png", "size:1024,1024", "filter:Linear,Linear"]
        for n, r in REGS.items():
            al += [n, f"bounds:{r['x']},{r['y']},{r['w']},{r['h']}"] + (["rotate:90"] if r["rot"] else [])
        open(out + f"\\ScoringFX_{name}.atlas", "w", encoding="utf-8").write("\n".join(al) + "\n")
        json.dump(lfx, open(out + f"\\{name}.lfx.json", "w", encoding="utf-8"))
        p = base + r"\library_index.json"; idx = json.load(open(p, encoding="utf-8"))
        idx = [i for i in idx if i["name"] != name]
        idx.insert(0, dict(name=name, file=f"{name}/{name}.lfx.json", animations=sorted(lfx["animations"].keys())))
        json.dump(idx, open(p, "w", encoding="utf-8"), indent=2)
    # previews
    prev = os.path.join(r"C:\Users\liamc\.gemini\antigravity\brain\5ba69886-6e95-43b6-9dcc-35499bbe77eb\scratch", f"preview_{name}.png")
    sheet = Image.new("RGBA", (1100, 330), (12, 8, 24, 255)); x = 10
    for k in ["PERFECT", "SUPER", "GOOD", "OK", "YEAH", "MISS"]:
        im = R[k]; sheet.paste(im, (x if k != "SUPER" else 10, 10 if k == "PERFECT" else (150 if k in ("SUPER", "GOOD") else 190)) if False else (10 + {"PERFECT":0,"SUPER":520,"GOOD":10,"OK":400,"YEAH":620,"MISS":960}[k], {"PERFECT":10,"SUPER":10,"GOOD":170,"OK":170,"YEAH":170,"MISS":170}[k]), im)
    sheet.save(prev); print("OK", name)

if __name__ == "__main__":
    for name, fn, title in [("JD2014_2016", pack_jd2014, "JD 2014-2016"), ("JD4", pack_jd4, "JUST DANCE 4"), ("Custom_Scratch", pack_scratch, "CUSTOM")]:
        R, c = fn(); build(name, R, c, title, None)
