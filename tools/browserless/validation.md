# browserless — independent validation (Fable-role audit)

Auditor: independent, fresh context, adversarial default. Docker present (colima 6CPU/11.6GiB,
Docker 29.2.1), image `ghcr.io/browserless/chromium:latest` v2.55.0 digest `9e48bf8d…`.
All re-runs done in an **isolated copy** of `tests/` writing to a scratch `artifacts/` — the
pack's four canonical artifacts were confirmed **byte-pristine** afterward. Every container I
started was `docker rm -f`'d; no `bl_*` container or runner process survives; no wide `pkill`
used (parallel-worker fixtures untouched).

## Verdict: **PASS-WITH-FIXES**

Every headline measurement (H1–H5) reproduced independently on my own runs; the instruments are
real, not blind; the anti-hardcode, secret, and image-copy gates pass. **One factual defect** in
FINDING-02 requires correction: the "silently accepted, no error" claim is **wrong for
KEEP_ALIVE**, which the harness never tested and which actually emits a deprecation warning. This
does not invalidate any measurement, hence PASS-WITH-FIXES, not FAIL.

---

## Mandatory re-runs (my own execution, not the worker's)

### H2 — concurrency ceiling, dual truth — REPRODUCED EXACTLY
Fresh container per config, fired C+Q+4 session-holding `/slow?ms=5000` requests:

| (C,Q) | client 200 | client 429 | server `/pressure` peak (run/queue/reject) | ceiling==C+Q |
|---|---:|---:|---|:--:|
| (2,2) | 4 | 4 | 2 / 2 / 4 | ✅ |
| (3,5) | 8 | 4 | 3 / 5 / 4 | ✅ |
| (5,5) | 10 | 4 | 5 / 5 / 4 | ✅ |

Ceiling **moves** 4→8→10 with config. **Dual truth is genuine**: client 200/429 come from real
HTTP status codes; `/pressure` is polled by a *separate sampler thread* from the container's own
accounting — two independent sources, agreeing. No cross-config contamination (each config's
first `/pressure` sample reads running=0/rejected=0, so `recentlyRejected` does not bleed across
containers). Matches the pack's `concurrency.json` cell-for-cell.

### H4 — leak soak + detector calibration (highest-risk: blind instrument) — CONFIRMED NOT BLIND
30/30 sessions ok. **The `/proc` enumerator read 11 chrome procs mid-flight and 0 post-run**, with
the post-run comm map genuinely reduced to `{MainThread, Xvfb, dumb-init, sh, start.sh}` — i.e.
the *same* detector that counts to 11 during a live `/slow` nav counts to 0 after, with a
different process map. The "0 zombie / 0 chrome" reading is therefore a real measurement, **not a
blind zero**. Memory plateaued (my run 298→308 MiB, growth ~11 MB; artifact 294→303, ~9.5 MB) —
different absolute numbers across runs, same logarithmic-plateau shape → confirms non-hardcoded
and confirms "no linear per-session leak" over this window.

### H3 — endpoint fidelity + token gate — REPRODUCED BYTE-IDENTICAL
`/content` surfaced the runtime-injected marker (**811 B**), `/scrape` returned
`SCRAPE_TARGET_VALUE_CC`, `/screenshot` valid PNG (**18,621 B**), `/pdf` valid PDF (**40,974 B**) —
all identical to the artifact. **All four endpoints returned exactly HTTP 401 with no token**
(not 403; verified live). I also validated the premise directly: a static fetch of `/render`
(702 B) contains **neither** marker (both assembled from JS fragments), while it does contain the
static heading — so `/content` surfacing the marker genuinely proves real browser rendering, and a
static crawler would miss it (the katana cross-series contrast is well-founded).

### H1 startup / H5 TIMEOUT — REPRODUCED
H1: ready ~0.71 s, cold render ~0.27 s, warm ~0.14 s (artifact 0.78/0.32/0.15) — same magnitudes,
values shift run-to-run (non-hardcoded). PREBOOT arm within noise of default → independently
confirms PREBOOT is inert. Cold→warm gap (~0.13 s) matches sibling in-process launch magnitudes
(102–168 ms), supporting the **hypothesis-labeled** "amortizes launch, not faster" attribution;
the pack explicitly does not claim a faster/slower verdict. H5: under-timeout → 200 @ 2.38 s;
over-timeout → **408 @ 5.019 s** (budget 5.000; artifact 5.007). Boundary confirmed.

## PREBOOT / KEEP_ALIVE migration trap — PARTIALLY TRUE (this is the fix)

Direct probe of v2 with the removed v1 flags:

- **PREBOOT=true**: genuinely **silent** — zero mention in container logs, no deprecation/error;
  absent from `/config` (keys: concurrent, queued, timeout, token, maxCPU, maxMemory, retries, …);
  **0 idle chrome procs**. The pack's PREBOOT claim is **correct and verified**.
- **KEEP_ALIVE=true**: **NOT silent** — the container logs
  `Environment variable of "KEEP_ALIVE" is deprecated and ignored.` It IS accepted-and-ignored, but
  with an explicit operator-facing warning.

