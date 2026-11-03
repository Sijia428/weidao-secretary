# -*- coding: utf-8 -*-
"""
第 4b 步 · 重建评测集（修正四格的参照系）

课件的四格（PPT 第 113 页）：
    训练事实 × 原问法  → 就是训练时那句原话（测"背没背住"）
    训练事实 × 换问法  → 同一件事换个说法
    未见事实 × 原问法  → 整块没进过训练
    未见事实 × 换问法

所以：
    T1（split=train）= 真正进了 train.jsonl 的那些问题的原句 + 换问法
    T2（split=unseen）= 未见块（每份报告后 20%，整块没进训练）的问题 + 换问法

输出 build/eval.jsonl（覆盖旧的）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
KEPT = os.path.join(BUILD, "qa_kept.jsonl")
CHUNKS = os.path.join(BUILD, "chunks.jsonl")
EVAL = os.path.join(BUILD, "eval.jsonl")


def numbers_in(text):
    import re
    out = []
    for m in re.findall(r"\d+(?:\.\d+)?%?", text or ""):
        v = m.rstrip("%")
        if ("." in v or len(v) >= 2) and v not in out:
            out.append(v)
    return out[:12]


def main():
    kept = [json.loads(l) for l in open(KEPT, encoding="utf-8")]
    chunks = {c["id"]: c for c in (json.loads(l) for l in open(CHUNKS, encoding="utf-8"))}

    by_chunk = {}
    for r in kept:
        by_chunk.setdefault(r["chunk_id"], []).append(r)

    by_doc = {}
    for cid in by_chunk:
        ch = chunks.get(cid)
        if ch:
            by_doc.setdefault(ch["doc"], []).append(cid)

    train_ids, unseen_ids = [], []
    for doc, ids in by_doc.items():
        ids.sort(key=lambda x: (chunks[x]["page"], chunks[x]["chunk_no"]))
        n_cut = max(1, int(len(ids) * 0.2))
        unseen_ids.extend(ids[-n_cut:])
        train_ids.extend(ids[:-n_cut])

    rows = []
    # T1：进训练集的那几条（与 build_dataset.py 的 items[:-1] 完全对应）
    for cid in train_ids:
        ch = chunks[cid]
        for it in by_chunk[cid][:-1]:
            rows.append({"chunk_id": cid, "split": "train", "doc": ch["doc"],
                         "page": ch["page"], "q": it["q"], "ref_a": it["a"],
                         "ref_nums": numbers_in(it["a"])})
    # T2：未见块的全部问答
    for cid in unseen_ids:
        ch = chunks[cid]
        for it in by_chunk[cid]:
            rows.append({"chunk_id": cid, "split": "unseen", "doc": ch["doc"],
                         "page": ch["page"], "q": it["q"], "ref_a": it["a"],
                         "ref_nums": numbers_in(it["a"])})

    print(f"T1（训练事实）{sum(1 for r in rows if r['split']=='train')} 条　"
          f"T2（未见事实）{sum(1 for r in rows if r['split']=='unseen')} 条")

    from llm import LLM
    llm = LLM()
    print("生成换问法……")
    for i, r in enumerate(rows, 1):
        try:
            alt = llm.chat([{"role": "user", "content":
                             f"把下面这个问题换一种问法，意思必须完全一样，长度相近，"
                             f"不要照抄原句，只输出改写后的问题本身：\n{r['q']}"}],
                           temperature=0.7, max_tokens=200, json_mode=False).strip().strip('"')
            r["q_alt"] = alt if 5 < len(alt) < 120 else r["q"]
        except Exception as e:
            print(f"  {i} 失败 {type(e).__name__}，沿用原问法")
            r["q_alt"] = r["q"]
        if i % 20 == 0:
            print(f"  {i}/{len(rows)}")
        time.sleep(0.15)
    print("  " + llm.stats())

    with open(EVAL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("已写入", EVAL)
    print("\n样例：")
    for r in rows[:2] + rows[-2:]:
        print(f"  [{r['split']}] 原问法: {r['q']}")
        print(f"            换问法: {r['q_alt']}")
        print(f"            参考数字: {r['ref_nums']}　页码: {r['page']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
