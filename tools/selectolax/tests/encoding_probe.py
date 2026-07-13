#!/usr/bin/env python3
"""Non-UTF-8 bytes behaviour, measured (not asserted from memory).

Fable 5 caught the v2 prose describing this wrong: it claimed Lexbor's .text()
RAISES UnicodeDecodeError on non-UTF-8 bytes and that only Modest silently drops.
Direct measurement shows the opposite framing is needed:

  - Parsing raw non-UTF-8 bytes SUCCEEDS on both engines (bytes stored raw).
  - .text() does NOT raise on either engine -- it SILENTLY CORRUPTS:
        Lexbor -> U+FFFD replacement characters
        Modest -> drops the offending bytes
  - .html serialization RAISES UnicodeDecodeError on BOTH engines.
  - Workaround: decode the bytes yourself first; both engines then return the
    correct text.

Every value in the output JSON is computed at runtime from the actual call
results (no hardcoded verdicts). This script is the executable source for the
research doc's non-UTF-8 section.
"""
import json
import os

RAW = os.environ.get("SLX_RESULTS_DIR") or os.path.join(os.path.dirname(__file__), "..", "artifacts", "raw")
os.makedirs(RAW, exist_ok=True)


def probe_call(fn):
    """Run fn(); return ('OK', value) or ('RAISED', 'ExcType: msg')."""
    try:
        v = fn()
        return {"outcome": "OK", "value": v}
    except Exception as e:
        return {"outcome": "RAISED", "error": f"{type(e).__name__}: {str(e)[:120]}"}


def classify_text(result):
    """Given an OK .text() value on the latin-1 café fixture, describe corruption
    by COMPARING to the intended text -- computed, not asserted."""
    if result["outcome"] != "OK":
        return None
    v = result["value"]
    intended = "café éè"
    has_replacement = "�" in v
    dropped_bytes = (v != intended) and not has_replacement
    return {
        "returned": v,
        "equals_intended": v == intended,
        "contains_U+FFFD_replacement": has_replacement,
        "silently_dropped_bytes": dropped_bytes,
        "corruption": ("replacement_chars" if has_replacement
                       else "dropped_bytes" if dropped_bytes
                       else "none"),
    }


def main():
    from selectolax.lexbor import LexborHTMLParser
    from selectolax.parser import HTMLParser

    # café + two trailing latin-1 accented bytes, encoded latin-1 (NOT valid UTF-8)
    raw = "<p>café éè</p>".encode("latin-1")
    engines = {"lexbor": LexborHTMLParser, "modest": HTMLParser}

    out = {
        "fixture_bytes_repr": repr(raw),
        "intended_text": "café éè",
        "engines": {},
        "workaround": {},
    }

    for name, Cls in engines.items():
        # parse (should succeed on both)
        parse = probe_call(lambda: (Cls(raw) is not None))
        tree = Cls(raw)
        node = tree.css_first("p")
        text_res = probe_call(lambda: node.text())
        html_res = probe_call(lambda: tree.html)
        out["engines"][name] = {
            "parse": parse,
            "text_call": text_res,
            "text_analysis": classify_text(text_res),
            "html_serialization": {
                "outcome": html_res["outcome"],
                "error": html_res.get("error"),
                # don't dump the whole doc if OK; just length
                "value_len": (len(html_res["value"]) if html_res["outcome"] == "OK" else None),
            },
        }

    # workaround: decode first, then parse the str
    s = raw.decode("latin-1")
    for name, Cls in engines.items():
        v = Cls(s).css_first("p").text()
        out["workaround"][name] = {"decoded_first_text": v, "correct": v == "café éè"}

    with open(os.path.join(RAW, "encoding_probe.json"), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # human-readable summary
    print("=== non-UTF-8 latin-1 bytes into selectolax ===")
    for name in engines:
        e = out["engines"][name]
        ta = e["text_analysis"]
        print(f"{name}:")
        print(f"  parse:  {e['parse']['outcome']}")
        print(f"  .text() {e['text_call']['outcome']} -> {ta['returned']!r} "
              f"[corruption={ta['corruption']}]")
        print(f"  .html   {e['html_serialization']['outcome']}"
              f"{' -> '+e['html_serialization']['error'] if e['html_serialization']['error'] else ''}")
    print("workaround (decode first):",
          {k: v["correct"] for k, v in out["workaround"].items()})
    print("\nwritten", os.path.join(RAW, "encoding_probe.json"))


if __name__ == "__main__":
    main()
