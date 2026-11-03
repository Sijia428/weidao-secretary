# -*- coding: utf-8 -*-
"""
交出前自检：把能在本地验的全验一遍，验不过就不交给学生。

检查项：
  1. notebook 每个代码单元语法能否编译（去掉 !/% 魔法行后 ast.parse）
  2. T1 的每道原问法必须真在 train.jsonl 里出现过（否则测的不是"背没背住"）
  3. 防泄漏：未见事实的问题不能出现在训练集里
  4. 判分链路真跑：把 notebook 第 8、9 单元 exec 起来
       · 喂"完美回答" → 四格答对率必须 100%
       · 喂"垃圾回答" → 四格答对率必须 0%
  5. 总表（第 11 单元）能否用假数据跑通并写出 对照表.csv

所有产物都写在临时目录，不污染 build/。
用法：python selftest.py
"""
import ast
import json
import os
import shutil
import sys
import tempfile
import types

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(BASE, "build")
NB = os.path.join(BASE, "train_lora.ipynb")
EVAL = os.path.join(BUILD, "eval.jsonl")
TRAIN = os.path.join(BUILD, "train.jsonl")

FAIL, PASS = [], []


def ok(m):
    PASS.append(m)
    print("  ✅ " + m)


def bad(m):
    FAIL.append(m)
    print("  ❌ " + m)


def mk_tmpdir():
    td = os.path.join(BASE, ".tmp", "selftest")     # 沙箱对"新建目录"有 ACL 限制，用预先建好的目录
    for f in ("eval.jsonl", "train.jsonl"):
        src = os.path.join(BUILD, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(td, f))
    return td


def stub_google():
    """让 colab_files.download 在本地也能跑通"""
    g = types.ModuleType("google")
    gc = types.ModuleType("google.colab")
    gf = types.ModuleType("google.colab.files")
    gf.download = lambda path: print("   (模拟下载)", path)
    sys.modules.setdefault("google", g)
    sys.modules["google.colab"] = gc
    sys.modules["google.colab.files"] = gf


def load_cells():
    nb = json.load(open(NB, encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def strip_magic(src):
    out = []
    for line in src.splitlines():
        s = line.lstrip()
        out.append("pass  # magic" if (s.startswith("!") or s.startswith("%")) else line)
    return "\n".join(out)


def check_syntax(cells):
    print("\n[1] notebook 语法")
    for i, src in enumerate(cells):
        try:
            ast.parse(strip_magic(src))
        except SyntaxError as e:
            bad(f"第 {i+1} 个代码单元语法错误：{e.msg} (line {e.lineno})")
    if not FAIL:
        ok(f"{len(cells)} 个代码单元全部可编译")


def check_data():
    print("\n[2] T1 的原问法必须在训练集里出现过")
    train_q = set()
    for line in open(TRAIN, encoding="utf-8"):
        for m in json.loads(line)["messages"]:
            if m["role"] == "user":
                train_q.add(m["content"].replace("投资者提问：", "").strip())
    rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
    t1 = [r for r in rows if r["split"] == "train"]
    miss = [r for r in t1 if r["q"].strip() not in train_q]
    if miss:
        bad(f"T1 有 {len(miss)}/{len(t1)} 道题不在训练集里（等于用没教过的题考背诵）")
    else:
        ok(f"T1 {len(t1)} 道题全部命中训练集")

    print("\n[3] 防泄漏：未见事实不能进训练集")
    unseen = [r for r in rows if r["split"] == "unseen"]
    leak = {r["q"].strip() for r in unseen} & train_q
    if leak:
        bad(f"T2 有 {len(leak)} 道题同时出现在训练集里")
    else:
        ok(f"T2 {len(unseen)} 道题没有泄漏进训练集")
    return rows


STUB = '''
import types, json, os
class _FakeModel:
    def generate(self, **kw):
        raise RuntimeError("stub")
class _FakeTok:
    def apply_chat_template(self, msgs, tokenize=False, add_generation_prompt=True):
        return msgs[-1]["content"]
class _FakeFLM:
    @staticmethod
    def for_inference(m): pass
FastLanguageModel = _FakeFLM
model = _FakeModel()
tokenizer = _FakeTok()
torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_bf16_supported=lambda: True))
'''


def run_eval_units(cells, answer_fn, tag):
    print(f"\n[4] 判分链路实跑（{tag}）")
    src = cells[7].replace('print(gen("公司报告期内研发人员数量占员工总数的比例是多少？"))', "")
    ns = {}
    exec(STUB, ns)
    td = mk_tmpdir()
    old = os.getcwd()
    os.chdir(td)
    try:
        exec(src, ns)
        index = {}
        for line in open("eval.jsonl", encoding="utf-8"):
            r = json.loads(line)
            index[r["q"]] = r
            index[r["q_alt"]] = r

        def fake_gen(question, context=None, max_new_tokens=0):
            r = index.get(question)
            return answer_fn(r) if r else "报告未披露"

        ns["gen"] = fake_gen
        exec(cells[8], ns)
        return ns["grid"]
    finally:
        os.chdir(old)
        pass   # 复用同一个目录，不删


def check_scoring(cells):
    perfect = run_eval_units(cells, lambda r: r["ref_a"], "完美回答（应 100%）")
    print(perfect)
    if perfect["答对率"].min() >= 0.999:
        ok("完美回答时四格答对率均 100%（判分没把对的判错）")
    else:
        bad(f"完美回答时最低只有 {perfect['答对率'].min():.1%}")

    junk = run_eval_units(cells, lambda r: "不知道。", "垃圾回答（应 0%）")
    print(junk)
    if junk["答对率"].max() <= 0.001:
        ok("垃圾回答时四格答对率均为 0（判分没把错的判对）")
    else:
        bad(f"垃圾回答时最高仍有 {junk['答对率'].max():.1%}")


def check_summary(cells):
    print("\n[5] 总表 + 导出 CSV")
    import pandas as pd
    stub_google()
    recs = [{"split": s, "mode": m, "chunk_id": "x", "page": 1, "q": "q", "pred": "p",
             "ref": "r", "数字命中率": 1.0, "片段重合": 1, "答对": 1, "引用正确": 1, "带引文": 1}
            for s in ("train", "unseen") for m in ("原问法", "换问法") for _ in range(5)]
    ns = {"pd": pd, "df": pd.DataFrame(recs),
          "rag": pd.DataFrame([{"答对": 0, "引用正确": 0, "数字命中率": 0.0}] * 5)}
    td = mk_tmpdir()
    old = os.getcwd()
    os.chdir(td)
    made = False
    try:
        exec(cells[10], ns)
        made = os.path.exists(os.path.join(td, "对照表.csv"))
    except Exception as e:
        bad(f"第 11 单元跑不通：{type(e).__name__}: {e}")
    finally:
        os.chdir(old)
        pass   # 复用同一个目录，不删
    if made:
        ok("第 11 单元能正常生成 对照表.csv")


def main():
    print("=" * 66)
    print("交出前自检")
    print("=" * 66)
    cells = load_cells()
    check_syntax(cells)
    if FAIL:
        print("\n有语法错误，后面的检查跳过。")
        return 1
    check_data()
    check_scoring(cells)
    check_summary(cells)
    print("\n" + "=" * 66)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for f in FAIL:
        print("  ❌", f)
    print("=" * 66)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())


