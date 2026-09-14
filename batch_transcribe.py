#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量转写器（必须用装了 funasr 的解释器直接跑，或设 FUNASR_PYTHON 后由 transcribe 自举）：
- 模型只加载一次，循环对已下载视频抽 16k 音轨 → FunASR 转写，避免每条重载模型；
- 读 00_manifest/manifest.json，只转 status=downloaded 且本地有视频、尚缺 transcript 的；
- 产物 04_transcript/<分类>/<视频名>/transcript.md + .json，转完把台账置 transcribed；
- 断点续跑：已有 transcript.md 自动跳过。
用法：<funasr-python> batch_transcribe.py [--limit N] [--lang zh]
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "library"
SKILL = Path("/Users/wenjiechen/Doubao/skills/multiplatform-media-fetch/scripts")
sys.path.insert(0, str(SKILL))
import transcribe as T  # 在 funasr venv 下 import funasr 成功，复用其清洗/抽轨/加载模型

# 实测同音错字校正表（只收录确认的，宁少勿滥，避免误伤）
TYPO = {"香费": "镶嵌", "接助": "借助"}
VIDEO_EXT = (".mp4", ".mkv", ".webm", ".m4a")


def fix(t: str) -> str:
    for a, b in TYPO.items():
        t = t.replace(a, b)
    return t


def find_video(r):
    vd = LIB / "01_video" / r["category"]
    if not vd.exists():
        return None
    tag = f"[{r['bvid']}]"  # 文件名含字面方括号，不能用 glob（[] 会被当字符类），用字符串包含
    hits = [p for p in vd.iterdir() if tag in p.name and p.suffix.lower() in VIDEO_EXT]
    return hits[0] if hits else None


def duration_of(p: Path) -> float:
    try:
        q = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                           capture_output=True, text=True)
        return float(q.stdout.strip() or 0)
    except Exception:
        return 0.0


def save(rows):
    json.dump(rows, open(LIB / "00_manifest" / "manifest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--lang", default="zh")
    a = ap.parse_args()

    rows = json.load(open(LIB / "00_manifest" / "manifest.json", encoding="utf-8"))
    model, done, skip, miss = None, 0, 0, 0
    for i, r in enumerate(rows, 1):
        if r.get("status") not in ("downloaded", "transcribed"):
            continue
        vf = find_video(r)
        if not vf:
            miss += 1; continue
        outdir = LIB / "04_transcript" / r["category"] / vf.stem
        md = outdir / "transcript.md"
        if md.exists() and md.stat().st_size > 100:
            r["status"] = "transcribed"; skip += 1; continue
        if a.limit and done >= a.limit:
            print(f"到达 --limit {a.limit}，本轮停"); break
        if model is None:
            t = time.time(); model = T._load_model(); print(f"模型加载 {time.time()-t:.1f}s", flush=True)

        outdir.mkdir(parents=True, exist_ok=True)
        wav = outdir / "_a16k.wav"
        if not T._ffmpeg_to_wav(str(vf), str(wav)):
            print(f"  [warn] 抽轨失败 {vf.name}"); continue
        total = duration_of(wav)
        t0 = time.time()
        res = model.generate(input=str(wav), language=a.lang, use_itn=True, batch_size_s=60)
        el = time.time() - t0
        segs = [fix(T._clean(x.get("text", ""))) for x in res]
        segs = [s for s in segs if s]
        full = "。".join(segs) + "。"
        speed = total / el if el else 0
        paras = T._split_paras(full)
        md.write_text(
            f"# {vf.stem}\n\n> 自动转写 | 语言 {a.lang} | 时长 {total:.0f}s | "
            f"耗时 {el:.1f}s | {speed:.1f}x实时 | 约 {len(full)} 字 | BV {r['bvid']} | "
            f"分类 {r['category']}\n\n" + "\n\n".join(f"## 第{k}段\n\n{p}" for k, p in enumerate(paras, 1))
            + "\n", encoding="utf-8")
        json.dump({"bvid": r["bvid"], "title": r["title"], "category": r["category"],
                   "topic": r.get("topic"), "season": r.get("season"), "duration": total,
                   "elapsed": el, "chars": len(full), "segments": segs},
                  open(outdir / "transcript.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        wav.unlink(missing_ok=True)
        r["status"] = "transcribed"; done += 1; save(rows)
        print(f"[{i}] {speed:.1f}x {len(full)}字 {r['category']} | {vf.stem[:34]}", flush=True)

    save(rows)
    nt = sum(r.get("status") == "transcribed" for r in rows)
    print(f"\n本轮新转 {done}、已存在跳过 {skip}、缺视频 {miss}；台账 transcribed 累计 {nt}/{len(rows)}")


if __name__ == "__main__":
    main()
