#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu_doc.py — 本地图文 → 飞书 docx XML 的「v2 话题化」通用渲染层。

定位：本地 06_articles 是唯一权威源，本模块只负责把「已经组织好的结构 spec」渲染成
lark-cli docs +create/+update 可用的 XML，不负责抓取、不回写本地、不替你做话题归纳。

为什么需要 v2（对照 scripts/feishu/article_to_xml.py 的 v1 平铺）：
  v1 按图逐张堆 OCR 散行，读起来是噪声；v2 要求先由人/AI 多模态读图，把随机话题
  组织成固定 5 块：①话题概述 ②原图（全部保留）③结构化主体（货盘→清单表 /
  款式→分组表 / 设计稿→设计元素表 / 直播→信息表 / 知识→要点）④有价值评论（可无）
  ⑤选品/做号观察。

全量单篇流程：
  1. 多模态逐张读 images/（超长图先用 PIL 切片再读），核对 ocr/*.txt 但以读图为准；
  2. 写一个 spec（dict / JSON，结构见 build_spec 示例与 README）；
  3. python3 scripts/feishu/feishu_doc.py spec.json -o out.xml
  4. lark-cli docs +update --as user --doc <obj_token> --command overwrite \
         --doc-format xml --content @out.xml   # 新建用 docs +create --parent-token <wiki节点>
  5. docs +fetch 回读，核对 h2/表格行数/图片数。

内容安全：p/li/callout/单元格为「受控富文本」，允许 <b>/<span>/<a> 等内联标签，
默认不转义（由组织方保证无裸 < >）；确有不可信文本时用本模块 esc() 先转义。
"""
import argparse
import json
from pathlib import Path


def esc(s: str) -> str:
    """转义不可信文本里的 XML 特殊字符。"""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def title(t: str) -> str:
    return f"<title>{t}</title>"


def callout(paragraphs, emoji: str = "📌", bg: str = "light-gray") -> str:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f'<callout emoji="{emoji}" background-color="{bg}">{body}</callout>'


def h2(t: str) -> str:
    return f"<h2>{t}</h2>"


def p(html: str) -> str:
    return f"<p>{html}</p>"


def ul(items) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def ol(items) -> str:
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def img(abs_path: str, width: int = 520, caption: str = "") -> str:
    cap = f' caption="{caption}"' if caption else ""
    return f'<img path="@{abs_path}"{cap} width="{width}"/>'


def table(headers, rows) -> str:
    """headers:[str]；rows:[[单元格富文本...]]，列数需与表头一致。"""
    th = "".join(f"<th><p>{h}</p></th>" for h in headers)
    body = []
    for r in rows:
        body.append("<tr>" + "".join(f"<td><p>{c}</p></td>" for c in r) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def hr_note(text: str, gray: bool = True) -> str:
    inner = f'<span text-color="gray">{text}</span>' if gray else text
    return f"<hr/><p>{inner}</p>"


# block 种类 -> 渲染。payload 见各函数入参。
def _render_block(kind, payload):
    if kind == "h2":
        return h2(payload)
    if kind == "p":
        return p(payload)
    if kind == "callout":
        return callout(payload["paragraphs"], payload.get("emoji", "📌"))
    if kind == "img":
        return img(payload["path"], payload.get("width", 520), payload.get("caption", ""))
    if kind == "table":
        return table(payload["headers"], payload["rows"])
    if kind == "ul":
        return ul(payload)
    if kind == "ol":
        return ol(payload)
    if kind == "hr_note":
        return hr_note(payload)
    raise ValueError(f"未知 block 种类: {kind}")


def render_spec(spec: dict) -> str:
    """spec = {title:str, blocks:[(kind,payload),...]}（JSON 里写成 [kind,payload] 二元组）。"""
    out = [title(spec["title"])]
    for item in spec["blocks"]:
        kind, payload = item[0], item[1]
        out.append(_render_block(kind, payload))
    return "\n".join(out) + "\n"


# 5 块结构的便捷骨架：返回带占位标题的 blocks 框架，组织方往里填 payload。
def five_block_skeleton(kind_hint: str = "货盘"):
    """生成图文 v2 五块的 block 模板（kind_hint 仅用于第三块标题措辞提示）。"""
    third = {
        "货盘": "三、裸石/货品清单",
        "款式": "三、款式分组",
        "设计稿": "三、设计清单（逐图点设计元素）",
        "直播": "三、关键信息",
        "知识": "三、核心要点",
    }.get(kind_hint, "三、结构化主体")
    return [
        ["callout", {"paragraphs": ["作者/发布/类型/图片数", "原页链接 + 重组稿声明"]}],
        ["h2", "一、话题概述"],
        ["p", "一句话讲清这是什么、多少件/款、按什么组织。"],
        ["h2", "二、原图"],
        ["p", "（在此放若干 img block，原图全部保留）"],
        ["h2", third],
        ["p", "（表格或要点，按内容类型选）"],
        ["h2", "四、有价值评论"],
        ["p", "（默认不采集；仅爆款且有信息量时保留，否则整块可删）"],
        ["h2", "五、选品 / 做号观察"],
        ["ul", ["观察点1", "观察点2"]],
    ]


def main():
    ap = argparse.ArgumentParser(description="把 v2 话题化 spec(JSON) 渲染成飞书 XML")
    ap.add_argument("spec_json", nargs="?", help="v2 spec 的 JSON 文件；用 --skeleton 时可不传")
    ap.add_argument("-o", "--out")
    ap.add_argument("--skeleton", action="store_true", help="只打印五块结构 spec 骨架模板")
    a = ap.parse_args()
    if a.skeleton:
        print(json.dumps({"title": "标题", "blocks": five_block_skeleton()},
                         ensure_ascii=False, indent=2))
        return
    if not a.spec_json:
        ap.error("需要传入 spec_json 文件路径，或使用 --skeleton 查看模板")
    spec = json.loads(Path(a.spec_json).read_text(encoding="utf-8"))
    xml = render_spec(spec)
    if a.out:
        Path(a.out).write_text(xml, encoding="utf-8")
        print(f"写出 {a.out}（{len(xml)} 字符，{len(spec['blocks'])} 个 block）")
    else:
        print(xml)


if __name__ == "__main__":
    main()
