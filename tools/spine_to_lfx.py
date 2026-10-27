"""
spine_to_lfx.py - Convierte un ScoringFX original de Spine 4.0 (.skel + .atlas + .png)
al formato horneado LiamFX (.lfx.json) que reproducen la herramienta web y el runtime de Unity.

Cada animacion se muestrea a 60 fps: vertices del mesh en espacio del mundo (ya con huesos,
pesos y deform aplicados), color RGBA final (slot x adjunto), adjunto activo y orden de dibujo.

Uso:
    python spine_to_lfx.py <carpeta_ScoringFXs> <carpeta_salida>
    python spine_to_lfx.py <carpeta_ScoringFXs> <carpeta_salida> Basic Neon
"""
import sys, os, json, math, shutil, glob
import spine_skel as S

FPS = 60.0

def _bone_apply(m, x, y):
    a, b, c, d, tx, ty = m
    return a * x + b * y + tx, c * x + d * y + ty

def _sample_deform(frames, t):
    if not frames or t < frames[0][0] - 1e-9: return None
    last = frames[-1]
    if t >= last[0]: return last[1]
    i = 0
    while i + 1 < len(frames) and frames[i+1][0] <= t: i += 1
    f0, f1 = frames[i], frames[i+1]
    cv = f0[2]
    if cv == 'stepped': return f0[1]
    if cv is None:
        s = (t - f0[0]) / (f1[0] - f0[0]) if f1[0] != f0[0] else 1
    else:
        s = S._bez(cv[0], f0[0], 0.0, f1[0], 1.0, t)
    return [p + (q - p) * s for p, q in zip(f0[1], f1[1])]

def _apply_draw(order_count, offs):
    draw = [-1] * order_count
    unchanged = []
    oi = 0
    for slot_i, off in offs:
        while oi != slot_i: unchanged.append(oi); oi += 1
        draw[oi + off] = oi; oi += 1
    while oi < order_count: unchanged.append(oi); oi += 1
    for i in range(order_count - 1, -1, -1):
        if draw[i] == -1: draw[i] = unchanged.pop()
    return draw

def build_attachment_table(sk, atlas):
    """Devuelve (lista de adjuntos horneados, mapa (slot, nombre)->id)."""
    regions = {}
    for pi, page in enumerate(atlas):
        for name, rg in page['regions'].items():
            regions[name] = (pi, page, rg)
    atts = []; amap = {}
    for slot_i, d in sorted(sk['skins'][0]['att'].items()):
        for name, a in d.items():
            if a['type'] not in (0, 2): continue
            reg = regions.get(a['path'])
            if reg is None:
                print('   ! region no encontrada en atlas:', a['path']); continue
            pi, page, rg = reg
            pw, ph = page['w'], page['h']
            rot = rg.get('rotate', 0)
            w, h = rg['w'], rg['h']
            fw, fh = (h, w) if rot == 90 else (w, h)
            def to_uv(u, v):
                if rot == 90: return ((rg['x'] + v * fw) / pw, (rg['y'] + (1 - u) * fh) / ph)
                return ((rg['x'] + u * w) / pw, (rg['y'] + v * h) / ph)
            if a['type'] == 0:
                # quad: BL, TL, TR, BR en espacio local del hueso
                hw, hh = a['w'] * a['sx'] / 2, a['h'] * a['sy'] / 2
                cr, sr = math.cos(math.radians(a['rot'])), math.sin(math.radians(a['rot']))
                local = []
                for lx, ly in ((-hw, -hh), (-hw, hh), (hw, hh), (hw, -hh)):
                    local += [lx * cr - ly * sr + a['x'], lx * sr + ly * cr + a['y']]
                uvs = []
                for u, v in ((0, 1), (0, 0), (1, 0), (1, 1)): uvs += list(to_uv(u, v))
                tris = [0, 1, 2, 2, 3, 0]
                ent = {'slot': slot_i, 'name': name, 'region': a['path'], 'pi': pi, 'uvs': uvs, 'tris': tris,
                       'nv': 4, 'local': local, 'weighted': None, 'color': a['color']}
            else:
                uvs = []
                for k in range(a['vcount']): uvs += list(to_uv(a['uvs'][k*2], a['uvs'][k*2+1]))
                ent = {'slot': slot_i, 'name': name, 'region': a['path'], 'pi': pi, 'uvs': uvs, 'tris': a['tris'],
                       'nv': a['vcount'], 'local': None if a['weighted'] else a['verts'],
                       'weighted': a['verts'] if a['weighted'] else None, 'color': a['color']}
            amap[(slot_i, name)] = len(atts); atts.append(ent)
    return atts, amap

def world_verts(ent, mats, deform):
    out = []
    if ent['weighted'] is None:
        loc = deform if deform is not None else ent['local']
        slot_m = mats
        for k in range(ent['nv']):
            x, y = _bone_apply(slot_m, loc[k*2], loc[k*2+1]); out += [x, y]
        return out
    f = 0
    for infl in ent['weighted']:
        wx = wy = 0.0
        for (bi, vx, vy, wt) in infl:
            if deform is not None: vx += deform[f]; vy += deform[f+1]
            f += 2
            x, y = _bone_apply(mats[bi], vx, vy)
            wx += x * wt; wy += y * wt
        out += [wx, wy]
    return out

