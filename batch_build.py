#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宝石学家老许 全量归档编排器（manifest 驱动、断点续跑、防风控慢速）。
职责：读投稿清单 -> 分类规划 -> 逐 BV（取文字 + 下视频）-> 台账落盘。
- 取文字：优先复用技能 fetch_for_article.py（字幕>最小音频），音频再交 transcribe.py；
- 下视频：技能 media_downloader.py（B站强制直连/限速2MiB/s/请求间隔，已内置）；
- 防风控：单线程、文件间随机间隔、每 BATCH 个长冷却、子进程返回 412(退出码14) 则长冷却；
           已 done 的 BV 自动跳过，可随时中断重跑。
用法：
  python3 batch_build.py --plan-only        # 只做分类规划+台账，不下载（先给人看分类）
  python3 batch_build.py --limit 3          # 只处理前3个（链路实测）
  python3 batch_build.py                    # 正式全量（慢速、可中断续跑）
"""
import argparse, csv, json, os, random, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "library"
SKILL = Path("/Users/wenjiechen/Doubao/skills/multiplatform-media-fetch/scripts")
FETCH_ART = SKILL / "fetch_for_article.py"
DOWNLOAD = SKILL / "media_downloader.py"
TRANSCRIBE = SKILL / "transcribe.py"
# 有 yt-dlp 的解释器（脚本也会自举，显式指定更稳）
PY = "/Users/wenjiechen/Doubao/chats/2026-09-05/new-chat-2/.venv/bin/python"

# ---- 两段式分类：先材质/品类（查某类宝石能聚合其选购/真假/价格全部内容），
#      无明确材质才按场景维度兜底。标题先去空格（UP 常用插空格规避检索）----
# 第一段：材质 / 品类 / 佩戴（按优先级，首个命中即归）
MATERIAL_RULES = [
    ("01_钻石", ["钻", "莫桑"]),
    ("02_彩色宝石", ["红宝石", "蓝宝石", "红宝", "蓝宝", "彩宝", "宝石", "祖母绿", "碧玺", "尖晶",
                  "石榴石", "海蓝宝", "圣玛利亚", "托帕", "坦桑", "橄榄石", "水晶", "锆石", "金绿",
                  "猫眼", "变石", "萤石", "沙弗莱", "帕拉伊巴", "帕帕拉恰", "绝地", "芬达", "欧泊",
                  "赛黄晶", "月光石", "拉长石", "天河石", "青金", "堇青", "榍石", "锂辉", "透辉",
                  "长石", "柱石", "刚玉", "鸽血红", "色石", "裸石", "矿标", "矿"]),
    ("03_玉石", ["翡翠", "和田玉", "玉石", "南红", "玛瑙", "绿松石", "岫玉", "碧玉", "籽料",
               "白玉", "玉", "翠"]),
    ("04_有机宝石", ["珍珠", "澳白", "akoya", "蜜蜡", "琥珀", "珊瑚", "海螺珠", "象牙", "猛犸",
                  "玳瑁", "沉香", "紫檀", "老山檀", "檀", "木质", "手串", "隔珠", "牛角"]),
    ("05_金属首饰与佩戴", ["黄金", "铂金", "白金", "k金", "18k", "足金", "硬金", "纯银", "银饰",
                   "金饰", "大金链", "首饰", "项链", "戒指", "对戒", "吊坠", "手镯", "手链",
                   "耳饰", "耳钉", "耳环", "胸针", "鸡尾酒戒", "镶嵌", "镶", "定制", "客订",
                   "设计", "款式", "两戴", "搭配", "佩戴", "怎么戴", "这么戴", "戴", "同款", "风格",
                   "流行色", "美拉德", "叠戴", "轻奢", "高级感", "贵气", "显白", "显老", "送礼",
                   "礼物", "备婚", "结婚", "情侣", "七夕", "母亲节", "圣诞", "情人节", "相亲",
                   "男士", "珐琅", "编织", "工艺", "精切", "切工", "保养", "养护", "焕新"]),
]
# 第二段：无材质时的场景 / 维度
DIMENSION_RULES = [
    ("06_鉴定与避坑", ["鉴定", "证书", "真假", "造假", "骗局", "骗", "避坑", "避雷", "染色", "注胶",
                   "充填", "填充", "合成", "处理", "优化", "烤色", "辐照", "老烧", "套路", "揭秘",
                   "辨别", "鉴别", "区别", "玻璃", "塑料", "人造", "翻车", "智商税", "猫腻", "ngtc",
                   "国检", "igi", "实验室", "复检", "无良商家", "红黑榜", "造谣", "伪", "假"]),
    ("07_行情与选购", ["价格", "行情", "保值", "升值", "回收", "市场", "值不值", "值得买", "值得",
                   "选购", "怎么选", "这样选", "这么选", "怎么挑", "怎么买", "多少钱", "涨价", "降价",
                   "投资", "预算", "入手", "性价比", "热度", "排行", "趋势", "划算", "长期主义",
                   "价位", "买", "平替", "捡漏", "消费", "等等党", "增值", "跑赢"]),
    ("08_行业与商业", ["行业", "商业", "创业", "从业", "生意", "供应链", "水贝", "番禺", "批发",
                   "零售", "关税", "加征", "展会", "珠宝展", "展览", "拍卖", "春拍", "秋拍", "老板",
                   "职业", "毕业", "就业", "转型", "赛道", "寒冬", "洗牌", "震荡", "危机", "停工",
                   "停产", "爆雷", "代购", "门店", "品牌", "新媒体", "短视频", "流量", "课程",
                   "精品课", "开课", "招生", "培训", "报告", "前瞻", "复盘", "商家", "珠宝商",
                   "珠宝人", "珠宝店", "赚钱", "经营", "拓品", "政策", "特朗普", "俄乌", "市监局",
                   "整顿", "IP", "疗愈", "盛会"]),
    ("09_品牌新品与动态", ["新品", "上新", "新款", "首发", "返场", "周年", "福利", "抽奖", "礼盒",
                   "预告", "直播", "粉丝", "成就", "重磅", "抢先", "到货", "专场见", "庆"]),
    ("10_珠宝文化与故事", ["历史", "王室", "王妃", "皇室", "国王", "皇后", "戴安娜", "关之琳",
                   "豪门", "港圈", "故事", "由来", "起源", "文化", "东方", "非遗", "五行", "生肖",
                   "寓意", "传统", "神话", "女明星", "名人", "失窃", "定情信物"]),
]
FALLBACK = "11_其他"

def safe_name(s, maxlen=80):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen] or "untitled"

def classify_topic(title):
    t = re.sub(r"\s+", "", (title or "").lower())   # 去全部空白，修复“祖 母 绿”式插空格
    for rules in (MATERIAL_RULES, DIMENSION_RULES):       # 先材质，后维度
        for cat, kws in rules:
            if any(k.lower() in t for k in kws):
                return cat
    return FALLBACK

def load_videos():
    # 权威清单：登录态 arc/search 全量产物（743）
    p = ROOT / "up_videos_login.json"
    if p.exists():
        return json.load(open(p, encoding="utf-8"))["videos"]
    sys.exit("还没有投稿清单 up_videos_login.json（先用 login_list.py 拉全）")

def load_season_map():
    p = ROOT / "season_map.json"   # {bvid: 官方合集名}，collect_full_seasons.py 生成
    return json.load(open(p, encoding="utf-8")) if p.exists() else {}

def build_plan(videos, season_map=None):
    """两层归类：有官方合集 -> 合集·<名>（UP 亲分，最权威）；否则按 8 大主题兜底。
    每条同时记 topic（主题标签，合集内视频也打，便于知识库交叉检索）。"""
    rows, seen = [], set()
    for v in videos:
        bv = v.get("bvid")
        if not bv or bv in seen:
            continue
        seen.add(bv)
        topic = classify_topic(v.get("title"))
        season = (season_map or {}).get(bv) or ""
        if season:   # 去掉合集名自带的“合集·”前缀，统一加【合集】聚拢，避免重复
            sn = re.sub(r"^合集[·:：\s]*", "", season)
            cat = "【合集】" + safe_name(sn)
        else:
            cat = topic
        rows.append({"bvid": bv, "title": v.get("title", ""), "length": v.get("length", ""),
                     "created": v.get("created"), "play": v.get("play"), "url": v.get("url"),
                     "topic": topic, "season": season, "category": cat,
                     "video": "", "text": "", "status": "pending"})
    return rows

def save_manifest(rows):
    mp = LIB / "00_manifest" / "manifest.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cp = mp.with_suffix(".csv")
    with open(cp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["bvid", "title", "length", "category", "topic",
                                          "season", "created", "play", "status", "video", "text", "url"])
        w.writeheader()
        for r in rows: w.writerow({k: r.get(k, "") for k in w.fieldnames})
    return mp

def run(cmd):
    print("   $", " ".join(cmd[:2]), "...", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True)

def process_one(r, quality=720):
    """只负责下载 720p 到分类目录（限速/间隔/直连由下载器内置）。
    全库分层实测 0 CC 字幕，故不再单独下最小音频；转写交给 batch_transcribe.py
    从本地视频抽轨（避免同一条重复下载两份流量）。"""
    cat, bv = r["category"], r["bvid"]
    vdir = LIB / "01_video" / cat
    vdir.mkdir(parents=True, exist_ok=True)
    vd = run([PY, str(DOWNLOAD), bv, "--quality", str(quality), "-o", str(vdir)])
    if vd.returncode == 14:   # B站412风控
        return "cool412"
    if vd.returncode != 0:
        print("   [warn] 下载返回码", vd.returncode, (vd.stderr or "")[-200:])
        return "fail"
    r["video"] = str(vdir)
    r["status"] = "downloaded"
    return "ok"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="本轮最多新处理多少条（不影响全量台账）")
    ap.add_argument("--quality", type=int, default=720)
    ap.add_argument("--gap", type=float, default=(3, 6), nargs=2)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--batch-cool", type=int, default=120)
    ap.add_argument("--risk-cool", type=int, default=900)
    a = ap.parse_args()

    videos = load_videos()
    season_map = load_season_map()
    rows = build_plan(videos, season_map)
    # 断点续跑：按 bvid 合并旧台账的状态/路径，中断重跑不丢进度
    mp0 = LIB / "00_manifest" / "manifest.json"
    if mp0.exists():
        old = {r["bvid"]: r for r in json.load(open(mp0, encoding="utf-8"))}
        merged = 0
        for r in rows:
            o = old.get(r["bvid"])
            if o and o.get("status") in ("downloaded", "transcribed"):
                r["status"] = o["status"]; r["video"] = o.get("video", ""); merged += 1
        if merged:
            print(f"[resume] 旧台账已有 {merged} 条完成，自动跳过\n")
    mp = save_manifest(rows)
    import collections
    dist = collections.Counter(r["category"] for r in rows)
    tdist = collections.Counter(r["topic"] for r in rows)

    def to_sec(s):
        try:
            p = list(map(int, str(s).split(":")))
            return sum(n * 60 ** i for i, n in enumerate(p[::-1]))
        except Exception:
            return 0
    total_sec = sum(to_sec(r["length"]) for r in rows)
    print(f"清单 {len(rows)} 个去重视频，总时长 {total_sec/3600:.1f} 小时\n")
    print("== 顶层归档目录（官方合集优先，其余按主题） ==")
    for c, n in sorted(dist.items()):
        print(f"  {n:>4}  {c}")
    print("\n== 主题交叉分布（合集内视频也计入，供知识库打标） ==")
    for c, n in sorted(tdist.items()):
        print(f"  {n:>4}  {c}")
    print("台账：", mp)
    if a.plan_only:
        print("\n[plan-only] 只规划不下载。前 25 条分类预览：")
        for r in rows[:25]:
            print(f"  [{r['category']}] {str(r['length']):>7} {r['bvid']} {r['title'][:30]}")
        return

    DONE = {"downloaded", "transcribed"}
    tried = done = fail = 0
    for i, r in enumerate(rows, 1):
        if r["status"] in DONE:
            continue
        if a.limit and tried >= a.limit:
            print(f"\n到达 --limit {a.limit}，本轮停止（全量台账已保存，可续跑）"); break
        print(f"[{i}/{len(rows)}] {r['category']} | {r['bvid']} | {r['title'][:36]}", flush=True)
        tried += 1
        st = process_one(r, a.quality)
        if st == "cool412":
            print(f"  !! 触发412，整体冷却 {a.risk_cool}s（台账已存可续跑）", flush=True)
            save_manifest(rows); time.sleep(a.risk_cool); continue
        if st == "ok":
            done += 1
        else:
            fail += 1
        save_manifest(rows)
        if tried % a.batch == 0:
            print(f"  -- 每{a.batch}个长冷却 {a.batch_cool}s --", flush=True); time.sleep(a.batch_cool)
        else:
            time.sleep(random.uniform(*a.gap))
    save_manifest(rows)
    nd = sum(r["status"] in DONE for r in rows)
    print(f"\n本轮新下载成功 {done}、失败 {fail}；累计完成 {nd}/{len(rows)}")

if __name__ == "__main__":
    main()
