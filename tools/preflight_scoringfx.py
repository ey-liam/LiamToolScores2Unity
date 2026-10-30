"""preflight_scoringfx.py - Comprobacion previa oficial antes de entregar un paquete ScoringFX a JDNext.
Basado en SCORINGFX-ENTREGA-MOTOR-2026-10-30.md (Seccion 8) + validacion de catalog_item.json y SHA256SUMS.txt.

Uso:
    python -I preflight_scoringfx.py <carpeta> <Nombre> [<carpeta ScoringFXs del juego>]
"""
import hashlib, json, pathlib, struct, sys

def run_preflight(folder_path, name, installed_path=None):
    folder = pathlib.Path(folder_path)
    installed = pathlib.Path(installed_path) if installed_path else None
    skel, atlas, png = (folder / f"ScoringFX_{name}{ext}" for ext in (".skel", ".atlas", ".png"))
    fails, warns = [], []

    if "ScoringFX_" in name or "_SkeletonData" in name or " " in name:
        fails.append(f"Nombre invalido '{name}': no debe contener espacios, 'ScoringFX_' ni '_SkeletonData'")

    for f in (skel, atlas, png):
        if not f.exists():
            fails.append(f"Falta archivo obligatorio: {f.name}")
    if fails:
        print(f"[{name}] FALTAN ARCHIVOS:")
        for m in fails:
            print("  FALLA :", m)
        return 1

    data = skel.read_bytes()
    version = data[9:8 + data[8]].decode("ascii", errors="replace")  # 8 bytes de hash + cadena (longitud+1)
    if not version.startswith("4.0."):
        fails.append(f"version Spine {version}: el juego carga ScoringFX solo en 4.0.x")

    lines = atlas.read_text(encoding="utf-8").split("\n")
    if lines[0].strip() != png.name:
        fails.append(f"1.a linea del atlas '{lines[0].strip()}' != '{png.name}'")
    regions = [
        l.strip() for l in lines[1:]
        if l.strip() and not l.startswith((" ", "\t"))
        and ":" not in l and not l.strip().lower().endswith(".png")
    ]
    missing = [r for r in regions if r.encode("utf-8") not in data]
    if missing:
        warns.append(f"{len(missing)} de {len(regions)} regiones del atlas no aparecen en el .skel: {missing[:8]}")

    for req_word in ("PERFECT", "SUPER", "GOOD", "OK", "MISS", "GOLDMISS", "YEAH"):
        if req_word not in regions:
            warns.append(f"falta region estandar de palabra en el atlas: {req_word}")

    md5 = hashlib.md5(data).hexdigest()
    for other in (installed.glob("*/ScoringFX_*.skel") if installed and installed.exists() else []):
        if other.resolve() != skel.resolve() and other.read_bytes() == data:
            fails.append(f".skel identico al instalado {other.name}: no es un esqueleto propio")

    w, h, depth, ctype = struct.unpack(">IIBB", png.read_bytes()[16:26])
    if ctype != 6 or depth != 8:
        warns.append(f"PNG del atlas no es RGBA de 8 bits (tipo {ctype}, {depth} bits)")

    thumb = folder / f"ScoringFX_Thumbnail_{name}.png"
    if thumb.exists():
        tw, th, tdepth, tctype = struct.unpack(">IIBB", thumb.read_bytes()[16:26])
        if (tw, th) != (256, 256):
            warns.append(f"miniatura {tw}x{th}, el resto del catalogo usa 256x256")
        if tctype != 6 or tdepth != 8:
            warns.append(f"miniatura no es RGBA de 8 bits (tipo {tctype}, {tdepth} bits)")
    else:
        warns.append(f"falta ScoringFX_Thumbnail_{name}.png")

    cat = folder / "catalog_item.json"
    if cat.exists():
        raw_cat = cat.read_text(encoding="utf-8")
        obj = json.loads(raw_cat)
        keys = list(obj.keys())
        if not keys or keys[0] != "itemId":
            fails.append("catalog_item.json: 'itemId' debe ser la primera clave del objeto")
        if raw_cat.count('"itemId"') != 1:
            fails.append("catalog_item.json: 'itemId' debe aparecer exactamente una vez")
        expected_addr = f"Assets/Data/Spine/ScoringFXs/{name}/ScoringFX_{name}_SkeletonData.asset"
        if obj.get("obj", {}).get("assetAddress") != expected_addr:
            fails.append(f"catalog_item.json: assetAddress != '{expected_addr}'")
    else:
        warns.append("falta catalog_item.json")

    sums = folder / "SHA256SUMS.txt"
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                expected_h, fname = parts[0], parts[-1].lstrip("*")
                fp = folder / fname
                if not fp.exists():
                    fails.append(f"SHA256SUMS.txt referencia archivo inexistente: {fname}")
                else:
                    actual_h = hashlib.sha256(fp.read_bytes()).hexdigest()
                    if actual_h.lower() != expected_h.lower():
                        fails.append(f"SHA256 mismatch en {fname}: {actual_h} != {expected_h}")
    else:
        warns.append("falta SHA256SUMS.txt")

    print(f"[{name}] spine={version} skel={len(data)//1024}KB md5={md5} atlas={w}x{h} regiones={len(regions)}")
    for m in fails:
        print("  FALLA :", m)
    for m in warns:
        print("  AVISO :", m)
    print("  RESULTADO:", "NO ENVIAR" if fails else "PASA COMPROBACION PREVIA OK")
    return 1 if fails else 0

if __name__ == "__main__":
    rc = run_preflight(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else None,
    )
    sys.exit(rc)
