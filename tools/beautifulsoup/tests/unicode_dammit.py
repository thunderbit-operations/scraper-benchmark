#!/usr/bin/env python3
"""UnicodeDammit 编码检测探针 —— bs4 独有能力 (selectolax 无对应组件)。

selectolax pack 的 §ENC 显示: 传非 UTF-8 bytes 给 selectolax 会在 .text()/.html
静默损坏或抛错。bs4 走的是相反路线: 内置 UnicodeDammit 自动嗅探编码并解码为 str。
本探针系统测一个"声明 vs 实际"字符集矩阵, 记录 UnicodeDammit 猜到的编码 + 是否
把内容正确还原。`recovered_correctly` 由运行时比对目标串算出 (闸门 3)。

同时对照: 同样的非 UTF-8 bytes 直接喂 BeautifulSoup(bytes, backend), 看 bs4
整体的字节->str 恢复行为。

输出: artifacts/raw/unicode_dammit.json
"""
import json
import os
import sys
import warnings

from bs4 import BeautifulSoup, UnicodeDammit

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "artifacts", "raw", "unicode_dammit.json")

# 目标可读串 (还原成功的判据)
TARGET = "café éè —— 汉字 ★"

# 各编码把 TARGET 编成 bytes; 有的编码无法表示全部字符, 用能表示的子集
CASES = [
    dict(id="utf8_no_decl", enc="utf-8", text="café éè", declared=None),
    dict(id="latin1_no_decl", enc="latin-1", text="café éè", declared=None),
    dict(id="cp1252_no_decl", enc="cp1252", text="café €99", declared=None),
    dict(id="utf16_bom", enc="utf-16", text="café éè", declared=None),
    dict(id="gbk_chinese", enc="gbk", text="汉字编码测试", declared=None),
    dict(id="shiftjis", enc="shift_jis", text="日本語テスト", declared=None),
    dict(id="latin1_declared_utf8", enc="latin-1", text="café éè", declared="utf-8"),  # 声明错的
    dict(id="utf8_declared_latin1", enc="utf-8", text="café éè", declared="latin-1"),  # 声明错的
]


def make_bytes(case):
    body = case["text"]
    if case["declared"]:
        html = f'<html><head><meta charset="{case["declared"]}"></head><body><p>{body}</p></body></html>'
    else:
        html = f"<html><body><p>{body}</p></body></html>"
    return html.encode(case["enc"]), body


def main():
    import bs4

    results = []
    for case in CASES:
        raw, expected_text = make_bytes(case)
        rec = {"id": case["id"], "true_encoding": case["enc"], "declared": case["declared"]}

        # (1) UnicodeDammit 单独跑
        try:
            dammit = UnicodeDammit(raw)
            rec["dammit_detected_encoding"] = dammit.original_encoding
            recovered = dammit.unicode_markup or ""
            rec["dammit_text_recovered"] = expected_text in recovered
            rec["dammit_sample"] = recovered[:80]
        except Exception as e:
            rec["dammit_error"] = f"{type(e).__name__}: {e}"
            rec["dammit_text_recovered"] = False

        # (2) BeautifulSoup 整体喂 bytes, 看 p 文本能否还原 (html.parser)
        try:
            soup = BeautifulSoup(raw, "html.parser")
            p = soup.find("p")
            got = p.get_text() if p else ""
            rec["bs4_htmlparser_recovered"] = expected_text in got
            rec["bs4_detected_encoding"] = getattr(soup, "original_encoding", None)
            rec["bs4_sample"] = got[:80]
        except Exception as e:
            rec["bs4_error"] = f"{type(e).__name__}: {e}"
            rec["bs4_htmlparser_recovered"] = False

        results.append(rec)

    n_dammit_ok = sum(1 for r in results if r.get("dammit_text_recovered"))
    n_bs4_ok = sum(1 for r in results if r.get("bs4_htmlparser_recovered"))
    out = {
        "meta": {
            "bs4_version": bs4.__version__,
            "python": sys.version.split()[0],
            "note": "UnicodeDammit 编码嗅探; recovered 字段运行时比对目标串算出",
            "chardet_available": _has_chardet(),
        },
        "n_dammit_recovered": n_dammit_ok,
        "n_bs4_recovered": n_bs4_ok,
        "n_cases": len(CASES),
        "cases": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps({"dammit_ok": n_dammit_ok, "bs4_ok": n_bs4_ok, "n": len(CASES)}, ensure_ascii=False))


def _has_chardet():
    try:
        import chardet  # noqa
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
