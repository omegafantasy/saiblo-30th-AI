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

- `docs/generated/game2_late_probe_results.md`: the strongest single own sample remains `qci` at `2837`, but `qci_more` has already produced `2757/2657/2557`, so `2837` is not a stable plateau. `qcd` remains the cleanest proof of Poker lane coexistence (`2757x2,2797x2`, all four rooms merge `404+501+502+503/504+601-604`, three reach `505/606`), but it is expensive (`264-306` records). `qcf` is unstable because its four-room distribution includes a `2557` low tail. `qcg/qch/qcj` are rejected branches. `qcl` is now rejected after `2717x2`.
- New macro probes are running through direct room eval only: `qcm` enables Poker post-`606`, `qcn` enables Yuan post-`708`, `qco` enables both, `qcp` front-loads Yuan `706`, `qcr` retargets post-`708` to the confessor named in evidence `708`, and `qcs` follows the newly observed verbal "`605` is a password; `607/608` are internal dossier/core roster" gate.
- Partial new-probe evidence: `qcn` reached `404/501/502/503/504/505/606+707/708` but only scored `2717` and opened no `709`; `qco` reached `606+708` at `2757` and opened no registered `605/607/608/709`, but its trace revealed the "`605` password / `607/608` internal dossier" clue now targeted by `qcs`; `qcp` first sample still missed `706` and went to `708`.
- `docs/generated/game2_late_story_transcripts.md`: regenerated over the latest room set. Exact late counts are Poker `502x47`, `503x40`, `504x41`, `505x22`, `601-604x31`, `606x18`, and `405/605/607/608=0`; Yuan `705x10`, `706x3`, `707x67`, `708x4`.
- `n619a/b/c`, `n620a/b/c`, and `n621a` confirm Yuan `707` is reproducible. `n620a` shows post-`606` final-answer attribution does not unlock `605/607/608` and can drop score to the `2557-2617` band.
- The active next target is not score micro-tuning: verify whether the trace-level `605` password / `607/608` dossier clue is actionable, and whether post-`708` must target the named confessor rather than generic official sources. For Yuan, `707 -> confession -> 708` still looks more promising than forcing `706`; the first `706`-first probe did not make `706` reliable.

## Completion Decision

Not complete.

The Poker/Yuan information ceiling has moved materially again: `qcd/qcf/qci` prove the previously split `404` and `501/601-604/606` lanes can coexist in one run, and `qci` reached the first own `2837` by pairing that state with Yuan `707/708`. The goal remains active because `2837` is not yet stable, Poker `405/605/607/608` remain unseen, Yuan `706/708` are still order-sensitive, and no Yuan stage2 has been observed.
