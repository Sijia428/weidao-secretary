# 作业3 · 方向B：用财报训练一个「董秘」

MF70050.01《人工智能与数据分析》第三次作业。
选 **微导纳米（科创板 688147）**，用 2022 年报 ~ 2026 半年报共 **7 份、1329 页**财报，
做 LoRA 微调（Qwen2.5-1.5B-Instruct + unsloth，Colab 免费 T4）。

## 流水线

```
抓取(巨潮) → 抽页(1329页) → 切块(1499块) → 生成问答(210条)
   → 质检(留200条) → 切训练/评测(104/144) → Colab 微调 → 四格对照
scripts/fetch_all_reports.py  extract_pages.py  chunk.py  gen_qa.py
        qc.py  build_dataset.py  build_eval.py  make_notebook.py  selftest.py
```

## 结果（真实数字）

| 方案 | 样本 | 答对率 | 引用页码正确 | 有引文率 |
| --- | --- | --- | --- | --- |
| 微调后 · 训练事实 · 原问法 | 104 | **16.3%** | 0.0% | 83.7% |
| 微调后 · 训练事实 · 换问法 | 104 | 10.6% | 0.0% | 81.7% |
| 微调后 · 未见事实 · 原问法 | 40 | 32.5% | 0.0% | 72.5% |
| 微调后 · 未见事实 · 换问法 | 40 | 20.0% | 0.0% | 72.5% |
| A 基线：BM25 检索 + 同一基座（不训练） | 40 | **50.0%** | 0.0% | 7.5% |

**结论：口径可以微调进去，事实调不进去。** 详见 `一页结论.pdf`。

## 复现

1. `python scripts/fetch_all_reports.py` —— 从巨潮资讯下载财报（PDF 不进仓库）
2. `python scripts/extract_pages.py` → `chunk.py` → `gen_qa.py` → `qc.py`
   → `build_dataset.py` → `build_eval.py`（需要 `.env` 里的 `DEEPSEEK_API_KEY`）
3. `python scripts/selftest.py` —— 交付前自检（语法/参照系/防泄漏/判分双向/汇总导出）
4. 把 `colab_upload/` 里的 `train.jsonl`、`eval.jsonl`、`kb.jsonl` 传上 Colab，
   跑 `train_lora.ipynb`（运行时选 T4 GPU）

## 目录

```
scripts/        全部脚本（可复跑）
build/          qa_qc.csv 抽检记录、train/eval、对照表、每次作答明细
colab_upload/   传 Colab 的 3 个 jsonl + notebook
一页结论.pdf/.md/.docx
操作手册.md   提交清单.md
.gitignore    .env.example
```
