# -*- coding: utf-8 -*-
"""
生成 Colab 训练笔记本 train_lora.ipynb（作业3 方向B · 微导纳米「董秘」LoRA）
v2：修正四格参照系（T1 = 训练事实的原问法）、把"答对"与"引用正确"分开统计
用法：python make_notebook.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "train_lora.ipynb")

CELLS = []


def md(text):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})


def code(text):
    CELLS.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "outputs": [], "source": text.splitlines(keepends=True)})


md("""# 作业3 · 方向B：用微导纳米的财报训练一个「董秘」

**思路**：把「投资者提问 → 董秘作答」的问答对喂给 Qwen2.5-1.5B 做 LoRA 微调（SFT），
让它学会董秘的**口径与格式**（先结论、再引原文、最后标出处），
再用四格对照量出它到底学会了什么、没学会什么。

**跑之前**：菜单 `代码执行程序/Runtime → 更改运行时类型/Change runtime type → 硬件加速器选 T4 GPU`。

**需要上传三个文件**（都在 `colab_upload/` 里）：
- `train.jsonl`：104 条训练问答（chat 格式）
- `eval.jsonl`：四格评测数据（`split`=train/unseen，`q` 原问法，`q_alt` 换问法，`ref_a` 参考答案，`ref_nums` 关键数字，`page`）
- `kb.jsonl`：2219 块知识库（给 A 方案做 BM25 检索）
""")

code("""# 0. 确认 GPU
!nvidia-smi
import torch
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "没有 GPU，请先改运行时类型")
""")

code("""# 1. 装 unsloth（2~4 分钟，转圈正常）
%%capture
!pip install unsloth
print("安装完成")
""")

code("""# 2. 上传三个文件：train.jsonl / eval.jsonl / kb.jsonl（一起选）
from google.colab import files
uploaded = files.upload()
print("已上传:", list(uploaded.keys()))
""")

code("""# 3. 加载小模型（纯文本 Qwen2.5-1.5B-Instruct，4bit 量化）
from unsloth import FastLanguageModel
import torch, gc

try:
    del model
except Exception:
    pass
gc.collect(); torch.cuda.empty_cache()

max_seq_length = 2048
CANDIDATES = ["unsloth/Qwen2.5-1.5B-Instruct", "unsloth/Qwen2.5-3B-Instruct"]
model = tokenizer = MODEL = None
for name in CANDIDATES:
    try:
        print("尝试加载", name)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=name, max_seq_length=max_seq_length, load_in_4bit=True, dtype=None)
        MODEL = name
        break
    except Exception as e:
        print("  失败:", type(e).__name__, str(e)[:200])
if model is None:
    raise SystemExit("模型没加载成功，请把报错发给助教")
print("已加载:", MODEL)
""")

code("""# 4. 装 LoRA
model = FastLanguageModel.get_peft_model(
    model, r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16, lora_dropout=0.0, bias="none",
    use_gradient_checkpointing="unsloth", random_state=3407,
    max_seq_length=max_seq_length)
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"可训练参数 {trainable:,} / {total:,} = {trainable/total*100:.2f}%")
""")

code("""# 5. 准备训练数据
import json
from datasets import Dataset

rows = [json.loads(l) for l in open("train.jsonl", encoding="utf-8")]
def to_text(ex):
    return {"text": tokenizer.apply_chat_template(
        ex["messages"], tokenize=False, add_generation_prompt=False)}
ds = Dataset.from_list(rows).map(to_text, remove_columns=["messages"])
print(f"训练样本 {len(ds)} 条")
print(ds[0]["text"][:500])
""")

code("""# 6. 训练（3 轮，3~6 分钟）
from trl import SFTTrainer
try:
    from trl import SFTConfig
    args = SFTConfig(
        dataset_text_field="text", max_seq_length=max_seq_length,
        per_device_train_batch_size=2, gradient_accumulation_steps=4,
        warmup_steps=5, num_train_epochs=3, learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(), bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1, optim="adamw_8bit", weight_decay=0.01,
        lr_scheduler_type="linear", seed=3407, output_dir="outputs", report_to="none")
    trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=ds, args=args)
