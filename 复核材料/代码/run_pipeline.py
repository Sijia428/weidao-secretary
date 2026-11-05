# -*- coding: utf-8 -*-
"""
一键复现整条数据生成：财报 PDF → 逐页文字 → 切块 → 带出处的问答 → 质检 → 训练/评测集。

用法：
    python run_pipeline.py           # 从第 1 步跑到最后
    python run_pipeline.py --from 3  # 从第 3 步开始（前面结果已存在）

前提：raw/ 下有财报 PDF（由第 1 步下载）；.env 里有 DEEPSEEK_API_KEY（第 4 步用）。
每一步的产物都会打印出来，字段对应关系见 证据_数据生成流水线.md。
"""
import os
import subprocess
import sys

STEPS = [
    ("fetch_all_reports.py", "从巨潮资讯下载年报/半年报 PDF → raw/"),
    ("extract_pages.py", "逐页抽文字，保留物理页码 → build/pages.jsonl (doc/page/text)"),
    ("chunk.py", "切块 800 字/重合 100，带 报告/页码/章节 → build/chunks.jsonl"),
    ("gen_qa.py", "每块 3 问：投资者问→董秘答，必须「」引原文+标出处 → build/qa_raw.jsonl"),
    ("qc.py", "三道回查：引文/数字/页码 → build/qa_qc.csv + qa_kept.jsonl"),
    ("build_dataset.py", "切训练/评测/知识库 → train.jsonl / eval.jsonl / kb.jsonl"),
    ("build_eval.py", "四格评测集（T1=训练事实原问法）→ 覆盖 eval.jsonl"),
]

HERE = os.path.dirname(os.path.abspath(__file__))
start = 1
if "--from" in sys.argv:
    start = int(sys.argv[sys.argv.index("--from") + 1])

for i, (script, desc) in enumerate(STEPS, 1):
    if i < start:
        continue
    print(f"\n{'='*60}\n[{i}/{len(STEPS)}] {script}\n        {desc}\n{'='*60}")
    r = subprocess.run([sys.executable, os.path.join(HERE, script)])
    if r.returncode != 0:
        print(f"\n!! {script} 失败，流水线中止")
        sys.exit(r.returncode)

print("\n全部完成。产物：")
for f in ("pages.jsonl", "chunks.jsonl", "qa_raw.jsonl", "qa_kept.jsonl",
          "qa_qc.csv", "train.jsonl", "eval.jsonl", "kb.jsonl"):
    p = os.path.join(os.path.dirname(HERE), "build", f)
    if os.path.exists(p):
        print(f"  build/{f:16} {os.path.getsize(p)/1024:>8.0f} KB")
