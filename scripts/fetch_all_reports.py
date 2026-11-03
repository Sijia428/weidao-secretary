# -*- coding: utf-8 -*-
"""列出微导纳米(688147)所有"年度报告/半年度报告"类的公告，并下载全部报告正文"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "http://www.cninfo.com.cn/",
}
STOCK = "688147,nssc1000585"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "raw")
os.makedirs(OUT, exist_ok=True)


def post(url, form):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=HDR)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def all_announcements():
    out, seen = [], set()
    for p in range(1, 61):
        form = {"pageNum": str(p), "pageSize": "30", "column": "sse", "tabName": "fulltext",
                "plate": "", "stock": STOCK, "searchkey": "", "secdate": "", "tdate": "",
                "type": "", "isHLtitle": "true"}
        try:
            data = json.loads(post("http://www.cninfo.com.cn/new/hisAnnouncement/query", form))
        except Exception:
            break
        anns = data.get("announcements") or []
        if not anns:
            break
        for a in anns:
            if a["announcementId"] not in seen:
                seen.add(a["announcementId"])
                out.append(a)
    return out


def title_of(a):
    return re.sub(r"</?em>", "", a["announcementTitle"]).replace("\u3000", " ").strip()


def main():
    anns = all_announcements()
    print(f"公告总数: {len(anns)}")
    cands = []
    for a in anns:
        t = title_of(a)
        if not re.search(r"(年度|半年度)报告", t):
            continue
        bad = any(x in t for x in ("摘要", "英文", "制度", "关于", "核查", "问询", "说明",
                                    "鉴证", "意见", "公告", "纠正", "预案", "保荐"))
        if bad:
            continue
        cands.append(a)

    print(f"\n== 报告正文候选 {len(cands)} 份 ==")
    for a in cands:
        d = time.strftime("%Y-%m-%d", time.localtime(a["announcementTime"] / 1000))
        print("  ", d, title_of(a))

    print("\n== 下载 ==")
    for a in cands:
        t = title_of(a)
        d = time.strftime("%Y-%m-%d", time.localtime(a["announcementTime"] / 1000))
        tag = "半年报" if "半年度报告" in t else "年报"
        fn = f"{d}_{tag}_{t}.pdf"
        path = os.path.join(OUT, fn)
        if os.path.exists(path) and os.path.getsize(path) > 200000:
            print("   已存在:", fn)
            continue
        try:
            req = urllib.request.Request("http://static.cninfo.com.cn/" + a["adjunctUrl"], headers=HDR)
            with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
                f.write(r.read())
            print(f"   下载完成: {fn}  {os.path.getsize(path) / 1024 / 1024:.1f} MB")
        except Exception as e:
            print("   失败:", fn, type(e).__name__, e)
        time.sleep(0.3)

    print("\n== raw 目录 ==")
    total = 0
    for f in sorted(os.listdir(OUT)):
        if f.lower().endswith(".pdf"):
            sz = os.path.getsize(os.path.join(OUT, f)) / 1024 / 1024
            total += sz
            print(f"   {f}  {sz:.1f} MB")
    print(f"   合计 {total:.1f} MB")


if __name__ == "__main__":
    main()
