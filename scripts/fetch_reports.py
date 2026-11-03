# -*- coding: utf-8 -*-
"""
从巨潮资讯下载微导纳米(688147)的年度报告 / 半年度报告全文 PDF。
用法：python fetch_reports.py [--years 3]
"""
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
NAME = "微导纳米"
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(BASE), "raw")
os.makedirs(OUT, exist_ok=True)


def post(url, form):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=HDR)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def all_announcements(pages=40):
    """按页拉全部公告（接口的 type 过滤不可靠，改成本地按标题筛）"""
    out, seen = [], set()
    for p in range(1, pages + 1):
        form = {
            "pageNum": str(p), "pageSize": "30", "column": "sse", "tabName": "fulltext",
            "plate": "", "stock": STOCK, "searchkey": "", "secdate": "", "tdate": "",
            "type": "", "isHLtitle": "true",
        }
        try:
            data = json.loads(post("http://www.cninfo.com.cn/new/hisAnnouncement/query", form))
        except Exception as e:
            print(f"  第 {p} 页失败: {type(e).__name__}: {e}")
            break
        anns = data.get("announcements") or []
        if not anns:
            break
        for a in anns:
            if a["announcementId"] in seen:
                continue
            seen.add(a["announcementId"])
            out.append(a)
        time.sleep(0.3)
    return out


def title_of(a):
    return re.sub(r"</?em>", "", a["announcementTitle"]).replace("\u3000", " ").strip()


def is_annual(t):
    return bool(re.search(r"\d{4}年年度报告$", t))


def is_semi(t):
    return bool(re.search(r"\d{4}年半年度报告$", t))


def download(a, tag):
    url = "http://static.cninfo.com.cn/" + a["adjunctUrl"]
    d = time.strftime("%Y-%m-%d", time.localtime(a["announcementTime"] / 1000))
    fn = f"{d}_{tag}_{title_of(a)}.pdf"
    path = os.path.join(OUT, fn)
    if os.path.exists(path) and os.path.getsize(path) > 200000:
        print("   已存在:", fn)
        return path
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
        f.write(r.read())
    print(f"   下载完成: {fn}  {os.path.getsize(path) / 1024 / 1024:.1f} MB")
    return path


def main():
    print(f"== 拉取 {NAME}(688147) 的公告列表 ==")
    anns = all_announcements()
    print(f"  共 {len(anns)} 条")

    annual, semi = [], []
    for a in anns:
        t = title_of(a)
        if is_annual(t):
            annual.append(a)
        elif is_semi(t):
            semi.append(a)

    print(f"\n== 年度报告 {len(annual)} 份 ==")
    for a in annual:
        print("   ", time.strftime("%Y-%m-%d", time.localtime(a["announcementTime"] / 1000)), title_of(a))
    print(f"\n== 半年度报告 {len(semi)} 份 ==")
    for a in semi:
        print("   ", time.strftime("%Y-%m-%d", time.localtime(a["announcementTime"] / 1000)), title_of(a))

    print("\n== 下载最近 3 份年报 + 2 份半年报 ==")
    for a in annual[:3]:
        try:
            download(a, "年报")
        except Exception as e:
            print("   失败:", type(e).__name__, e)
    for a in semi[:2]:
        try:
            download(a, "半年报")
        except Exception as e:
            print("   失败:", type(e).__name__, e)

    print("\n== 目录 ==", OUT)
    for f in sorted(os.listdir(OUT)):
        if f.lower().endswith(".pdf"):
            print("   ", f, f"{os.path.getsize(os.path.join(OUT, f)) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

