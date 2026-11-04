[README.md](https://github.com/user-attachments/files/34349991/README.md)
# 作业3 · 方向B：用财报训练一个「董秘」

MF70050.01《人工智能与数据分析》第三次作业。
选 **微导纳米（科创板 688147）**，用 2022 年报 ~ 2026 半年报共 **7 份、1329 页**财报，
做 LoRA 微调（Qwen2.5-1.5B-Instruct + unsloth，Colab 免费 T4）。

---

## 📁 证据索引（按批改意见补齐，点开即可核对）

| 批改要求 | 对应文件 | 内容 |
| --- | --- | --- |
| **实际生成回答** | `复核材料/证据_实际生成回答_288条.csv` | 288 条 SFT 回答，每条含 **块ID / 出处页码 / 问题 / 参考答案 / 模型实际回答 / 判定** |
| 同上（对照组） | `复核材料/证据_RAG回答_40条.csv` | 同一基座 + BM25 检索的回答 40 条，含召回块 ID |
| **带出处的问答样本** | `复核材料/证据_训练数据样例.md` | 10 条训练问答，注明「哪份报告·第几页」，附原文片段与机器质检分 |
| **人工抽检** | `复核材料/证据_抽检记录.md` | 20 条抽检（低/中/高三档），210 条中有据分≤1 的 3 条已剔除 |
| **四格各一组对照** | `复核材料/证据_四格样例.md` | 每格 2 条：问题 / 参考答案 / SFT 回答 / 同一基座 RAG 回答 / 判定 |
| 运行痕迹与核对方法 | `复核材料/证据_运行痕迹说明.md` | 训练配置、块ID 怎么回查页码、**训练日志未落盘的说明** |
| 四格汇总 | `build/对照表.csv` | 5 行百分比 |

> **关于训练日志**：本次 notebook 没有把 `trainer.state.log_history` 落盘，因此没有 loss 曲线文件；
> 说明见 `复核材料/证据_运行痕迹说明.md` 第五节。权重确实被改过的直接痕迹是：
> 288 条回答里 82.7%~89.4% 带「」引文与「依据：…第X页」，而同一基座不微调时只有 7.5% 会引原文。

---

## 结果（真实数字）

| 方案 | 样本 | 答对率 | 引用页码正确 | 有引文率 |
| --- | --- | --- | --- | --- |
| 微调后 · 训练事实 · 原问法 | 104 | **16.3%** | 0.0% | 83.7% |
| 微调后 · 训练事实 · 换问法 | 104 | 10.6% | 0.0% | 81.7% |
| 微调后 · 未见事实 · 原问法 | 40 | 32.5% | 0.0% | 72.5% |
| 微调后 · 未见事实 · 换问法 | 40 | 20.0% | 0.0% | 72.5% |
| A 基线：BM25 检索 + 同一基座（不训练） | 40 | **50.0%** | 0.0% | 7.5% |

**结论：口径可以微调进去，事实调不进去。** 详见 `一页结论.pdf`。

## 流水线

```
抓取(巨潮) → 抽页(1329页) → 切块(1499块) → 生成问答(210条)
   → 质检(留200条) → 切训练/评测(104/144) → Colab 微调 → 四格对照
scripts/fetch_all_reports.py  extract_pages.py  chunk.py  gen_qa.py
        qc.py  build_dataset.py  build_eval.py  make_notebook.py  selftest.py
```

## 复现

1. `python scripts/fetch_all_reports.py` —— 从巨潮资讯下载财报（PDF 不进仓库）
2. `python scripts/extract_pages.py` → `chunk.py` → `gen_qa.py` → `qc.py`
   → `build_dataset.py` → `build_eval.py`（需要 `.env` 里的 `DEEPSEEK_API_KEY`）
3. `python scripts/selftest.py` —— 交付前自检（语法/参照系/防泄漏/判分双向/汇总导出）
4. 把 `colab_upload/` 里的 `train.jsonl`、`eval.jsonl`、`kb.jsonl` 传上 Colab，
   跑 `train_lora.ipynb`（运行时选 T4 GPU）
5. `python scripts/make_evidence.py`、`make_evidence2.py` —— 生成复核材料

## 目录

```
scripts/        全部脚本（可复跑）
复核材料/        ★ 批改补交的证据（实际回答 / 抽检 / 四格样例 / 训练数据样例）
build/          qa_qc.csv 抽检记录、train/eval、对照表、每次作答明细
colab_upload/   传 Colab 的 3 个 jsonl + notebook
一页结论.pdf/.md/.docx
操作手册.md   提交清单.md
.gitignore    .env.example
```
