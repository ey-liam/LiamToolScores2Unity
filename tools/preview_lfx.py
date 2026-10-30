"""preview_lfx.py - Renderizador de verificacion visual con mezcla ALFA NORMAL estricta
(identica a JDSpineMesh en Unity UI Toolkit de Just Dance Next, donde NO hay mezcla aditiva).
"""
import json, sys, os
from PIL import Image, ImageDraw
import numpy as np

def render(lfx_path, png_path, anim, t, W=900, H=700, bg=(18, 12, 34)):
    d = json.load(open(lfx_path, encoding="utf-8"))
    atlas = Image.open(png_path).convert("RGBA")
    S_w, S_h = atlas.size
    A = d["animations"][anim]
    canvas = np.zeros((H, W, 3), np.float32)
    canvas[:] = bg
    order = sorted(A["tracks"], key=lambda tr: tr["slot"])
    for tr in order:
        fr = tr["frames"]
        cur = None
        for f in fr:
            if f[0] <= t + 1e-6:
                cur = f
            else:
                break
        if cur is None or cur[1] < 0:
            continue
        att = d["attachments"][cur[1]]
        r, g, b, a = cur[2:6]
        v = cur[6:14]
        u = att["uvs"]
        x0, x1 = min(u[0], u[2]) * S_w, max(u[0], u[2]) * S_w
        y0, y1 = min(u[1], u[5]) * S_h, max(u[1], u[5]) * S_h
        tex = atlas.crop((max(0, int(round(x0))), max(0, int(round(y0))), min(S_w, int(round(x1))), min(S_h, int(round(y1)))))
        w_, h_ = tex.size
        if w_ < 1 or h_ < 1:
            continue
        # vertices Spine: v0 RB, v1 LB, v2 LT, v3 RT (world y-up)
        P = [(v[2 * i] + W / 2, H / 2 - v[2 * i + 1]) for i in range(4)]
        ax, ay = P[2]
        bx, by = P[3]
        cx, cy = P[1]
        m = np.array([[(bx - ax) / w_, (cx - ax) / h_], [(by - ay) / w_, (cy - ay) / h_]])
        det = np.linalg.det(m)
        if abs(det) < 1e-9:
            continue
        inv = np.linalg.inv(m)
        off = -inv @ np.array([ax, ay])
        layer = tex.transform(
            (W, H),
            Image.Transform.AFFINE,
            (inv[0, 0], inv[0, 1], off[0], inv[1, 0], inv[1, 1], off[1]),
            Image.Resampling.BILINEAR,
        )
        arr = np.asarray(layer, np.float32) / 255.0
        al = arr[..., 3:4] * a
        col = arr[..., :3] * np.array([r, g, b], dtype=np.float32)
        # Mezcla ALFA NORMAL estricta (UI Toolkit JDSpineMesh ignora Additive!)
        canvas = canvas * (1.0 - al) + col * 255.0 * al
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def sheet(name, anims, times, out, base=r"C:\Users\liamc\Documents\LiamToolScores2Unity\Library"):
    lp = os.path.join(base, name, f"{name}.lfx.json")
    pp = os.path.join(base, name, f"ScoringFX_{name}.png")
    tw, th = 360, 280
    sh = Image.new("RGB", (tw * len(times), th * len(anims)))
    for j, an in enumerate(anims):
        for i, t in enumerate(times):
            im = render(lp, pp, an, t).resize((tw, th), Image.Resampling.LANCZOS)
            sh.paste(im, (i * tw, j * th))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sh.save(out)
    print(f"[SHEET] {out}")


def strip6(name, out, t_peak=0.22, base=r"C:\Users\liamc\Documents\LiamToolScores2Unity\Library"):
    lp = os.path.join(base, name, f"{name}.lfx.json")
    pp = os.path.join(base, name, f"ScoringFX_{name}.png")
    order = ["Bad", "Ok", "Good", "Super", "Perfect", "Gold"]
    pw, ph = 280, 320
    st = Image.new("RGB", (pw * len(order), ph))
    for i, an in enumerate(order):
        t = 0.24 if an in ("Perfect", "Super", "Gold") else t_peak
        im = render(lp, pp, an, t, W=760, H=860, bg=(14, 10, 28)).resize((pw, ph), Image.Resampling.LANCZOS)
        st.paste(im, (i * pw, 0))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    st.save(out)
    print(f"[STRIP] {out}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all-docs":
        docs = r"C:\Users\liamc\Documents\LiamToolScores2Unity\docs"
        anims = ["Perfect", "Super", "Good", "Ok", "Bad", "Gold", "GoldMiss"]
        times = [0.10, 0.22, 0.32, 0.50]
        sheet("JD2014_2016", anims, times, os.path.join(docs, "sheet14a.png"))
        sheet("JD4", anims, times, os.path.join(docs, "sheet4a.png"))
        strip6("JD2014_2016", os.path.join(docs, "strip_jd2014_6panel.png"))
        strip6("JD4", os.path.join(docs, "strip_jd4_6panel.png"))
    else:
        name = sys.argv[1]
        anims = sys.argv[2].split(",")
        times = [float(x) for x in sys.argv[3].split(",")]
        sheet(name, anims, times, sys.argv[4])
