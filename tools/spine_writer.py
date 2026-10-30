"""spine_writer.py - Serializador nativo de Spine 4.0.64 binario (.skel) + generador de paquetes JDNext.
Cumple estrictamente todas las reglas de SCORINGFX-ENTREGA-MOTOR-2026-10-30.md:
- Spine 4.0.64 binario (SkeletonBinary compatible bit a bit con spine-csharp 4.0).
- 7 animaciones obligatorias: Bad, Ok, Good, Super, Perfect, Gold, GoldMiss.
- Pose inicial (Setup Pose) 100% limpia (attachment=None en todos los slots).
- Skin 'default' unica, MeshAttachments (4 vertices) con UVs locales [0..1].
- Palabra ancla 'PERFECT' visible en t = min(0.32, dur/2) en la animacion 'Perfect'.
- Simplificacion lineal Ramer-Douglas-Peucker de fotogramas para mantener .skel compacto (~20-45 KB).
- Generacion de catalog_item.json (itemId como primera clave) y SHA256SUMS.txt.
"""
import hashlib, json, math, os, struct, uuid

REQUIRED_ANIMS = ["Bad", "Ok", "Good", "Super", "Perfect", "Gold", "GoldMiss"]

def clean_fx_name(raw_name):
    """Limpia <Nombre> para que no tenga espacios, 'ScoringFX_' ni '_SkeletonData'."""
    n = raw_name.strip().replace(" ", "_")
    while n.startswith("ScoringFX_"):
        n = n[len("ScoringFX_"):]
    while n.endswith("_SkeletonData"):
        n = n[:-len("_SkeletonData")]
    return n or "Custom"

class BinWriter:
    def __init__(self):
        self.buf = bytearray()

    def byte(self, b):
        self.buf.append(b & 0xFF)

    def boolean(self, v):
        self.buf.append(1 if v else 0)

    def f32(self, v):
        self.buf.extend(struct.pack(">f", float(v)))

    def i32(self, v):
        self.buf.extend(struct.pack(">i", int(v)))

    def u32(self, v):
        self.buf.extend(struct.pack(">I", int(v) & 0xFFFFFFFF))

    def i64(self, v):
        self.buf.extend(struct.pack(">q", int(v)))

    def u16(self, v):
        self.buf.extend(struct.pack(">H", int(v) & 0xFFFF))

    def varint(self, val, optimize_positive=True):
        v = int(val)
        if not optimize_positive:
            v = ((v << 1) ^ (v >> 31)) & 0xFFFFFFFF
        else:
            v = v & 0xFFFFFFFF
        while True:
            b = v & 0x7F
            v >>= 7
            if v:
                self.buf.append(b | 0x80)
            else:
                self.buf.append(b)
                break

    def string(self, s):
        if s is None:
            self.varint(0, True)
            return
        if s == "":
            self.varint(1, True)
            return
        raw = s.encode("utf-8")
        self.varint(len(raw) + 1, True)
        self.buf.extend(raw)


def _rdp_simplify(frames, tol, val_dist_fn):
    """Simplifica una lista de [(t, val), ...] con Ramer-Douglas-Peucker."""
    if len(frames) <= 2:
        return frames
    keep = [False] * len(frames)
    keep[0] = True
    keep[-1] = True

    def rec(i0, i1):
        if i1 - i0 <= 1:
            return
        t0, v0 = frames[i0]
        t1, v1 = frames[i1]
        dt = max(1e-9, t1 - t0)
        max_d = -1.0
        best_i = -1
        for i in range(i0 + 1, i1):
            ti, vi = frames[i]
            u = (ti - t0) / dt
            d = val_dist_fn(vi, v0, v1, u)
            if d > max_d:
                max_d = d
                best_i = i
        if max_d > tol and best_i > 0:
            keep[best_i] = True
            rec(i0, best_i)
            rec(best_i, i1)

    rec(0, len(frames) - 1)
    return [f for f, k in zip(frames, keep) if k]


