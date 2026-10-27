"""verify_render.py - renderiza fotogramas de un .lfx.json con PIL+numpy (referencia de verificacion)."""
import sys, json, os
import numpy as np
from PIL import Image, ImageDraw

def render(lfx, atlas_imgs, anim, t, size=(560, 360), scale=0.9, origin=(280, 200)):
    A = lfx['animations'][anim]
    W, H = size
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    canvas[:] = (22, 26, 40)
    order = list(range(len(lfx['slots'])))
    if 'draw' in A:
        cur = None
        for ft, o in A['draw']:
            if ft <= t + 1e-9: cur = o
        if cur: order = cur
    tracks = {tr['slot']: tr['frames'] for tr in A['tracks']}
    for si in order:
        fr = tracks.get(si)
        if not fr: continue
        # frame mas cercano
        best = min(fr, key=lambda f: abs(f[0] - t))
        if best[1] < 0: continue
        att = lfx['attachments'][best[1]]
        rgba = best[2:6]; v = best[6:]
        blend = lfx['slots'][si]['blend']
        img = atlas_imgs[att['page']]
        pw, ph = img.size
        for k in range(0, len(att['tris']), 3):
            ids = att['tris'][k:k+3]
            dst = [(origin[0] + v[i*2] * scale, origin[1] - v[i*2+1] * scale) for i in ids]
            src = [(att['uvs'][i*2] * pw, att['uvs'][i*2+1] * ph) for i in ids]
            # transformacion afin destino->origen
            M = np.array([[dst[0][0], dst[0][1], 1], [dst[1][0], dst[1][1], 1], [dst[2][0], dst[2][1], 1]])
            if abs(np.linalg.det(M)) < 1e-6: continue
            sx = np.linalg.solve(M, np.array([s[0] for s in src]))
            sy = np.linalg.solve(M, np.array([s[1] for s in src]))
            tile = img.transform((W, H), Image.AFFINE, (sx[0], sx[1], sx[2], sy[0], sy[1], sy[2]), resample=Image.BILINEAR)
            mask = Image.new('L', (W, H), 0); ImageDraw.Draw(mask).polygon(dst, fill=255)
            arr = np.asarray(tile, dtype=np.float32) / 255.0
            m = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
            a = arr[..., 3:4] * rgba[3] * m
            col = arr[..., :3] * np.array(rgba[:3], dtype=np.float32) * 255.0
            if blend == 'additive': canvas += col * a
            else: canvas = canvas * (1 - a) + col * a
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))

if __name__ == '__main__':
    folder, name, anim, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    lfx = json.load(open(os.path.join(folder, name, name + '.lfx.json')))
    imgs = [Image.open(os.path.join(folder, name, p['file'])).convert('RGBA') for p in lfx['pages']]
    dur = lfx['animations'][anim]['duration']
    ts = [dur * k / 5 for k in range(6)]
    frames = [render(lfx, imgs, anim, t) for t in ts]
    sheet = Image.new('RGB', (560 * 3, 360 * 2))
    for i, f in enumerate(frames): sheet.paste(f, ((i % 3) * 560, (i // 3) * 360))
    sheet.save(out); print('guardado', out, 'dur', dur)
