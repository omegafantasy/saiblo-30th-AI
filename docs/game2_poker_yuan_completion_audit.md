# Game2 Poker/Yuan Completion Audit

Updated: 2026-05-10 UTC

## Objective Restated

Concrete success criteria for the active objective:

1. Analyze Poker and Yuan story structure deeply enough to identify plausible hidden evidence/stage gates.
2. Expand the information ceiling for the last two scripts rather than micro-tuning final-answer wording or score variance.
3. Keep local work independent from the other session and do not edit `n*` candidate directories.
4. Track the other session's newest `n*` candidates and room outputs, absorbing only genuinely new plot axes.
5. Keep local notes, generated summaries, and operational scripts synchronized with real evidence.
6. Upload/evaluate the new probes when the Saiblo API is usable, while avoiding blind upload loops.
7. Treat the goal as complete only after new probes are actually sampled and checked for `405/502/706+` or a higher Poker/Yuan stage.

## Prompt-To-Artifact Checklist

| Requirement | Evidence inspected | Status |
| --- | --- | --- |
| Analyze Poker late plot gates | `docs/game2_poker_yuan_story_notes.md`; raw `pzb/qbb/qbc/qbk` matches; generated unlock summaries showing `502/503/504/505/601-604/606` and still no Poker `405/605/607/608` | Covered locally |
| Analyze Yuan late plot gates | Old `705` samples, `qaz/qbb/qbc/qbj/qbl`, and `n606/n611/n619/n621` traces; generated transcript summary now shows `705x10`, `706x3`, `707x67`, `708x4`, with newer own `708` reopenings that did not improve score | Covered locally |
| Expand beyond score micro-tuning | Own probes `sk548e0910pzt` through `sk548e0910qbn` target distinct plot axes: post-`404/501`, Joker digital/payment, police dossier, hidden `705`, post-`706`, absent-voter/admin logs, suitcase/transport/DNA, half-name/source resolution, police authorization, post-`601-604` tattoo/final-dossier continuation, a narrow `502 -> 503/504/606` bridge, Yuan concrete-memory replay, and forced missing-lane complement tests | Covered and partially remotely verified |
| Keep independent from `n*` | Own namespace `Game2/deepclue_ai/sk548e0910pz*`; `n*` directories only inspected, not edited | Covered locally |
| Track other session | Latest inspected local candidates now include `n621a-c`; generated summary includes `n621a` as one valid `2797`/`707` sample and `n621b/c` at `0 valid`; watcher scans candidate dirs | Covered operationally |
| Absorb only useful new axes | `n596` suitcase/repair/transport/DNA axis was absorbed into `sk548e0910pzy`; `n597` half-name/external-source resolution was absorbed into `sk548e0910pzz`; later `n619-n621` outputs were tracked but did not justify copying code | Covered locally |
| Sync docs and generated summaries | `docs/game2_poker_yuan_story_notes.md`; `docs/generated/game2_story_unlocks.*`; `docs/generated/game2_late_probe_results.*`; this audit file | Covered |
| Avoid blind upload loops | `scripts/game2_poker_yuan_ceiling_queue.sh` health-checks `codes --entity-id 21493` before upload and skips labels with existing room dirs | Covered operationally |
| Periodic tracking and retry path | `scripts/game2_poker_yuan_watch_start.sh/status/stop.sh`; watcher running under `Game2/runtime/game2_poker_yuan_watch`, pid `424581` | Covered operationally |
| Actual upload/evaluation of new probes | API recovered; own `pzz`, `qaa-qbn`, and observed other-session rooms through `n621a` are now sampled; all own samples were evaluated through direct room eval without activation | Covered |
| Demonstrated new information ceiling | Own `pzz` reached Poker `502/503/504/601-604`; own `qbc` reached `501/502/505/601-604/606` at `2797`; own `qbk` reached `501/502/503/504/601-604/606` in the stronger structural lane; own `qbb/qbj/qbl` reached Yuan `708`; Yuan `706/707/708` are known reachable in the runtime corpus | Partially covered; still missing robust Yuan `706/708`, Yuan stage2, and Poker `405/605/607/608` |

## Current Evidence Snapshot

Latest inspected generated summaries:

- `docs/generated/game2_late_probe_results.md`: `qbc` now has six valid samples (`2757x4,2797x2`) and can separately show the `404/502/503/504` lane and the `501/505/601-604/606` lane. `qbj` has six valid samples (`2717x1,2757x3,2797x2`) and reopened Yuan `708` twice without a score break. `qbk` is the strongest own structural probe (`2757x1,2797x2`) with `501` and `601-604` in all samples and `502/503/504/606` in two samples. `qbm/qbn` failed as forced complement tests. `n621a` adds two `2797` samples with `707` but no new ceiling.
- `docs/generated/game2_late_story_transcripts.md`: regenerated over the latest room set. Exact late counts are Poker `502x47`, `503x40`, `504x41`, `505x22`, `601-604x31`, `606x18`, and `405/605/607/608=0`; Yuan `705x10`, `706x3`, `707x67`, `708x4`.
- `n619a/b/c`, `n620a/b/c`, and `n621a` confirm Yuan `707` is reproducible. `n620a` shows post-`606` final-answer attribution does not unlock `605/607/608` and can drop score to the `2557-2617` band.
- The active next target is not score micro-tuning: compare exact source/order differences between `n607a`'s `2837` run and qbk's `2797` runs, especially why qbk loses `404` while reaching `501/503/504/601-604/606`; for Yuan, reconstruct a robust source order that reproduces `706 -> 707 -> 708` without relying on the other thread's sampled paths.

## Completion Decision

Not complete.

The Poker information ceiling has moved materially (`502/503/504/505/601-604/606`), and Yuan `705/706/707/708` are now known reachable somewhere in the local runtime corpus. The newest probes clarify that Yuan `708` alone and simple Poker missing-lane complement questions are insufficient. The goal remains active because Yuan `706/708` are not robustly reproduced by the current own mixed path, Poker `405/605/607/608` remain unseen, no Yuan stage2 has been observed, and no durable higher score than the known `2797/2837` region has been validated.
