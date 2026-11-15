#!/usr/bin/env python3
"""Static sanity checks for a merged Victoria 3 mod."""
from __future__ import annotations
import argparse, re
from pathlib import Path

KEY_RE=re.compile(r'^\s*([A-Za-z0-9_.:-]+):\d*\s*(.*)$')

def loc_entries(path: Path):
    result={}; duplicates=[]
    for number,line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
        m=KEY_RE.match(line)
        if not m or m.group(1) in {"l_english","l_russian"}: continue
        key,value=m.group(1),m.group(2)
        if key in result: duplicates.append((number,key))
        else: result[key]=value
    return result,duplicates

def brace_check(path: Path):
    text=path.read_text(encoding="utf-8-sig",errors="replace")
    depth=0; in_string=False; escaped=False; comment=False
    for ch in text:
        if comment:
            if ch=="\n": comment=False
            continue
        if in_string:
            if escaped: escaped=False
            elif ch=="\\": escaped=True
            elif ch=='"': in_string=False
            continue
        if ch=="#": comment=True
        elif ch=='"': in_string=True
        elif ch=="{": depth+=1
        elif ch=="}":
            depth-=1
            if depth<0: return "unexpected closing brace"
    if in_string: return "unterminated quoted string"
    if depth: return f"unclosed braces: {depth}"
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mod",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    a=ap.parse_args(); root=a.mod
    script_errors=[]; duplicate_keys=[]; missing_keys=[]; placeholders=[]
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".txt",".gui",".asset",".gfx",".script",".mod"}:
            err=brace_check(p)
            if err: script_errors.append((str(p.relative_to(root)),err))
    enroot=root/"localization"/"english"; ruroot=root/"localization"/"russian"
    english_files=sorted(enroot.rglob("*_l_english.yml")) if enroot.is_dir() else []
    total_en=0; total_ru=0
    for en in english_files:
        rel=en.relative_to(enroot)
        ru=ruroot/rel.parent/rel.name.replace("_l_english.yml","_l_russian.yml")
        enmap,_=loc_entries(en); total_en+=len(enmap)
        if not ru.is_file():
            missing_keys.append((str(rel),"entire Russian file missing")); continue
        rumap,dups=loc_entries(ru); total_ru+=len(rumap)
        duplicate_keys.extend((str(rel),line,key) for line,key in dups)
        for key,value in enmap.items():
            if key not in rumap: missing_keys.append((str(rel),key))
            elif rumap[key]==value: placeholders.append((str(rel),key))
    required=["descriptor.mod"]
    missing_required=[x for x in required if not (root/x).is_file()]
    lines=["# Static validation report","",
        f"- English localization keys: {total_en}",
        f"- Russian localization keys found: {total_ru}",
        f"- English-identical Russian values (possible untranslated placeholders): {len(placeholders)}",
        f"- Missing Russian keys/files: {len(missing_keys)}",
        f"- Duplicate keys within Russian files: {len(duplicate_keys)}",
        f"- Script/config brace or quote errors: {len(script_errors)}",
        f"- Missing required files: {len(missing_required)}","",
        "## Script/config syntax balance errors",""]
    lines += [f"- {p}: {e}" for p,e in script_errors] or ["- None detected"]
    lines += ["","## Duplicate Russian localization keys",""]
    lines += [f"- {p} line {n}: {k}" for p,n,k in duplicate_keys[:300]] or ["- None detected"]
    lines += ["","## Missing Russian localization keys",""]
    lines += [f"- {p}: {k}" for p,k in missing_keys[:300]] or ["- None detected"]
    lines += ["","## English-identical Russian values (first 300)",""]
    lines += [f"- {p}: {k}" for p,k in placeholders[:300]] or ["- None detected"]
    lines += ["","## Missing required files",""]
    lines += [f"- {p}" for p in missing_required] or ["- None detected"]
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("\n".join(lines[:11]))
    for item in duplicate_keys: print("DUPLICATE_RUSSIAN_KEY", item)
    if script_errors or missing_required: raise SystemExit(1)

if __name__=="__main__": main()