def bake(skel_path, atlas_path, name):
    sk = S.load_auto(skel_path)
    if 'error' in sk or not sk.get('eof_ok'):
        raise ValueError('skel no valido: %s' % sk.get('error', 'EOF no consumido'))
    atlas = S.parse_atlas(atlas_path)
    atts, amap = build_attachment_table(sk, atlas)
    slots = sk['slots']
    # adjuntos por slot en orden estable
    out = {
        'format': 'LiamFX', 'version': 1, 'name': name, 'source': sk['file'], 'spine': sk['version'],
        'fps': FPS, 'editorFps': sk['fps'],
        'pages': [{'file': p['name'], 'w': p['w'], 'h': p['h']} for p in atlas],
        'regions': {n: {'page': pi, 'x': rg['x'], 'y': rg['y'], 'w': rg['w'], 'h': rg['h'], 'rotate': rg.get('rotate', 0)}
                    for pi, p in enumerate(atlas) for n, rg in p['regions'].items()},
        'slots': [{'name': s['name'], 'blend': s['blend'], 'bone': sk['bones'][s['bone']]['name']} for s in slots],
        'attachments': [{'slot': a['slot'], 'name': a['name'], 'region': a['region'], 'page': a['pi'], 'nv': a['nv'],
                         'uvs': [round(u, 5) for u in a['uvs']], 'tris': a['tris']} for a in atts],
        'animations': {}
    }
    # Mapa de nombres de feedback del juego -> animacion de Spine
    for an, A in sk['anims'].items():
        dur = S.anim_duration(A)
        n = max(1, int(math.ceil(dur * FPS - 1e-6)))
        times = [k / FPS for k in range(n)] + [dur]
        tracks = {}
        draw_frames = []
        for t in times:
            mats = S.world_bones(sk, A, t)
            for si, s in enumerate(slots):
                tl = A['slots'].get(si, {})
                # adjunto actual
                att_name = s['att']
                fr = tl.get('attachment')
                if fr:
                    if t >= fr[0][0] - 1e-9:
                        for ft, fn in fr:
                            if ft <= t + 1e-9: att_name = fn
                            else: break
                # color
                col = list(s['color'])
                v = S.sample_frames(tl.get('rgba'), t, 4)
                if v: col = v
                else:
                    v = S.sample_frames(tl.get('rgb'), t, 3)
                    if v: col[0:3] = v
                    v = S.sample_frames(tl.get('alpha'), t, 1)
                    if v: col[3] = v[0]
                aid = amap.get((si, att_name)) if att_name else None
                if aid is None or col[3] * atts[aid]['color'][3] < 0.002:
                    tracks.setdefault(si, []).append([round(t, 4), -1])
                    continue
                ent = atts[aid]
                dfr = A['deform'].get((si, att_name))
                dv = _sample_deform(dfr, t) if dfr else None
                bm = mats[sk['slots'][si]['bone']]
                vs = world_verts(ent, bm if ent['weighted'] is None else mats, dv)
                ac = ent['color']
                tracks.setdefault(si, []).append(
                    [round(t, 4), aid] + [round(col[i] * ac[i], 3) for i in range(4)] + [round(x, 1) for x in vs])
            # draw order
            if A['draw']:
                cur = None
                for dt, offs in A['draw']:
                    if dt <= t + 1e-9: cur = _apply_draw(len(slots), offs)
                if cur is None: cur = list(range(len(slots)))
                draw_frames.append([round(t, 4), cur])
        # quitar slots nunca visibles
        slots_out = []
        for si, frames in tracks.items():
            if any(f[1] >= 0 for f in frames): slots_out.append({'slot': si, 'frames': frames})
        entry = {'duration': round(dur, 4), 'tracks': slots_out}
        if draw_frames:
            # comprimir: solo cuando cambia
            comp = []; last = None
            for t, o in draw_frames:
                if o != last: comp.append([t, o]); last = o
            entry['draw'] = comp
        out['animations'][an] = entry
    return out, atlas

def main():
    root = sys.argv[1]; dest = sys.argv[2]; only = set(sys.argv[3:])
    os.makedirs(dest, exist_ok=True)
    index = []
    for d in sorted(os.listdir(root)):
        folder = os.path.join(root, d)
        if not os.path.isdir(folder) or (only and d not in only): continue
        skel = glob.glob(os.path.join(folder, '*.skel')); atl = glob.glob(os.path.join(folder, '*.atlas'))
        if not skel or not atl: continue
        try:
            data, atlas = bake(skel[0], atl[0], d)
        except Exception as e:
            print('[X] %-18s %s' % (d, e)); continue
        od = os.path.join(dest, d); os.makedirs(od, exist_ok=True)
        with open(os.path.join(od, d + '.lfx.json'), 'w') as f: json.dump(data, f, separators=(',', ':'))
        for p in atlas:
            src = os.path.join(folder, p['name'])
            if os.path.exists(src): shutil.copy(src, os.path.join(od, p['name']))
        for ext in ('.skel', '.atlas'):
            for fpath in glob.glob(os.path.join(folder, '*' + ext)): shutil.copy(fpath, os.path.join(od, os.path.basename(fpath)))
        size = os.path.getsize(os.path.join(od, d + '.lfx.json')) // 1024
        print('[OK] %-18s anims=%s  atts=%d  %d KB' % (d, ','.join(data['animations'].keys()), len(data['attachments']), size))
        index.append({'name': d, 'file': d + '/' + d + '.lfx.json', 'animations': list(data['animations'].keys())})
    with open(os.path.join(dest, 'library_index.json'), 'w') as f: json.dump(index, f, indent=1)

if __name__ == '__main__':
    main()
