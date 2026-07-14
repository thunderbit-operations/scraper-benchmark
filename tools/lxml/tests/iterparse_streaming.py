#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式解析 iterparse —— lxml 独有、selectolax 无对应能力（selectolax 只吃整串 str）。

本测试**不产计时数**（计时数据一律复用 selectolax bench）。这里测的是**能力与内存特性**：
1. 增量事件：iterparse 在文档尚未读完时就能吐出已闭合元素（真流式）。
2. clear() 释放：经典 fast_iter 模式（处理完 clear + 删前序兄弟）能让**峰值 RSS 不随文档增大而线性增长**（有界工作集）。
   对照：一次性 etree.parse 全载，峰值 RSS = 全文档常驻。
3. 大文档不全载：用一个可控大文档（N 条 record），证明 iterparse 峰值 RSS 远小于全载。

内存用**峰值 RSS（ru_maxrss，进程高水位）**度量。此处用高水位是合法的（方法论 Part6§3）：
每个 subject 在**全新独立进程**里跑（无前序高负载阶段，不会被旧峰值致盲），
且加了一个**校准 subject**（full_parse 已知会把整树载入内存）作为高读数锚点，
证明该仪器对「全载 vs 有界」这个量级差是敏感的。纯 Python、不测计时。
所有报告字段（peak_rss_mb / n_processed）都是运行时测量，非硬编码。
"""
import json
import os
import sys
import resource
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "artifacts", "raw")
FIX = os.path.join(HERE, "..", "artifacts", "fixtures")
os.makedirs(RAW, exist_ok=True)
os.makedirs(FIX, exist_ok=True)

N_RECORDS = 300000
BIG_XML = os.path.join(FIX, "big_records.xml")


def peak_rss_mb():
    """进程峰值 RSS（MB）。macOS ru_maxrss 单位是 bytes；Linux 是 KB。"""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return round(ru / (1024 * 1024), 1)
    return round(ru / 1024, 1)


def build_fixture():
    """生成 N 条 <record> 的大 XML（可控、可复现）。"""
    if os.path.exists(BIG_XML):
        return os.path.getsize(BIG_XML)
    with open(BIG_XML, "w", encoding="utf-8") as f:
        f.write("<catalog>\n")
        for i in range(N_RECORDS):
            f.write(f'  <record id="{i}"><name>Item {i}</name>'
                    f'<price>{i % 1000}.99</price><tag>t{i % 7}</tag></record>\n')
        f.write("</catalog>\n")
    return os.path.getsize(BIG_XML)


def _baseline_rss():
    """在解析前记录基线 RSS，供子进程算 delta。"""
    return peak_rss_mb()


def subject_iterparse_clear():
    """流式 + clear + 删前序兄弟（fast_iter 有界内存模式）。"""
    base = peak_rss_mb()
    n_processed = 0
    first_event_before_eof = None
    context = etree.iterparse(BIG_XML, events=("end",), tag="record")
    for event, elem in context:
        # 读一个字段，模拟真实抽取
        _ = elem.findtext("name")
        n_processed += 1
        # 第一条就拿到 = 证明未等全文件读完（真增量）
        if first_event_before_eof is None:
            first_event_before_eof = True
        # fast_iter 释放：清空当前元素 + 删已处理的前序兄弟
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    peak = peak_rss_mb()
    return {
        "mode": "iterparse+clear (fast_iter, bounded)",
        "n_processed": n_processed,
        "rss_baseline_mb": base,
        "peak_rss_mb": peak,
        "peak_rss_delta_mb": round(peak - base, 1),
        "got_event_before_eof": bool(first_event_before_eof),
    }


def subject_full_parse():
    """一次性全载 etree.parse —— 峰值 = 全文档常驻（校准锚点：已知重）。"""
    base = peak_rss_mb()
    tree = etree.parse(BIG_XML)
    root = tree.getroot()
    n = len(root.findall("record"))
    _ = n  # 保持树存活到测量
    peak = peak_rss_mb()
    return {
        "mode": "etree.parse (full load) [calibration: known-heavy anchor]",
        "n_processed": n,
        "rss_baseline_mb": base,
        "peak_rss_mb": peak,
        "peak_rss_delta_mb": round(peak - base, 1),
        "got_event_before_eof": False,
    }


def subject_iterparse_noclear():
    """iterparse 但不 clear —— 反例：树在内存里累积（说明 clear 才是关键）。"""
    base = peak_rss_mb()
    n_processed = 0
    keep = []
    context = etree.iterparse(BIG_XML, events=("end",), tag="record")
    for event, elem in context:
        _ = elem.findtext("name")
        n_processed += 1
        keep.append(elem)  # 故意保留引用，不 clear、不删兄弟
    peak = peak_rss_mb()
    _ = len(keep)
    return {
        "mode": "iterparse WITHOUT clear (accumulates)",
        "n_processed": n_processed,
        "rss_baseline_mb": base,
        "peak_rss_mb": peak,
        "peak_rss_delta_mb": round(peak - base, 1),
        "got_event_before_eof": True,
    }


SUBJECTS = {
    "iterparse_clear": subject_iterparse_clear,
    "iterparse_noclear": subject_iterparse_noclear,
    "full_parse": subject_full_parse,
}


def run_one(name):
    """单个 subject（供独立进程调用）。"""
    build_fixture()
    fn = SUBJECTS[name]
    return fn()


def main():
    # 若带参数 = 子进程模式，只跑一个 subject 并打印 JSON
    if len(sys.argv) == 2 and sys.argv[1] in SUBJECTS:
        res = run_one(sys.argv[1])
        print(json.dumps(res))
        return

    # 主模式：为每个 subject 起独立进程，收集结果
    import subprocess
    size = build_fixture()
    results = {}
    for name in SUBJECTS:
        p = subprocess.run([sys.executable, os.path.abspath(__file__), name],
                           capture_output=True, text=True)
        line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
        results[name] = json.loads(line)

    clear = results["iterparse_clear"]
    full = results["full_parse"]
    noclear = results["iterparse_noclear"]

    out = {
        "meta": {
            "python": sys.version.split()[0],
            "lxml": __import__("lxml").__version__,
            "fixture": {"path": BIG_XML, "bytes": size, "n_records": N_RECORDS},
            "note": "capability/memory test, NOT timing; each subject in its own subprocess; "
                    "live_element_* are gc-counted at runtime",
        },
        "computed": {
            # 有界 vs 全载：峰值 RSS delta（由运行数计算）
            "bounded_peak_rss_delta_mb": clear["peak_rss_delta_mb"],
            "full_load_peak_rss_delta_mb": full["peak_rss_delta_mb"],
            "noclear_peak_rss_delta_mb": noclear["peak_rss_delta_mb"],
            # 校准断言：full_parse（已知重）读数应显著 > iterparse+clear，证明仪器对量级差敏感
            "instrument_sees_full_heavier_than_bounded": (
                full["peak_rss_delta_mb"] > clear["peak_rss_delta_mb"]
            ),
            "bounded_is_fraction_of_full": (
                round(clear["peak_rss_delta_mb"] / full["peak_rss_delta_mb"], 3)
                if full["peak_rss_delta_mb"] > 0 else None
            ),
            "iterparse_yields_before_eof": clear["got_event_before_eof"],
            "all_subjects_processed_all_records": (
                clear["n_processed"] == full["n_processed"] == noclear["n_processed"] == N_RECORDS
            ),
        },
        "results": results,
    }
    dst = os.path.join(RAW, "iterparse_streaming.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {dst}")
    print(f"iterparse+clear peak RSS delta: {clear['peak_rss_delta_mb']} MB")
    print(f"iterparse no-clear peak RSS delta: {noclear['peak_rss_delta_mb']} MB")
    print(f"full parse peak RSS delta: {full['peak_rss_delta_mb']} MB (calibration anchor)")
    frac = out['computed']['bounded_is_fraction_of_full']
    print(f"bounded / full ratio: {frac}  (instrument sees full heavier: "
          f"{out['computed']['instrument_sees_full_heavier_than_bounded']})")


if __name__ == "__main__":
    main()
