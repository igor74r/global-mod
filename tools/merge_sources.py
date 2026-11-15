#!/usr/bin/env python3
"""Assemble and validate a Victoria 3 combined mod from the three source archives."""
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

def parse_loc_value(line: str):
    m=re.match(r'^\s*([A-Za-z0-9_.:-]+):(\d*)\s*(.*)$',line)
    if not m: return None
    return m.group(1),m.group(3)

def english_values(src: Path, rel: Path) -> dict[str,str]:
    name=rel.name.replace("_l_russian.yml","_l_english.yml")
    p=src/"localization"/"english"/rel.parent/name
    values={}
    if p.is_file():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            item=parse_loc_value(line)
            if item: values[item[0]]=item[1]
    return values

def merge_localization_files(dst: Path, sources: list[Path], conflicts: list):
    # Add missing keys and replace only English placeholders; never overwrite an existing translation.
    for src in sources:
        locroot=src/"localization"/"russian"
        if not locroot.is_dir(): continue
        for p in locroot.rglob("*_l_russian.yml"):
            if not p.is_file(): continue
            rel=p.relative_to(locroot)
            target=dst/rel
            incoming=p.read_text(encoding="utf-8-sig").splitlines()
            english=english_values(src,rel)
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target)
                continue
            existing=target.read_text(encoding="utf-8-sig").splitlines()
            positions={}; values={}
            for i,line in enumerate(existing):
                item=parse_loc_value(line)
                if item and item[0] not in positions:
                    positions[item[0]]=i; values[item[0]]=item[1]
            additions=[]; replaced=0
            for line in incoming:
                item=parse_loc_value(line)
                if not item: continue
                key,value=item
                if key not in positions:
                    positions[key]=len(existing)+len(additions)
                    values[key]=value
                    additions.append(line)
                elif key in english and values[key]==english[key] and value!=english[key]:
                    existing[positions[key]]=line
                    values[key]=value
                    replaced+=1
            if additions or replaced:
                if additions and existing and existing[-1].strip(): existing.append("")
                target.write_text("\n".join(existing+additions)+"\n",encoding="utf-8")
                conflicts.append(("localization-merged",str(rel),str(target),f"added {len(additions)} missing keys; replaced {replaced} English placeholders"))

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
    # Overlay user-prepared localization: preserve real Russian strings but replace English placeholders.
    prepared=a.existing/"work"/"localization"/"russian"
    if prepared.is_dir():
        for p in prepared.glob("*_l_russian.yml"):
            target=a.out/"localization"/"russian"/p.name
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists(): shutil.copy2(p,target)
            else:
                old=target.read_text(encoding="utf-8-sig").splitlines()
                positions={}; values={}
                for idx,line in enumerate(old):
                    item=parse_loc_value(line)
                    if item and item[0] not in positions:
                        positions[item[0]]=idx; values[item[0]]=item[1]
                prepared_lines=p.read_text(encoding="utf-8-sig").splitlines()
                english={}
                for source in [mr,bpm,tr]:
                    for key,value in english_values(source,Path(p.name)).items():
                        english.setdefault(key,set()).add(value)
                adds=[]; replaced=0
                for line in prepared_lines:
                    item=parse_loc_value(line)
                    if not item: continue
                    key,value=item
                    if key not in positions:
                        positions[key]=len(old)+len(adds); values[key]=value; adds.append(line)
                    elif values[key] in english.get(key,set()) and value not in english.get(key,set()):
                        old[positions[key]]=line; values[key]=value; replaced+=1
                if adds and old and old[-1].strip(): old.append("")
                if adds or replaced: target.write_text("\n".join(old+adds)+"\n",encoding="utf-8")
    # Preserve the hand-merged files and documentation already created in the working branch.
    manual=a.existing/"work"/"merged-mod"
    if manual.is_dir():
        for p in manual.rglob("*"):
            if p.is_file():
                # Keep project notes and build diagnostics in the repository, not inside the game mod.
                if p.name in {"README.md", "MERGE_NOTES.md", "BUILD_REPORT.md", "merge-conflicts.csv"}:
                    continue
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
