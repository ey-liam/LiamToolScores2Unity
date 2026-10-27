"""
spine_skel.py - Parser de Spine 4.0.x binario (.skel) + muestreador de animaciones.
Pensado para los ScoringFX de Just Dance Next (Spine 4.0.64).
Solo libreria estandar. Verifica que se consuma el archivo completo (pos == len).
"""
import struct, math, re, os

class R:
    def __init__(s, data): s.d = data; s.p = 0
    def byte(s): b = s.d[s.p]; s.p += 1; return b
    def sbyte(s): b = s.byte(); return b - 256 if b > 127 else b
    def boolean(s): return s.byte() != 0
    def f(s): v = struct.unpack('>f', s.d[s.p:s.p+4])[0]; s.p += 4; return v
    def i32(s): v = struct.unpack('>i', s.d[s.p:s.p+4])[0]; s.p += 4; return v
    def varint(s, positive=True):
        r = 0; shift = 0
        while True:
            b = s.byte(); r |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
        return r if positive else ((r >> 1) ^ -(r & 1))
    def string(s):
        n = s.varint()
        if n == 0: return None
        if n == 1: return ''
        n -= 1
        v = s.d[s.p:s.p+n].decode('utf-8', 'replace'); s.p += n; return v
    def rgba8(s): return [s.byte()/255.0 for _ in range(4)]
    def color_int(s):  # 0xRRGGBBAA
        v = s.i32() & 0xFFFFFFFF
        return [((v >> 24) & 255)/255.0, ((v >> 16) & 255)/255.0, ((v >> 8) & 255)/255.0, (v & 255)/255.0]

BLEND = ['normal', 'additive', 'multiply', 'screen']

