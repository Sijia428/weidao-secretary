# -*- coding: utf-8 -*-
"""
第 4 步 · 组数据集：把质检通过的问答切成「训练 / 四格评测」三份文件。

划分思路（对应课件的 T1 / T2）：
  · 训练块：每块 3 条问答 → 前 2 条进训练集，第 3 条留作 T1 评测（同块、原问法）
  · 未见块：整块不进训练，它的问答题全部作为 T2 评测（未见片段）
  · 每道评测题再生成一个「换问法」（调 API 改写，问的是同一件事）

输出：
  build/train.jsonl  SFT 训练数据（chat 格式）
  build/eval.jsonl   评测集（split=train/unseen × q/换问法）
  build/kb.jsonl     知识库全部块（给 A 基线做 BM25 检索）

用法：
    python build_dataset.py              # 含生成换问法（需要 .env 里的 key）
    python build_dataset.py --no-para    # 跳过换问法，先把训练集切出来
"""
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
KEPT = os.path.join(BUILD, "qa_kept.jsonl")
CHUNKS = os.path.join(BUILD, "chunks.jsonl")
TRAIN = os.path.join(BUILD, "train.jsonl")
EVAL = os.path.join(BUILD, "eval.jsonl")
KB = os.path.join(BUILD, "kb.jsonl")

SYSTEM = ("你是江苏微导纳米科技股份有限公司（科创板 688147）的董事会秘书办公室助理。"
          "只依据财报回答投资者提问：先给结论，再用「」原样引用原文，最后一行写 依据：[报告 第X页]；"
          "材料里没有的一律写“报告未披露”，绝不编造数字。")

random.seed(20261016)


def numbers_in(text):
    out = []
    for m in re.findall(r"\d+(?:\.\d+)?%?", text or ""):
        v = m.rstrip("%")
        if ("." in v or len(v) >= 2) and v not in out:
            out.append(v)
    return out[:12]


def para_prompt(q):
    return (f"把下面这个问题换一种问法，意思必须完全一样，长度相近，"
            f"不要照抄原句，只输出改写后的问题本身：\n{q}")


def main():
    no_para = "--no-para" in sys.argv
    kept = [json.loads(l) for l in open(KEPT, encoding="utf-8")]
    chunks = {c["id"]: c for c in (json.loads(l) for l in open(CHUNKS, encoding="utf-8"))}

    by_chunk = {}
    for r in kept:
        by_chunk.setdefault(r["chunk_id"], []).append(r)

    # 每份报告内部：按 (页, 块序号) 排序，后 20% 作未见块
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

    print(f"有问答的块：{len(by_chunk)}　训练块 {len(train_ids)}　未见块 {len(unseen_ids)}")

    train_rows, eval_rows = [], []
    for cid in train_ids:
        items = by_chunk[cid]
        ch = chunks[cid]
        for it in items[:-1]:                      # 前几条进训练
            train_rows.append({"messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"投资者提问：{it['q']}"},
                {"role": "assistant", "content": it["a"]}]})
        hold = items[-1]                            # 最后一条留作 T1 评测
        eval_rows.append({"chunk_id": cid, "split": "train", "doc": ch["doc"],
                          "page": ch["page"], "q": hold["q"], "ref_a": hold["a"],
                          "ref_nums": numbers_in(hold["a"])})

    for cid in unseen_ids:
        ch = chunks[cid]
        for it in by_chunk[cid]:
            eval_rows.append({"chunk_id": cid, "split": "unseen", "doc": ch["doc"],
                              "page": ch["page"], "q": it["q"], "ref_a": it["a"],
                              "ref_nums": numbers_in(it["a"])})

    # 换问法
    if no_para:
        for r in eval_rows:
            r["q_alt"] = r["q"]
    else:
        from llm import LLM
        llm = LLM()
        for i, r in enumerate(eval_rows, 1):
            try:
                alt = llm.chat([{"role": "user", "content": para_prompt(r["q"])}],
                               temperature=0.7, max_tokens=200, json_mode=False).strip()
                alt = alt.strip('"').strip()
                r["q_alt"] = alt if 5 < len(alt) < 120 else r["q"]
            except Exception as e:
                print(f"  换问法失败({i})：{type(e).__name__}，沿用原问法")
                r["q_alt"] = r["q"]
            time.sleep(0.2)
        print("  " + llm.stats())

    with open(TRAIN, "w", encoding="utf-8") as f:
        for r in train_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(EVAL, "w", encoding="utf-8") as f:
        for r in eval_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 知识库（全部块，供 A 基线检索；PDF 不必进仓库，这里只放文本）
    n_kb = 0
    with open(KB, "w", encoding="utf-8") as f:
        for c in (json.loads(l) for l in open(CHUNKS, encoding="utf-8")):
            f.write(json.dumps({"id": c["id"], "doc": c["doc"], "page": c["page"],
                                "text": c["text"]}, ensure_ascii=False) + "\n")
            n_kb += 1

    print(f"\n训练集 {len(train_rows)} 条 -> {TRAIN}")
    print(f"评测集 {len(eval_rows)} 条（train {sum(1 for r in eval_rows if r['split']=='train')} / "
          f"unseen {sum(1 for r in eval_rows if r['split']=='unseen')}）-> {EVAL}")
    print(f"知识库 {n_kb} 块 -> {KB}")
    print("\n评测样例：")
    for r in eval_rows[:2]:
        print(f"  [{r['split']}] 原问法: {r['q']}")
        print(f"            换问法: {r['q_alt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
