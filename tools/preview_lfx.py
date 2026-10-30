import json, sys, math, os
from PIL import Image, ImageChops, ImageDraw
import numpy as np

def render(lfx_path, png_path, anim, t, W=900, H=700, bg=(18, 12, 34)):
    d = json.load(open(lfx_path)); atlas = Image.open(png_path).convert("RGBA"); S = atlas.size[0]
    A = d["animations"][anim]; canvas = np.zeros((H, W, 3), np.float32); canvas[:] = bg
    order = sorted(A["tracks"], key=lambda tr: tr["slot"])
    for tr in order:
        fr = tr["frames"]; cur = None
        for f in fr:
            if f[0] <= t + 1e-6: cur = f
            else: break
        if cur is None or cur[1] < 0: continue
        att = d["attachments"][cur[1]]; r, g, b, a = cur[2:6]; v = cur[6:14]
        u = att["uvs"]; x0, x1 = u[2] * S, u[0] * S; y0, y1 = u[5] * S, u[1] * S
        tex = atlas.crop((int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))))
        w_, h_ = tex.size
        # vertices: v0 RB, v1 LB, v2 LT, v3 RT  (world y-up). mapear tex (w,h) -> pantalla
        P = [(v[2 * i] + W / 2, H / 2 - v[2 * i + 1]) for i in range(4)]
        # pantalla: LT=P2 -> (0,0); RT=P3 -> (w,0); LB=P1 -> (0,h)
        ax, ay = P[2]; bx, by = P[3]; cx, cy = P[1]
        # inversa: dest(x,y) = LT + (x/w)*(RT-LT) + (y/h)*(LB-LT) ; PIL AFFINE necesita map dest->src
        m = np.array([[(bx - ax) / w_, (cx - ax) / h_], [(by - ay) / w_, (cy - ay) / h_]]); det = np.linalg.det(m)
        if abs(det) < 1e-9: continue
        inv = np.linalg.inv(m); off = -inv @ np.array([ax, ay])
        layer = tex.transform((W, H), Image.Transform.AFFINE, (inv[0, 0], inv[0, 1], off[0], inv[1, 0], inv[1, 1], off[1]), Image.Resampling.BILINEAR)
        arr = np.asarray(layer, np.float32) / 255; al = arr[..., 3:4] * a; col = arr[..., :3] * np.array([r, g, b])
        if d["slots"][tr["slot"]]["blend"] == "additive": canvas += col * al * 255
        else: canvas = canvas * (1 - al) + col * 255 * al
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))

def sheet(name, anims, times, out, base=r"C:\Users\liamc\Documents\LiamToolScores2Unity\Library"):
    lp = f"{base}\\{name}\\{name}.lfx.json"; pp = f"{base}\\{name}\\ScoringFX_{name}.png"
    tw, th = 360, 280; sh = Image.new("RGB", (tw * len(times), th * len(anims)))
    for j, an in enumerate(anims):
        for i, t in enumerate(times):
            im = render(lp, pp, an, t).resize((tw, th), Image.Resampling.LANCZOS); sh.paste(im, (i * tw, j * th))
    sh.save(out)

if __name__ == "__main__":
    name = sys.argv[1]; anims = sys.argv[2].split(","); times = [float(x) for x in sys.argv[3].split(",")]
    sheet(name, anims, times, sys.argv[4])
