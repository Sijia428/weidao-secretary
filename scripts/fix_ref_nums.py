# -*- coding: utf-8 -*-
"""
清洗 eval.jsonl 里的 ref_nums：
  · 去掉千分位逗号（"13,839.54" → "13839.54"，避免被切成 "13"）
  · 去掉看起来像年份的 4 位数（2000~2035）
  · 去掉恰好等于该题页码的数字
不调用 API，原地重算。
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")
EVAL = os.path.join(BUILD, "eval.jsonl")


def numbers_in(text, page=None):
    t = (text or "").replace(",", "").replace("，", "")
    out = []
    for m in re.findall(r"\d+(?:\.\d+)?%?", t):
        v = m.rstrip("%")
        try:
            f = float(v)
        except ValueError:
            continue
        if "." not in v and 2000 <= f <= 2035:      # 年份
            continue
        if page and v == str(page):                 # 页码本身
            continue
        if ("." in v or len(v) >= 2) and v not in out:
            out.append(v)
    return out[:10]


rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
for r in rows:
    r["ref_nums"] = numbers_in(r["ref_a"], r.get("page"))
with open(EVAL, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"已清洗 {len(rows)} 条")
print("样例：")
for r in rows[:3]:
    print(f"  [{r['split']}] 页码 {r['page']}  ref_nums={r['ref_nums']}")
    print(f"     参考: {r['ref_a'][:90]}")
empty = [r for r in rows if not r["ref_nums"]]
print(f"\n没有可比数字的题：{len(empty)} 条（这些题只看引用页码）")