except Exception as e:
    print("退回 TrainingArguments：", type(e).__name__)
    from transformers import TrainingArguments
    args = TrainingArguments(
        per_device_train_batch_size=2, gradient_accumulation_steps=4,
        warmup_steps=5, num_train_epochs=3, learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(), bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1, optim="adamw_8bit", weight_decay=0.01,
        lr_scheduler_type="linear", seed=3407, output_dir="outputs", report_to="none")
    trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=ds,
                         args=args, dataset_text_field="text", max_seq_length=max_seq_length)
print(trainer.train())
""")

code("""# 7. 生成 + 判分工具
# 判分口径：
#   数字命中率 = 参考答案里的关键数字，预测里出现了多少
#   答对       = 数字命中率 >= 0.6
#   引用正确   = 预测里写对了"第 X 页"（格式学没学会）
FastLanguageModel.for_inference(model)

SYSTEM = ("你是江苏微导纳米科技股份有限公司（科创板 688147）的董事会秘书办公室助理。"
          "只依据财报回答投资者提问：先给结论，再用「」原样引用原文，最后一行写 依据：[报告 第X页]；"
          "材料里没有的一律写“报告未披露”，绝不编造数字。")

def gen(question, context=None, max_new_tokens=360):
    user = question if not context else f"【财报原文片段】\\n{context}\\n\\n投资者提问：{question}"
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                         pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

def norm(s):
    return s.replace(" ", "").replace("\\u3000", "")

def score(pred, item):
    np_ = norm(pred).replace(",", "")
    ref_body = norm(item.get("ref_a", "")).split("依据：")[0]
    grams = [ref_body[i:i + 8] for i in range(0, max(len(ref_body) - 8, 1), 4)]
    frag = 1 if any(g and g in np_ for g in grams) else 0
    nums = item.get("ref_nums") or []
    if nums:
        hit = sum(1 for n in nums if n in np_) / len(nums)
        ok = 1 if hit >= 0.6 else 0
    else:
        hit = float("nan")
        ok = frag
    page = str(item.get("page", ""))
    cite = 1 if f"第{page}页" in np_ else 0
    quote = 1 if ("「" in pred) or ("“" in pred) else 0
    return {"数字命中率": hit, "片段重合": frag, "答对": ok, "引用正确": cite, "带引文": quote}

print(gen("公司报告期内研发人员数量占员工总数的比例是多少？"))
""")

code("""# 8. 四格评测：训练事实 / 未见事实 × 原问法 / 换问法
import pandas as pd

items = [json.loads(l) for l in open("eval.jsonl", encoding="utf-8")]
print("评测集：", len(items), "条（train", sum(1 for x in items if x["split"]=="train"),
      "/ unseen", sum(1 for x in items if x["split"]=="unseen"), "）")

results = []
for it in items:
    for mode, q in (("原问法", it["q"]), ("换问法", it["q_alt"])):
        pred = gen(q)
        results.append({"split": it["split"], "mode": mode, "chunk_id": it["chunk_id"],
                        "page": it["page"], "q": q, "pred": pred, "ref": it["ref_a"],
                        **score(pred, it)})
        print(".", end="", flush=True)
df = pd.DataFrame(results)
df.to_csv("sft_results.csv", index=False, encoding="utf-8-sig")
print("\\n已保存 sft_results.csv")

grid = (df.groupby(["split", "mode"])
          .agg(样本数=("答对", "size"), 答对率=("答对", "mean"),
               引用正确率=("引用正确", "mean"), 数字命中率=("数字命中率", "mean"))
          .round(3))
print("\\n===== LoRA 微调后 · 四格对照 =====")
print(grid)
df.to_pickle("sft_df.pkl")
""")

code("""# 9. A 方案对照：BM25 检索 + 同一个基座模型（不微调）
!pip install -q jieba rank_bm25
import json, jieba
from rank_bm25 import BM25Okapi
from unsloth import FastLanguageModel as FLM

kb = [json.loads(l) for l in open("kb.jsonl", encoding="utf-8")]
corpus = [list(jieba.cut(c["text"])) for c in kb]
bm25 = BM25Okapi(corpus)
print("知识库块数:", len(kb))

base, base_tok = FLM.from_pretrained(model_name=MODEL, max_seq_length=max_seq_length,
                                     load_in_4bit=True, dtype=None)
FLM.for_inference(base)