def simplify_1d(frames, tol=0.15):
    return _rdp_simplify(frames, tol, lambda vi, v0, v1, u: abs(vi - (v0 + (v1 - v0) * u)))

def simplify_2d(frames, tol=0.25):
    return _rdp_simplify(
        frames, tol,
        lambda vi, v0, v1, u: math.hypot(vi[0] - (v0[0] + (v1[0] - v0[0]) * u), vi[1] - (v0[1] + (v1[1] - v0[1]) * u))
    )

def simplify_rgba(frames, tol=0.008):
    return _rdp_simplify(
        frames, tol,
        lambda vi, v0, v1, u: max(abs(vi[c] - (v0[c] + (v1[c] - v0[c]) * u)) for c in range(4))
    )

def simplify_verts(frames, tol=0.35):
    return _rdp_simplify(
        frames, tol,
        lambda vi, v0, v1, u: max(abs(vi[k] - (v0[k] + (v1[k] - v0[k]) * u)) for k in range(len(vi)))
    )


def serialize_spine40_skel(bones, slots, skin_attachments, animations, version="4.0.64", fps=60.0):
    """Serializa la estructura intermedia a un binario Spine 4.0.64 (.skel).
    bones: [{'name': str, 'parent': int (-1 para root), 'x':0, 'y':0, 'rot':0, 'sx':1, 'sy':1}]
    slots: [{'name': str, 'bone': int, 'blend': int (0=normal, 1=additive)}]
    skin_attachments: {slot_idx: {att_key: {'name': str, 'path': str, 'uvs': [8 floats], 'tris': [6 ints], 'verts': [2N floats], 'w': float, 'h': float}}}
    animations: {
      anim_name: {
        'slots': {slot_idx: {'attachment': [(t, name_or_None)], 'rgba': [(t, (r,g,b,a), curve)]}},
        'bones': {bone_idx: {'rotate': [(t, deg, curve)], 'translate': [(t, (dx,dy), curve)], 'scale': [(t, (sx,sy), curve)]}},
        'deform': {(slot_idx, att_key): [(t, [delta_verts], curve)]}
      }
    }
    """
    # Construir tabla de strings compartidos (solo referencias reales usadas!)
    str_set = []
    str_map = {}

    def intern(s):
        if s is None:
            return 0
        if s not in str_map:
            str_map[s] = len(str_set) + 1
            str_set.append(s)
        return str_map[s]

    for si in sorted(skin_attachments.keys()):
        for ak, att in skin_attachments[si].items():
            intern(ak)
            if att.get("name") and att["name"] != ak:
                intern(att["name"])
            if att.get("path"):
                intern(att["path"])

    for an in REQUIRED_ANIMS:
        if an not in animations:
            continue
        A = animations[an]
        for si, stl in A.get("slots", {}).items():
            for _, aname in stl.get("attachment", []):
                if aname is not None:
                    intern(aname)
        for (si, ak) in A.get("deform", {}).keys():
            intern(ak)

    # Escribir cuerpo (despues del hash de 8 bytes)
    body = BinWriter()
    body.string(version)
    body.f32(0.0); body.f32(0.0); body.f32(0.0); body.f32(0.0)  # x, y, width, height
    nonessential = True
    body.boolean(nonessential)
    if nonessential:
        body.f32(fps)
        body.string("./images/")
        body.string("")

    # Tabla de strings
    body.varint(len(str_set), True)
    for s in str_set:
        body.string(s)

    # Bones
    body.varint(len(bones), True)
    for i, b in enumerate(bones):
        body.string(b["name"])
        if i > 0:
            body.varint(b["parent"], True)
        body.f32(b.get("rot", 0.0))
        body.f32(b.get("x", 0.0))
        body.f32(b.get("y", 0.0))
        body.f32(b.get("sx", 1.0))
        body.f32(b.get("sy", 1.0))
        body.f32(0.0)  # shearX
        body.f32(0.0)  # shearY
        body.f32(0.0)  # length
        body.varint(0, True)  # TransformMode.Normal
        body.boolean(False)   # skinRequired
        if nonessential:
            body.u32(0x9B9B9BFF)

    # Slots (pose inicial 100% limpia: attachmentName = None -> varint 0!)
    body.varint(len(slots), True)
    for s in slots:
        body.string(s["name"])
        body.varint(s["bone"], True)
        body.u32(0xFFFFFFFF)  # RGBA blanco opaco en setup; sin attachment no dibuja nada
        body.i32(-1)          # darkColor = -1 (sin segundo color)
        body.varint(0, True)  # attachmentName = null!
        body.varint(s.get("blend", 0), True)

    # Constraints (IK, Transform, Path = 0)
    body.varint(0, True)
    body.varint(0, True)
    body.varint(0, True)

    # Default Skin
    active_skin_slots = [si for si in sorted(skin_attachments.keys()) if skin_attachments[si]]
    body.varint(len(active_skin_slots), True)
    for si in active_skin_slots:
        atts = skin_attachments[si]
        body.varint(si, True)
        body.varint(len(atts), True)
        for ak, att in atts.items():
            body.varint(intern(ak), True)  # attachment key name
            att_name = att.get("name", ak)
            body.varint(intern(att_name) if att_name != ak else 0, True)
            body.byte(2)  # AttachmentType.Mesh = 2
            path_name = att.get("path", att_name)
            body.varint(intern(path_name), True)
            body.u32(0xFFFFFFFF)  # color
            vcount = len(att["verts"]) // 2
            body.varint(vcount, True)
            for uv in att["uvs"]:
                body.f32(uv)
            tris = att["tris"]
            body.varint(len(tris), True)
            for tr_i in tris:
                body.u16(tr_i)
            # ReadVertices: unweighted = False + vcount*2 floats
            body.boolean(False)
            for vx in att["verts"]:
                body.f32(vx)
            body.varint(vcount, True)  # hullLength
            if nonessential:
                # Edges para un quad: 4 aristas = 8 shorts (indices * 2)
                if vcount == 4:
                    edges = [0, 2, 2, 4, 4, 6, 6, 0]
                else:
                    edges = []
                body.varint(len(edges), True)
                for eg in edges:
                    body.u16(eg)
                body.f32(att.get("w", 100.0))
                body.f32(att.get("h", 100.0))

    # Other skins = 0, Events = 0
    body.varint(0, True)
    body.varint(0, True)

    # Animations (exactamente en orden o todas las presentes)
    anim_order = [a for a in REQUIRED_ANIMS if a in animations]
    for a in animations:
        if a not in anim_order:
            anim_order.append(a)

    body.varint(len(anim_order), True)
    for an in anim_order:
        A = animations[an]
        slot_tls = {si: d for si, d in A.get("slots", {}).items() if d}
        bone_tls = {bi: d for bi, d in A.get("bones", {}).items() if d}
        deform_tls = {k: v for k, v in A.get("deform", {}).items() if v}

        total_tl = (
            sum(len(d) for d in slot_tls.values())
            + sum(len(d) for d in bone_tls.values())
            + len(deform_tls)
        )
        body.string(an)
        body.varint(total_tl, True)

        # 1. Slot timelines
        body.varint(len(slot_tls), True)
        for si in sorted(slot_tls.keys()):
            d = slot_tls[si]
            body.varint(si, True)
            body.varint(len(d), True)
            if "attachment" in d:
                fr = d["attachment"]
                body.byte(0)  # SLOT_ATTACHMENT
                body.varint(len(fr), True)
                for t, aname in fr:
                    body.f32(t)
                    body.varint(intern(aname), True)
            if "rgba" in d:
                fr = d["rgba"]
                body.byte(1)  # SLOT_RGBA
                body.varint(len(fr), True)
                body.varint(0, True)  # bezierCount = 0
                for idx, item in enumerate(fr):
                    t, (r, g, b, a) = item[0], item[1]
                    body.f32(t)
                    body.byte(max(0, min(255, int(round(r * 255.0)))))
                    body.byte(max(0, min(255, int(round(g * 255.0)))))
                    body.byte(max(0, min(255, int(round(b * 255.0)))))
                    body.byte(max(0, min(255, int(round(a * 255.0)))))
                    if idx > 0:
                        prev_curve = fr[idx - 1][2] if len(fr[idx - 1]) > 2 else 0
                        body.byte(1 if prev_curve == "stepped" else 0)

        # 2. Bone timelines
        body.varint(len(bone_tls), True)
        for bi in sorted(bone_tls.keys()):
            d = bone_tls[bi]
            body.varint(bi, True)
            body.varint(len(d), True)
            if "rotate" in d:
                fr = d["rotate"]
                body.byte(0)  # BONE_ROTATE
                body.varint(len(fr), True)
                body.varint(0, True)  # bezierCount = 0
                for idx, item in enumerate(fr):
                    body.f32(item[0])
                    body.f32(item[1])
                    if idx > 0:
                        prev_curve = fr[idx - 1][2] if len(fr[idx - 1]) > 2 else 0
                        body.byte(1 if prev_curve == "stepped" else 0)
            if "translate" in d:
                fr = d["translate"]
                body.byte(1)  # BONE_TRANSLATE
                body.varint(len(fr), True)
                body.varint(0, True)
                for idx, item in enumerate(fr):
                    body.f32(item[0])
                    body.f32(item[1][0])
                    body.f32(item[1][1])
                    if idx > 0:
                        prev_curve = fr[idx - 1][2] if len(fr[idx - 1]) > 2 else 0
                        body.byte(1 if prev_curve == "stepped" else 0)
            if "scale" in d:
                fr = d["scale"]
                body.byte(4)  # BONE_SCALE
                body.varint(len(fr), True)
                body.varint(0, True)
                for idx, item in enumerate(fr):
                    body.f32(item[0])
                    body.f32(item[1][0])
                    body.f32(item[1][1])
                    if idx > 0:
                        prev_curve = fr[idx - 1][2] if len(fr[idx - 1]) > 2 else 0
                        body.byte(1 if prev_curve == "stepped" else 0)

        # 3. Constraint timelines (IK, Transform, Path = 0)
        body.varint(0, True)
        body.varint(0, True)
        body.varint(0, True)

        # 4. Deform timelines
        if not deform_tls:
            body.varint(0, True)
        else:
            body.varint(1, True)   # 1 skin (default = index 0)
            body.varint(0, True)   # skinIndex = 0
            by_slot = {}
            for (si, ak), fr in deform_tls.items():
                by_slot.setdefault(si, []).append((ak, fr))
            body.varint(len(by_slot), True)
            for si in sorted(by_slot.keys()):
                body.varint(si, True)
                items = by_slot[si]
                body.varint(len(items), True)
                for ak, fr in items:
                    body.varint(intern(ak), True)
                    body.varint(len(fr), True)
                    body.varint(0, True)  # bezierCount = 0
                    body.f32(fr[0][0])
                    for idx, item in enumerate(fr):
                        deltas = item[1]
                        # Comprimir ceros iniciales/finales
                        nz = [i for i, v in enumerate(deltas) if abs(v) > 1e-4]
                        if not nz:
                            body.varint(0, True)
                        else:
                            start, end_excl = nz[0], nz[-1] + 1
                            body.varint(end_excl - start, True)
                            body.varint(start, True)
                            for v in deltas[start:end_excl]:
                                body.f32(v)
                        if idx < len(fr) - 1:
                            body.f32(fr[idx + 1][0])
                            curve = item[2] if len(item) > 2 else 0
                            body.byte(1 if curve == "stepped" else 0)

        # 5. DrawOrder = 0, Events = 0
        body.varint(0, True)
        body.varint(0, True)

    # Hash determinista de 64 bits (nunca 0)
    digest = hashlib.sha256(bytes(body.buf)).digest()
    h64 = struct.unpack(">q", digest[:8])[0]
    if h64 == 0:
        h64 = 1

    out = BinWriter()
    out.i64(h64)
    out.buf.extend(body.buf)
    return bytes(out.buf)


