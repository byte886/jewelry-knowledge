#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2 图文采集：把 UP 的图文动态(DYNAMIC_TYPE_DRAW / 少量 ARTICLE/WORD)采下来并 OCR 成 ArticleNote 初稿。

事实背景（2026-09-13 实测）：
- 该 UP 的图文动态几乎都是“纯图片、动态本身零文字”，文字烧在图里（1080 宽竖版卡），
  且每张铺满固定斜排水印；主力链路：登录态 detail 取图 URL -> 下图 -> macOS Vision OCR
  -> clean_watermark 去品牌水印 -> 按图顺序拼 ArticleNote。
- 用户口径（2026-09-13）：现货价格/货盘、克拉与品级、售出状态、设计稿本身就是珠宝知识的一部分，
  不做“纯科普”过滤，全部采、全部留；只做内容类型分类，不丢弃“非科普”内容。
- detail 接口 x/polymer/web-dynamic/v1/detail?id=<动态id>，须在已登录小号 Chrome 的 bilibili
  页面上下文 fetch（浏览器自动带 SESSDATA/bili_ticket）；连接同 harvest_dynamic_types.py：
  环境变量 CHROME_DEV_WS=ws://127.0.0.1:9223/devtools/browser/<id>
- 图在 modules.module_dynamic.major.draw.items[].src（new_dyn 图床，多为 .png）；
  新版 opus 在 major.opus.pics[].url；动态文字在 module_dynamic.desc.text（DRAW 多为空）。

产物（原始层 06_articles，不直接进 05_knowledge；验收后再编译知识层）：
  library/06_articles/raw/<yyyy-mm>/<动态id>/
      meta.json     # 元数据 + 每图(URL/尺寸/文件/原始字/有效字) + content_type
      images/NN.ext # 原图（不可变原始件）
      ocr/NN.txt    # 每张图 Vision OCR 原始逐行文本（不可变，保留水印以便追溯）
      article.md    # 去水印后按图顺序拼的 ArticleNote 初稿(OKF frontmatter, status:draft)

防风控：单线程；detail 每条 3-5s；图片 CDN 每张 0.8-1.8s；遇 code!=0/412/-352 立即停手保断点。
断点：meta.json 标 done 即跳过（--force 重采）。

用法（项目根，先确保 9223 登录 Chrome 已开且停在 space.bilibili.com）：
  /usr/bin/python3 scripts/harvest_articles.py --limit 15
  /usr/bin/python3 scripts/harvest_articles.py --ids 9764..,9765..
  /usr/bin/python3 scripts/harvest_articles.py --offset 20 --limit 10
  /usr/bin/python3 scripts/harvest_articles.py --rebuild       # 不联网：按最新清洗/模板重建所有 article.md
