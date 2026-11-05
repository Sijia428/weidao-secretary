# -*- coding: utf-8 -*-
"""
把 raw/ 下的财报 PDF 逐页抽成文本，输出 pages.jsonl（每行一页）和 docs.json（文档清单）。
页号从 1 开始，对应 PDF 的物理页码 —— 后面所有问答的"出自第几页"都用这个页码。
"""
import json
import os
import sys

sys.path.insert(0, r"C:\Users\14370\Documents\deepseek-harness\default-workspace\.pylibs")
from pypdf import PdfReader                              # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 作业3-董秘
RAW = os.path.join(BASE, "raw")
OUT_DIR = os.path.join(BASE, "build")
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = os.path.join(OUT_DIR, "pages.jsonl")
DOCS = os.path.join(OUT_DIR, "docs.json")


def doc_info(fn):
    """从文件名解析：日期、类型、报告期"""
    parts = fn.split("_")
    date = parts[0]
    kind = parts[1] if len(parts) > 1 else ""
    return {"file": fn, "date": date, "kind": kind}


def main():
    files = sorted(f for f in os.listdir(RAW) if f.lower().endswith(".pdf"))
    if not files:
        print("raw/ 里没有 PDF")
        return 1

    docs = []
    total_pages = 0
    with open(PAGES, "w", encoding="utf-8") as out:
        for fn in files:
            path = os.path.join(RAW, fn)
            info = doc_info(fn)
            print(f"  处理 {fn} ...", end="", flush=True)
            try:
                reader = PdfReader(path)
            except Exception as e:
                print(" 打开失败:", e)
                continue
            n = len(reader.pages)
            empty = 0
            for i, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                text = text.replace("\u3000", " ").strip()
                if len(text) < 30:
                    empty += 1
                out.write(json.dumps({"doc": fn, "page": i, "text": text},
                                     ensure_ascii=False) + "\n")
            docs.append({**info, "pages": n, "empty_pages": empty})
            total_pages += n
            print(f" {n} 页（其中 {empty} 页几乎无文字）")

    with open(DOCS, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=1)

    print(f"\n共 {len(docs)} 份文档、{total_pages} 页")
    print("输出:", PAGES)
    print("清单:", DOCS)

    # 抽一页看看质量
    print("\n===== 质量抽检：2025 年报第 20 页前 400 字 =====")
    with open(PAGES, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "2025年年度报告" in r["doc"] and r["page"] == 20:
                print(r["text"][:400])
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
