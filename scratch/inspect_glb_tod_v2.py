#!/usr/bin/env python3
"""
inspect_glb_tod_v2.py — deeper diagnostic.

Beyond v1: extracts each color accessor's raw byte stream and compares
COLOR_0 byte-for-byte with each _NAME slot to identify which slot (if any)
COLOR_0 actually contains. Also reports each attribute's componentType and
type so we can see whether the importer is being fed BYTE_COLOR vs FLOAT_COLOR,
VEC3 vs VEC4, etc.

Usage: python3 inspect_glb_tod_v2.py path/to/level.glb
"""
import json, struct, sys, hashlib
from pathlib import Path

GLB_MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
TOD_SLOTS = ["_SUNRISE", "_MORNING", "_NOON", "_AFTERNOON",
             "_SUNSET", "_TWILIGHT", "_EVENING", "_GREENSUN"]
COMPONENT_TYPE = {5120: "i8", 5121: "u8", 5122: "i16", 5123: "u16",
                  5125: "u32", 5126: "f32"}
TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}


def parse_glb(path: Path):
    data = path.read_bytes()
    magic, ver, total_len = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError("not a glb")
    json_len, json_type = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20:20 + json_len].decode("utf-8"))
    bin_offset = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", data, bin_offset)
    binary = data[bin_offset + 8:bin_offset + 8 + bin_len]
    return gltf, binary


def accessor_bytes(gltf, binary, acc_idx):
    acc = gltf["accessors"][acc_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    n = TYPE_COMPONENTS[acc["type"]]
    csize = COMPONENT_SIZE[acc["componentType"]]
    stride = bv.get("byteStride") or (n * csize)
    count = acc["count"]
    out = bytearray(count * n * csize)
    for i in range(count):
        src = offset + i * stride
        dst = i * n * csize
        out[dst:dst + n * csize] = binary[src:src + n * csize]
    return bytes(out), acc["componentType"], acc["type"], count


def main():
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    gltf, binary = parse_glb(Path(sys.argv[1]))

    color_streams = ["COLOR_0", "COLOR_1", "COLOR_2", "COLOR_3", "COLOR_4",
                     "COLOR_5", "COLOR_6", "COLOR_7", "COLOR_8"]
    all_attrs = color_streams + TOD_SLOTS

    print(f"Meshes: {len(gltf.get('meshes', []))}\n")

    # Pick the first primitive only — they should all be consistent
    mesh0 = gltf["meshes"][0]
    prim0 = mesh0["primitives"][0]
    attrs = prim0["attributes"]
    print(f"--- First primitive of mesh '{mesh0.get('name','?')}' ---\n")

    digests = {}
    type_info = {}
    for name in all_attrs:
        if name not in attrs:
            continue
        raw, ctype, gtype, count = accessor_bytes(gltf, binary, attrs[name])
        digests[name] = hashlib.sha1(raw).hexdigest()[:12]
        type_info[name] = f"{COMPONENT_TYPE[ctype]} {gtype} count={count}"

    print(f"{'attribute':<14} {'type':<22} {'sha1[:12]':<14}  first 8 bytes (hex)")
    print("-" * 80)
    for name in all_attrs:
        if name not in digests:
            continue
        raw, *_ = accessor_bytes(gltf, binary, attrs[name])
        first8 = raw[:8].hex()
        print(f"{name:<14} {type_info[name]:<22} {digests[name]:<14}  {first8}")

    # Match COLOR_N streams to named slots
    print("\n--- COLOR_N → _NAME match (by sha1 of full byte stream) ---")
    name_digest_to_label = {digests[n]: n for n in TOD_SLOTS if n in digests}
    for n in color_streams:
        if n not in digests:
            continue
        match = name_digest_to_label.get(digests[n], "** NO MATCH (different data) **")
        print(f"  {n}  →  {match}")

    # Cross-prim sanity: check 3 more random prims agree on COLOR_0 mapping
    print("\n--- Cross-primitive consistency for COLOR_0 ---")
    samples = []
    for m in gltf["meshes"][:5]:
        for p in m["primitives"][:1]:
            a = p["attributes"]
            if "COLOR_0" not in a:
                continue
            raw, *_ = accessor_bytes(gltf, binary, a["COLOR_0"])
            digest = hashlib.sha1(raw).hexdigest()[:12]
            # match against this prim's own _NAME slots
            local = {}
            for slot in TOD_SLOTS:
                if slot in a:
                    sraw, *_ = accessor_bytes(gltf, binary, a[slot])
                    local[hashlib.sha1(sraw).hexdigest()[:12]] = slot
            samples.append((m.get("name","?"), local.get(digest, "NO MATCH")))
    for name, match in samples:
        print(f"  mesh '{name}': COLOR_0 == {match}")


if __name__ == "__main__":
    main()
