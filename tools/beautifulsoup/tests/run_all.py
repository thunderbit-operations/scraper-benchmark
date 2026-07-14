#!/usr/bin/env python3
"""按顺序跑本 pack 全部 bs4 特有测试, 再生成汇总。

本 pack **不产任何计时数据** —— 计时/内存/GIL 分布全部复用 selectolax pack
(见 build_summary.py 的 reuse_* 段)。这里只跑纯 Python 秒级的能力/保真/容错测试,
互不争抢 CPU, 无需进程隔离计时。

用法: ./.venv/bin/python tests/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

SCRIPTS = [
    "malformed_matrix.py",
    "api_surface.py",
    "unicode_dammit.py",
    "gc_refcycles.py",
    "soupsieve_extended.py",
    "real_backend_divergence.py",
    "build_summary.py",  # 最后生成汇总
]


def main():
    for s in SCRIPTS:
        path = os.path.join(HERE, s)
        print(f"\n=== {s} ===")
        r = subprocess.run([PY, path], capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            print(f"!! {s} FAILED (exit {r.returncode})")
            sys.exit(r.returncode)
    print("\nAll bs4-specific tests passed; summary regenerated.")


if __name__ == "__main__":
    main()
