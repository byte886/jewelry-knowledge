#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
珠宝图文 OCR 常见误识纠错（零依赖、保守）。

定位：在 clean_watermark 去水印之后使用。只修“高置信、足够特异、正常中文不会出现”的错形，
对应高顿 OCR SOP 里“高顿教肓→高顿教育”的固定后处理；拿不准的不改，留给知识层人工精修。
两类：
  1) 固定错词表（字段名/宝石名/切工的形近误识，全局安全替换）；
  2) 货盘单位正则（数字后被切碎的 ct：c/ci/g/Gt；小数点误作逗号）。
原始 OCR 文本永不改写（ocr/NN.txt 保留），纠错只作用于 article.md 成稿。

用法：
  /usr/bin/python3 scripts/ocr/correct_ocr.py "名冰：岢伦比业祖母经 車量 2.11Gt 1,34ct"
  /usr/bin/python3 scripts/ocr/correct_ocr.py library/06_articles/raw   # 离线对照
"""
import re
import sys
from pathlib import Path

# 固定错词 → 正确词（按特异度，正常文本几乎不可能出现左侧错形）。
# 注意顺序：先处理多字组合错形（如“哥伦比业亚”），再处理短错形，避免过度替换。
WORD_FIX = [
    # 字段名（只收极特异、零误伤的错形；“3的/色孙/称：”这类低置信碎错不强改）
    ("名冰", "名称"), ("名林", "名称"), ("各称", "名称"),
    ("車量", "重量"), ("重昂", "重量"), ("更量", "重量"),
    ("编积", "编码"), ("網的", "编码"), ("骗的", "编码"), ("你价", "售价"),
    # 哥伦比亚祖母绿（高顿货盘高频，OCR 错形很多；组合错形在前）
    ("哥伦比业亚", "哥伦比亚"), ("肯伦比业", "哥伦比亚"),
    ("哥伦比业", "哥伦比亚"), ("岢伦比业", "哥伦比亚"), ("岢伦比", "哥伦比亚"),
    ("尋伦比亚", "哥伦比亚"), ("哥伦比", "哥伦比亚"),
    ("哥伦比亚亚", "哥伦比亚"),  # 替换后兜底归一
    ("祖母经", "祖母绿"), ("祖母终", "祖母绿"), ("祖母参", "祖母绿"),
    ("徂母经", "祖母绿"), ("徂母", "祖母"),
    # 证书
    ("GULDD", "GUILD"),
    # 宝石/切工形近
    ("黄遊宝", "黄蓝宝"), ("椭园", "椭圆"),
]

# 数字后被切碎的重量单位 ct（货盘行内）。整体消费 g/gt/gt，后方须不是其他字母，避免误伤英文单词。
_RE_CT_G = re.compile(r"(\d(?:\.\d+)?)[gG][tT]?(?=无|有|蓝|皇|矢|红|绿|宝|钻|翠|$|[^a-zA-Z])")
_RE_CT_CI = re.compile(r"(\d(?:\.\d+)?)ci(?![a-zA-Z])")
_RE_CT_C = re.compile(r"(\d(?:\.\d+)?)c(?=[^a-zA-Z]|$)")
# 小数点误作逗号：1,34ct / 1,235（后接货盘词或单位）
_RE_DOT = re.compile(r"(\d),(\d{2,3})(?=ct|克拉|无|有|蓝|皇|矢|红|绿|宝|钻)")


def correct_line(line: str):
    n = 0
    for wrong, right in WORD_FIX:
        if wrong in line:
            n += line.count(wrong)
            line = line.replace(wrong, right)
    def _g(m):  # G/Gt → ct
        return m.group(1) + "ct"
    line, k = _RE_CT_G.subn(_g, line); n += k
    line, k = _RE_CT_CI.subn(_g, line); n += k
    line, k = _RE_CT_C.subn(_g, line); n += k
    line, k = _RE_DOT.subn(lambda m: m.group(1) + "." + m.group(2), line); n += k
    return line, n


def correct_text(text: str):
    out, total = [], 0
    for ln in (text or "").splitlines():
        fixed, k = correct_line(ln)
        out.append(fixed)
        total += k
    return "\n".join(out), total


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    p = Path(arg)
    if p.exists() and p.is_dir():
        import json
        for meta_p in sorted(p.rglob("meta.json")):
            fixes = 0
            for txt in sorted((meta_p.parent / "ocr").glob("*.txt")):
                _, k = correct_text(txt.read_text(encoding="utf-8"))
                fixes += k
            print(f"{meta_p.parent.name}: 纠错 {fixes} 处")
    else:
        out, n = correct_text(arg)
        print(f"（纠错 {n} 处）\n{out}")