"""
import argparse
import importlib.util
import json
import random
import re
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/ocr"))
from clean_watermark import clean_ocr_text  # noqa: E402
from correct_ocr import correct_line  # noqa: E402

SCAN = ROOT / "library/00_manifest/articles_dynamic_scan.json"
OUT_ROOT = ROOT / "library/06_articles/raw"
OCR_BIN = ROOT / "scripts/ocr/ocr_vision"
UID = "1841256325"
CN_TZ = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

CONTENT_TYPE_CN = {
    "goods_price": "现货行情/货盘",
    "catalog": "款式目录",
    "event": "直播/活动预告",
    "knowledge": "知识科普",
    "mixed_text": "图文(待细分)",
    "image_only": "纯图/设计稿(以图为主)",
}


def load(n, f):
    s = importlib.util.spec_from_file_location(n, str(f))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def now_iso():
    return datetime.now(CN_TZ).replace(microsecond=0).isoformat()


def yq(s):
    return '"' + str(s).replace('"', "'").replace("\n", " ").strip() + '"'


def pub_date(ts):
    try:
        return datetime.fromtimestamp(int(ts), CN_TZ)
    except Exception:
        return None


def classify(clean_text: str, n_img: int) -> str:
    """启发式内容类型（初稿，可解释；不追求 100% 准，供后续组织）。"""
    t = re.sub(r"\s", "", clean_text or "")
    if not t:
        return "image_only"
    if re.search(r"直播|预告|展览|拍卖|专场|展会|复?盘|开播|时间[:：]", t):
        return "event"
    if len(re.findall(r"款\s*\d+|第?\d+\s*款", t)) >= 3:
        return "catalog"
    if (re.search(r"标价|售价|价格|编码|证书|现货|卖掉|已售|售出|无烧|有烧|皇家蓝|矢车菊|精切|切工|货盘", t)
            and re.search(r"\d", t)):
        return "goods_price"
    if len(re.findall(r"\d+[.,]?\d*\s*(?:ct|克拉|g)", t, re.I)) >= 2:
        return "goods_price"     # 多颗重量列表（货盘典型形态）
    if re.search(r"[$￥]\s*\d|\d+\s*元", t):
        return "goods_price"     # 货币价格
    if len(t) >= 120 and re.search(r"[？?。！!]|什么是|如何|怎么|区别|教你|科普|知识|分辨|挑选|保养", t):
        return "knowledge"
    return "mixed_text"


DETAIL_JS = r"""
(async () => {
  const r = await fetch('https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?id=%ID%',
    {credentials:'include', headers:{'Accept':'application/json'}});
  const j = await r.json();
  const it = (j.data && j.data.item) || {};
  const mods = it.modules || {};
  const au = mods.module_author || {};
  const md = mods.module_dynamic || {};
  const major = md.major || {};
  const draw = major.draw || {};
  const opus = major.opus || {};
  const di = (draw.items || []).map(p => ({src:p.src, w:p.width, h:p.height}));
  const op = (opus.pics || []).map(p => ({src:p.url, w:p.width, h:p.height}));
  return JSON.stringify({
    code: j.code, msg: j.message, type: it.type,
    pub_ts: au.pub_ts || null,
    desc: (md.desc && md.desc.text) || '',
    title: opus.title || draw.title || null,
    draw: di, opus: op
  });
})()
"""


def fetch_detail(cdp, sid, dyn_id):
    return json.loads(cdp.eval(sid, DETAIL_JS.replace("%ID%", dyn_id),
                               await_promise=True, timeout=30))


def download_img(url, dst: Path, retries=2):
    url = url.replace("http://", "https://")
    last = None
    for k in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                        "Referer": "https://www.bilibili.com/"})
            data = urllib.request.urlopen(req, context=_SSL, timeout=30).read()
            if len(data) < 200:
                raise RuntimeError(f"图片过小({len(data)}B)疑似异常")
            dst.write_bytes(data)
            return len(data)
        except Exception as e:
            last = e
            time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"下图失败 {url}: {last}")


def run_ocr(img: Path):
    if not OCR_BIN.exists():
        sys.exit(f"找不到 OCR 二进制 {OCR_BIN}，请先编译 scripts/ocr/ocr_vision.swift")
    r = subprocess.run([str(OCR_BIN), str(img)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return "", f"OCR退出码{r.returncode}:{r.stderr[:120]}"
    return "\n".join(x.strip() for x in (r.stdout or "").splitlines() if x.strip()), None


def ext_of(url):
    m = re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", url.lower())
    return ("." + m.group(1).replace("jpeg", "jpg")) if m else ".jpg"


def assemble(d, images, out_dir: Path):
    """images: 每图含 file/w/h/raw/clean(list)；写 article.md，返回(有效总字,类型)。"""
    pub = pub_date(d.get("pub_ts"))
    pub_iso = pub.replace(microsecond=0).isoformat() if pub else None
    pub_str = pub.strftime("%Y-%m-%d") if pub else "日期未知"
    raw_chars = sum(im["raw_chars"] for im in images)
    clean_all, fix_total = [], 0
    for im in images:
        fixed = []
        for ln in im["clean"]:
            c, k = correct_line(ln)
            fixed.append(c)
            fix_total += k
        im["clean_fixed"] = fixed
        im["clean_chars"] = len("".join(fixed))
        clean_all += fixed
    clean_text = "\n".join(clean_all)
    clean_chars = len(re.sub(r"\s", "", clean_text))
    ctype = classify(clean_text, len(images))
    title = d.get("title") or f"图文动态 {pub_str}"
    desc = (f"宝石学家老许 B站图文（{pub_str}，{len(images)}图，"
            f"类型：{CONTENT_TYPE_CN[ctype]}，Vision OCR+去水印初稿，未人工校）")
    fm = [
        "---", "type: ArticleNote",
        f"title: {yq(title)}",
        f"description: {yq(desc)}",
        f'tags: ["图文动态", "{ctype}"]',
        f'content_type: {ctype}',
        "sources:",
        "  - id: src-bili",
        f'    resource: "https://www.bilibili.com/opus/{d["id"]}"',
        '    title: "B站图文动态原页"',
        f'    author: "human:宝石学家老许(mid {UID})"',
        f"    last_modified: {pub_iso or now_iso()}",
        "  - id: src-ocr",
        '    resource: "ocr/"',
        '    title: "本地 Vision OCR 原始逐图文本（未人工校，含水印）"',
        f"generated: {{ by: \"doubao/m2-article-harvest\", at: {now_iso()} }}",
        "status: draft",
        f'dynamic_id: "{d["id"]}"',
        f"n_images: {len(images)}",
        f"published: {pub_iso}",
        f"ocr_chars: {raw_chars}",
        f"clean_chars: {clean_chars}", "---", "",
        f"# {title} ［{d['id']}］", "",
        f"> 作者：宝石学家老许　发布：{pub_str}　图片：{len(images)} 张　"
        f"类型：{CONTENT_TYPE_CN[ctype]}　OCR 原始 {raw_chars} 字 / 去水印有效 {clean_chars} 字"
        + (f"（纠错 {fix_total} 处）" if fix_total else ""),
        f"> 原页：https://www.bilibili.com/opus/{d['id']}　状态 **draft（Vision OCR 自动识别，未人工校）**。",
        "",
    ]
    body = []
    if (d.get("desc") or "").strip():
        body += ["## 动态文字（作者配文）", "", d["desc"].strip(), ""]
    body += ["## 图文正文（去水印后，按图片顺序）", ""]
    for i, im in enumerate(images, 1):
        body.append(f"### 图 {i}")
        body.append("")
        if im.get("clean_fixed"):
            body += ["\n".join(im["clean_fixed"]), ""]
        else:
            body += ["> （去水印后无文字：纯实物图/设计稿，信息在图片本身）", ""]
    body += ["## 图片清单", ""]
    for i, im in enumerate(images, 1):
        body.append(f"{i}. `images/{im['file']}`（{im['w']}×{im['h']}，原始 {im['raw_chars']}/有效 {im['clean_chars']} 字）")
    body.append("")
    (out_dir / "article.md").write_text("\n".join(fm + body), encoding="utf-8")
    return clean_chars, ctype


def harvest_one(cdp, sid, rec, args):
    dyn_id = rec["id"]
    pub = pub_date(rec.get("pub_ts"))
    ym = pub.strftime("%Y-%m") if pub else "unknown"
    out_dir = OUT_ROOT / ym / dyn_id
    meta_path = out_dir / "meta.json"
    if meta_path.exists() and not args.force:
        try:
            if json.loads(meta_path.read_text(encoding="utf-8")).get("done"):
                return "skip"
        except Exception:
            pass
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "ocr").mkdir(parents=True, exist_ok=True)

    d = fetch_detail(cdp, sid, dyn_id)
    if d.get("code") != 0:
        raise RuntimeError(f"detail 被拒 code={d.get('code')} msg={d.get('msg')} → 停手保断点")
    pics = (d.get("draw") or []) + (d.get("opus") or [])
    if not pics:
        raise RuntimeError("detail 无图片，结构异常，停手核对")
    d["id"] = dyn_id

    images, errors = [], []
    for i, p in enumerate(pics, 1):
        ext = ext_of(p.get("src", ""))
        fname = f"{i:02d}{ext}"
        img_path, ocr_path = out_dir / "images" / fname, out_dir / "ocr" / f"{i:02d}.txt"
        existed = img_path.exists()
        size = img_path.stat().st_size if existed else download_img(p["src"], img_path)
        if not existed:
            time.sleep(random.uniform(args.img_min, args.img_max))
        if ocr_path.exists():
            raw = ocr_path.read_text(encoding="utf-8")
            ocr_err = None
        else:
            raw, ocr_err = run_ocr(img_path)
            ocr_path.write_text(raw, encoding="utf-8")
        kept, _, clean_chars = clean_ocr_text(raw)
        if ocr_err:
            errors.append(f"图{i}:{ocr_err}")
        images.append({"idx": i, "url": p["src"].replace("http://", "https://"),
                       "w": p.get("w"), "h": p.get("h"), "file": fname, "bytes": size,
                       "raw_chars": len(re.sub(r"\s", "", raw)),
                       "clean_chars": clean_chars, "clean": kept, "ocr_err": ocr_err})

    clean_total, ctype = assemble(d, images, out_dir)
    img_meta = [{k: v for k, v in im.items() if k != "clean"} for im in images]
    meta = {"id": dyn_id, "type": d.get("type"), "title": d.get("title"),
            "desc": d.get("desc"), "pub_ts": d.get("pub_ts") or rec.get("pub_ts"),
            "n_images": len(images), "clean_chars": clean_total, "content_type": ctype,
            "images": img_meta, "errors": errors, "done": True, "harvested_at": now_iso()}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok", len(images), clean_total, ctype, errors


def rebuild_all():
    """离线重建：从 meta.json + ocr/*.txt 重新清洗、组装 article.md、回写分类/有效字。"""
    n = 0
    for meta_path in sorted(OUT_ROOT.rglob("meta.json")):
        m = json.load(open(meta_path, encoding="utf-8"))
        out_dir = meta_path.parent
        images = []
        for im in m.get("images", []):
            ocr_path = out_dir / "ocr" / f"{im['idx']:02d}.txt"
            raw = ocr_path.read_text(encoding="utf-8") if ocr_path.exists() else ""
            kept, _, cc = clean_ocr_text(raw)
            images.append({**im, "raw_chars": im.get("raw_chars", len(re.sub(r'\s', '', raw))),
                           "clean_chars": cc, "clean": kept})
        d = {"id": m["id"], "pub_ts": m.get("pub_ts"), "title": m.get("title"), "desc": m.get("desc")}
        clean_total, ctype = assemble(d, images, out_dir)
        m["clean_chars"], m["content_type"] = clean_total, ctype
        for i, im in enumerate(images):
            m["images"][i]["clean_chars"] = im["clean_chars"]
        meta_path.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
        print(f"rebuild {m['id']}: {m['n_images']}图 有效{clean_total}字 [{ctype}]")
    print(f"共重建 {n} 条")


def main():
    ap = argparse.ArgumentParser(description="M2 图文采集+OCR+去水印（登录态 detail，慢速防风控）")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="不联网，按最新清洗/模板重建所有 article.md")
    ap.add_argument("--detail-min", type=float, default=3.0)
    ap.add_argument("--detail-max", type=float, default=5.0)
    ap.add_argument("--img-min", type=float, default=0.8)
    ap.add_argument("--img-max", type=float, default=1.8)
    args = ap.parse_args()

    if args.rebuild:
        rebuild_all()
        return

    scan = json.load(open(SCAN, encoding="utf-8"))["items"]
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        recs = [r for r in scan if r["id"] in want]
    else:
        draws = [r for r in scan if r.get("type") == "DYNAMIC_TYPE_DRAW"]
        recs = draws[args.offset:args.offset + args.limit]
    print(f"计划采集 {len(recs)} 条；输出 {OUT_ROOT.relative_to(ROOT)}")

    cdpm = load("cdp_client", ROOT / "cdp_client.py")
    cdp = cdpm.CDP()
    ok = skip = fail = 0
    try:
        t = cdpm.find_space_page(cdp, UID)
        if not t:
            sys.exit("未找到 space.bilibili.com 页面标签，请先打开并确认登录")
        sid = cdp.attach(t["targetId"])
        for n, rec in enumerate(recs, 1):
            try:
                r = harvest_one(cdp, sid, rec, args)
                if r == "skip":
                    skip += 1
                    print(f"[{n}/{len(recs)}] skip(已采) {rec['id']}")
                else:
                    _, nimg, chars, ctype, errs = r
                    ok += 1
                    print(f"[{n}/{len(recs)}] OK {rec['id']} 图{nimg} 有效{chars}字[{ctype}]"
                          + (f" 错误:{errs}" if errs else ""), flush=True)
            except Exception as e:
                fail += 1
                print(f"[{n}/{len(recs)}] FAIL {rec['id']}: {e}", flush=True)
                if "被拒" in str(e) or "412" in str(e) or "-352" in str(e):
                    print("→ 命中风控，立即停止（断点保留，冷却后重跑自动续）", flush=True)
                    break
            if n < len(recs):
                time.sleep(random.uniform(args.detail_min, args.detail_max))
    finally:
        cdp.ws.close()
    print(f"\n汇总：成功 {ok}，跳过 {skip}，失败 {fail}")


if __name__ == "__main__":
    main()
