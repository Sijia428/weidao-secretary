# -*- coding: utf-8 -*-
"""
切块：把逐页正文切成 800 字左右的块（重合 100 字，尽量在句末断开），
每块带上【公司 / 报告 / 页码 / 章节】四个标签，并按"人才—技术—产业"关注点打一个权重。

输出 build/chunks.jsonl
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
PAGES = os.path.join(BUILD, "pages.jsonl")
DOCS = os.path.join(BUILD, "docs.json")
OUT = os.path.join(BUILD, "chunks.jsonl")

COMPANY = "微导纳米"
CHUNK_SIZE = 800
OVERLAP = 100

# 你的关注点：人才引进 → 技术进步与创新成果的机制、激励方式、产业
FOCUS_WORDS = {
    "人才": 3, "员工": 2, "人员": 2, "研发人员": 4, "博士": 3, "硕士": 2, "招聘": 2,
    "引进": 3, "博士后": 4, "产学研": 4, "高校": 3, "科研院所": 3, "核心技术人员": 4,
    "激励": 3, "股权激励": 5, "限制性股票": 5, "考核": 2, "归属": 2, "授予": 2,
    "研发投入": 4, "研发费用": 3, "专利": 3, "发明": 2, "技术创新": 4, "核心技术": 3,
    "产业化": 2, "行业": 2, "光伏": 2, "半导体": 2, "国产替代": 4, "竞争": 2,
    "境外": 2, "海外": 2, "海外收入": 3, "客户": 2, "产能": 2,
}

SECTION_RE = re.compile(r"第[一二三四五六七八九十]+节[^\n，。]{0,24}")


def short_doc(fn):
    m = re.search(r"(\d{4})年(年度|半年度)报告", fn)
    return f"{m.group(1)}年{'年报' if m.group(2) == '年度' else '半年报'}" if m else fn


def section_of(text):
    hits = SECTION_RE.findall(text)
    return hits[0].strip() if hits else ""


def split_text(text, size=CHUNK_SIZE, overlap=OVERLAP):
    """按句末优先切块"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    if len(text) <= size:
        return [text] if len(text) >= 120 else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start + int(size * 0.6):end]
            cuts = [m.end() for m in re.finditer(r"[。！？；\n]", window)]
            if cuts:
                end = start + int(size * 0.6) + cuts[-1]
        piece = text[start:end].strip()
        if len(piece) >= 120:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def weight_of(text):
    w = sum(v for k, v in FOCUS_WORDS.items() if k in text)
    return min(w, 40)


def main():
    docs = {d["file"]: d for d in json.load(open(DOCS, encoding="utf-8"))}
    pages = [json.loads(l) for l in open(PAGES, encoding="utf-8")]
    print(f"读入 {len(pages)} 页")

    n = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for pg in pages:
            text = pg["text"]
            if len(text) < 120:
                continue
            doc_short = short_doc(pg["doc"])
            sec = section_of(text)
            for k, piece in enumerate(split_text(text), 1):
                rec = {
                    "id": f"{doc_short}-p{pg['page']}-c{k}",
                    "doc": doc_short,
                    "doc_file": pg["doc"],
                    "doc_date": docs.get(pg["doc"], {}).get("date", ""),
                    "page": pg["page"],
                    "section": sec,
                    "chunk_no": k,
                    "chars": len(piece),
                    "weight": weight_of(piece),
                    "text": piece,
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1

    print(f"切出 {n} 块 -> {OUT}")

    chunks = [json.loads(l) for l in open(OUT, encoding="utf-8")]
    from collections import Counter
    by_doc = Counter(c["doc"] for c in chunks)
    print("\n各报告块数：")
    for d, c in by_doc.items():
        print(f"   {d:10} {c:5} 块")
    hi = [c for c in chunks if c["weight"] >= 8]
    print(f"\n权重≥8（与你的关注点高度相关）的块：{len(hi)} 块")
    print("\n权重最高的 5 块示例：")
    for c in sorted(chunks, key=lambda x: -x["weight"])[:5]:
        print(f"   [{c['id']}] w={c['weight']} {c['section'][:20]} | {c['text'][:60]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
