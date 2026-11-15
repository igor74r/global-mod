#!/usr/bin/env python3
"""Assemble a best-effort Victoria 3 combined mod from the three source archives."""
from __future__ import annotations
import argparse, csv, hashlib, os, re, shutil, sys, zipfile
from pathlib import Path

SKIP_PARTS={".git", ".github", "__pycache__"}
SKIP_NAMES={".DS_Store", ".gitignore", ".gitattributes"}
TEXT_EXT={".txt",".yml",".yaml",".json",".md",".gui",".asset",".info",".csv",".conf",".mod",".lua",".py",".sh"}

def sha(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def root_dir(p: Path) -> Path:
    entries=list(p.iterdir())
    dirs=[x for x in entries if x.is_dir() and x.name not in SKIP_PARTS]
    files=[x for x in entries if x.is_file()]
    if len(dirs)==1 and not files: return dirs[0]
    return p

def copy_source(src: Path, dst: Path, label: str, conflicts: list, base: bool=False):
    for p in src.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(src)
        if any(part in SKIP_PARTS for part in rel.parts) or p.name in SKIP_NAMES: continue
        target=dst/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            shutil.copy2(p,target)
        else:
            if sha(p)==sha(target): continue
            # Keep Morgenröte as initial baseline. Every non-identical alternative is preserved.
            conflict_path=Path("conflicts")/label/rel
            conflict_file=dst.parent/"merge-conflicts"/label/rel
            conflict_file.parent.mkdir(parents=True,exist_ok=True)
            if not conflict_file.exists(): shutil.copy2(p,conflict_file)
            conflicts.append((label,str(rel),str(target.relative_to(dst)),str(conflict_path)))

def parse_loc_line(line: str):
    m=re.match(r'^(\s*)([A-Za-z0-9_.:-]+):(\d*)\s*(.*)$',line)
    if not m: return None
    return m.group(2),line

def merge_localization_files(dst: Path, sources: list[Path], conflicts: list):
    # Keep the first existing translation for each key; append only genuinely missing keys.
    for src in sources:
        locroot=src/"localization"/"russian"
        if not locroot.is_dir(): continue
        for p in locroot.rglob("*_l_russian.yml"):
            if not p.is_file(): continue
            rel=p.relative_to(locroot)
            target=dst/rel
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target)
                continue
            existing=target.read_text(encoding="utf-8-sig").splitlines()
            keys=set()
            for line in existing:
                parsed=parse_loc_line(line)
                if parsed: keys.add(parsed[0])
            additions=[]
            for line in p.read_text(encoding="utf-8-sig").splitlines():
                parsed=parse_loc_line(line)
                if parsed and parsed[0] not in keys:
                    additions.append(line); keys.add(parsed[0])
            if additions:
                with target.open("a",encoding="utf-8",newline="\n") as f:
                    if existing and existing[-1].strip(): f.write("\n")
                    f.write("\n".join(additions)+"\n")
                conflicts.append(("localization-merged",str(rel),str(target),"added missing keys"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--morgenroete",required=True,type=Path)
    ap.add_argument("--better-politics",required=True,type=Path)
    ap.add_argument("--tech-res",required=True,type=Path)
    ap.add_argument("--existing",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    a=ap.parse_args()
    mr=root_dir(a.morgenroete); bpm=root_dir(a.better_politics); tr=root_dir(a.tech_res)
    # BPM archive contains both full and Lite mods; deliberately use only the full one.
    bpm_full=bpm/"better-politics-mod"
    if bpm_full.is_dir(): bpm=bpm_full
    # Tech & Res archive may have a single enclosing directory.
    a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.exists(): shutil.rmtree(a.out)
    conflict_dir=a.out.parent/"merge-conflicts"
    if conflict_dir.exists(): shutil.rmtree(conflict_dir)
    conflict_dir.mkdir(parents=True,exist_ok=True)
    conflicts=[]
    copy_source(mr,a.out,"morgenroete",conflicts,base=True)
    copy_source(bpm,a.out,"better-politics-full",conflicts)
    copy_source(tr,a.out,"tech-and-res",conflicts)
    # Merge Russian localization by key: preserve Morgenröte's existing values and append only missing keys from the other mods.
    merge_localization_files(a.out/"localization"/"russian", [mr,bpm,tr], conflicts)
    # Overlay user-prepared localization without deleting or replacing existing Russian strings.
    prepared=a.existing/"work"/"localization"/"russian"
    if prepared.is_dir():
        for p in prepared.glob("*_l_russian.yml"):
            target=a.out/"localization"/"russian"/p.name
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists(): shutil.copy2(p,target)
            else:
                old=target.read_text(encoding="utf-8-sig").splitlines()
                keys={x[0] for x in (parse_loc_line(z) for z in old) if x}
                adds=[]
                for line in p.read_text(encoding="utf-8-sig").splitlines():
                    q=parse_loc_line(line)
                    if q and q[0] not in keys: adds.append(line); keys.add(q[0])
                if adds:
                    with target.open("a",encoding="utf-8",newline="\n") as f:
                        if old and old[-1].strip(): f.write("\n")
                        f.write("\n".join(adds)+"\n")
    # Preserve the hand-merged files and documentation already created in the working branch.
    manual=a.existing/"work"/"merged-mod"
    if manual.is_dir():
        for p in manual.rglob("*"):
            if p.is_file():
                rel=p.relative_to(manual); target=a.out/rel
                target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,target)
    # Create a launcher descriptor. Morgenröte's CMF dependency is retained.
    (a.out/"descriptor.mod").write_text('''name="Global Mod — Morgenröte + Better Politics + Tech & Res"
version="1.0"
supported_version="1.15.*"
dependencies={
  "Community Mod Framework"
}
''',encoding="utf-8")
    # Replace the workshop metadata name while preserving the source metadata structure.
    meta=a.out/".metadata"/"metadata.json"
    if meta.exists():
        import json
        try:
            data=json.loads(meta.read_text(encoding="utf-8"))
            data["name"]="Global Mod — Morgenröte + Better Politics + Tech & Res"
            data["short_description"]="Combined working build of Morgenröte, Better Politics Mod and Tech & Res. See merge report for unresolved file conflicts."
            meta.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        except Exception as e:
            conflicts.append(("metadata-warning",str(meta),"","Could not update metadata: "+str(e)))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["source","source_path","destination_path","handling"])
        w.writerows(conflicts)
    print(f"Output files: {sum(1 for x in a.out.rglob('*') if x.is_file())}")
    print(f"Conflicts/merge notes: {len(conflicts)}")
    print(f"Output size MB: {sum(x.stat().st_size for x in a.out.rglob('*') if x.is_file())/1048576:.1f}")
if __name__=="__main__": main()