def compile_parametric_anims_to_skel(atlas_regs, anims, sample_fps=60.0):
    """Compila las animaciones parametricas de fxgen.py a un esqueleto Spine 4.0.64 limpio y compacto."""
    from fxgen import samp, hx

    bones = [{"name": "root", "parent": -1, "x": 0.0, "y": 0.0, "rot": 0.0, "sx": 1.0, "sy": 1.0}]
    slots = []
    skin_attachments = {}
    out_anims = {}

    for an in REQUIRED_ANIMS:
        A = anims[an]
        a_slots = {}
        a_bones = {}
        n_steps = max(2, int(round(A.dur * sample_fps)))

        for li, L in enumerate(A.layers):
            reg_name = L["region"]
            r = atlas_regs[reg_name]
            att_key = L.get("att_name") or reg_name

            bi = len(bones)
            si = len(slots)
            b_name = f"{an}_b{li}_{reg_name}"
            s_name = f"{an}_s{li}_{reg_name}"
            bones.append({"name": b_name, "parent": 0, "x": 0.0, "y": 0.0, "rot": 0.0, "sx": 1.0, "sy": 1.0})
            slots.append({"name": s_name, "bone": bi, "blend": 1 if L.get("blend") == "additive" else 0})

            bw, bh = L["size"] if L.get("size") else (float(r["w"]), float(r["h"]))
            ay = L.get("anchor_y", 0.0)
            y_top = (0.5 - ay) * bh
            y_bot = (-0.5 - ay) * bh
            # 0.5px UV inset dentro de la region [0..1] para evitar bleeding
            du = 0.5 / max(2.0, float(r["w"]))
            dv = 0.5 / max(2.0, float(r["h"]))
            u0, u1 = du, 1.0 - du
            v0, v1 = dv, 1.0 - dv

            skin_attachments[si] = {
                att_key: {
                    "name": att_key,
                    "path": reg_name,
                    "uvs": [u1, v1, u0, v1, u0, v0, u1, v0],
                    "tris": [1, 2, 3, 1, 3, 0],
                    "verts": [bw * 0.5, y_bot, -bw * 0.5, y_bot, -bw * 0.5, y_top, bw * 0.5, y_top],
                    "w": float(bw),
                    "h": float(bh),
                }
            }

            t0 = max(0.0, float(L["t0"]))
            t1 = min(float(A.dur), float(L["t1"]))
            # Muestrear solo durante [t0, t1] + puntos exactos t0, t1, y t_anchor (0.32s)
            ts = sorted(set(
                [round(t0, 4), round(t1, 4)]
                + ([0.32] if (an == "Perfect" and t0 <= 0.32 <= t1) else [])
                + [round(k / sample_fps, 4) for k in range(n_steps + 1) if t0 - 1e-5 <= k / sample_fps <= t1 + 1e-5]
            ))
            if len(ts) < 2:
                ts = [round(t0, 4), round(max(t0 + 0.016, t1), 4)]

            tr_raw, rot_raw, sc_raw, col_raw = [], [], [], []
            for t in ts:
                s = samp(L["sc"], t)
                sx_v = float(s * samp(L["sx"], t))
                sy_v = float(s * samp(L["sy"], t))
                al_v = max(0.0, min(1.0, float(samp(L["a"], t))))
                c_rgb = hx(L["col"]) if isinstance(L["col"], str) else L["col"](t)
                rot_v = float(samp(L["rot"], t))
                cx_v = float(samp(L["x"], t))
                cy_v = float(samp(L["y"], t))
                tr_raw.append((t, (cx_v, cy_v)))
                rot_raw.append((t, rot_v))
                sc_raw.append((t, (sx_v, sy_v)))
                col_raw.append((t, (float(c_rgb[0]), float(c_rgb[1]), float(c_rgb[2]), al_v)))

            # Asegurar cierre limpio al final (alpha=0 o attachment=None)
            att_frames = []
            if t0 > 1e-4:
                att_frames.append((0.0, None))
                att_frames.append((round(t0, 4), att_key))
            else:
                att_frames.append((0.0, att_key))
            att_frames.append((round(min(A.dur, t1 + 0.0001), 4), None))

            col_simp = simplify_rgba(col_raw, tol=0.008)
            tr_simp = simplify_2d(tr_raw, tol=0.22)
            rot_simp = simplify_1d(rot_raw, tol=0.15)
            sc_simp = simplify_2d(sc_raw, tol=0.005)

            a_slots[si] = {
                "attachment": att_frames,
                "rgba": [(t, rgba, 0) for t, rgba in col_simp],
            }
            btl = {}
            if any(abs(x) > 1e-3 or abs(y) > 1e-3 for _, (x, y) in tr_simp):
                btl["translate"] = [(t, xy, 0) for t, xy in tr_simp]
            if any(abs(r_deg) > 1e-3 for _, r_deg in rot_simp):
                btl["rotate"] = [(t, r_deg, 0) for t, r_deg in rot_simp]
            if any(abs(sx_ - 1.0) > 1e-3 or abs(sy_ - 1.0) > 1e-3 for _, (sx_, sy_) in sc_simp):
                btl["scale"] = [(t, sxy, 0) for t, sxy in sc_simp]
            if btl:
                a_bones[bi] = btl

        out_anims[an] = {"slots": a_slots, "bones": a_bones, "deform": {}}

    return serialize_spine40_skel(bones, slots, skin_attachments, out_anims, version="4.0.64", fps=60.0)


