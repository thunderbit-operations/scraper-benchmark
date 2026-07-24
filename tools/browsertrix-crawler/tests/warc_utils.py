#!/usr/bin/env python3
"""Stdlib-only WARC / WACZ inspection for the Browsertrix evidence pack.

No third-party deps (no warcio): a `.warc.gz` is a sequence of concatenated
gzip members that `gzip` reads to one byte stream; each WARC record is a header
block terminated by CRLFCRLF followed by exactly `Content-Length` content bytes.
A `.wacz` is a plain ZIP containing the WARC(s) plus indexes (pages.jsonl, CDX,
datapackage). Everything here is read-only accounting so archive contents — not
browsertrix's own logs — are the source of truth for capture recall and cost.
"""

from __future__ import annotations

import gzip
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_CLEN = re.compile(rb"(?im)^Content-Length:\s*(\d+)\s*$")


@dataclass
class WarcRecord:
    warc_type: str
    target_uri: str
    content_len: int
    header_block: bytes
    content: bytes


def iter_warc_records(data: bytes):
    """Yield WarcRecord for a decompressed WARC byte stream."""
    i, n = 0, len(data)
    while i < n:
        start = data.find(b"WARC/", i)
        if start == -1:
            return
        hdr_end = data.find(b"\r\n\r\n", start)
        if hdr_end == -1:
            return
        header_block = data[start:hdr_end]
        m = _CLEN.search(header_block)
        clen = int(m.group(1)) if m else 0
        content_start = hdr_end + 4
        content = data[content_start:content_start + clen]
        # advance past content + the record's trailing CRLFCRLF
        i = content_start + clen
        while i < n and data[i:i + 2] == b"\r\n":
            i += 2
        htxt = header_block.decode("latin-1", "replace")
        wtype = _hdr(htxt, "WARC-Type")
        uri = _hdr(htxt, "WARC-Target-URI")
        yield WarcRecord(warc_type=wtype, target_uri=uri, content_len=clen,
                         header_block=header_block, content=content)


def _hdr(header_text: str, name: str) -> str:
    for line in header_text.split("\r\n"):
        if line.lower().startswith(name.lower() + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def read_warc_gz(path: Path) -> bytes:
    with gzip.open(path, "rb") as fh:
        return fh.read()


@dataclass
class ArchiveInventory:
    """Everything we can account for from the WARC/WACZ on disk."""
    warc_gz_files: list[str] = field(default_factory=list)
    warc_gz_bytes: int = 0
    wacz_bytes: int = 0
    record_type_counts: dict[str, int] = field(default_factory=dict)
    record_type_content_bytes: dict[str, int] = field(default_factory=dict)
    response_uris: list[str] = field(default_factory=list)   # WARC-Target-URI of response records
    response_paths: list[str] = field(default_factory=list)  # path component only
    response_bytes_total: int = 0                            # sum of response record content-length
    request_bytes_total: int = 0
    pages_count: int | None = None                           # from pages.jsonl if a WACZ
    wacz_entry_bytes: dict[str, int] = field(default_factory=dict)  # compressed size per WACZ member

    def to_dict(self) -> dict[str, Any]:
        return {
            "warc_gz_files": self.warc_gz_files,
            "warc_gz_bytes": self.warc_gz_bytes,
            "wacz_bytes": self.wacz_bytes,
            "record_type_counts": self.record_type_counts,
            "record_type_content_bytes": self.record_type_content_bytes,
            "response_record_count": len(self.response_uris),
            "response_paths_sorted": sorted(set(self.response_paths)),
            "response_bytes_total": self.response_bytes_total,
            "request_bytes_total": self.request_bytes_total,
            "pages_count": self.pages_count,
            "wacz_entry_bytes": self.wacz_entry_bytes,
        }


def _account_records(data: bytes, inv: ArchiveInventory) -> None:
    for rec in iter_warc_records(data):
        wt = rec.warc_type or "unknown"
        inv.record_type_counts[wt] = inv.record_type_counts.get(wt, 0) + 1
        inv.record_type_content_bytes[wt] = inv.record_type_content_bytes.get(wt, 0) + rec.content_len
        if wt == "response":
            inv.response_uris.append(rec.target_uri)
            if rec.target_uri:
                inv.response_paths.append(urlparse(rec.target_uri).path)
            inv.response_bytes_total += rec.content_len
        elif wt == "request":
            inv.request_bytes_total += rec.content_len


def inventory_from_warcs(warc_paths: list[Path]) -> ArchiveInventory:
    inv = ArchiveInventory()
    for p in sorted(warc_paths):
        inv.warc_gz_files.append(p.name)
        inv.warc_gz_bytes += p.stat().st_size
        _account_records(read_warc_gz(p), inv)
    return inv


def inventory_from_wacz(wacz_path: Path) -> ArchiveInventory:
    """Account for a WACZ: its own on-disk size, the WARC record composition of
    its embedded archive/*.warc.gz, page count from pages/*.jsonl, and the
    compressed size of every member (so index/overhead is visible)."""
    inv = ArchiveInventory()
    inv.wacz_bytes = wacz_path.stat().st_size
    with zipfile.ZipFile(wacz_path) as zf:
        pages = 0
        for zi in zf.infolist():
            inv.wacz_entry_bytes[zi.filename] = zi.compress_size
            name = zi.filename
            if name.startswith("archive/") and name.endswith(".warc.gz"):
                inv.warc_gz_files.append(name)
                inv.warc_gz_bytes += zi.compress_size
                raw = zf.read(name)
                _account_records(gzip.decompress(raw), inv)
            elif name.startswith("pages/") and name.endswith(".jsonl"):
                text = zf.read(name).decode("utf-8", "replace")
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # pages.jsonl first line is a header {"format":...}; data lines have "url"
                    if isinstance(obj, dict) and "url" in obj:
                        pages += 1
        inv.pages_count = pages
    return inv


def redact(obj: Any, home: str, tmp_prefixes: tuple[str, ...]) -> Any:
    """Fold $HOME -> ~ and $TMPDIR / /var/folders -> <TMP> so committed
    artifacts carry no absolute local path (durable fix per the selenium pack)."""
    if isinstance(obj, str):
        s = obj
        for pref in tmp_prefixes:
            if pref and pref in s:
                s = s.replace(pref, "<TMP>")
        if home and home in s:
            s = s.replace(home, "~")
        return s
    if isinstance(obj, list):
        return [redact(x, home, tmp_prefixes) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v, home, tmp_prefixes) for k, v in obj.items()}
    return obj
