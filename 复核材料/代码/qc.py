# -*- coding: utf-8 -*-
"""
第 3 步 · 质检（抽检记录）：对生成的每一条问答做机器可核的检查。

三道检查：
  ① 引文回查：答案里「」引号中的原文，是否真的出现在该块原文里
  ② 数字回查：答案里出现的数字，是否都能在原文里找到（找不到 = 可能是编造/背串）
  ③ 页码回查：答案末尾标注的页码是否等于该块的页码

输出：
  build/qa_qc.csv     抽检表（Excel 可直接打开，留了一列"人工抽检"给你填）
  build/qa_kept.jsonl 通过质检、可进训练集的问答
"""
import csv
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
CHUNKS = os.path.join(BUILD, "chunks.jsonl")
QA = os.path.join(BUILD, "qa_raw.jsonl")
CSV_OUT = os.path.join(BUILD, "qa_qc.csv")
KEPT = os.path.join(BUILD, "qa_kept.jsonl")

NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")
# 引文可能用「」也可能用 “”，两种都认
QUOTE_RE = re.compile(r"[「“]([^」”]{4,120})[」”]")


def norm(s):
    return re.sub(r"[\s，。、；：（）()\"'“”‘’]", "", s)


def numbers_in(text):
    """提取数字（去掉年份、页码这类噪声）"""
    out = set()
    for m in NUM_RE.findall(text):
        v = m.rstrip("%")
        if "." in v or len(v) >= 2:
            out.add(v)
    return out


def main():
    chunks = {}
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        chunks[c["id"]] = c

    rows = []
    for line in open(QA, encoding="utf-8"):
        r = json.loads(line)
        ch = chunks.get(r["chunk_id"])
        if not ch:
            continue
        src = norm(ch["text"])
        ans = r["a"]

        # ① 引文回查
        quotes = QUOTE_RE.findall(ans)
        hit = sum(1 for q in quotes if norm(q) and norm(q)[:20] in src)
        quote_ok = 1 if (quotes and hit == len(quotes)) else (0.5 if quotes and hit else 0)

        # ② 数字回查
        nums = numbers_in(ans)
        n_hit = sum(1 for n in nums if n in ch["text"])
        num_ok = 1 if (not nums or n_hit == len(nums)) else (0.5 if n_hit >= len(nums) * 0.6 else 0)

        # ③ 页码回查
        page_ok = 1 if re.search(rf"第\s*{ch['page']}\s*页", ans) else 0

        score = quote_ok + num_ok + page_ok          # 0~3
        rows.append({
            "chunk_id": r["chunk_id"], "doc": r["doc"], "page": ch["page"],
            "section": ch.get("section", ""),
            "问题": r["q"], "回答": ans,
            "引文数": len(quotes), "引文命中": hit,
            "答案数字数": len(nums), "数字命中": n_hit,
            "页码正确": page_ok,
            "有据分(0-3)": score,
            "是否保留": "是" if score >= 2 and quote_ok >= 1 else "否",
            "人工抽检": "",          # 留给你填：✓ / ✗ / 说明
            "原文片段": ch["text"][:300].replace("\n", " "),
        })

    rows.sort(key=lambda x: (-x["有据分(0-3)"], x["doc"], x["page"]))
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    kept = [r for r in rows if r["是否保留"] == "是"]
    with open(KEPT, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps({
                "chunk_id": r["chunk_id"], "doc": r["doc"], "page": r["page"],
                "section": r["section"], "q": r["问题"], "a": r["回答"],
            }, ensure_ascii=False) + "\n")

    n = len(rows)
    print(f"共 {n} 条问答")
    print(f"  有据分 3 分：{sum(1 for r in rows if r['有据分(0-3)'] == 3)} 条")
    print(f"  有据分 2 分：{sum(1 for r in rows if r['有据分(0-3)'] == 2)} 条")
    print(f"  有据分 ≤1 ：{sum(1 for r in rows if r['有据分(0-3)'] <= 1)} 条（视为编造/不合格，剔除）")
    print(f"  保留 {len(kept)} 条 -> {KEPT}")
    print(f"  抽检表 -> {CSV_OUT}（共 {len(rows)} 行，留了'人工抽检'列）")

    print("\n不合格样例（前 3 条）：")
    for r in [x for x in rows if x["是否保留"] == "否"][:3]:
        print(f"  [{r['chunk_id']}] 有据分{r['有据分(0-3)']} 引文命中{r['引文命中']}/{r['引文数']} "
              f"数字命中{r['数字命中']}/{r['答案数字数']}")
        print(f"    Q: {r['问题'][:60]}")
        print(f"    A: {r['回答'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
