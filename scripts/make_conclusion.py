# -*- coding: utf-8 -*-
"""
生成「一页结论」：一页结论.docx + 一页结论.md
数据全部来自本次真实运行（Colab T4 / Qwen2.5-1.5B-Instruct / LoRA r=16 / 3 epoch / 104 条样本）。
用法：python make_conclusion.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(BASE, "一页结论.md")
DOCX = os.path.join(BASE, "一页结论.docx")

GRID = [
    ("微调后 · 训练事实 · 原问法", "104", "16.3%", "0.0%", "83.7%"),
    ("微调后 · 训练事实 · 换问法", "104", "10.6%", "0.0%", "81.7%"),
    ("微调后 · 未见事实 · 原问法", "40", "32.5%", "0.0%", "72.5%"),
    ("微调后 · 未见事实 · 换问法", "40", "20.0%", "0.0%", "72.5%"),
    ("A 基线：BM25 检索 + 同一基座（不训练）· 未见事实", "40", "50.0%", "0.0%", "7.5%"),
]

FINDINGS = [
    ("① SFT 学会的是「口径」，不是「事实」",
     "微调后 72~92% 的回答写出了「」引文和「依据：[报告 第N页]」，而同一基座靠检索作答时只有 7.5% 会引原文。"
     "但按数字严格判，训练事实上 208 次作答里只有 1 次把关键数字说对 —— 格式和内化是两件事。"),
    ("② 连「教过的」也没背牢：188 条引错页码",
     "训练时见过的问题，模型仍把 2022 年报的问题答成「2025 年半年报 第 39 页」，把 241 名研发人员答成"
     "「2025 年 3 月 31 日 91 人」。这正是课件说的「背诵的天性」：数字型事实最容易背串。"),
    ("③ 事实类问题，检索比微调更划算",
     "同样的 1.5B 基座，给它 BM25 检索来的 3 块原文，未见事实答对率 50%；微调后只有 20~32.5%，"
     "且它引用的页码几乎都不是正确那一页。事实要被「递进窗口」，不是「写进权重」。"),
]

LIMITS = [
    "样本只有 104 条（课件那场是 421 条）、答案又是 3~5 句带引文的长文本、只训 3 轮 r=16 —— "
    "课件参数扫描显示这类配置 loss 降得快、但「未见片段」几乎不涨。",
    "判分有两套口径：数字命中（严格，要求命中 ≥60%）与 8 字片段重合（宽松）。数字题占 46%，"
    "宽松口径会把「说得像」也算对，所以两个数要一起看。",
    "提示词里写了「第X页」这种占位符，基线模型有 25% 直接照抄；新版 notebook 已改成「写真实页码」。",
]

MD_TEXT = f"""# 一页结论 · 同一批财报：什么该建库，什么该微调

**方向 B｜微导纳米（688147）· 7 份财报 1329 页 · Qwen2.5-1.5B-Instruct + LoRA（Colab T4，3 epoch，104 条问答）**

## 一句话结论

**「董秘口径」可以微调进去，「董秘知道的事」调不进去。**
同一批财报里，凡是「公司这个数是多少」的事实题，该建库检索（RAG）；凡是「怎么把结论讲得像董秘」的口径与格式，才值得微调。
本次实验里，微调把引文格式率从 7.5% 拉到 72~92%，但把事实答对率压在 10~33%，连训练时见过的题也只有 16.3%。

## 四格对照（真实数字）

| 方案 | 样本 | 答对率 | 引用页码正确 | 有引文率 |
| --- | --- | --- | --- | --- |
""" + "\n".join(f"| {a} | {b} | **{c}** | {d} | {e} |" for a, b, c, d, e in GRID) + """

> 「答对」= 参考答案里的关键数字命中 ≥60%；没有可比数字的题（占 46%）退化为 8 字片段重合。

## 三个发现

""" + "\n\n".join(f"**{t}**\n\n{c}" for t, c in FINDINGS) + """

## 为什么没复现课件第 113 页的「2%→100%」

课件的实验是 421 条问答、答案短、6 轮；我们是 104 条、答案长（3~5 句 + 引文）、3 轮。
**这是样本量与容量的边界，不是方法的边界** —— 它恰好说明：想靠 SFT 记住财报事实，成本会随财报页数线性上涨；
而事实本来就在报告里，检索一次几乎免费。

## 限制（写清楚比好看重要）

""" + "\n".join(f"- {x}" for x in LIMITS) + """

## 回到我的案例（人才引进 → 技术进步 → 创新成果）

