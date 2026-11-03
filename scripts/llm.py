# -*- coding: utf-8 -*-
"""
DeepSeek API 客户端（只依赖标准库）。
密钥从 .env 读：DEEPSEEK_API_KEY=sk-xxxx
.env 不进仓库、不上屏；代码里只出现变量名。
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE, ".env")
DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def load_env():
    cfg = {}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE", "DEEPSEEK_MODEL"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


class LLM:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_env()
        self.key = self.cfg.get("DEEPSEEK_API_KEY", "")
        self.base = (self.cfg.get("DEEPSEEK_BASE") or DEFAULT_BASE).rstrip("/")
        self.model = self.cfg.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
        self.calls = 0
        self.tin = 0
        self.tout = 0
        if not self.key:
            raise RuntimeError(f"没有找到 API key。请把 DEEPSEEK_API_KEY=sk-... 写进 {ENV_PATH}")

    def chat(self, messages, temperature=0.3, max_tokens=1600, retries=4, json_mode=True):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = json.dumps(payload).encode("utf-8")
        last = None
        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(
                    self.base + "/chat/completions", data=data,
                    headers={"Content-Type": "application/json",
                             "Authorization": "Bearer " + self.key})
                with urllib.request.urlopen(req, timeout=180,
                                            context=ssl.create_default_context()) as r:
                    body = json.loads(r.read().decode("utf-8"))
                self.calls += 1
                u = body.get("usage", {})
                self.tin += u.get("prompt_tokens", 0)
                self.tout += u.get("completion_tokens", 0)
                return body["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read(300).decode("utf-8", "replace")
                except Exception:
                    pass
                last = f"HTTP {e.code}: {detail}"
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(3 * attempt)
                    continue
                raise RuntimeError(f"API 报错 {last}")
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                time.sleep(2 * attempt)
        raise RuntimeError(f"重试 {retries} 次仍失败：{last}")

    def stats(self):
        return f"调用 {self.calls} 次，输入 {self.tin} tokens，输出 {self.tout} tokens"