FINDING-02's title ("…**silently accepted, no error**"), its body ("accepts the unknown env var
without error … **not a warning**"), the README headline (lists PREBOOT/KEEP_ALIVE), and the
scorecard row all extend the *silent* framing to KEEP_ALIVE. That is factually wrong, and the
harness has **no KEEP_ALIVE arm** — so it is also an un-artifacted claim. Browserless is in fact
*more* honest than the pack credits (it warns on KEEP_ALIVE); only PREBOOT is a genuine silent
trap. Note the score direction is not inflated by this (if anything the "-2 operator trap"
rationale is overstated), but the evidence text must be corrected.

## Four漏网 categories

1. **Blind instrument (H4)** — CLEARED. Detector proven to count (11 mid-flight) then read 0
   post-run on my own run; calibration probe runs during a dedicated live nav before the soak.
2. **Attribution (H1 "amortizes, not faster" / ceiling dual-truth)** — CLEARED. Cold/warm split
   is explicitly a hypothesis (process-level, not CDP-trace); ceiling's two axes are independently
   sourced (client status vs server `/pressure`), not one source dressed as two.
3. **Self-contradictory winner / 92 over-credit** — MINOR CAVEAT. The 92 is evidence-anchored
   within a **pack-local, deployment-weighted** rubric and *does* dock for the costs (footprint
   2/4 for the 4.3 GB image + VM-mediated numbers; PREBOOT 4/6; recycling 13/14; memory 7/8). The
   full-mark dimensions (ceiling 16/16, queue obs 8/8, REST 12/12, auth 6/6, TIMEOUT 10/10) I
   independently reproduced and they genuinely earned it. The pack makes no cross-tool "browserless
   wins" sentence and its header explicitly says "not a cross-tool ranking." The only residual
   tension is Gate-11: a synthetic total exists under a weight template *different* from the
   feature-weighted siblings, so 92 must not be read as "series-highest = best tool." The
   disclaimer pre-empts this; acceptable, but dropping the synthetic total (or freezing one
   template) would be cleaner.
4. **Claims without artifact** — ONE HIT: the KEEP_ALIVE "silent" claim (above). Spot-checked
   others (byte sizes, 401s, ceiling, RSS trajectory, mid-flight 11) — all traced to a computed
   field and reproduced. "dumb-init as PID 1" is asserted from the image design, not from a
   PID-capturing scan (the comm scan shows dumb-init present, not that it is PID 1) — true and
   documented, low severity.

## Novelty (Gate 1) — SOUND
Mechanisms are correctly tagged **DOCUMENTED** (one-command deploy, C+Q→429, TOKEN, REST endpoints,
PREBOOT removal, observability); zombie risk **KNOWN-ISSUE** (#20/#228). EXCLUSIVE tags are scoped
to *quantification / same-fixture proof* (decomposed 3-stage startup, moving ceiling on dual truth,
located TIMEOUT boundary, calibrated leak trajectory, runtime-injected recall beside the static
miss) — not to the mechanisms' existence, and the pretest documents the negative SERP/doc search
behind them. This is the discipline v3 wants. Caveat: FINDING-02's EXCLUSIVE "silent-accept" clause
inherits the KEEP_ALIVE error above.

## Anti-hardcode (Gate 3) — PASS
All result fields computed from measured output (counts summed, medians via `statistics`, mem
parsed from `docker stats`, presence via `in`, magic via byte compare). Cross-run value drift
(startup latencies, memory 298 vs 294, kill 5.019 vs 5.007) confirms no frozen constants.

## Secret / abspath / image scan — CLEAN
No `/Users/richardli`, no `/var/folders` leak (only redaction-mechanism docs mention them). Token
literal `local-bench-token` lives only in `tests/bl_common.py`; `grep -c` = **0** in all four
artifacts (redaction works). No `sk-`/bearer/apikey shapes. **No file >1 MB** — the 4.3 GB image is
digest-referenced only; pack total **144 K**. Confirmed.

## Required fixes (must, before publish)
1. **FINDING-02 + README headline + scorecard row**: correct the "silently accepted, no error /
   not a warning" framing — it holds for **PREBOOT only**. **KEEP_ALIVE emits
   `deprecated and ignored`** (verified live). Either scope every "silent" statement to PREBOOT, or
   add the KEEP_ALIVE-warns nuance. Ideally add a KEEP_ALIVE arm to the harness so the claim is
   artifact-backed rather than asserted.

## Recommended (non-blocking)
2. Consider dropping the synthetic 92 total (or freezing the sibling weight template) per Gate 11,
   so a deployment-weighted pack-local score is not mistaken for a cross-series ranking.
3. Optionally soften FINDING-05's "dumb-init (PID 1)" to note it is documented image design, not a
   PID captured by the scan.

_Audited 2026-07-24. Re-ran H1–H5 + PREBOOT/KEEP_ALIVE probe with Docker; all containers removed;
pack artifacts left pristine; no headline/score edited by me._