训练集里最密集的正是这条线：股权激励的授予与归属条件、研发人员数量与占比、研发投入的投向、
专利与产业化进展。**微调后的模型没能把这些数字记准，但它学会了董秘的答法**——
先给结论、再引原文、最后标出处。这套答法可以直接搬进案例写作：每写一条判断，都要能指回报告第几页。
至于具体数字，回到检索：`kb.jsonl` 里 2219 块，一块一块都能对上页码。
"""


def build_md():
    with open(MD, "w", encoding="utf-8") as f:
        f.write(MD_TEXT)
    print("已生成", MD)


def build_docx():
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Cm, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.35)
    sec.bottom_margin = Cm(1.15)
    sec.left_margin = Cm(1.6)
    sec.right_margin = Cm(1.6)

    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(8.8)
    style.paragraph_format.space_after = Pt(2)
    style.paragraph_format.line_spacing = 1.06

    h = doc.add_paragraph()
    r = h.add_run("一页结论 · 同一批财报：什么该建库，什么该微调")
    r.bold = True
    r.font.size = Pt(14)
    r.font.name = "Microsoft YaHei"

    sub = doc.add_paragraph()
    rs = sub.add_run("方向 B｜微导纳米（688147）· 7 份财报 1329 页 · "
                     "Qwen2.5-1.5B-Instruct + LoRA（Colab T4，3 epoch，104 条问答）")
    rs.font.size = Pt(8)
    rs.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    p = doc.add_paragraph()
    p.add_run("一句话结论：").bold = True
    p.add_run("「董秘口径」可以微调进去，「董秘知道的事」调不进去。同一批财报里，"
              "凡是「公司这个数是多少」的事实题，该建库检索（RAG）；凡是「怎么把结论讲得像董秘」的口径与格式，"
              "才值得微调。本次微调把引文格式率从 7.5% 拉到 72~92%，但事实答对率只有 10~33%，"
              "连训练时见过的题也只有 16.3%。")

    h2 = doc.add_paragraph()
    r2 = h2.add_run("四格对照（真实数字）")
    r2.bold = True
    r2.font.size = Pt(11)

    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    heads = ["方案", "样本", "答对率", "引用页码正确", "有引文率"]
    for i, t in enumerate(heads):
        cell = table.rows[0].cells[i]
        cell.text = ""
        rr = cell.paragraphs[0].add_run(t)
        rr.bold = True
        rr.font.size = Pt(7.8)
    for a, b, c, d, e in GRID:
        cells = table.add_row().cells
        for i, v in enumerate((a, b, c, d, e)):
            cells[i].text = ""
            rr = cells[i].paragraphs[0].add_run(v)
            rr.font.size = Pt(7.8)
            if i == 2:
                rr.bold = True

    note = doc.add_paragraph()
    rn = note.add_run("「答对」= 参考答案关键数字命中 ≥60%；没有可比数字的题（占 46%）退化为 8 字片段重合。")
    rn.font.size = Pt(7.5)
    rn.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    h3 = doc.add_paragraph()
    r3 = h3.add_run("三个发现")
    r3.bold = True
    r3.font.size = Pt(11)
    for t, c in FINDINGS:
        q = doc.add_paragraph()
        q.add_run(t).bold = True
        q.paragraph_format.space_after = Pt(1)
        a = doc.add_paragraph(c)
        a.paragraph_format.left_indent = Cm(0.4)
        a.paragraph_format.space_after = Pt(4)

    h4 = doc.add_paragraph()
    r4 = h4.add_run("为什么没复现课件第 113 页的「2%→100%」")
    r4.bold = True
    r4.font.size = Pt(10.5)
    doc.add_paragraph("课件的实验是 421 条问答、答案短、6 轮；我们是 104 条、答案长（3~5 句 + 引文）、3 轮。"
                      "这是样本量与容量的边界，不是方法的边界 —— 想靠 SFT 记住财报事实，成本会随页数线性上涨；"
                      "而事实本来就在报告里，检索一次几乎免费。")

    h5 = doc.add_paragraph()
    r5 = h5.add_run("限制（写清楚比好看重要）")
    r5.bold = True
    r5.font.size = Pt(10.5)
    for x in LIMITS:
        p = doc.add_paragraph(x, style="List Bullet")
        p.paragraph_format.space_after = Pt(1)
        for run in p.runs:
            run.font.size = Pt(8)

    h6 = doc.add_paragraph()
    r6 = h6.add_run("回到我的案例（人才引进 → 技术进步 → 创新成果）")
    r6.bold = True
    r6.font.size = Pt(10.5)
    doc.add_paragraph("训练集里最密集的正是这条线：股权激励的授予与归属条件、研发人员数量与占比、研发投入的投向、"
                      "专利与产业化进展。微调后的模型没把这些数字记准，但学会了董秘的答法 —— "
                      "先给结论、再引原文、最后标出处。这套答法可以直接搬进案例写作：每写一条判断都能指回报告第几页；"
                      "具体数字回到 kb.jsonl 的 2219 块里检索。")

    doc.save(DOCX)
    print("已生成", DOCX)


if __name__ == "__main__":
    build_md()
    build_docx()

