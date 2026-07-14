#!/usr/bin/env python3
"""BeautifulSoup 引用环 / GC 行为探针 —— bs4 生产维度 (纯 Python 秒级, 非计时)。

selectolax pack 的方法论段明确点到: "计时循环内会累积垃圾的对象 (如 bs4 循环引用
树) 做 per-iteration 清理"。bs4 的每个 Tag 同时持有对 parent 和 children 的引用,
构成引用环 —— 纯 `del soup` + refcount 无法立刻回收, 必须靠 CPython 的分代 GC。

本探针用**已知信号先校准仪器再下结论** (方法论 v3 Part 6 §3):
1. 先确认 bs4 树确实构成引用环 (gc.collect() 关掉时 del 后对象仍在 gc 里)。
2. 关 GC, 循环建/删 soup, 测对象计数是否单调涨 (环不回收的证据)。
3. 开 GC 重跑, 测对象计数是否被回收到基线 (GC 回收环的证据)。
仪器 = `gc.get_objects()` 里 bs4 对象数 + `len(gc.garbage)`; 结论字段运行时算出。

对照组: 用一个**已知无环**的对象 (纯 list of str) 跑同样循环, 证明"涨"确实来自 bs4
的环而非仪器噪声。

输出: artifacts/raw/gc_refcycles.json
"""
import gc
import json
import os
import sys
import warnings

from bs4 import BeautifulSoup, Tag

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "artifacts", "raw", "gc_refcycles.json")

SAMPLE = "<html><body>" + "".join(f"<div><p>item {i}</p></div>" for i in range(200)) + "</body></html>"
ITERS = 300


def count_bs4_objs():
    """当前存活的 bs4 Tag/NavigableString 对象数 —— 仪器。"""
    n = 0
    for o in gc.get_objects():
        if isinstance(o, Tag):
            n += 1
    return n


def probe_is_cyclic():
    """校准: 证明 bs4 树确实有引用环 (child.parent <-> parent.contents)。"""
    soup = BeautifulSoup(SAMPLE, "html.parser")
    p = soup.find("p")
    # child 指回 parent, parent.contents 里含 child -> 环
    parent_holds_child = p in (p.parent.contents if p.parent else [])
    child_holds_parent = p.parent is not None
    return {
        "child_references_parent": bool(child_holds_parent),
        "parent_contents_holds_child": bool(parent_holds_child),
        "is_reference_cycle": bool(child_holds_parent and parent_holds_child),
    }


def loop_measure(gc_on, make, is_bs4):
    """循环建/删对象, 关注对象计数增长。返回 (baseline, after_del_no_collect, after_final)。"""
    if gc_on:
        gc.enable()
    else:
        gc.disable()
    gc.collect()  # 清场
    baseline = count_bs4_objs() if is_bs4 else len(gc.get_objects())
    held = None
    for _ in range(ITERS):
        obj = make()
        # 模拟真实用法: 用完就丢, 不手动 gc
        obj = None  # noqa
    # 关键测量点: del 之后、**不主动 collect**, 看还剩多少
    after_del = count_bs4_objs() if is_bs4 else len(gc.get_objects())
    # 现在强制 collect 一次, 看能否回收
    gc.collect()
    after_collect = count_bs4_objs() if is_bs4 else len(gc.get_objects())
    gc.enable()
    return baseline, after_del, after_collect


def main():
    import bs4

    calib = probe_is_cyclic()

    # bs4: GC 关 vs 开
    b_off_base, b_off_del, b_off_coll = loop_measure(
        gc_on=False, make=lambda: BeautifulSoup(SAMPLE, "html.parser"), is_bs4=True
    )
    b_on_base, b_on_del, b_on_coll = loop_measure(
        gc_on=True, make=lambda: BeautifulSoup(SAMPLE, "html.parser"), is_bs4=True
    )

    # 对照组: 已知无环对象 (list of str), GC 关 —— 不应累积
    def make_acyclic():
        return ["item %d" % i for i in range(200)]

    ctrl_base, ctrl_del, ctrl_coll = loop_measure(gc_on=False, make=make_acyclic, is_bs4=False)

    # 结论字段全部运行时算出 (闸门 3)
    accumulates_without_gc = b_off_del > b_off_base + 50  # bs4 对象在 GC 关时堆积
    reclaimed_by_collect = b_off_coll <= b_off_base + 50  # collect 后回落
    # GC 开时是"周期性回收", 不是每次 del 即清零; 判据是 GC 开时残留远低于 GC 关时
    # (分代 GC 已在循环中触发过若干次, 把峰值压下来), 而非要求瞬时归零。
    bounded_with_gc = b_on_del < b_off_del * 0.5

    out = {
        "meta": {
            "bs4_version": bs4.__version__,
            "python": sys.version.split()[0],
            "iters": ITERS,
            "instrument": "count of live bs4.Tag objects via gc.get_objects()",
            "note": "先校准环存在, 再用对象计数证明 GC 关时堆积/开时回收; 结论运行时算出",
        },
        "cycle_calibration": calib,
        "bs4_gc_off": {
            "baseline_tags": b_off_base,
            "after_del_no_collect_tags": b_off_del,
            "after_forced_collect_tags": b_off_coll,
        },
        "bs4_gc_on": {
            "baseline_tags": b_on_base,
            "after_del_no_collect_tags": b_on_del,
            "after_forced_collect_tags": b_on_coll,
        },
        "control_acyclic_gc_off": {
            "baseline_objs": ctrl_base,
            "after_del_objs": ctrl_del,
            "after_collect_objs": ctrl_coll,
            "delta_after_del": ctrl_del - ctrl_base,
        },
        "conclusions": {
            "tree_is_reference_cycle": calib["is_reference_cycle"],
            "accumulates_when_gc_disabled": bool(accumulates_without_gc),
            "reclaimed_only_by_gc_collect": bool(reclaimed_by_collect and accumulates_without_gc),
            "bounded_when_gc_enabled": bool(bounded_with_gc),
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps(out["conclusions"], ensure_ascii=False))
    print(json.dumps({"gc_off": out["bs4_gc_off"], "gc_on": out["bs4_gc_on"],
                      "control": out["control_acyclic_gc_off"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