def gen_base(question, context, max_new_tokens=400):
    user = (f"【财报原文片段】\\n{context}\\n\\n"
            f"请只依据上面的原文回答投资者提问：{question}\\n"
            "要求：第一句给结论（带关键数字），第二句用「」引用原文，最后一行写 依据：[报告 第X页]；"
            "原文里没有答案就写：报告未披露。")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    prompt = base_tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inp = base_tok(prompt, return_tensors="pt").to("cuda")
    out = base.generate(**inp, max_new_tokens=max_new_tokens, do_sample=False,
                        pad_token_id=base_tok.eos_token_id)
    text = base_tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    if len(text) < 30:      # 只吐了个"依据"行 → 用更直白的问法重试一次
        msgs2 = [{"role": "user", "content":
                  f"根据下面的财报原文回答问题：{question}\\n\\n原文：\\n{context}\\n\\n请给出完整回答。"}]
        p2 = base_tok.apply_chat_template(msgs2, tokenize=False, add_generation_prompt=True)
        i2 = base_tok(p2, return_tensors="pt").to("cuda")
        o2 = base.generate(**i2, max_new_tokens=max_new_tokens, do_sample=False,
                           pad_token_id=base_tok.eos_token_id)
        text = base_tok.decode(o2[0][i2["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return text

rows_rag = []
unseen = [x for x in items if x["split"] == "unseen"]
for it in unseen:
    idx = bm25.get_top_n(list(jieba.cut(it["q"])), range(len(kb)), n=3)
    ctx = "\\n\\n".join(kb[i]["text"] for i in idx)
    pred = gen_base(it["q"], ctx)
    rows_rag.append({"chunk_id": it["chunk_id"], "page": it["page"],
                     "recalled": [kb[i]["id"] for i in idx], "pred": pred,
                     **score(pred, it)})
    print(".", end="", flush=True)
rag = pd.DataFrame(rows_rag)
rag.to_csv("rag_results.csv", index=False, encoding="utf-8-sig")
print("\\n\\n===== A 方案（BM25 + 基座，未微调）· 未见事实 =====")
print("答对率 %.1f%%　引用正确率 %.1f%%　数字命中率 %.3f" % (
    rag["答对"].mean()*100, rag["引用正确"].mean()*100, rag["数字命中率"].mean()))
""")

code("""# 10. 总表 + 下载
import pandas as pd
rows = []
for split, label in (("train", "训练事实"), ("unseen", "未见事实")):
    for mode in ("原问法", "换问法"):
        sub = df[(df["split"] == split) & (df["mode"] == mode)]
        if len(sub):
            rows.append({"方案": f"微调后 · {label} · {mode}", "样本数": len(sub),
                         "答对率": sub["答对"].mean(),
                         "引用正确率": sub["引用正确"].mean(),
                         "数字命中率": sub["数字命中率"].mean()})
rows.append({"方案": "A 基线：BM25 + 基座（未微调）· 未见事实", "样本数": len(rag),
             "答对率": rag["答对"].mean(), "引用正确率": rag["引用正确"].mean(),
             "数字命中率": rag["数字命中率"].mean()})

summary = pd.DataFrame(rows).round(3)
summary["答对率"] = (summary["答对率"] * 100).round(1).astype(str) + "%"
summary["引用正确率"] = (summary["引用正确率"] * 100).round(1).astype(str) + "%"
print(summary.to_string(index=False))
summary.to_csv("对照表.csv", index=False, encoding="utf-8-sig")

from google.colab import files as colab_files
for f in ["对照表.csv", "sft_results.csv", "rag_results.csv"]:
    try:
        colab_files.download(f)
    except Exception as e:
        print("下载", f, "失败:", e)
""")

md("""## 把结果发我

跑完会下载 `对照表.csv`。**五行数字**就是这次实验的全部结论：

| 方案 | 答对率 | 引用正确率 |
| --- | --- | --- |
| 微调后 · 训练事实 · 原问法 | ? | ? |
| 微调后 · 训练事实 · 换问法 | ? | ? |
| 微调后 · 未见事实 · 原问法 | ? | ? |
| 微调后 · 未见事实 · 换问法 | ? | ? |
| A 基线（BM25 + 基座） | ? | ? |

预期：**训练事实上明显涨、换问法还能接住一部分、未见事实仍然接近 0** —— 这就是 SFT 的能与界。
""")

nb = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4", "toc_visible": True},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("已生成:", OUT, f"{os.path.getsize(OUT)/1024:.1f} KB，{len(CELLS)} 个单元")
