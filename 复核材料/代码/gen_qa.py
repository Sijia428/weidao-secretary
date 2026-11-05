# -*- coding: utf-8 -*-
"""
第 2 步 · 造数据：让大模型从财报原文片段生成「投资者提问 → 董秘作答」的问答对。

- 每份报告抽 10 块（6 块按"人才—技术—产业"相关度最高的 + 4 块随机），保证既有重点又有广度
- 答案硬性要求：先结论、再「」引原文、末尾注 [报告 第X页]；片段里没有的一律写"报告未披露"
- 断点续跑：已经生成的块会跳过
- 输出 build/qa_raw.jsonl

用法：
    python gen_qa.py --limit 3        # 先跑 3 块试味道
    python gen_qa.py                  # 跑全部抽样块
"""
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from llm import LLM                                    # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
CHUNKS = os.path.join(BUILD, "chunks.jsonl")
OUT = os.path.join(BUILD, "qa_raw.jsonl")

COMPANY = "江苏微导纳米科技股份有限公司（科创板 688147，简称微导纳米）"
PER_DOC = 10
PER_DOC_TOP = 6
random.seed(20261015)

SYSTEM = (
    f"你是{COMPANY}董事会秘书办公室的助理，只依据我给你的财报原文片段回答投资者提问。"
    "回答要像业绩说明会上的董秘：先给结论，再引出原文，最后写清依据；"
    "片段里没有的信息必须写“报告未披露”，绝不编造数字。"
)

USER_TMPL = """【报告】{doc}（披露日 {date}）
【页码】第 {page} 页　【章节】{section}
【原文片段】
{text}

请完成两件事：

1. 以投资者口吻提出 {nq} 个「这段原文能回答」的问题。问题要具体，像路演或业绩说明会上真会问的；
   优先围绕：人才引进与培养、研发投入与技术创新、股权激励等激励约束机制、产业化与竞争格局。

2. 每个问题给出董秘口径的回答，硬性要求：
   - 第一句先给结论（一句话，尽量带关键数字）；
   - 紧接着用「」原样引用片段中支撑这个结论的原文（连续不超过 60 字，不得改写）；
   - 最后一行写：依据：[{doc} 第 {page} 页]
   - 片段里没有的信息，一律写“报告未披露”，绝不编造数字或年份。

只输出 JSON，格式：
{{"items": [{{"q": "问题", "a": "回答"}}]}}
"""


def sample_blocks(per_doc=PER_DOC, top=PER_DOC_TOP):
    chunks = [json.loads(l) for l in open(CHUNKS, encoding="utf-8")]
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c["doc"], []).append(c)
    picked = []
    for doc, items in by_doc.items():
        items_sorted = sorted(items, key=lambda x: -x["weight"])
        top_items = [c for c in items_sorted if c["chars"] >= 300][:top]
        used = {c["id"] for c in top_items}
        rest = [c for c in items if c["id"] not in used and c["chars"] >= 300]
        random.shuffle(rest)
        picked.extend(top_items)
        picked.extend(rest[:max(per_doc - len(top_items), 0)])
    return picked


def parse_items(text):
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    data = json.loads(text)
    items = data.get("items") or data.get("data") or []
    out = []
    for it in items:
        q = (it.get("q") or "").strip()
        a = (it.get("a") or "").strip()
        if q and a and len(a) > 20:
            out.append({"q": q, "a": a})
    return out


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    nq = 3
    if "--nq" in sys.argv:
        nq = int(sys.argv[sys.argv.index("--nq") + 1])

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["chunk_id"])
            except Exception:
                pass

    blocks = sample_blocks()
    todo = [b for b in blocks if b["id"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"抽样 {len(blocks)} 块；已完成 {len(done)} 块；本次处理 {len(todo)} 块；每块 {nq} 问")

    llm = LLM()
    print("模型:", llm.model, "@", llm.base)

    ok = fail = 0
    with open(OUT, "a", encoding="utf-8") as out:
        for i, b in enumerate(todo, 1):
            prompt = USER_TMPL.format(doc=b["doc"], date=b["doc_date"], page=b["page"],
                                      section=b["section"] or "（未标注）", text=b["text"], nq=nq)
            t0 = time.time()
            try:
                raw = llm.chat([{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": prompt}])
                items = parse_items(raw)
                if not items:
                    raise ValueError("没解析出问答")
                for it in items:
                    out.write(json.dumps({
                        "chunk_id": b["id"], "doc": b["doc"], "doc_date": b["doc_date"],
                        "page": b["page"], "section": b["section"],
                        "weight": b["weight"], "q": it["q"], "a": it["a"],
                        "model": llm.model,
                    }, ensure_ascii=False) + "\n")
                out.flush()
                ok += 1
                print(f"  [{i}/{len(todo)}] {b['id']} -> {len(items)} 条  {time.time()-t0:.1f}s")
            except Exception as e:
                fail += 1
                print(f"  [{i}/{len(todo)}] {b['id']} 失败: {type(e).__name__}: {e}")
            time.sleep(0.4)

    print(f"\n完成：成功 {ok} 块，失败 {fail} 块")
    print(llm.stats())
    total = sum(1 for _ in open(OUT, encoding="utf-8")) if os.path.exists(OUT) else 0
    print(f"qa_raw.jsonl 现有 {total} 条问答")
    return 0


if __name__ == "__main__":
    sys.exit(main())
