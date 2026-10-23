"""Split a build folder into zips small enough for the Steamworks WEB
uploader (SteamPipe > Builds > Upload), for when you cannot use SteamCMD.

    python tools/make_chunks.py dist/windows
    python tools/make_chunks.py dist/windows --out steam/chunks

The web uploader takes one zip per upload, capped at 2048 MB. Upload the
first zip normally, then each later one with "Merge With Baseline".

TRAP (learned on O'BLOCK): "Merge With Baseline" merges onto the build that
is LIVE ON THE DEFAULT BRANCH, not onto your last upload. For a multi-zip
build, set each upload live (on a private beta branch is fine) before
merging the next one, and check the final build's file list and size in
Steamworks before you set it live on default.

Paths inside each zip are depot-relative. Small top-level files (the exe,
DLLs) go in the LAST zip, so the build only becomes runnable once all of
its data is there. Files are stored, not deflated: game data (audio,
textures) barely compresses and storing is much faster.
"""
import argparse
import json
import os
import zipfile

LIMIT = 1_900_000_000  # under 2048 MB with room for zip overhead


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default=os.path.join("steam", "chunks"))
    ap.add_argument("--name", default="build")
    a = ap.parse_args()

    files = []
    for r, _, fs in os.walk(a.root):
        for f in fs:
            p = os.path.join(r, f)
            files.append((os.path.relpath(p, a.root).replace("\\", "/"), os.path.getsize(p)))
    if any(n > LIMIT for _, n in files):
        raise SystemExit("a single file is over the web upload limit: use SteamCMD (steam/upload.py)")
    top = [f for f in files if "/" not in f[0]]
    rest = sorted((f for f in files if "/" in f[0]), key=lambda x: x[0])
    chunks, cur, size = [], [], 0
    for rel, n in rest + top:
        if cur and size + n > LIMIT:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(rel)
        size += n
    if cur:
        chunks.append(cur)

    os.makedirs(a.out, exist_ok=True)
    plan = []
    for i, c in enumerate(chunks, 1):
        path = os.path.join(a.out, f"{a.name}-{i:02d}.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for rel in c:
                z.write(os.path.join(a.root, rel), rel)
        plan.append({"zip": path, "files": len(c), "bytes": os.path.getsize(path), "merge_with_baseline": i > 1})
        print(f"{path}  {len(c)} files  {os.path.getsize(path) / 1e6:.0f} MB  {'merge' if i > 1 else 'first, no merge'}")
    json.dump(plan, open(os.path.join(a.out, f"{a.name}-plan.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