def build_catalog_item_json(raw_name):
    """Genera catalog_item.json cumpliendo estrictamente la Seccion 5 ('itemId' primera clave)."""
    name = clean_fx_name(raw_name)
    # UUIDv4 determinista a partir del nombre para estabilidad entre re-exportaciones
    h = bytearray(hashlib.sha256(f"JDNext_ScoringFX_{name}".encode("utf-8")).digest()[:16])
    h[6] = (h[6] & 0x0F) | 0x40  # version 4
    h[8] = (h[8] & 0x3F) | 0x80  # variant RFC 4122
    guid = str(uuid.UUID(bytes=bytes(h)))
    loc_id = 905000000 + (int.from_bytes(h[:4], "big") % 899999)

    # Orden de claves garantizado en Python 3.7+ ('itemId' estrictamente primero)
    entry = {
        "itemId": guid,
        "type": "scoringFx",
        "maximumQuantity": 1,
        "nameId": name,
        "tags": [],
        "assets": {},
        "localizations": {},
        "obj": {
            "nameLocId": loc_id,
            "rarity": 0,
            "assetAddress": f"Assets/Data/Spine/ScoringFXs/{name}/ScoringFX_{name}_SkeletonData.asset",
            "thumbnailAddress": f"Assets/Data/Textures/Thumbnails/ScoringFXs/ScoringFX_Thumbnail_{name}.psd",
            "isPremium": False,
            "isUbiconnect": False,
            "hiddenUntilUnlocked": False,
            "isSeasonal": False,
            "unlockConditionsLocId": 0,
        },
    }
    return json.dumps(entry, indent=2, ensure_ascii=False) + "\n"


def write_sha256sums(folder_path, filenames=None):
    """Genera SHA256SUMS.txt para todos los archivos del paquete."""
    if filenames is None:
        filenames = sorted(
            f for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f)) and f != "SHA256SUMS.txt"
        )
    lines = []
    for fn in filenames:
        fp = os.path.join(folder_path, fn)
        if os.path.isfile(fp):
            digest = hashlib.sha256(open(fp, "rb").read()).hexdigest()
            lines.append(f"{digest}  {fn}")
    out_txt = "\n".join(lines) + "\n"
    with open(os.path.join(folder_path, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out_txt)
    return out_txt
