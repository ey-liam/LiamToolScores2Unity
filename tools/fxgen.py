"""fxgen.py - Generador autentico de ScoringFX para Just Dance 2014-2016, Just Dance 4 y Custom_Scratch.
Usa las texturas originales decodificadas de UbiArt (2014 UI TEXTURES: ui_hud_wdg_feedback_*,
grad_v_coach, ui_com_barcode, ui_com_fx_lens_bubbles, ui_fx_light_saber, ui_fx_multi_sparks,
ui_com_fx_circles, ui_fx_starfield, ui_com_fx_simpleglow, ui_com_fx_pointglow, ui_com_fx_sparks_32,
x_flare, x_planeterays, sfx_goldemove_speed) y evalua las curvas Bezier reales de feedback_*.tape.ckd."""

import os, io, re, json, math, random, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

FPS = 60
ROOT_MOD = r"C:\Users\liamc\Downloads\JD Modding"
SRC_2014 = ROOT_MOD + r"\2014 UI TEXTURES"
REPO_LIB = r"C:\Users\liamc\Documents\LiamToolScores2Unity\Library"
MOD_LIB  = ROOT_MOD + r"\ScoringFX\Library"
BASIC_DIR = REPO_LIB + r"\Basic"
REC_14   = ROOT_MOD + r"\ScoringFX\Recreations\JD2014_2016\Individual_Textures"
REC_4    = ROOT_MOD + r"\ScoringFX\Recreations\JD4\Individual_Textures"

F_BOLD  = ROOT_MOD + r"\Just Dance Bold.ttf"
F_REG   = ROOT_MOD + r"\Just Dance Font Regular.ttf"
F_LIT   = ROOT_MOD + r"\litera-regular.ttf"
F_PRESS = ROOT_MOD + r"\PressGothic.otf"

# ======================= Decodificador UbiArt (.tga.ckd & .tape.ckd) =======================
def load_ckd_tex(rel_path):
    p = os.path.join(SRC_2014, rel_path)
    raw = open(p, "rb").read()
    idx = raw.find(b"DDS ")
    if idx < 0:
        raise ValueError(f"No DDS header in {p}")
    return Image.open(io.BytesIO(raw[idx:])).convert("RGBA")

def load_png_tex(rel_path):
    return Image.open(os.path.join(SRC_2014, rel_path)).convert("RGBA")

def load_tape_json(tape_name):
    p = os.path.join(SRC_2014, r"animations\feedbacks", tape_name)
    txt = open(p, "rb").read().rstrip(b"\x00").decode("utf-8", errors="replace")
    txt = re.sub(r"(?<![.\d])0+(\d+\.)", r"\1", txt)
    return json.loads(txt)

def eval_ubi_bezier(keys, tick):
    """Evalua BezierCurveFloatMulti real de UbiArt ([tick, val], NormalIn, NormalOut)."""
    if not keys:
        return 0.0
    if tick <= keys[0]["Value"][0]:
        return keys[0]["Value"][1]
    if tick >= keys[-1]["Value"][0]:
        return keys[-1]["Value"][1]
    for k0, k1 in zip(keys, keys[1:]):
        t0, v0 = k0["Value"]
        t1, v1 = k1["Value"]
        if tick <= t1:
            if t1 - t0 < 1e-6:
                return v1
            to0, vo0 = k0.get("NormalOut", [t0, v0])
            ti1, vi1 = k1.get("NormalIn", [t1, v1])
            # Resolver B_t(u) = tick por biseccion (monotono en tiempo)
            lo, hi = 0.0, 1.0
            for _ in range(12):
                u = 0.5 * (lo + hi)
                mu = 1.0 - u
                bt = (mu**3)*t0 + 3*(mu**2)*u*to0 + 3*mu*(u**2)*ti1 + (u**3)*t1
                if bt < tick:
                    lo = u
                else:
                    hi = u
            u = 0.5 * (lo + hi)
            mu = 1.0 - u
            return (mu**3)*v0 + 3*(mu**2)*u*vo0 + 3*mu*(u**2)*vi1 + (u**3)*v1
    return keys[-1]["Value"][1]

def lum_to_white_alpha(im, gamma=1.0, gain=1.0):
    """Convierte mascaras UbiArt en negro (DXT1/DXT5) a RGB blanco puro + Alpha = luminancia * alpha."""
    arr = np.asarray(im.convert("RGBA"), np.float32) / 255.0
    lum = np.maximum(np.maximum(arr[..., 0], arr[..., 1]), arr[..., 2])
    if gamma != 1.0:
        lum = np.power(np.clip(lum, 0.0, 1.0), gamma)
    al = np.clip(lum * arr[..., 3] * gain, 0.0, 1.0)
    out = np.zeros_like(arr)
    out[..., :3] = 1.0
    out[..., 3] = al
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")

def tight_crop(im, pad=3, thresh=3):
    arr = np.asarray(im.convert("RGBA"))
    ys, xs = np.where(arr[..., 3] > thresh)
    if len(xs) == 0:
        return im
    x0, x1 = max(0, int(xs.min()) - pad), min(im.width, int(xs.max()) + 1 + pad)
    y0, y1 = max(0, int(ys.min()) - pad), min(im.height, int(ys.max()) + 1 + pad)
    return im.crop((x0, y0, x1, y1))

