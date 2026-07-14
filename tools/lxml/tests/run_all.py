#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按序跑全部 lxml 能力测试并生成 summary。纯能力/保真测试（非计时），可重复执行。
计时数据不在此产出——一律复用 selectolax pack。
用法：<venv>/bin/python tests/run_all.py
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    "xpath_matrix.py",
    "two_api_behavior.py",
    "iterparse_streaming.py",
    "namespaces.py",
    "xpath_vs_css.py",
    "real_world_lxml.py",
    "api_capabilities.py",
    "depth_limit.py",
    "build_summary.py",
]


def main():
    py = sys.executable
    for s in SCRIPTS:
        print(f"\n=== {s} ===")
        p = subprocess.run([py, os.path.join(HERE, s)], text=True)
        if p.returncode != 0:
            print(f"!! {s} exited {p.returncode}", file=sys.stderr)
            sys.exit(p.returncode)
    print("\nALL OK")


if __name__ == "__main__":
    main()