def load(path, anim_header_variant=0):
    raw = open(path, 'rb').read()
    r = R(raw)
    sk = {'file': os.path.basename(path)}
    r.p = 8
    sk['version'] = r.string()
    r.f(); r.f(); r.f(); r.f()
    ne = r.boolean(); sk['nonessential'] = ne
    sk['fps'] = 30.0
    if ne:
        sk['fps'] = r.f(); r.string(); r.string()
    strings = [r.string() for _ in range(r.varint())]
    ref = lambda: (lambda i: None if i == 0 else strings[i-1])(r.varint())

    bones = []
    for i in range(r.varint()):
        b = {'name': r.string()}
        b['parent'] = r.varint() if i > 0 else -1
        b['rot'] = r.f(); b['x'] = r.f(); b['y'] = r.f()
        b['sx'] = r.f(); b['sy'] = r.f(); b['shx'] = r.f(); b['shy'] = r.f(); b['len'] = r.f()
        b['mode'] = r.varint(); b['skinReq'] = r.boolean()
        if ne: r.color_int()
        bones.append(b)
    sk['bones'] = bones

    slots = []
    for i in range(r.varint()):
        s = {'name': r.string(), 'bone': r.varint(), 'color': r.color_int()}
        dc = r.i32() & 0xFFFFFFFF
        s['dark'] = None if dc == 0xFFFFFFFF else dc
        s['att'] = ref(); s['blend'] = BLEND[r.varint()]
        slots.append(s)
    sk['slots'] = slots

    nik = r.varint(); sk['ik'] = nik
    for _ in range(nik):
        r.string(); r.varint(); r.boolean()
        for _ in range(r.varint()): r.varint()
        r.varint(); r.f(); r.f(); r.sbyte(); r.boolean(); r.boolean(); r.boolean()
    ntc = r.varint(); sk['transform'] = ntc
    for _ in range(ntc):
        r.string(); r.varint(); r.boolean()
        for _ in range(r.varint()): r.varint()
        r.varint(); r.boolean(); r.boolean()
        for _ in range(6): r.f()   # offsets
        for _ in range(6): r.f()   # mixes
    npc = r.varint(); sk['path'] = npc
    if npc: raise ValueError('path constraints no soportadas')

    def vertices(n):
        weighted = r.boolean()
        if not weighted:
            return [r.f() for _ in range(n*2)], False
        out = []
        for _ in range(n):
            bc = r.varint()
            out.append([(r.varint(), r.f(), r.f(), r.f()) for _ in range(bc)])
        return out, True

    def attachment(name):
        nm = ref() or name
        t = r.byte()
        a = {'name': nm, 'type': t}
        if t == 0:
            a['path'] = ref() or nm
            a['rot'] = r.f(); a['x'] = r.f(); a['y'] = r.f(); a['sx'] = r.f(); a['sy'] = r.f()
            a['w'] = r.f(); a['h'] = r.f(); a['color'] = r.color_int()
        elif t == 1:
            n = r.varint(); vertices(n)
            if ne: r.color_int()
        elif t == 2:
            a['path'] = ref() or nm; a['color'] = r.color_int()
            n = r.varint()
            a['uvs'] = [r.f() for _ in range(n*2)]
            tn = r.varint(); a['tris'] = [(r.byte() << 8) | r.byte() for _ in range(tn)]
            v, wt = vertices(n); a['verts'] = v; a['weighted'] = wt; a['vcount'] = n
            r.varint()
            if ne:
                en = r.varint()
                for _ in range(en): r.byte(); r.byte()
                a['w'] = r.f(); a['h'] = r.f()
        elif t == 3:
            a['path'] = ref() or nm; r.color_int(); ref(); ref(); r.boolean()
            if ne: r.f(); r.f()
        elif t == 4:
            r.boolean(); r.boolean(); n = r.varint(); vertices(n)
            for _ in range(n//3): r.f()
            if ne: r.color_int()
        elif t == 5:
            r.f(); r.f(); r.f()
            if ne: r.color_int()
        elif t == 6:
            r.varint(); n = r.varint(); vertices(n)
            if ne: r.color_int()
        else:
            raise ValueError('attachment type %d' % t)
        return a

    skins = []
    # default skin
    dskin = {'name': 'default', 'att': {}}
    sc = r.varint()
    for _ in range(sc):
        si = r.varint()
        for _ in range(r.varint()):
            an = ref(); a = attachment(an)
            dskin['att'].setdefault(si, {})[an] = a
    skins.append(dskin)
    for _ in range(r.varint()):
        sn = ref()
        for _ in range(r.varint()): r.varint()
        for _ in range(r.varint()): r.varint()
        for _ in range(r.varint()): r.varint()
        for _ in range(r.varint()): r.varint()
        sk_ = {'name': sn, 'att': {}}
        for _ in range(r.varint()):
            si = r.varint()
            for _ in range(r.varint()):
                an = ref(); a = attachment(an)
                sk_['att'].setdefault(si, {})[an] = a
        skins.append(sk_)
    sk['skins'] = skins

    events = []
    for _ in range(r.varint()):
        e = {'name': ref(), 'int': r.varint(False), 'float': r.f(), 'string': r.string(), 'audio': r.string()}
        if e['audio'] is not None: r.f(); r.f()
        events.append(e)
    sk['events'] = events

    def curve(nch):
        c = r.byte()
        if c == 0: return None
        if c == 1: return 'stepped'
        return [(r.f(), r.f(), r.f(), r.f()) for _ in range(nch)]

    anims = {}
    for _ in range(r.varint()):
        an = r.string()
        if anim_header_variant == 1: r.varint()
        A = {'slots': {}, 'bones': {}, 'draw': [], 'events': [], 'deform': 0}
        # slot timelines
        for _ in range(r.varint()):
            si = r.varint()
            for _ in range(r.varint()):
                tt = r.byte(); fc = r.varint()
                if tt == 0:
                    fr = [(r.f(), ref()) for _ in range(fc)]
                    A['slots'].setdefault(si, {})['attachment'] = fr
                else:
                    r.varint()  # bezierCount
                    nb = {1: 4, 2: 3, 3: 7, 4: 6, 5: 1}[tt]
                    chans = {1: 4, 2: 3, 3: 4, 4: 3, 5: 1}[tt]   # canales de color usados por nosotros
                    frames = []
                    t = r.f(); vals = [r.byte()/255.0 for _ in range(nb)]
                    for fi in range(fc):
                        frames.append((t, vals[:chans], None))
                        if fi == fc - 1: break
                        t2 = r.f(); v2 = [r.byte()/255.0 for _ in range(nb)]
                        cv = curve(nb)
                        frames[-1] = (t, vals[:chans], cv if cv is None or cv == 'stepped' else cv[:chans])
                        t, vals = t2, v2
                    key = {1: 'rgba', 2: 'rgb', 3: 'rgba', 4: 'rgb', 5: 'alpha'}[tt]
                    if tt in (3, 4): A['slots'].setdefault(si, {})['dark'] = True
                    A['slots'].setdefault(si, {})[key] = frames
        # bone timelines
        chmap = {0: ('rotate', 1), 1: ('translate', 2), 2: ('translatex', 1), 3: ('translatey', 1),
                 4: ('scale', 2), 5: ('scalex', 1), 6: ('scaley', 1), 7: ('shear', 2), 8: ('shearx', 1), 9: ('sheary', 1)}
        for _ in range(r.varint()):
            bi = r.varint()
            for _ in range(r.varint()):
                tt = r.byte(); fc = r.varint(); r.varint()
                name, nch = chmap[tt]
                frames = []
                t = r.f(); vals = [r.f() for _ in range(nch)]
                for fi in range(fc):
                    frames.append([t, vals, None])
                    if fi == fc - 1: break
                    t2 = r.f(); v2 = [r.f() for _ in range(nch)]
                    frames[-1][2] = curve(nch)
                    t, vals = t2, v2
                A['bones'].setdefault(bi, {})[name] = frames
        # constraints (esperamos 0)
        for kind in ('ik', 'transform', 'path'):
            n = r.varint()
            if n: raise ValueError('timeline de %s no soportada' % kind)
        # deform
        A['deform'] = {}
        for _ in range(r.varint()):
            skin_i = r.varint()
            for _ in range(r.varint()):
                slot_i = r.varint()
                for _ in range(r.varint()):
                    an_ = ref()
                    att = skins[skin_i]['att'].get(slot_i, {}).get(an_)
                    if att is None: raise ValueError('deform sobre adjunto desconocido %s' % an_)
                    weighted = att['weighted']
                    dlen = (sum(len(v) for v in att['verts']) * 2) if weighted else len(att['verts'])
                    fc = r.varint(); r.varint()
                    frames = []
                    t = r.f()
                    for fi in range(fc):
                        end = r.varint()
                        if end == 0:
                            arr = [0.0] * dlen if weighted else list(att['verts'])
                        else:
                            arr = [0.0] * dlen
                            start = r.varint(); end += start
                            for v in range(start, end): arr[v] = r.f()
                            if not weighted:
                                for v in range(dlen): arr[v] += att['verts'][v]
                        cv = None
                        if fi < fc - 1:
                            t2 = r.f(); cv = curve(1)
                        frames.append([t, arr, cv])
                        if fi < fc - 1: t = t2
                    A['deform'][(slot_i, an_)] = frames
        # draw order
        for _ in range(r.varint()):
            t = r.f(); offs = []
            for _ in range(r.varint()):
                si_ = r.varint(); off_ = r.varint()
                if off_ >= 2**31: off_ -= 2**32
                offs.append((si_, off_))
            A['draw'].append((t, offs))
        # events
        for _ in range(r.varint()):
            t = r.f(); ei = r.varint(); r.varint(False); r.f()
            if r.boolean(): r.string()
            if events[ei]['audio'] is not None: r.f(); r.f()
            A['events'].append((t, events[ei]['name']))
        anims[an] = A
    sk['anims'] = anims
    sk['eof_ok'] = (r.p == len(raw))
    sk['pos'] = r.p; sk['len'] = len(raw)
    return sk


def load_auto(path):
    """Prueba variantes de cabecera de animacion hasta consumir exactamente el archivo."""
    last = None
    for v in (0, 1):
        try:
            sk = load(path, v)
            if sk['eof_ok']: return sk
            last = sk
        except Exception as e:
            last = {'error': str(e), 'file': os.path.basename(path)}
    return last


# ---------------- Atlas ----------------
def parse_atlas(path):
    pages = []; cur = None; region = None
    for line in open(path, encoding='utf-8-sig').read().splitlines():
        if not line.strip(): cur = None; region = None; continue
        if cur is None:
            cur = {'name': line.strip(), 'regions': {}}; pages.append(cur); continue
        if ':' in line and not line.startswith(' ') and region is None and cur is not None and not cur.get('_started'):
            k, v = line.split(':', 1); cur[k.strip()] = v.strip(); continue
        if ':' not in line:
            cur['_started'] = True
            region = {'name': line.strip()}; cur['regions'][region['name']] = region; continue
        k, v = [x.strip() for x in line.split(':', 1)]
        if k == 'bounds':
            x, y, w, h = [int(n) for n in v.split(',')]
            region.update(x=x, y=y, w=w, h=h)
        elif k == 'rotate':
            region['rotate'] = 90 if v in ('true', '90') else 0
        elif k == 'offsets':
            region['offsets'] = [int(n) for n in v.split(',')]
        else:
            region[k] = v
    for p in pages:
        p.pop('_started', None)
        if 'size' in p: p['w'], p['h'] = [int(n) for n in p['size'].split(',')]
    return pages


# ---------------- Muestreo ----------------
def _bez(c, t0, v0, t1, v1, t):
    cx1, cy1, cx2, cy2 = c
    lo, hi = 0.0, 1.0
    for _ in range(40):
        s = (lo + hi) / 2; u = 1 - s
        x = u*u*u*t0 + 3*u*u*s*cx1 + 3*u*s*s*cx2 + s*s*s*t1
        if x < t: lo = s
        else: hi = s
    s = (lo + hi) / 2; u = 1 - s
    return u*u*u*v0 + 3*u*u*s*cy1 + 3*u*s*s*cy2 + s*s*s*v1

def sample_frames(frames, t, nch):
    """Devuelve lista de nch valores en t, o None si t < primer frame."""
    if not frames or t < frames[0][0] - 1e-9: return None
    last = frames[-1]
    if t >= last[0]: return list(last[1])
    i = 0
    while i + 1 < len(frames) and frames[i+1][0] <= t: i += 1
    f0, f1 = frames[i], frames[i+1]
    cv = f0[2]
    if cv == 'stepped': return list(f0[1])
    out = []
    for ch in range(nch):
        v0, v1 = f0[1][ch], f1[1][ch]
        if cv is None:
            a = (t - f0[0]) / (f1[0] - f0[0]) if f1[0] != f0[0] else 1
            out.append(v0 + (v1 - v0) * a)
        else:
            out.append(_bez(cv[ch], f0[0], v0, f1[0], v1, t))
    return out

def anim_duration(A):
    d = 0.0
    for tls in A['bones'].values():
        for fr in tls.values():
            d = max(d, fr[-1][0])
    for tls in A['slots'].values():
        for k, fr in tls.items():
            if isinstance(fr, list) and fr: d = max(d, fr[-1][0])
    for t, _ in A['draw']: d = max(d, t)
    for t, _ in A['events']: d = max(d, t)
    return d

def world_bones(sk, A, t):
    bones = sk['bones']; out = []
    for i, b in enumerate(bones):
        rot, x, y, sx, sy, shx, shy = b['rot'], b['x'], b['y'], b['sx'], b['sy'], b['shx'], b['shy']
        tl = A['bones'].get(i, {}) if A else {}
        v = sample_frames(tl.get('rotate'), t, 1)
        if v: rot = b['rot'] + v[0]
        v = sample_frames(tl.get('translate'), t, 2)
        if v: x = b['x'] + v[0]; y = b['y'] + v[1]
        v = sample_frames(tl.get('translatex'), t, 1)
        if v: x = b['x'] + v[0]
        v = sample_frames(tl.get('translatey'), t, 1)
        if v: y = b['y'] + v[0]
        v = sample_frames(tl.get('scale'), t, 2)
        if v: sx = b['sx'] * v[0]; sy = b['sy'] * v[1]
        v = sample_frames(tl.get('scalex'), t, 1)
        if v: sx = b['sx'] * v[0]
        v = sample_frames(tl.get('scaley'), t, 1)
        if v: sy = b['sy'] * v[0]
        v = sample_frames(tl.get('shear'), t, 2)
        if v: shx = b['shx'] + v[0]; shy = b['shy'] + v[1]
        v = sample_frames(tl.get('shearx'), t, 1)
        if v: shx = b['shx'] + v[0]
        v = sample_frames(tl.get('sheary'), t, 1)
        if v: shy = b['shy'] + v[0]
        r1 = math.radians(rot + shx); r2 = math.radians(rot + 90 + shy)
        la, lb = math.cos(r1) * sx, math.cos(r2) * sy
        lc, ld = math.sin(r1) * sx, math.sin(r2) * sy
        if b['parent'] < 0:
            out.append((la, lb, lc, ld, x, y)); continue
        pa, pb, pc, pd, px, py = out[b['parent']]
        mode = b['mode']
        wx = pa * x + pb * y + px; wy = pc * x + pd * y + py
        if mode == 0:
            out.append((pa*la + pb*lc, pa*lb + pb*ld, pc*la + pd*lc, pc*lb + pd*ld, wx, wy))
        elif mode == 1:  # onlyTranslation
            out.append((la, lb, lc, ld, wx, wy))
        elif mode == 2:  # noRotationOrReflection (aprox)
            s = pa*pa + pc*pc
            prx = math.degrees(math.atan2(pc, pa)) if s > 1e-4 else 0
            ps = math.sqrt(s)
            out.append((la*ps, lb*ps, lc*ps, ld*ps, wx, wy))
        else:  # noScale / noScaleOrReflection (aprox: usa rotacion del padre sin escala)
            ps1 = math.hypot(pa, pc) or 1; ps2 = math.hypot(pb, pd) or 1
            na, nc = pa/ps1, pc/ps1; nb, nd = pb/ps2, pd/ps2
            out.append((na*la + nb*lc, na*lb + nb*ld, nc*la + nd*lc, nc*lb + nd*ld, wx, wy))
    return out