# ======================= Texturas Reales & Sprites Artesanales =======================
def make_jd14_super_sprite():
    """Crea el texto SUPER celeste claro con la misma anatomia pixel a pixel que
    ui_hud_wdg_feedback_perfect_text.png y ui_hud_wdg_feedback_good_text.png."""
    S = 4
    fnt = ImageFont.truetype(F_BOLD, 84 * S)
    txt = "SUPER"
    spacing = 5.5 * S
    d0 = ImageDraw.Draw(Image.new("RGBA", (16, 16)))
    adv = [d0.textlength(c, font=fnt) + spacing for c in txt]
    tw = sum(adv) - spacing
    W, H = int(tw + 72 * S), int(122 * S)
    ox, oy = int(36 * S), int(18 * S)

    def draw_mask(stroke_px=0.0):
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        x = ox
        for c, a in zip(txt, adv):
            d.text((x, oy), c, font=fnt, fill=255, stroke_width=int(round(stroke_px)), stroke_fill=255)
            x += a
        return m

    # Estiramiento vertical 1.13x identico al condensado de PERFECT/GOOD en JD 2014
    glow_outer = draw_mask(3.4 * S).filter(ImageFilter.GaussianBlur(3.8 * S))
    glow_mid   = draw_mask(2.0 * S).filter(ImageFilter.GaussianBlur(1.6 * S))
    rim        = draw_mask(1.35 * S).filter(ImageFilter.GaussianBlur(0.45 * S))
    core       = draw_mask(0.0).filter(ImageFilter.GaussianBlur(0.3 * S))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # Celeste claro luminoso (#74EEFF / #AEF7FF), claramente mas claro y celeste hielo que el azul cyan de GOOD
    for mask, rgb, gain in [
        (glow_outer, (100, 236, 255), 0.92),
        (glow_mid,   (138, 245, 255), 0.98),
        (rim,        (170, 250, 255), 1.00),
        (core,       (255, 255, 255), 1.00),
    ]:
        lay = Image.new("RGBA", (W, H), rgb + (0,))
        lay.putalpha(mask.point(lambda v, g=gain: min(255, int(v * g))))
        out = Image.alpha_composite(out, lay)

    target_w = W // S
    target_h = int(round((H // S) * 1.13))
    out = out.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return tight_crop(out, pad=3)

def make_jd4_text_sprite(txt, glow_rgb, rim_rgb=None, size=76, stroke_core=1.75, spacing=2.5):
    """Tipografia fiel de Just Dance 4: geometrica limpia (Just Dance Font Regular engrosada),
    nucleo blanco puro y halo neon suave sin borde oscuro, horizontal (0 grados)."""
    S = 4
    fnt = ImageFont.truetype(F_REG, int(size * S))
    sp = spacing * S
    d0 = ImageDraw.Draw(Image.new("RGBA", (16, 16)))
    adv = [d0.textlength(c, font=fnt) + sp for c in txt]
    tw = sum(adv) - sp
    W, H = int(tw + 96 * S), int(128 * S)
    ox, oy = int(48 * S), int(24 * S)

    def draw_mask(stroke_px=0.0):
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        x = ox
        for c, a in zip(txt, adv):
            d.text((x, oy), c, font=fnt, fill=255, stroke_width=int(round(stroke_px)), stroke_fill=255)
            x += a
        return m

    g_wide = draw_mask((stroke_core + 4.2) * S).filter(ImageFilter.GaussianBlur(5.6 * S))
    g_near = draw_mask((stroke_core + 1.8) * S).filter(ImageFilter.GaussianBlur(2.2 * S))
    core   = draw_mask(stroke_core * S).filter(ImageFilter.GaussianBlur(0.35 * S))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for mask, rgb, gain in [
        (g_wide, glow_rgb, 0.90),
        (g_near, rim_rgb or glow_rgb, 0.96),
        (core,   (255, 255, 255), 1.00),
    ]:
        lay = Image.new("RGBA", (W, H), rgb + (0,))
        lay.putalpha(mask.point(lambda v, g=gain: min(255, int(v * g))))
        out = Image.alpha_composite(out, lay)

    out = out.resize((W // S, H // S), Image.Resampling.LANCZOS)
    return tight_crop(out, pad=3)

def make_jd4_cross_sprite(glow_rgb, rim_rgb, w=128, h=116):
    """Cruz 'X' de Just Dance 4 (HAPPY X): brazos ligeramente mas abiertos horizontalmente,
    extremos redondeados, interior blanco puro y halo carmesi/dorado suave."""
    S = 4
    W, H = w * S, h * S
    cx, cy = W // 2, H // 2
    rx, ry = int(W * 0.27), int(H * 0.24)

    def draw_x(width_px):
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        pts = [((cx - rx, cy - ry), (cx + rx, cy + ry)), ((cx - rx, cy + ry), (cx + rx, cy - ry))]
        for p0, p1 in pts:
            d.line([p0, p1], fill=255, width=width_px)
            r = width_px // 2
            for px_, py_ in (p0, p1):
                d.ellipse([px_ - r, py_ - r, px_ + r, py_ + r], fill=255)
        return m

    g_wide = draw_x(int(W * 0.19)).filter(ImageFilter.GaussianBlur(6.0 * S))
    g_near = draw_x(int(W * 0.155)).filter(ImageFilter.GaussianBlur(2.0 * S))
    core   = draw_x(int(W * 0.125)).filter(ImageFilter.GaussianBlur(0.4 * S))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for mask, rgb, gain in [(g_wide, glow_rgb, 0.85), (g_near, rim_rgb, 0.95), (core, (255, 255, 255), 1.0)]:
        lay = Image.new("RGBA", (W, H), rgb + (0,))
        lay.putalpha(mask.point(lambda v, g=gain: min(255, int(v * g))))
        out = Image.alpha_composite(out, lay)
    return tight_crop(out.resize((w, h), Image.Resampling.LANCZOS), pad=3)

def build_col_coach(grad_im, w=128, h=256):
    """Columna vertical autentica de JD 2014 basada en textures/grad_v_coach.png:
    solida arriba, degradado suave abajo y bordes laterales nitidos con sutil realce."""
    g = grad_im.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA")
    arr = np.asarray(g, np.float32) / 255.0
    lum = arr[..., 0].copy()  # 1.0 arriba -> 0.0 abajo
    # Suavizado minimo en los 10px superiores para evitar corte duro si se hace zoom-out
    top_fade = np.minimum(1.0, np.arange(h, dtype=np.float32) / 10.0)[:, None]
    # Realce sutil en los bordes izquierdo y derecho (como el marco luminoso del HUD JD14/15/16)
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    edge_dist = np.minimum(x, 1.0 - x)
    rim = 1.0 + 0.22 * np.exp(-edge_dist / 0.035)
    side_aa = np.minimum(1.0, edge_dist / 0.012)
    alpha = np.clip(lum * top_fade * rim * side_aa, 0.0, 1.0)
    out = np.ones((h, w, 4), np.float32)
    out[..., 3] = alpha
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")

def build_col_barcode(grad_im, barcode_im, w=160, h=256):
    """Rayos verticales laser de PERFECT en JD 2014 combinando grad_v_coach.png x ui_com_barcode.png."""
    g = np.asarray(grad_im.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA"), np.float32) / 255.0
    b = np.asarray(barcode_im.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA"), np.float32) / 255.0
    # Canal verde/azul de ui_com_barcode contiene las franjas laser de distinto grosor
    stripe = 0.5 * (b[..., 1] + b[..., 2])
    s_min, s_max = float(stripe.min()), float(stripe.max())
    stripe = np.clip((stripe - s_min) / max(1e-5, s_max - s_min), 0.0, 1.0)
    stripe = np.power(stripe, 1.55)
    top_fade = np.minimum(1.0, np.arange(h, dtype=np.float32) / 12.0)[:, None]
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    side = np.minimum(1.0, np.minimum(x, 1.0 - x) / 0.03)
    alpha = np.clip(g[..., 0] * stripe * top_fade * side, 0.0, 1.0)
    out = np.ones((h, w, 4), np.float32)
    out[..., 3] = alpha
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")

def build_sunburst_12(s=320, n_rays=12, duty=0.46):
    """ Abanico radial nitido de 12 rayos dorados de YEAH (JD 2014 panel 5 / Gold_GodRays)."""
    S = 2
    W = s * S
    im = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(im)
    c = W / 2.0
    R = W * 0.52
    for i in range(n_rays):
        a = i * (2 * math.pi / n_rays) + math.pi / n_rays * 0.35
        wa = (math.pi / n_rays) * duty
        d.polygon([
            (c, c),
            (c + R * math.cos(a - wa), c + R * math.sin(a - wa)),
            (c + R * math.cos(a + wa), c + R * math.sin(a + wa)),
        ], fill=255)
    im = im.filter(ImageFilter.GaussianBlur(1.4 * S))
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    dist = np.hypot(xx - c, yy - c) / (W * 0.49)
    fall = np.clip(1.0 - np.power(np.clip(dist, 0.0, 1.0), 1.85), 0.0, 1.0)
    arr = (np.asarray(im, np.float32) / 255.0) * fall
    out = np.ones((W, W, 4), np.float32)
    out[..., 3] = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA").resize((s, s), Image.Resampling.LANCZOS)

def build_jd4_curtain(w=256, h=256):
    """Cortina luminosa unilateral de Just Dance 4: linea divisoria vertical izquierda ultra nitida
    que se desvanece suavemente hacia la derecha y arriba/abajo (HAPPY | PERFECT, JAZZY | OK, FUNKY | GOOD)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = xx / (w - 1.0)
    v = yy / (h - 1.0)
    # Borde izquierdo afilado en u=0.02 con linea divisoria brillante y caida exponencial suave a la derecha
    left_mask = np.clip((u - 0.012) / 0.010, 0.0, 1.0)
    horiz = np.power(np.clip(1.0 - u, 0.0, 1.0), 1.75) * left_mask
    divider_line = np.exp(-((u - 0.022) / 0.008) ** 2) * 0.55
    # Caida vertical: mas extendida hacia arriba (como en el HUD superior de JD4) y suave abajo
    vert = np.minimum(1.0, v / 0.10) * np.power(np.clip((1.0 - v) / 0.78, 0.0, 1.0), 0.85)
    vert_full = np.power(np.maximum(0.0, np.sin(np.clip(v, 0.0, 1.0) * math.pi)), 0.55)
    vy = 0.65 * vert_full + 0.35 * vert
    alpha = np.clip((horiz + divider_line) * vy, 0.0, 1.0)
    out = np.ones((h, w, 4), np.float32)
    out[..., 3] = alpha
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")

def build_jd4_half_sunburst(w=288, h=352, n_rays=15):
    """Medio-sol radial de PERFECT en Just Dance 4: nucleo brillante sobre la linea divisoria izquierda
    y rayos verde-lima irradiando 180 grados unicamente hacia la derecha detras de PERFECT."""
    S = 2
    W, H = w * S, h * S
    ox = int(W * 0.03)
    oy = int(H * 0.50)
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    R = max(W, H) * 0.98
    for i in range(n_rays):
        frac = (i + 0.5) / n_rays
        ang = -math.pi * 0.48 + frac * (math.pi * 0.96)  # solo hacia la derecha (-86 a +86 grados)
        wa = (math.pi / n_rays) * (0.28 + 0.16 * (1.0 - abs(frac - 0.5) * 1.5))
        r_len = R * (0.72 + 0.28 * ((i * 7) % 3) / 2.0)
        d.polygon([
            (ox, oy),
            (ox + r_len * math.cos(ang - wa), oy + r_len * math.sin(ang - wa)),
            (ox + r_len * math.cos(ang + wa), oy + r_len * math.sin(ang + wa)),
        ], fill=255)
    im = im.filter(ImageFilter.GaussianBlur(1.8 * S))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.hypot((xx - ox) / (W * 0.88), (yy - oy) / (H * 0.50))
    ray_fall = np.power(np.clip(1.0 - dist, 0.0, 1.0), 1.35)
    core_glow = np.exp(-((dist / 0.30) ** 2)) * 0.38
    clip_left = np.clip((xx - ox + 1.5 * S) / (2.0 * S), 0.0, 1.0)
    arr = np.clip(((np.asarray(im, np.float32) / 255.0) * ray_fall + core_glow) * clip_left, 0.0, 1.0)
    out = np.ones((H, W, 4), np.float32)
    out[..., 3] = arr
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA").resize((w, h), Image.Resampling.LANCZOS)

def load_real_fx_bank():
    """Carga y separa todas las hojas de sprites FX reales de 2014 UI TEXTURES."""
    grad_coach = load_png_tex(r"textures\grad_v_coach.png")
    barcode    = load_png_tex(r"textures\ui_com_barcode.png")
    x_flare    = lum_to_white_alpha(load_png_tex(r"textures\x_flare.png").crop((256, 256, 768, 768)).resize((192, 192), Image.Resampling.LANCZOS), gamma=0.9, gain=1.15)
    planet_rays= lum_to_white_alpha(load_png_tex(r"textures\x_planeterays.png").resize((192, 192), Image.Resampling.LANCZOS), gamma=0.85, gain=1.6)
    speed_rays = load_png_tex(r"textures\sfx_goldemove_speed.png").resize((224, 224), Image.Resampling.LANCZOS)

    bubbles    = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_com_fx_lens_bubbles.tga.ckd"), gamma=0.95, gain=1.08)
    msparks    = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_fx_multi_sparks.tga.ckd"), gamma=0.92, gain=1.15)
    circles    = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_com_fx_circles.tga.ckd"), gamma=0.85, gain=1.55)
    saber      = load_ckd_tex(r"fx\fx\ui_fx_light_saber.tga.ckd")
    dglow      = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_com_fx_simpleglow.tga.ckd"), gamma=1.0, gain=1.0)
    pglow      = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_com_fx_pointglow.tga.ckd"), gamma=0.9, gain=1.15)
    sparks32   = lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_com_fx_sparks_32.tga.ckd"), gamma=1.1, gain=1.0)
    # Starfield: usar max-pooling 2x2 para que las estrellas de 1-2px no pierdan brillo al reducir 512->256
    sf_raw     = np.asarray(lum_to_white_alpha(load_ckd_tex(r"fx\fx\ui_fx_starfield.tga.ckd"), gamma=0.85, gain=1.35))
    sf_256     = sf_raw.reshape(256, 2, 256, 2, 4).max(axis=(1, 3))
    starfield  = Image.fromarray(sf_256, "RGBA")

    return dict(
        col_coach    = build_col_coach(grad_coach, 128, 256),
        col_barcode  = build_col_barcode(grad_coach, barcode, 160, 256),
        light_saber  = saber,
        dglow        = dglow,
        point_glow   = pglow,
        sparks_32    = sparks32,
        starfield    = starfield,
        bubble_soft  = bubbles.crop((0, 0, 128, 128)),
        bubble_disc  = bubbles.crop((128, 0, 256, 128)),
        bubble_ring  = bubbles.crop((0, 128, 128, 256)),
        bubble_fill  = bubbles.crop((128, 128, 256, 256)),
        spark_pin    = msparks.crop((0, 0, 128, 128)),
        spark_orb    = msparks.crop((128, 0, 256, 128)),
        spark_wave   = msparks.crop((0, 128, 128, 256)),
        spark_cross  = msparks.crop((128, 128, 256, 256)),
        circle_double= tight_crop(circles.crop((0, 0, 256, 256)), pad=2).resize((128, 128), Image.Resampling.LANCZOS),
        circle_thin  = tight_crop(circles.crop((256, 0, 512, 256)), pad=2).resize((160, 160), Image.Resampling.LANCZOS),
        x_flare      = x_flare,
        planet_rays  = planet_rays,
        speed_rays   = speed_rays,
        sunburst_12  = build_sunburst_12(256, 12, 0.46),
        jd4_curtain  = build_jd4_curtain(224, 224),
        jd4_half_sun = build_jd4_half_sunburst(256, 296, 15),
    )

# ======================= Empaquetador de Atlas (Best-Fit Shelf + Free-Rects) =======================
class Atlas:
    def __init__(self, size=1024):
        self.size = size
        self.items = {}
        self.regs = {}

    def add(self, name, img):
        self.items[name] = img.convert("RGBA")

    def pack(self):
        # MaxRects / Guillotine simple para aprovechar huecos verticales junto a sprites altos (ej. 32x256)
        order = sorted(self.items, key=lambda n: (-max(self.items[n].size), -self.items[n].width * self.items[n].height))
        pad = 3
        free = [(pad, pad, self.size - 2 * pad, self.size - 2 * pad)]
        self.img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        for n in order:
            im = self.items[n]
            rw, rh = im.width + pad, im.height + pad
            best_i = -1
            best_score = (10**9, 10**9)
            for idx, (fx, fy, fw, fh) in enumerate(free):
                if rw <= fw and rh <= fh:
                    score = (fy, fx)  # Top-left skyline preference
                    if score < best_score:
                        best_score = score
                        best_i = idx
            if best_i < 0:
                raise RuntimeError(f"Atlas {self.size}x{self.size} lleno al insertar {n} ({im.size})")
            fx, fy, fw, fh = free.pop(best_i)
            self.img.paste(im, (fx, fy))
            self.regs[n] = dict(page=0, x=fx, y=fy, w=im.width, h=im.height, rotate=0)
            # Guillotine split (elegir corte que maximice el area del rectangulo mayor restante)
            rem_w, rem_h = fw - rw, fh - rh
            if rem_w * fh > fw * rem_h:
                if rem_w > 0:
                    free.append((fx + rw, fy, rem_w, fh))
                if rem_h > 0:
                    free.append((fx, fy + rh, rw, rem_h))
            else:
                if rem_w > 0:
                    free.append((fx + rw, fy, rem_w, rh))
                if rem_h > 0:
                    free.append((fx, fy + rh, fw, rem_h))

# ======================= Motor de Curvas & Compilador LiamFX =======================
def ease(name, t):
    t = max(0.0, min(1.0, t))
    if name == "outBack":
        c = 2.1
        return 1.0 + (c + 1.0) * (t - 1.0) ** 3 + c * (t - 1.0) ** 2
    if name == "outCubic":
        return 1.0 - (1.0 - t) ** 3
    if name == "outQuad":
        return 1.0 - (1.0 - t) ** 2
    if name == "inQuad":
        return t * t
    if name == "inCubic":
        return t ** 3
    if name == "inOutSine":
        return -(math.cos(math.pi * t) - 1.0) / 2.0
    return t

def samp(v, t):
    if callable(v):
        return v(t)
    if not isinstance(v, list):
        return v
    if t <= v[0][0]:
        return v[0][1]
    for a, b in zip(v, v[1:]):
        if t <= b[0]:
            e = a[2] if len(a) > 2 else "linear"
            u = ease(e, (t - a[0]) / max(1e-6, b[0] - a[0]))
            return a[1] + (b[1] - a[1]) * u
    return v[-1][1]

def hx(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

class Anim:
    def __init__(self, dur):
        self.dur = dur
        self.layers = []

    def layer(self, region, t0=0.0, t1=None, blend="normal", x=0.0, y=0.0, sc=1.0, sx=1.0, sy=1.0, rot=0.0, a=1.0, col="#ffffff", size=None, anchor_y=0.0):
        """anchor_y: 0.0 = centro, +0.5 = anclado arriba (crece hacia abajo), -0.5 = anclado abajo."""
        self.layers.append(dict(
            region=region, t0=t0, t1=self.dur if t1 is None else t1, blend=blend,
            x=x, y=y, sc=sc, sx=sx, sy=sy, rot=rot, a=a, col=col, size=size, anchor_y=anchor_y
        ))

def build_lfx(name, atlas, anims):
    regs = atlas.regs
    slots, atts, out = [], [], {}
    for an, A in anims.items():
        tracks = []
        for L in A.layers:
            si = len(slots)
            r = regs[L["region"]]
            slots.append(dict(name=f"{an}_{L['region']}_{si}", blend=L["blend"], bone="root"))
            # Inset 0.5px UV para evitar bleeding de bordes
            u0 = (r["x"] + 0.5) / atlas.size
            u1 = (r["x"] + r["w"] - 0.5) / atlas.size
            v0 = (r["y"] + 0.5) / atlas.size
            v1 = (r["y"] + r["h"] - 0.5) / atlas.size
            ai = len(atts)
            atts.append(dict(
                slot=si, name=L["region"], region=L["region"], page=0, nv=4,
                uvs=[round(u1, 5), round(v1, 5), round(u0, 5), round(v1, 5), round(u0, 5), round(v0, 5), round(u1, 5), round(v0, 5)],
                tris=[1, 2, 3, 1, 3, 0]
            ))
            bw, bh = L["size"] if L["size"] else (r["w"], r["h"])
            ay = L.get("anchor_y", 0.0)
            fr = []
            n = int(round(A.dur * FPS))
            prev_on = None
            for k in range(n + 1):
                t = k / FPS
                on = L["t0"] - 1e-5 <= t <= L["t1"] + 1e-5
                if not on:
                    if prev_on is not False:
                        fr.append([round(t, 4), -1])
                    prev_on = False
                    continue
                prev_on = True
                s = samp(L["sc"], t)
                w = bw * s * samp(L["sx"], t)
                h = bh * s * samp(L["sy"], t)
                al = max(0.0, min(1.0, samp(L["a"], t)))
                c = hx(L["col"]) if isinstance(L["col"], str) else L["col"](t)
                rot = math.radians(samp(L["rot"], t))
                cx, cy = samp(L["x"], t), samp(L["y"], t)
                co, si_ = math.cos(rot), math.sin(rot)
                # Con anchor_y=+0.5 el borde superior queda fijo en cy y crece hacia abajo
                y_top = (0.5 - ay) * h
                y_bot = (-0.5 - ay) * h
                vs = []
                for lx, ly in ((w / 2.0, y_bot), (-w / 2.0, y_bot), (-w / 2.0, y_top), (w / 2.0, y_top)):
                    vs += [round(lx * co - ly * si_ + cx, 2), round(lx * si_ + ly * co + cy, 2)]
                fr.append([round(t, 4), ai, round(c[0], 3), round(c[1], 3), round(c[2], 3), round(al, 3)] + vs)
            if prev_on:
                fr.append([round(A.dur + 1.0 / FPS, 4), -1])
            tracks.append(dict(slot=si, frames=fr))
        out[an] = dict(duration=A.dur, tracks=tracks)
    return dict(
        format="LiamFX", version=1, name=name, source=f"ScoringFX_{name}.skel",
        spine="custom", fps=60.0, editorFps=30.0,
        pages=[dict(file=f"ScoringFX_{name}.png", w=atlas.size, h=atlas.size)],
        regions=regs, slots=slots, attachments=atts, animations=out
    )

# ======================= Coreografia 1: JUST DANCE 2014 - 2016 (1:1 UbiArt Tapes) =======================
def build_jd2014_anims():
    """Coreografia extraida directamente de animations/feedbacks/feedback_*.tape.ckd."""
    tapes = {
        k: load_tape_json(f"feedback_{k}.tape.ckd")
        for k in ("perfect", "good", "ok", "gold", "bad", "gold_bad")
    }

    def find_clip(tape, cls, actor_substr):
        actors = tape.get("ActorPaths", [])
        for c in tape["Clips"]:
            if c.get("__class") == cls:
                for ai in c.get("ActorIndices", []):
                    if ai < len(actors) and actor_substr.lower() in actors[ai].lower():
                        return c
        return None

    # Extraer curvas Bezier reales de cada .tape.ckd
    def tape_text_fns(tape_key, txt_sub, base_ubi_w, base_ubi_h, total_ticks, dur_s, y_drift_px=28.0):
        tp = tapes[tape_key]
        sz_clip = find_clip(tp, "SizeClip", txt_sub) or find_clip(tp, "ScaleClip", txt_sub)
        al_clip = find_clip(tp, "AlphaClip", txt_sub)
        tr_clip = find_clip(tp, "TranslationClip", txt_sub)
        kx = sz_clip["CurveX"]["Curve"]["Keys"]
        ky = sz_clip["CurveY"]["Curve"]["Keys"]
        ka = al_clip["Curve"]["Curve"]["Keys"]
        kt = tr_clip["CurveY"]["Curve"]["Keys"] if tr_clip else []

        def sx_fn(t):
            tk = (t / dur_s) * total_ticks
            return eval_ubi_bezier(kx, tk) / base_ubi_w

        def sy_fn(t):
            tk = (t / dur_s) * total_ticks
            return eval_ubi_bezier(ky, tk) / base_ubi_h

        def al_fn(t):
            tk = (t / dur_s) * total_ticks
            return max(0.0, min(1.0, eval_ubi_bezier(ka, tk)))

        def dy_fn(t):
            tk = (t / dur_s) * total_ticks
            return (eval_ubi_bezier(kt, tk) / 10.0) * y_drift_px if kt else 0.0

        return sx_fn, sy_fn, al_fn, dy_fn

    def tape_col_fns(tape_key, ray_sub, base_ubi_h, total_ticks, dur_s, peak_gain=1.22):
        tp = tapes[tape_key]
        pr_clip = find_clip(tp, "ProportionClip", ray_sub)
        al_clip = find_clip(tp, "AlphaClip", ray_sub)
        ky = pr_clip["CurveY"]["Curve"]["Keys"]
        ka = al_clip["Curve"]["Curve"]["Keys"]

        def sy_fn(t):
            tk = (t / dur_s) * total_ticks
            return max(0.02, eval_ubi_bezier(ky, tk) / base_ubi_h)

        def al_fn(t):
            tk = (t / dur_s) * total_ticks
            return max(0.0, min(1.0, eval_ubi_bezier(ka, tk) * peak_gain))

        return sy_fn, al_fn

    def tape_dglow_fn(tape_key, dg_sub, total_ticks, dur_s, gain=1.15):
        tp = tapes[tape_key]
        al_clip = find_clip(tp, "AlphaClip", dg_sub)
        ka = al_clip["Curve"]["Curve"]["Keys"]
        return lambda t: max(0.0, min(1.0, eval_ubi_bezier(ka, (t / dur_s) * total_ticks) * gain))

    TILT_DEG = 10.0  # Exacto: 0.174533 rad = 10.000 grados en todos los .tape.ckd!
    TOP_Y = 395.0    # Tope superior de la columna (se despliega de arriba hacia abajo hasta y=-95 debajo del texto)
    COL_H = 490.0
    anims = {}
    rng = random.Random(2014)

    def add_jd14_text(A, reg, dur, sx_fn, sy_fn, al_fn, dy_fn, size_wh, flash_col):
        # Pulso aditivo de impacto en los primeros 0.18s + texto nitido original a 10.0 grados
        A.layer(reg, 0.0, dur, "additive", x=0.0, y=dy_fn, sx=lambda t: sx_fn(t)*1.04, sy=lambda t: sy_fn(t)*1.04,
                rot=TILT_DEG, a=lambda t: al_fn(t) * max(0.0, 0.42 * (1.0 - t / 0.22)), col=flash_col, size=size_wh)
        A.layer(reg, 0.0, dur, "normal", x=0.0, y=dy_fn, sx=sx_fn, sy=sy_fn,
                rot=TILT_DEG, a=al_fn, col="#ffffff", size=size_wh)

    # -------------------- 1. PERFECT (72 ticks -> 0.88s) --------------------
    d = 0.88
    A = Anim(d)
    col_sy, col_al = tape_col_fns("perfect", "GodRays", 220.0, 72.0, d, peak_gain=1.22)
    dg_al = tape_dglow_fn("perfect", "DGlow", 72.0, d, gain=0.95)
    # Columna verde grad_v_coach + franjas verticales reales ui_com_barcode + haces ui_fx_light_saber equilibrados
    A.layer("col_coach", 0.0, d, "normal", x=0.0, y=TOP_Y, size=(375, COL_H), sy=col_sy, a=col_al, col="#44CA08", anchor_y=0.5)
    A.layer("col_barcode", 0.0, d, "additive", x=0.0, y=TOP_Y, size=(370, COL_H), sy=col_sy, a=lambda t: col_al(t)*0.52, col="#9CFF2E", anchor_y=0.5)
    # 5 haces verticales ui_fx_light_saber sutiles para dar textura laser sin quemar el contraste del texto
    for bx, bw, ph, amp in [(-144, 38, 0.0, 0.36), (-68, 46, 0.02, 0.42), (4, 32, 0.04, 0.30), (76, 48, 0.015, 0.42), (146, 34, 0.03, 0.35)]:
        A.layer("light_saber", 0.01, d - 0.06, "additive", x=bx, y=TOP_Y - 12, size=(bw, COL_H * 0.94),
                sy=lambda t, p=ph: col_sy(max(0.0, t - p)) * (0.90 + 0.10 * math.sin(t * 24.0 + p * 80.0)),
                a=lambda t, am=amp: col_al(t) * am, col="#B8FF4C", anchor_y=0.5)
    # DGlow real (ColorClip: 0.337, 0.769, 0.027 -> #56C407)
    A.layer("dglow", 0.0, d, "additive", x=0.0, y=55.0, size=(560, 500), a=dg_al, col="#56C407")
    # Starfield real (ui_fx_starfield) + micro-chispas finas ascendentes incluso fuera de los bordes de la columna (CRAZY PERFECT!)
    A.layer("starfield", 0.02, d - 0.05, "additive", x=-14.0, y=[(0.02, 75.0), (d, 145.0)], size=(430, 390),
            sc=[(0.02, 0.94), (d, 1.08)], a=[(0.02, 0.0), (0.09, 0.92), (0.52, 0.72), (d - 0.05, 0.0)], col="#E2FF9E")
    A.layer("starfield", 0.04, d - 0.08, "additive", x=18.0, y=[(0.04, 15.0), (d, 105.0)], size=(410, 360),
            rot=90.0, a=[(0.04, 0.0), (0.12, 0.78), (0.50, 0.58), (d - 0.08, 0.0)], col="#FFFFFF")
    for i in range(34):
        s = 0.01 + rng.uniform(0.0, 0.22)
        l = rng.uniform(0.36, 0.62)
        px = rng.uniform(-225, 225)
        py0 = rng.uniform(-70, 215)
        py1 = py0 + rng.uniform(50, 150)
        sz = rng.uniform(6, 15) if i % 5 != 0 else rng.uniform(14, 22)
        reg_sp = "spark_pin" if i % 4 == 0 else ("point_glow" if i % 3 == 0 else "sparks_32")
        A.layer(reg_sp, s, min(d, s + l), "additive",
                x=[(s, px), (s + l, px + rng.uniform(-18, 18))],
                y=[(s, py0, "outQuad"), (s + l, py1)],
                size=(sz, sz), sc=[(s, 0.45, "outBack"), (s + l * 0.25, 1.0), (s + l, 0.15)],
                rot=rng.uniform(0, 90),
                a=[(s, 0.0), (s + 0.05, rng.uniform(0.75, 1.0)), (s + l, 0.0)],
                col="#FFFFFF" if i % 2 == 0 else "#C4FF5C")
    sx, sy, al, dy = tape_text_fns("perfect", "Perfect_Text", 108.0, 27.0, 72.0, d, y_drift_px=26.0)
    add_jd14_text(A, "PERFECT", d, sx, sy, al, dy, (418, 128), "#B8FF54")
    anims["Perfect"] = A

    # -------------------- 2. SUPER (Puente celeste claro entre GOOD y PERFECT, 0.86s) --------------------
    d = 0.86
    A = Anim(d)
    col_sy_s, col_al_s = tape_col_fns("perfect", "GodRays", 220.0, 72.0, d, peak_gain=1.16)
    A.layer("col_coach", 0.0, d, "normal", x=0.0, y=TOP_Y, size=(350, COL_H - 10), sy=col_sy_s, a=col_al_s, col="#52D4FC", anchor_y=0.5)
    A.layer("col_barcode", 0.0, d, "additive", x=0.0, y=TOP_Y, size=(346, COL_H - 10), sy=col_sy_s, a=lambda t: col_al_s(t)*0.24, col="#C4F6FF", anchor_y=0.5)
    for bx, bw, amp in [(-115, 42, 0.26), (-32, 48, 0.30), (54, 44, 0.28), (124, 36, 0.24)]:
        A.layer("light_saber", 0.02, d - 0.08, "additive", x=bx, y=TOP_Y - 15, size=(bw, (COL_H - 20) * 0.9),
                sy=col_sy_s, a=lambda t, am=amp: col_al_s(t) * am, col="#CCF8FF", anchor_y=0.5)
    A.layer("dglow", 0.0, d, "additive", x=0.0, y=55.0, size=(520, 470),
            a=tape_dglow_fn("perfect", "DGlow", 72.0, d, gain=0.85), col="#6EE6FF")
    # Onda difusa spark_wave + 5 burbujas celestes suaves (puente natural con GOOD sin linea dura sobre el texto)
    A.layer("spark_wave", 0.01, 0.46, "additive", x=0.0, y=20.0, size=(170, 170),
            sc=[(0.01, 0.7, "outCubic"), (0.46, 2.3)], a=[(0.01, 0.42), (0.46, 0.0)], col="#C4F6FF")
    super_bubbles = [
        ("bubble_ring", -112, 122, 172, 0.01, 0.64, 0.46),
        ("spark_orb",    122,  98, 142, 0.03, 0.62, 0.50),
        ("bubble_fill",  -20,  42, 185, 0.00, 0.60, 0.26),
        ("spark_orb",     64, 178, 112, 0.05, 0.58, 0.44),
        ("bubble_ring", -138,  20, 108, 0.04, 0.55, 0.38),
    ]
    for reg_b, bx, by, bsz, t0_, life_, am in super_bubbles:
        A.layer(reg_b, t0_, min(d, t0_ + life_), "additive",
                x=[(t0_, bx * 0.82, "outQuad"), (t0_ + life_, bx * 1.08)],
                y=[(t0_, by - 16, "outQuad"), (t0_ + life_, by + 32)],
                size=(bsz, bsz), sc=[(t0_, 0.55, "outBack"), (t0_ + 0.14, 1.0), (t0_ + life_, 1.12)],
                a=[(t0_, 0.0), (t0_ + 0.08, am), (t0_ + life_ * 0.65, am * 0.75), (t0_ + life_, 0.0)],
                col="#B8F4FF")
    for i in range(20):
        s = 0.01 + rng.uniform(0.0, 0.20)
        l = rng.uniform(0.34, 0.56)
        px = rng.uniform(-190, 190)
        py0 = rng.uniform(-60, 195)
        sz = rng.uniform(13, 26) if i % 4 == 0 else rng.uniform(7, 15)
        reg_sp = "spark_cross" if i % 4 == 0 else ("point_glow" if i % 3 == 0 else "sparks_32")
        A.layer(reg_sp, s, min(d, s + l), "additive",
                x=[(s, px), (s + l, px + rng.uniform(-18, 18))],
                y=[(s, py0, "outQuad"), (s + l, py0 + rng.uniform(45, 135))],
                size=(sz, sz), sc=[(s, 0.35, "outBack"), (s + l * 0.28, 1.0), (s + l, 0.1)],
                rot=rng.uniform(0, 90),
                a=[(s, 0.0), (s + 0.06, 0.88), (s + l, 0.0)],
                col="#FFFFFF" if i % 2 == 0 else "#AEF4FF")
    sx_p, sy_p, al_p, dy_p = tape_text_fns("perfect", "Perfect_Text", 108.0, 27.0, 72.0, d, y_drift_px=25.0)
    sx_g, sy_g, _, _       = tape_text_fns("good", "Good_Text", 56.0, 28.0, 72.0, d, y_drift_px=25.0)
    add_jd14_text(A, "SUPER", d, lambda t: 0.5*(sx_p(t)+sx_g(t)), lambda t: 0.5*(sy_p(t)+sy_g(t)), al_p, dy_p, (305, 128), "#C8F8FF")
    anims["Super"] = A

    # -------------------- 3. GOOD (72 ticks -> 0.84s) --------------------
    d = 0.84
    A = Anim(d)
    col_sy_g, col_al_g = tape_col_fns("good", "GodRays", 200.0, 72.0, d, peak_gain=1.28)
    dg_al_g = tape_dglow_fn("good", "DGlow", 72.0, d, gain=0.92)
    # Color exacto de UbiArt feedback_good.tape.ckd: (0.008, 0.678, 0.827) -> #02ADD3
    A.layer("col_coach", 0.0, d, "normal", x=0.0, y=TOP_Y, size=(325, COL_H - 18), sy=col_sy_g, a=col_al_g, col="#02ADD3", anchor_y=0.5)
    A.layer("dglow", 0.0, d, "additive", x=0.0, y=55.0, size=(500, 460), a=dg_al_g, col="#02ADD3")
    # Las burbujas bokeh reales de ui_com_fx_lens_bubbles calibradas para verse traslucidas sin saturar el centro (JAZZY GOOD!)
    good_bokeh = [
        ("bubble_fill",   10,  22, 248, 0.00, 0.72, 0.34, "#10C2F4"),
        ("bubble_ring", -122, 134, 198, 0.01, 0.70, 0.54, "#24DCFF"),
        ("bubble_ring",  144,  98, 134, 0.03, 0.66, 0.62, "#2EE2FF"),
        ("bubble_fill",  -92, -10, 158, 0.02, 0.65, 0.36, "#18CEFF"),
        ("spark_orb",     88,  -6, 148, 0.04, 0.64, 0.50, "#4AE8FF"),
        ("bubble_soft",  -28, 190, 168, 0.02, 0.68, 0.30, "#14C8F5"),
        ("bubble_ring",   46, 152, 114, 0.06, 0.60, 0.46, "#58ECFF"),
        ("spark_orb",   -152,  56,  94, 0.05, 0.56, 0.44, "#40E4FF"),
    ]
    for reg_b, bx, by, bsz, t0_, life_, am, col_b in good_bokeh:
        A.layer(reg_b, t0_, min(d, t0_ + life_), "additive",
                x=[(t0_, bx * 0.78, "outCubic"), (t0_ + life_, bx * 1.10)],
                y=[(t0_, by - 16, "outCubic"), (t0_ + life_, by + 32)],
                size=(bsz, bsz),
                sc=[(t0_, 0.48, "outBack"), (t0_ + 0.14, 1.0), (t0_ + life_, 1.10)],
                a=[(t0_, 0.0), (t0_ + 0.07, am), (t0_ + life_ * 0.58, am * 0.82), (t0_ + life_, 0.0)],
                col=col_b)
    sx, sy, al, dy = tape_text_fns("good", "Good_Text", 56.0, 28.0, 72.0, d, y_drift_px=24.0)
    add_jd14_text(A, "GOOD", d, sx, sy, al, dy, (258, 128), "#5CE8FF")
    anims["Good"] = A

    # -------------------- 4. OK (48 ticks -> 0.64s) --------------------
    d = 0.64
    A = Anim(d)
    col_sy_o, col_al_o = tape_col_fns("ok", "GodRays", 200.0, 48.0, d, peak_gain=1.32)
    dg_al_o = tape_dglow_fn("ok", "DGlow", 48.0, d, gain=1.25)
    # Color exacto de UbiArt feedback_ok.tape.ckd: (0.875, 0.204, 0.976) -> #DF34F9 / #CA16E8
    A.layer("col_coach", 0.0, d, "normal", x=0.0, y=TOP_Y, size=(248, COL_H - 22), sy=col_sy_o, a=col_al_o, col="#C914E8", anchor_y=0.5)
    A.layer("dglow", 0.0, d, "additive", x=0.0, y=45.0, size=(420, 400), a=dg_al_o, col="#DF34F9")
    # Pulso suave magenta limpio detras de OK (sin anillos duros falsos, fiel a HAPPY OK / FUNKY OK)
    A.layer("bubble_soft", 0.0, 0.42, "additive", x=0.0, y=4.0, size=(220, 180),
            sc=[(0.0, 0.65, "outCubic"), (0.42, 1.35)], a=[(0.0, 0.52), (0.42, 0.0)], col="#FF58FF")
    sx, sy, al, dy = tape_text_fns("ok", "Ok_Text", 28.0, 28.0, 48.0, d, y_drift_px=15.0)
    add_jd14_text(A, "OK", d, sx, sy, al, dy, (146, 128), "#FF80FF")
    anims["Ok"] = A

    # -------------------- 5. GOLD / YEAH (72 ticks -> 0.90s) --------------------
    d = 0.90
    A = Anim(d)
    tp_gold = tapes["gold"]
    spot_al_clip = find_clip(tp_gold, "AlphaClip", "Gold_Spot")
    rays_pr_clip = find_clip(tp_gold, "ProportionClip", "Gold_GodRays")
    rays_al_clip = find_clip(tp_gold, "AlphaClip", "Gold_GodRays")
    spot_ka = spot_al_clip["Curve"]["Curve"]["Keys"]
    rays_kx = rays_pr_clip["CurveX"]["Curve"]["Keys"]
    rays_ka = rays_al_clip["Curve"]["Curve"]["Keys"]

    # Gold_Spot: columna dorada grad_v_coach brillante y sostenida (igual que panel 5 de referencia JD14!)
    A.layer("col_coach", 0.0, d, "normal", x=0.0, y=TOP_Y, size=(355, COL_H - 10),
            sy=[(0.0, 0.05, "outCubic"), (0.06, 1.0)],
            a=[(0.0, 0.72), (0.14, 0.82), (0.38, 0.62), (0.68, 0.0)],
            col="#FFBE10", anchor_y=0.5)
    # Gold_GodRays: abanico radial de 12 rayos que hace slam de 540->360 (1.5x -> 1.0x) igual que el .tape.ckd!
    A.layer("sunburst_12", 0.0, d, "additive", x=0.0, y=22.0, size=(660, 660),
            sc=lambda t: eval_ubi_bezier(rays_kx, (t / d) * 72.0) / 360.0,
            rot=[(0.0, -3.0), (d, 10.0)],
            a=[(0.0, 0.55), (0.14, 0.90), (0.42, 0.68), (0.72, 0.0)],
            col="#FFD854")
    # Capa secundaria con x_flare + onda suave spark_wave (sin anillo duro sobre YEAH)
    A.layer("x_flare", 0.0, 0.55, "additive", x=0.0, y=10.0, size=(500, 500),
            sc=[(0.0, 0.7, "outCubic"), (0.55, 1.40)], a=[(0.0, 0.78), (0.55, 0.0)], col="#FFE888")
    A.layer("dglow", 0.0, d, "additive", x=0.0, y=25.0, size=(540, 500),
            a=tape_dglow_fn("gold", "DGlow", 72.0, d, gain=1.15), col="#FF9800")
    A.layer("spark_wave", 0.01, 0.44, "additive", x=0.0, y=10.0, size=(190, 190),
            sc=[(0.01, 0.6, "outCubic"), (0.44, 2.7)], a=[(0.01, 0.45), (0.44, 0.0)], col="#FFE684")
    # FXClip SERIALIZED:be64fcd7 -> explosion de chispas y destellos dorados
    for i in range(26):
        s = 0.01 + rng.uniform(0.0, 0.14)
        l = rng.uniform(0.38, 0.64)
        ang = rng.uniform(0, 2 * math.pi)
        r0, r1 = rng.uniform(25, 70), rng.uniform(160, 310)
        sz = rng.uniform(14, 28) if i % 3 == 0 else rng.uniform(9, 18)
        reg_sp = "spark_cross" if i % 3 == 0 else ("point_glow" if i % 2 == 0 else "sparks_32")
        A.layer(reg_sp, s, min(d, s + l), "additive",
                x=[(s, math.cos(ang) * r0, "outCubic"), (s + l, math.cos(ang) * r1)],
                y=[(s, math.sin(ang) * r0 + 10, "outCubic"), (s + l, math.sin(ang) * r1 + 25)],
                size=(sz, sz), sc=[(s, 0.4, "outBack"), (s + 0.1, 1.0), (s + l, 0.0)],
                rot=rng.uniform(0, 180),
                a=[(s, 0.0), (s + 0.05, 1.0), (s + l, 0.0)],
                col="#FFF8C8" if i % 2 == 0 else "#FFD038")
    sx, sy, _, dy = tape_text_fns("gold", "Yeah_Text", 64.0, 32.0, 72.0, d, y_drift_px=18.0)
    al_yeah = lambda t: 1.0 if t <= 0.36 else max(0.0, 1.0 - ((t - 0.36) / (d - 0.36)) ** 1.35)
    add_jd14_text(A, "YEAH", d, sx, sy, al_yeah, dy, (315, 152), "#FFE87C")
    anims["Gold"] = A

    # -------------------- 6. BAD & GOLDMISS (48 ticks -> 0.62s, SIN columna, 10.0 grados!) --------------------
    for an_name, tp_key, txt_sub, reg_name, glow_hex, dg_gain in [
        ("Bad",      "bad",      "Bad_Text", "MISS",     "#C40606", 2.2),
        ("GoldMiss", "gold_bad", "Bad_Gold", "GOLDMISS", "#FF7800", 1.7),
    ]:
        d = 0.62
        A = Anim(d)
        # En feedback_bad.tape.ckd NO hay columna GodRays: solo un DGlow sutil detras de la X inclinada 10 grados!
        A.layer("dglow", 0.0, d, "additive", x=0.0, y=0.0, size=(310, 310),
                a=tape_dglow_fn(tp_key, "DGlow", 48.0, d, gain=dg_gain), col=glow_hex)
        sx, sy, al, dy = tape_text_fns(tp_key, txt_sub, 28.0, 28.0, 48.0, d, y_drift_px=20.0)
        add_jd14_text(A, reg_name, d, sx, sy, al, dy, (124, 124), glow_hex)
        anims[an_name] = A

    return anims

# ======================= Coreografia 2: JUST DANCE 4 (Cortina Izquierda + Medio-Sol + Bokeh UbiArt) =======================
def build_jd4_anims():
    """Coreografia fiel a las capturas reales del HUD de Just Dance 4:
    linea divisoria vertical izquierda nitida, cortina unilateral que se desvanece a la derecha,
    medio-sol verde-lima a la izquierda de PERFECT, burbujas UbiArt alrededor de GOOD,
    variante celeste claro en SUPER, y cruz X horizontal sin cortina."""
    rng = random.Random(2012)
    anims = {}

    def add_jd4_curtain(A, dur, x_left, width, height, col_main, col_bright, alpha_peak=0.88):
        cx = x_left + width * 0.5
        A.layer("jd4_curtain", 0.0, dur, "normal", x=cx, y=28.0, size=(width, height),
                sx=[(0.0, 0.15, "outCubic"), (0.08, 1.0)],
                a=[(0.0, 0.0), (0.05, alpha_peak), (0.34, alpha_peak * 0.92), (dur, 0.0)],
                col=col_main)
        A.layer("jd4_curtain", 0.0, dur * 0.85, "additive", x=x_left + width * 0.28, y=28.0, size=(width * 0.56, height * 0.92),
                sx=[(0.0, 0.1, "outCubic"), (0.08, 1.0)],
                a=[(0.0, 0.0), (0.06, alpha_peak * 0.42), (dur * 0.85, 0.0)],
                col=col_bright)

    def add_jd4_text(A, reg, dur, size_wh, flash_col, slam=1.34):
        sc = [(0.0, slam, "outCubic"), (0.09, 0.97, "outQuad"), (0.16, 1.0), (dur, 1.02)]
        al = [(0.0, 0.0), (0.03, 1.0), (dur * 0.58, 1.0), (dur, 0.0)]
        xx = [(0.0, -8.0, "outCubic"), (0.14, 0.0), (dur, 4.0)]
        A.layer(reg, 0.0, 0.24, "additive", x=xx, y=0.0, size=size_wh,
                sc=[(0.0, slam * 1.06, "outCubic"), (0.24, 1.02)],
                a=[(0.0, 0.55), (0.24, 0.0)], col=flash_col)
        A.layer(reg, 0.0, dur, "normal", x=xx, y=0.0, size=size_wh, sc=sc, a=al, col="#ffffff")

    # -------------------- 1. PERFECT (HAPPY | PERFECT / JAZZY | PERFECT) --------------------
    d = 0.86
    A = Anim(d)
    X_DIV = -212.0  # Justo a la izquierda de la 'P' de PERFECT
    add_jd4_curtain(A, d, X_DIV, 490, 390, "#6FD408", "#B8F830", alpha_peak=0.78)
    # Medio-sol icónico anclado sobre la linea divisoria izquierda irradiando 180 grados hacia la derecha (sin quemar la 'P')!
    A.layer("jd4_half_sun", 0.0, d, "additive", x=X_DIV + 195.0, y=14.0, size=(410, 430),
            sx=[(0.0, 0.35, "outBack"), (0.12, 1.0), (d, 1.12)],
            sy=[(0.0, 0.45, "outBack"), (0.12, 1.0), (d, 1.08)],
            a=[(0.0, 0.0), (0.05, 0.82), (0.38, 0.72), (d, 0.0)], col="#ADFA24")
    A.layer("dglow", 0.0, d * 0.85, "additive", x=X_DIV + 85.0, y=10.0, size=(310, 300),
            a=[(0.0, 0.0), (0.06, 0.30), (d * 0.85, 0.0)], col="#CEFF48")
    # Puntitos brillantes dentro del nucleo solar izquierdo y alrededor de PERFECT
    for i in range(20):
        s = 0.01 + rng.uniform(0.0, 0.18)
        l = rng.uniform(0.32, 0.55)
        ang = rng.uniform(-math.pi * 0.44, math.pi * 0.44)
        r0 = rng.uniform(16, 70)
        r1 = r0 + rng.uniform(55, 165)
        sz = rng.uniform(8, 18)
        reg_sp = "spark_pin" if i % 3 == 0 else "sparks_32"
        A.layer(reg_sp, s, min(d, s + l), "additive",
                x=[(s, X_DIV + 14 + math.cos(ang) * r0, "outQuad"), (s + l, X_DIV + 14 + math.cos(ang) * r1)],
                y=[(s, 10 + math.sin(ang) * r0, "outQuad"), (s + l, 10 + math.sin(ang) * r1)],
                size=(sz, sz), sc=[(s, 0.4), (s + 0.08, 1.0), (s + l, 0.1)],
                a=[(s, 0.0), (s + 0.05, 0.88), (s + l, 0.0)],
                col="#FFFFFF" if i % 2 == 0 else "#E8FF78")
    add_jd4_text(A, "PERFECT", d, (425, 112), "#C8FF3E", slam=1.32)
    anims["Perfect"] = A

    # -------------------- 2. SUPER (Variante celeste claro entre GOOD y PERFECT) --------------------
    d = 0.84
    A = Anim(d)
    X_DIV = -172.0
    add_jd4_curtain(A, d, X_DIV, 440, 375, "#4CCCF8", "#A8F0FF", alpha_peak=0.76)
    # Medio abanico celeste delicado + burbujas bokeh celestes + destellos (manteniendo la 'S' 100% legible)
    A.layer("jd4_half_sun", 0.0, d * 0.9, "additive", x=X_DIV + 165.0, y=12.0, size=(345, 360),
            sx=[(0.0, 0.3, "outCubic"), (0.14, 0.95), (d * 0.9, 1.08)],
            a=[(0.0, 0.0), (0.07, 0.40), (0.36, 0.32), (d * 0.9, 0.0)], col="#A6F0FF")
    for reg_b, ox_, oy_, bsz, t0_, life_, am in [
        ("bubble_soft",  70,  34, 185, 0.00, 0.62, 0.28),
        ("bubble_ring", 118,  54, 152, 0.02, 0.64, 0.54),
        ("spark_orb",   225,  22, 138, 0.04, 0.60, 0.56),
        ("bubble_fill", 165, -36, 148, 0.03, 0.58, 0.38),
        ("bubble_ring", 285,  48, 108, 0.05, 0.55, 0.48),
    ]:
        A.layer(reg_b, t0_, min(d, t0_ + life_), "additive",
                x=[(t0_, X_DIV + ox_ * 0.85, "outQuad"), (t0_ + life_, X_DIV + ox_ * 1.08)],
                y=[(t0_, oy_ - 10, "outQuad"), (t0_ + life_, oy_ + 22)],
                size=(bsz, bsz), sc=[(t0_, 0.5, "outBack"), (t0_ + 0.14, 1.0), (t0_ + life_, 1.1)],
                a=[(t0_, 0.0), (t0_ + 0.07, am), (t0_ + life_, 0.0)], col="#C0F6FF")
    for i in range(14):
        s = 0.02 + rng.uniform(0.0, 0.16)
        l = rng.uniform(0.32, 0.52)
        px = rng.uniform(X_DIV + 15, X_DIV + 340)
        py = rng.uniform(-55, 85)
        sz = rng.uniform(12, 26)
        A.layer("spark_cross" if i % 3 == 0 else "sparks_32", s, min(d, s + l), "additive",
                x=[(s, px), (s + l, px + rng.uniform(10, 40))],
                y=[(s, py), (s + l, py + rng.uniform(25, 70))],
                size=(sz, sz), sc=[(s, 0.35), (s + 0.08, 1.0), (s + l, 0.0)],
                rot=rng.uniform(0, 90), a=[(s, 0.0), (s + 0.05, 0.9), (s + l, 0.0)], col="#EEFCFF")
    add_jd4_text(A, "SUPER", d, (328, 110), "#BFF6FF", slam=1.34)
    anims["Super"] = A

    # -------------------- 3. GOOD (FUNKY | GOOD) --------------------
    d = 0.82
    A = Anim(d)
    X_DIV = -162.0
    add_jd4_curtain(A, d, X_DIV, 415, 365, "#127CE6", "#58C8FF", alpha_peak=0.84)
    # Nucleo luminoso cian arriba-izquierda detras de 'GO' + racimo de burbujas bokeh UbiArt a la derecha de la linea!
    A.layer("bubble_soft", 0.0, 0.66, "additive", x=X_DIV + 92.0, y=38.0, size=(240, 220),
            sc=[(0.0, 0.6, "outCubic"), (0.66, 1.15)], a=[(0.0, 0.0), (0.06, 0.85), (0.66, 0.0)], col="#7CE2FF")
    jd4_bubbles = [
        ("bubble_ring",  88,  46, 175, 0.00, 0.68, 0.82, "#66DCFF"),
        ("bubble_fill", 168,  64, 152, 0.02, 0.66, 0.65, "#48C8FF"),
        ("bubble_ring", 248,  26, 162, 0.03, 0.66, 0.76, "#58D4FF"),
        ("bubble_ring", 132, -38, 144, 0.02, 0.62, 0.72, "#4CC8FF"),
        ("spark_orb",   215, -34, 118, 0.04, 0.60, 0.68, "#7CE4FF"),
        ("bubble_fill",  66, -24, 115, 0.01, 0.58, 0.58, "#38B8FF"),
        ("bubble_ring", 296,  62, 104, 0.05, 0.56, 0.58, "#68D8FF"),
    ]
    for reg_b, ox_, oy_, bsz, t0_, life_, am, col_b in jd4_bubbles:
        A.layer(reg_b, t0_, min(d, t0_ + life_), "additive",
                x=[(t0_, X_DIV + ox_ * 0.84, "outCubic"), (t0_ + life_, X_DIV + ox_ * 1.08)],
                y=[(t0_, oy_ - 10, "outCubic"), (t0_ + life_, oy_ + 22)],
                size=(bsz, bsz), sc=[(t0_, 0.48, "outBack"), (t0_ + 0.13, 1.0), (t0_ + life_, 1.10)],
                a=[(t0_, 0.0), (t0_ + 0.06, am), (t0_ + life_ * 0.6, am * 0.78), (t0_ + life_, 0.0)],
                col=col_b)
    add_jd4_text(A, "GOOD", d, (295, 110), "#68D4FF", slam=1.35)
    anims["Good"] = A

    # -------------------- 4. OK (JAZZY | OK / CRAZY | OK) --------------------
    d = 0.64
    A = Anim(d)
    X_DIV = -112.0
    add_jd4_curtain(A, d, X_DIV, 330, 350, "#9A12F0", "#DF58FF", alpha_peak=0.88)
    A.layer("dglow", 0.0, d * 0.85, "additive", x=X_DIV + 95.0, y=8.0, size=(260, 240),
            a=[(0.0, 0.0), (0.05, 0.48), (d * 0.85, 0.0)], col="#D848FF")
    add_jd4_text(A, "OK", d, (162, 108), "#E878FF", slam=1.30)
    anims["Ok"] = A

    # -------------------- 5. GOLD / YEAH --------------------
    d = 0.88
    A = Anim(d)
    X_DIV = -172.0
    add_jd4_curtain(A, d, X_DIV, 450, 380, "#F09C00", "#FFE468", alpha_peak=0.85)
    A.layer("sunburst_12", 0.0, d, "additive", x=0.0, y=8.0, size=(620, 620),
            sc=[(0.0, 0.55, "outBack"), (0.14, 1.0), (d, 1.22)],
            rot=[(0.0, 0.0), (d, 24.0)],
            a=[(0.0, 0.0), (0.06, 0.92), (0.42, 0.78), (d, 0.0)], col="#FFD646")
    A.layer("x_flare", 0.0, 0.52, "additive", x=0.0, y=4.0, size=(480, 480),
            sc=[(0.0, 0.65, "outCubic"), (0.52, 1.38)], a=[(0.0, 0.85), (0.52, 0.0)], col="#FFF098")
    A.layer("circle_thin", 0.01, 0.50, "additive", x=0.0, y=4.0, size=(170, 170),
            sc=[(0.01, 0.6, "outCubic"), (0.50, 2.9)], a=[(0.01, 0.8), (0.50, 0.0)], col="#FFE680")
    for i in range(22):
        s = 0.01 + rng.uniform(0.0, 0.14)
        l = rng.uniform(0.35, 0.60)
        ang = rng.uniform(0, 2 * math.pi)
        r0, r1 = rng.uniform(25, 65), rng.uniform(150, 290)
        sz = rng.uniform(14, 32)
        A.layer("spark_cross" if i % 3 == 0 else "sparks_32", s, min(d, s + l), "additive",
                x=[(s, math.cos(ang) * r0, "outCubic"), (s + l, math.cos(ang) * r1)],
                y=[(s, math.sin(ang) * r0, "outCubic"), (s + l, math.sin(ang) * r1)],
                size=(sz, sz), sc=[(s, 0.4), (s + 0.08, 1.0), (s + l, 0.0)],
                rot=rng.uniform(0, 180), a=[(s, 0.0), (s + 0.05, 1.0), (s + l, 0.0)], col="#FFF6C0")
    add_jd4_text(A, "YEAH", d, (305, 114), "#FFE474", slam=1.45)
    anims["Gold"] = A

    # -------------------- 6. BAD & GOLDMISS (HAPPY | X: horizontal 0 grados, sin cortina!) --------------------
    for an_name, reg_name, glow_hex in [("Bad", "MISS", "#E01434"), ("GoldMiss", "GOLDMISS", "#FFA800")]:
        d = 0.58
        A = Anim(d)
        A.layer("dglow", 0.0, d * 0.85, "additive", x=0.0, y=0.0, size=(240, 220),
                a=[(0.0, 0.0), (0.05, 0.34), (d * 0.85, 0.0)], col=glow_hex)
        shake = [(0.0, 0.0), (0.05, -8.0), (0.10, 6.0), (0.15, -3.0), (0.20, 0.0)]
        sc = [(0.0, 1.42, "outCubic"), (0.09, 0.96, "outQuad"), (0.15, 1.0), (d, 1.0)]
        al = [(0.0, 0.0), (0.02, 1.0), (0.36, 1.0), (d, 0.0)]
        A.layer(reg_name, 0.0, d, "normal", x=shake, y=0.0, size=(122, 110), sc=sc, a=al, col="#ffffff")
        anims[an_name] = A

    return anims

# ======================= Coreografia 3: CUSTOM SCRATCH (Plantilla Limpia Desde 0 con Banco UbiArt) =======================
def build_scratch_anims():
    """Plantilla neutra en blanco puro con todas las regiones FX reales de UbiArt en el atlas,
    ideal para personalizar colores, fuentes y capas desde cero en LiamToolScores2Unity."""
    anims = {}
    specs = [
        ("Perfect", "PERFECT", (415, 120), "#6EFF46", 0.85, True),
        ("Super",   "SUPER",   (315, 116), "#88F0FF", 0.82, True),
        ("Good",    "GOOD",    (275, 116), "#24B8FF", 0.78, False),
        ("Ok",      "OK",      (155, 114), "#D838FF", 0.62, False),
        ("Gold",    "YEAH",    (305, 124), "#FFC824", 0.88, True),
        ("Bad",     "MISS",    (120, 120), "#FF2E4C", 0.58, False),
        ("GoldMiss","GOLDMISS",(120, 120), "#FFA814", 0.58, False),
    ]
    rng = random.Random(77)
    for an, reg, wh, col, d, with_sparks in specs:
        A = Anim(d)
        A.layer("dglow", 0.0, d, "additive", x=0.0, y=0.0, size=(420, 320),
                sc=[(0.0, 0.6, "outCubic"), (d, 1.25)], a=[(0.0, 0.0), (0.08, 0.55), (d, 0.0)], col=col)
        if an in ("Perfect", "Gold"):
            A.layer("circle_thin", 0.01, 0.50, "additive", size=(160, 160),
                    sc=[(0.01, 0.6, "outCubic"), (0.50, 2.7)], a=[(0.01, 0.75), (0.50, 0.0)], col=col)
        if an == "Good":
            for i in range(6):
                ang = i * math.pi / 3.0 + 0.3
                A.layer("bubble_ring", 0.02, 0.62, "additive",
                        x=[(0.02, math.cos(ang)*55, "outCubic"), (0.62, math.cos(ang)*145)],
                        y=[(0.02, math.sin(ang)*40, "outCubic"), (0.62, math.sin(ang)*110 + 25)],
                        size=(130, 130), sc=[(0.02, 0.5), (0.62, 1.05)],
                        a=[(0.02, 0.0), (0.10, 0.7), (0.62, 0.0)], col=col)
        if with_sparks:
            for i in range(16):
                s = 0.01 + rng.uniform(0.0, 0.14)
                l = rng.uniform(0.32, 0.52)
                ang = rng.uniform(0, 2 * math.pi)
                r1 = rng.uniform(120, 240)
                sz = rng.uniform(14, 28)
                A.layer("spark_cross" if i % 2 == 0 else "sparks_32", s, min(d, s + l), "additive",
                        x=[(s, math.cos(ang)*30, "outCubic"), (s + l, math.cos(ang)*r1)],
                        y=[(s, math.sin(ang)*25, "outCubic"), (s + l, math.sin(ang)*r1)],
                        size=(sz, sz), sc=[(s, 0.4), (s + 0.08, 1.0), (s + l, 0.0)],
                        a=[(s, 0.0), (s + 0.05, 0.95), (s + l, 0.0)], col=col)
        sc = [(0.0, 1.36, "outCubic"), (0.10, 0.97, "outQuad"), (0.18, 1.0), (d, 1.02)]
        al = [(0.0, 0.0), (0.03, 1.0), (d * 0.62, 1.0), (d, 0.0)]
        A.layer(reg, 0.0, d, "normal", size=wh, sc=sc, a=al, col="#ffffff")
        anims[an] = A
    return anims

# ======================= Miniatura Renderizada con el Motor Real =======================
def make_thumbnail(lfx_path, png_path, title, badge_rgb):
    import preview_lfx as P
    th = Image.new("RGBA", (256, 256), (10, 8, 22, 255))
    # Cuadricula 2x2 con Perfect, Super, Good y Gold reales renderizados en su frame pico!
    quads = [("Perfect", 0.16, (0, 28)), ("Super", 0.16, (128, 28)), ("Good", 0.16, (0, 142)), ("Gold", 0.16, (128, 142))]
    for an, t_sample, (qx, qy) in quads:
        im = P.render(lfx_path, png_path, an, t_sample, W=540, H=480, bg=(12, 10, 24)).convert("RGBA")
        im = im.resize((128, 114), Image.Resampling.LANCZOS)
        th.paste(im, (qx, qy))
    dr = ImageDraw.Draw(th)
    dr.rectangle([0, 0, 256, 28], fill=badge_rgb + (235,))
    dr.line([(128, 28), (128, 256)], fill=(255, 255, 255, 35), width=1)
    dr.line([(0, 142), (256, 142)], fill=(255, 255, 255, 35), width=1)
    dr.text((128, 14), title, font=ImageFont.truetype(F_BOLD, 19), fill=(255, 255, 255, 255), anchor="mm")
    return th

# ======================= Construccion y Sincronizacion de Packs =======================
def build_all():
    fx_bank = load_real_fx_bank()

    # 1. Textos reales JD 2014-2016 + SUPER celeste claro
    t14 = dict(
        PERFECT  = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_perfect_text.png"), pad=3),
        SUPER    = make_jd14_super_sprite(),
        GOOD     = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_good_text.png"), pad=3),
        OK       = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_ok_text.png"), pad=3),
        YEAH     = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_gold_text.png"), pad=3),
        MISS     = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_bad_text.png"), pad=3),
        GOLDMISS = tight_crop(load_png_tex(r"textures\ui_hud_wdg_feedback_bad_gold.png"), pad=3),
    )
    os.makedirs(REC_14, exist_ok=True)
    for fn, im in [
        ("01_PERFECT_Original_HD.png", t14["PERFECT"]),
        ("02_SUPER_Celeste_Custom_HD.png", t14["SUPER"]),
        ("03_GOOD_Original_HD.png", t14["GOOD"]),
        ("04_OK_Original_HD.png", t14["OK"]),
        ("05_MISS_Original_HD.png", t14["MISS"]),
        ("06_YEAH_Original_HD.png", t14["YEAH"]),
        ("07_GOLDMISS_Original_HD.png", t14["GOLDMISS"]),
    ]:
        im.save(os.path.join(REC_14, fn))
    fx_out_14 = os.path.join(REC_14, "FX_Sprites")
    os.makedirs(fx_out_14, exist_ok=True)
    for k, im in fx_bank.items():
        im.save(os.path.join(fx_out_14, f"{k}.png"))

    # 2. Textos fieles JD 4 + SUPER celeste claro
    t4 = dict(
        PERFECT  = make_jd4_text_sprite("PERFECT", (172, 255, 28), (215, 255, 95)),
        SUPER    = make_jd4_text_sprite("SUPER",   (125, 240, 255), (185, 250, 255)),
        GOOD     = make_jd4_text_sprite("GOOD",    (28, 168, 255), (90, 205, 255)),
        OK       = make_jd4_text_sprite("OK",      (192, 36, 255), (225, 105, 255)),
        YEAH     = make_jd4_text_sprite("YEAH",    (255, 188, 16), (255, 228, 95)),
        MISS     = make_jd4_cross_sprite((225, 18, 50), (255, 75, 100)),
        GOLDMISS = make_jd4_cross_sprite((255, 168, 0), (255, 215, 75)),
    )
    os.makedirs(REC_4, exist_ok=True)
    for k, im in t4.items():
        im.save(os.path.join(REC_4, f"JD4_{k}.png"))

    # 3. Textos neutros blancos para Custom_Scratch
    t_scr = dict(
        PERFECT  = make_jd4_text_sprite("PERFECT", (255, 255, 255), (255, 255, 255)),
        SUPER    = make_jd4_text_sprite("SUPER",   (255, 255, 255), (255, 255, 255)),
        GOOD     = make_jd4_text_sprite("GOOD",    (255, 255, 255), (255, 255, 255)),
        OK       = make_jd4_text_sprite("OK",      (255, 255, 255), (255, 255, 255)),
        YEAH     = make_jd4_text_sprite("YEAH",    (255, 255, 255), (255, 255, 255)),
        MISS     = make_jd4_cross_sprite((255, 255, 255), (255, 255, 255)),
        GOLDMISS = make_jd4_cross_sprite((255, 255, 255), (255, 255, 255)),
    )

    packs = [
        ("JD2014_2016",    t14,   build_jd2014_anims(),  "JD 2014 - 2016", (18, 128, 178), "classic"),
        ("JD4",            t4,    build_jd4_anims(),     "JUST DANCE 4",   (128, 32, 195), "classic"),
        ("Custom_Scratch", t_scr, build_scratch_anims(), "CUSTOM STUDIO",  (16, 145, 115), "custom"),
    ]

    for name, texts, anims, title, badge_rgb, grp in packs:
        at = Atlas(1024)
        for k, im in texts.items():
            at.add(k, im)
        for k, im in fx_bank.items():
            at.add(k, im)
        at.pack()
        lfx = build_lfx(name, at, anims)

        for base in (REPO_LIB, MOD_LIB):
            out_dir = os.path.join(base, name)
            os.makedirs(out_dir, exist_ok=True)
            png_p = os.path.join(out_dir, f"ScoringFX_{name}.png")
            lfx_p = os.path.join(out_dir, f"{name}.lfx.json")
            atl_p = os.path.join(out_dir, f"ScoringFX_{name}.atlas")
            skl_p = os.path.join(out_dir, f"ScoringFX_{name}.skel")
            thm_p = os.path.join(out_dir, f"ScoringFX_Thumbnail_{name}.png")

            at.img.save(png_p)
            with open(lfx_p, "w", encoding="utf-8") as fh:
                json.dump(lfx, fh, separators=(",", ":"))
            al_lines = [f"ScoringFX_{name}.png", f"size:{at.size},{at.size}", "filter:Linear,Linear"]
            for rn, rr in at.regs.items():
                al_lines += [rn, f"bounds:{rr['x']},{rr['y']},{rr['w']},{rr['h']}"]
            with open(atl_p, "w", encoding="utf-8") as fh:
                fh.write("\n".join(al_lines) + "\n")
            shutil.copy2(os.path.join(BASIC_DIR, "ScoringFX_Basic.skel"), skl_p)

            th = make_thumbnail(lfx_p, png_p, title, badge_rgb)
            th.save(thm_p)

            idx_p = os.path.join(base, "library_index.json")
            if os.path.exists(idx_p):
                idx = json.load(open(idx_p, encoding="utf-8"))
                idx = [i for i in idx if i["name"] != name]
                idx.insert(0, dict(
                    name=name,
                    file=f"{name}/{name}.lfx.json",
                    animations=sorted(lfx["animations"].keys()),
                    group=grp,
                    thumb=f"{name}/ScoringFX_Thumbnail_{name}.png"
                ))
                with open(idx_p, "w", encoding="utf-8") as fh:
                    json.dump(idx, fh, indent=2)

        kb = os.path.getsize(os.path.join(REPO_LIB, name, f"{name}.lfx.json")) // 1024
        print(f"[OK] {name:16} regions={len(at.regs):2d} lfx={kb:4d} KB")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    build_all()
