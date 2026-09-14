#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图文 OCR 水印清洗（零依赖）。

背景：该 UP 每张图都铺满斜排固定水印（宝石学家老许® / 許多福珠寶 / 原創設計 /
DESIGN AND VALUE / COLORED GEMSTONE / TEXTURE OF MATERIAL），Vision 会反复识别、
产生大量残缺/误识变体并虚增字数，淹没真实内容。

策略（整行判定，不做行内抹除，最少误伤）：
  1) 归一化 = 小写 + 繁→简(仅水印相关字) + 去除非中英数字字符；
  2) 删尽已知水印短语；
  3) 用 STRONG（具体货种/成品/字段/交易词）保护现货行情、款式、标签、标题；
  4) 短碎片（≤6 中文且含水印特征字、又无 STRONG 实义词）判为水印丢弃；
  5) 其余：有≥2 中文或“数字+单位/款N/编码”则保留，否则丢。
现货价格、货盘、设计稿图里的真实标签都保留；只清品牌水印。

离线重算已采目录（不必重新下图/OCR）：
  /usr/bin/python3 scripts/ocr/clean_watermark.py library/06_articles/raw
"""
import re
import sys
from pathlib import Path

# 归一化空间里的水印短语（小写/去标点/繁转简），按长度降序替换
_WM = [
    "designandvalue", "ofmaterials", "ofmaterial",
    "coloredgemstone", "gemstone", "colored", "texture", "material",
    "宝石学家老许", "金石学家老许", "宝石学家者许", "宝石学家者", "宝石学家",
    "金石学家", "学家老许", "学家者许", "学家君许", "学家竞许", "学家查",
    "学家育", "学家",
    "许多福珠宝", "許多福珠寶", "许多福珠", "許多福珠", "許受福珠", "許多玢",
    "多福珠宝", "多福珠", "受福珠", "福珠宝", "福珠寶", "福珠",
    "原创设计", "原創設計", "原創設言", "原創設计", "原創設", "原創言",
    "創設計", "創設許", "創設", "創设", "原创設", "創设计",
]
WM = sorted(set(_WM), key=len, reverse=True)

_T2S = {"許": "许", "創": "创", "設": "设", "計": "计", "寶": "宝",
        "學": "学", "玢": "玢", "經": "经", "賣": "卖"}
_NON_KEEP = re.compile(r"[^0-9a-z\u4e00-\u9fff]")
_CJK = re.compile(r"[\u4e00-\u9fff]")

# 强实义词：具体货种 / 成品 / 参数字段 / 交易与场景词。命中即倾向保留。
STRONG = re.compile(
    r"蓝宝石|红宝石|祖母绿|钻石|钻戒|翡翠|和田|珍珠|珊瑚|琥珀|蜜蜡|玛瑙|欧泊|澳宝|"
    r"沙佛莱|沙弗莱|尖晶|碧玺|帕拉伊巴|托帕|石榴石|海蓝宝|摩根石|月光石|绿松石|青金|南红|"
    r"贝母|螺钿|蓝宝|红宝|矢车菊|皇家蓝|粉蓝宝|黄蓝宝|白蓝宝|沙弗莱|无烧|有烧|"
    r"耳钉|耳环|戒指|项链|吊坠|手链|手镯|胸针|挂件|镶嵌|成品|裸石|戒面|"
    r"名称|标价|售价|你价|价格|编码|编号|货号|重量|車量|重昂|证书|规格|尺寸|系列|"
    r"现货|上新|卖掉|售出|已售|直播|拍卖|专场|展览|珠宝展|展会|克拉|净度|切工|颜色等级|"
    r"18k|14k|9k|k金|足金|黄金|铂金|金重")
# 水印特征：现货/标签行几乎不会出现这些字（学/创/设/许/福/珠/家），用于碎片兜底
WM_HINT = re.compile(r"[学創设設许許福珠家]|原创|原創")
_CODE = re.compile(r"[a-z]{0,3}\d{4,}|s\d{6,}", re.I)          # 货号/编码
_KUAN = re.compile(r"款\s*\d+|第?\d+\s*款")                    # 款式编号
# 报价/价格档：商家常用 x 隐去尾数（1xxxx / 3xxx / 8xXX，钱袋emoji常被OCR成⑤/幽/$），
# 这类行只有1位数字+若干x、中文为0，会被“超短碎片”误删，必须在归一化空间优先保护。
_PRICE = re.compile(
    r"\d\s*[x*]{1,}|"            # 数字+隐去尾数：1xxxx / 3xxx（归一化后大写X已转小写、乘号×被去标点移除）
    r"[x*]{1,}\s*\d|"            # x1xx 之类错位写法
    r"\d[\d,，.]*\s*(?:元|块|万|w|k|千|百)")  # 常规货币价：8000元 / 1.2w / 1万
_NUM_UNIT = re.compile(r"\d")
_UNIT = re.compile(r"ct|克|k金|mm|分|价|编号|编码|款|系列|无烧|有烧", re.I)


def _norm(s: str) -> str:
    s = s.lower()
    s = "".join(_T2S.get(c, c) for c in s)
    return _NON_KEEP.sub("", s)


def _strip_wm(n: str) -> str:
    for t in WM:
        if t in n:
            n = n.replace(t, "")
    return n


def _substance(r: str) -> bool:
    cn = _CJK.findall(r)
    if _PRICE.search(r):          # 报价行（数字+x隐尾数 / 货币价）优先保护，避免被当超短碎片删除
        return True
    if STRONG.search(r) and len(cn) >= 2:
        return True
    if _NUM_UNIT.search(r) and (_UNIT.search(r) or STRONG.search(r)):
        return True
    if _KUAN.search(r) or _CODE.search(r):
        return True
    if len(cn) >= 4:           # 较长中文：标题/句子（如直播预告、展名），宁留
        return True
    return False


def _is_wm_fragment(r: str) -> bool:
    cn = _CJK.findall(r)
    if len(cn) <= 9 and WM_HINT.search(r) and not STRONG.search(r):
        return True
    return False


def clean_ocr_text(raw: str):
    """返回 (保留行列表, 丢弃行数, 去水印后有效字数)。"""
    kept, dropped = [], 0
    for line in (raw or "").splitlines():
        orig = line.strip()
        if not orig:
            continue
        r = _strip_wm(_norm(orig))
        cn = _CJK.findall(r)
        if not r:
            dropped += 1
        elif _is_wm_fragment(r):
            dropped += 1            # 水印特征碎片优先（哪怕 OCR 凑够 4–9 字）
        elif _substance(r):
            kept.append(orig)
        elif len(cn) <= 3 and not STRONG.search(r):
            dropped += 1            # 超短泛碎片/乱码（如孤立“宝石”）
        elif len(cn) >= 2:
            kept.append(orig)       # 有实际中文、又非水印，宁留勿杀
        else:
            dropped += 1
    clean = "\n".join(kept)
    return kept, dropped, len(re.sub(r"\s", "", clean))


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "library/06_articles/raw")
    import json
    for meta_p in sorted(root.rglob("meta.json")):
        d = json.load(open(meta_p, encoding="utf-8"))
        kept_all, drop_total, raw_chars = [], 0, 0
        for txt in sorted((meta_p.parent / "ocr").glob("*.txt")):
            raw = txt.read_text(encoding="utf-8")
            raw_chars += len(re.sub(r"\s", "", raw))
            kept, drop, _ = clean_ocr_text(raw)
            kept_all.extend(kept)
            drop_total += drop
        clean_chars = sum(len(re.sub(r"\s", "", x)) for x in kept_all)
        print(f"\n=== {d['id']} 图{d['n_images']} | 原始{raw_chars} → 有效{clean_chars}字，删水印行{drop_total} ===")
        for ln in kept_all[:16]:
            print("   ", ln)
        if len(kept_all) > 16:
            print(f"    …余{len(kept_all)-16}行")
