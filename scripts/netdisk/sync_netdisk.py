#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
珠宝知识库 → 百度网盘成品同步编排器（只传成品，不传过程件）。

分层映射（网盘风格对齐「股票知识库」：顶层中文 + 编号-中文）：
  library/01_video       -> 珠宝知识库/01-视频原片   (*.mp4)
  library/04_transcript  -> 珠宝知识库/02-视频转写   (仅 transcript.md，跳过 transcript.json/_wav)
  library/06_articles    -> 珠宝知识库/03-图文动态   (将来 M2 成品 .md/.txt/.jpg/.png)
  library/07_books       -> 珠宝知识库/04-书籍精华   (将来 M4 .md/.txt/.pdf)
  library/05_knowledge   -> 珠宝知识库/05-知识成品   (OKF 全部 .md)

设计原则（参考高顿 upload_course.sh）：
  - 通用上传交给同目录 baidu_upload.py（分片/秒传/同名覆盖 rtype=3/URL编码），本脚本只做枚举、过滤、编排、断点；
  - 过程件一律不传：02_audio、transcript.json、workspace/、_archive/、secrets/、.DS_Store、__pycache__；
  - 百度 create 拒绝 emoji（errno -7，全库 96 个路径命中）：仅对【网盘远程名】做净化去 emoji，本地文件名一律不动；
  - 断点续传：workspace/netdisk/uploaded.tsv 记录已传(相对路径+size)，重跑自动跳过；失败落 failed.tsv 不中断整体。

用法（在项目根运行）：
  python3 scripts/netdisk/sync_netdisk.py --dry-run                 # 只看会传什么/远程映射，不真传
  python3 scripts/netdisk/sync_netdisk.py --only knowledge,transcript --limit 3   # 选层限量试传
  python3 scripts/netdisk/sync_netdisk.py                           # 全量同步（含13G视频，耗时长，建议后台）
  python3 scripts/netdisk/sync_netdisk.py --only video --sleep 4    # 只传视频且文件间隔4s
可选：--force 忽略已传记录重传；--only 取值 video/transcript/article/book/knowledge
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ---- 定位项目根（含 library/ 的祖先）与通用上传器 ----
def project_root() -> Path:
    p = Path(__file__).resolve()
    for _ in range(6):
        p = p.parent
        if (p / "library").is_dir():
            return p
    sys.exit("找不到项目根（应含 library/）")

ROOT = project_root()
UPLOADER = Path(__file__).resolve().parent / "baidu_upload.py"
NETDISK_BASE = "/apps/CPA课程归档/珠宝知识库"
STATE_DIR = ROOT / "workspace" / "netdisk"
UPLOADED_TSV = STATE_DIR / "uploaded.tsv"
FAILED_TSV = STATE_DIR / "failed.tsv"

# 每层：key, 本地目录, 网盘目录, 接收哪些文件（返回 True/False）
def only_transcript_md(rel: Path) -> bool:
    # 只传成品 transcript.md；transcript.json、_audio16k.wav 等过程件不传
    return rel.name == "transcript.md"

def is_md(rel: Path) -> bool:
    return rel.suffix.lower() == ".md"

def is_article_asset(rel: Path) -> bool:
    return rel.suffix.lower() in {".md", ".txt", ".jpg", ".jpeg", ".png"}

def is_book_asset(rel: Path) -> bool:
    return rel.suffix.lower() in {".md", ".txt", ".pdf", ".epub"}

def is_video(rel: Path) -> bool:
    return rel.suffix.lower() == ".mp4"

LAYERS = [
    ("video",      "library/01_video",      "01-视频原片", is_video),
    ("transcript", "library/04_transcript", "02-视频转写", only_transcript_md),
    ("article",    "library/06_articles",   "03-图文动态", is_article_asset),
    ("book",       "library/07_books",      "04-书籍精华", is_book_asset),
    ("knowledge",  "library/05_knowledge",  "05-知识成品", is_md),
]

# 任意层出现这些路径段都跳过（过程件/敏感件）
SKIP_PARTS = {"workspace", "_archive", "secrets", ".secrets", "__pycache__", ".git", "02_audio"}
SKIP_NAMES = {".DS_Store", "transcript.json"}

# emoji / 百度非法字符：仅用于【远程名】净化（本地不动）
_EMOJI = re.compile(
    "[" 
    "\U0001F000-\U0001FAFF"   # 杂项符号、emoji、补充符号、交通、补充A/B/C
    "\U00002600-\U000027BF"   # 杂项符号、装饰符号
    "\U0001F1E6-\U0001F1FF"   # 区域指示符（旗帜）
    "\u2190-\u2BFF"           # 箭头/数学/符号里的图形字符（⚠ 等）
    "\uFE0F\u200D"            # 变体选择符、零宽连字
    "]"
)
_BAD = re.compile(r'[\\/:*?"<>|]')  # 半角非法（网盘/Windows），本地虽无也兜底

