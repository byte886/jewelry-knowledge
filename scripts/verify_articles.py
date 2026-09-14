#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_articles.py — 图文采集完整性/一致性校验（思路移植高顿 verify_ocr.py：
源数量必须与各层产物数量逐一对齐，少即残缺）。

逐篇核对：
  meta.done；实际 images 文件数 == meta.n_images == meta.images 条数；
  ocr/*.txt 数 == 图数；article.md 存在且 frontmatter 合规、n_images 与实际一致；
  每张原图非空(>2KB)。
用法：/usr/bin/python3 scripts/verify_articles.py [library/06_articles/raw]
残缺退出码 1。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "library/06_articles/raw"
MIN_IMG_BYTES = 2048


def main():
    dirs = sorted(p for p in RAW.glob("*/*") if p.is_dir())
    ok, bad = 0, []
    if not dirs:
        print("未发现任何采集目录")
        sys.exit(1)
    for d in dirs:
        errs = []
        mp = d / "meta.json"
        if not mp.exists():
            bad.append((d.name, ["缺 meta.json"])); continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as e:
            bad.append((d.name, [f"meta 解析失败:{e}"])); continue
        if not m.get("done"):
            errs.append("meta 未 done")
        n = m.get("n_images")
        imgs = sorted((d / "images").glob("*")) if (d / "images").exists() else []
        ocrs = sorted((d / "ocr").glob("*.txt")) if (d / "ocr").exists() else []
        imgs = [x for x in imgs if not x.name.startswith(".")]
        if n is not None and len(imgs) != n:
            errs.append(f"实际图{len(imgs)}≠n_images{n}")
        if len(m.get("images", [])) != len(imgs):
            errs.append(f"meta.images{len(m.get('images', []))}≠实际图{len(imgs)}")
        if len(ocrs) != len(imgs):
            errs.append(f"OCR文本{len(ocrs)}≠图{len(imgs)}")
        for im in imgs:
            if im.stat().st_size < MIN_IMG_BYTES:
                errs.append(f"图过小 {im.name}={im.stat().st_size}B")
        ap = d / "article.md"
        if not ap.exists():
            errs.append("缺 article.md")
        else:
            t = ap.read_text(encoding="utf-8")
            if not t.startswith("---") or "type: ArticleNote" not in t:
                errs.append("article frontmatter 异常")
            mm = re.search(r"n_images:\s*(\d+)", t)
            if mm and n is not None and int(mm.group(1)) != n:
                errs.append(f"article.n_images{mm.group(1)}≠meta{n}")
        if errs:
            bad.append((d.name, errs))
        else:
            ok += 1
    print(f"图文篇数 {len(dirs)} | 完整 {ok} | 残缺 {len(bad)}")
    for name, errs in bad:
        print(f"  [残缺] {name}: {'；'.join(errs)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