def sanitize_remote_segment(seg: str) -> str:
    s = _EMOJI.sub("", seg)
    s = _BAD.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()  # 折叠空白
    return s

def sanitize_remote(rel: Path) -> str:
    return "/".join(sanitize_remote_segment(p) for p in rel.parts if p not in ("", "."))

def iter_layer_files(local_dir: Path, accept):
    if not local_dir.is_dir():
        return
    for dp, dn, fn in os.walk(local_dir):
        # 原地剪枝跳过目录
        dn[:] = [d for d in dn if d not in SKIP_PARTS]
        for f in sorted(fn):
            if f in SKIP_NAMES:
                continue
            full = Path(dp) / f
            rel = full.relative_to(local_dir)
            if accept(rel):
                yield full, rel

def load_uploaded():
    done = {}
    if UPLOADED_TSV.exists():
        for line in UPLOADED_TSV.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                done[parts[0]] = (parts[1], parts[2])  # rel -> (size, remote)
    return done

def append_uploaded(rel, size, remote):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with UPLOADED_TSV.open("a", encoding="utf-8") as f:
        f.write(f"{rel}\t{size}\t{remote}\n")

def append_failed(rel, remote, msg):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with FAILED_TSV.open("a", encoding="utf-8") as f:
        f.write(f"{rel}\t{remote}\t{msg}\n")

def main():
    ap = argparse.ArgumentParser(description="珠宝知识库成品同步到百度网盘")
    ap.add_argument("--only", default="", help="只同步指定层，逗号分隔：video/transcript/article/book/knowledge")
    ap.add_argument("--limit", type=int, default=0, help="每层最多传 N 个（试传用，0=不限）")
    ap.add_argument("--sleep", type=float, default=1.5, help="文件间隔秒（视频自动×3），默认1.5")
    ap.add_argument("--dry-run", action="store_true", help="只列计划不真传")
    ap.add_argument("--force", action="store_true", help="忽略已传记录强制重传")
    args = ap.parse_args()

    sel = {s.strip() for s in args.only.split(",") if s.strip()}
    uploaded = {} if args.force else load_uploaded()
    total_ok = total_skip = total_fail = 0

    for key, ldir_name, ndir, accept in LAYERS:
        if sel and key not in sel:
            continue
        ldir = ROOT / ldir_name
        plan = list(iter_layer_files(ldir, accept))
        if not plan:
            print(f"[{key}] {ldir_name} 无待传文件（目录不存在或被过滤）")
            continue
        n_sent = 0
        print(f"\n===== [{key}] {ldir_name} -> {ndir}（候选 {len(plan)} 个）=====")
        for full, rel in plan:
            rel_s = rel.as_posix()
            size = full.stat().st_size
            remote_rel = sanitize_remote(rel)
            remote = f"{NETDISK_BASE}/{ndir}/{remote_rel}"
            # 断点：已传且大小一致则跳过
            prev = uploaded.get(rel_s)
            if prev and prev[0] == str(size):
                total_skip += 1
                continue
            if args.dry_run:
                tag = " [名字含emoji将净化]" if remote_rel != rel_s else ""
                print(f"  DRY {rel_s} ({size}B){tag}\n     -> {remote}")
                n_sent += 1
            else:
                r = subprocess.run([sys.executable, str(UPLOADER), "upload", str(full), remote],
                                   capture_output=True, text=True)
                out = (r.stdout or "") + (r.stderr or "")
                if "Done!" in out:
                    append_uploaded(rel_s, size, remote)
                    total_ok += 1
                    n_sent += 1
                    print(f"  OK [{n_sent}] {rel_s} ({size}B)")
                else:
                    total_fail += 1
                    msg = out.strip().replace("\n", " ")[-200:]
                    append_failed(rel_s, remote, msg)
                    print(f"  FAIL {rel_s} -> {msg[:120]}")
                import time
                time.sleep(args.sleep * (3 if key == "video" else 1))
            if args.limit and n_sent >= args.limit:
                print(f"  达到 --limit {args.limit}，本层停止")
                break
    print(f"\n汇总：成功 {total_ok}，跳过(已传) {total_skip}，失败 {total_fail}")
    if not args.dry_run and total_fail:
        print(f"失败清单见 {FAILED_TSV}，修复后重跑本脚本即可续传（已传自动跳过）")

if __name__ == "__main__":
    main()
