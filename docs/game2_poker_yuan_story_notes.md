# Game2 Poker/Yuan Story Notes

Updated: 2026-05-10 UTC

## Objective

Expand the information ceiling for the two late scripts, Poker and Yuan, without blindly chasing small score variance. Keep the useful findings independent from the `n*` session while still watching its results.

## Active Completion Audit

Concrete success criteria for this objective:

- Broaden Poker/Yuan information ceiling, not just final-answer wording.
- Keep independent own variants outside the `n*` namespace.
- Track the other session and absorb only validated or genuinely new plot axes.
- Keep local docs synchronized with trace evidence and decisions.
- Upload and evaluate new probes when the Saiblo API is usable.

Current evidence against those criteria:

- Analysis done: regenerated summaries now show Poker `502/503/504/505/601-604/606` and Yuan `705/706/707/708` are all reachable somewhere in the local runtime corpus. The current missing Poker evidence remains `405/605/607/608`; the current Yuan gap is the inability to robustly reproduce `706 -> 707 -> 708` or open Yuan stage2.
- Own variants prepared and sampled through `sk548e0910qbn`. `qbb` is the best mixed Yuan-memory sample (`708` once, `2777` avg); `qbc` is the best own normal-score Poker continuation sample because one run reached `501/502/505/601-604/606` while both runs retained Yuan `707`; `qbj/qbl` show `708` can be reopened without improving score; `qbk` is the best own structural probe because it can hit both late Poker lanes across different rooms, but still does not beat the known ceiling.
- Other session tracked through `n621a-c`; `n621a` has one valid `2797` sample with Yuan `707` but no new ceiling. No `n*` candidate code has been edited or depended on.
- Docs/tooling synchronized: `docs/generated/game2_late_probe_results.md` includes `n618-n621` and own labels through `qbc`; `docs/generated/game2_late_story_transcripts.md` and `docs/generated/game2_story_unlocks.md` were regenerated over `4159` analysis files.
- Unmet gate: no activation. The objective remains active because Poker `605/607/608` are still unseen, Poker `405` remains unconfirmed as Poker evidence, Yuan `706/708` are not robust in the current own path, and no Yuan stage2 has been observed.

## Current Evidence

| sample | score | records | Yuan start | Yuan evidence | takeaway |
| --- | ---: | ---: | ---: | --- | --- |
| `sk548e0910pyh_w1` match `8136433` | 2757 | 119 | 112 | `001` | Stable baseline. Poker gets stage3 but spends too much budget before Yuan. |
| `n558d` match `8138313` | 2797 | 120 | 103 | `001,703,704` | Good ceiling sample. Poker is short; Yuan gets phone and vote sheet. |
| `n559a_more` match `8138303` | 2797 | 120 | 103 | `001,703,704` | Same ceiling pattern as `n558d`, but later expanded sample has low tail. |
| `sk548e0910pyk` match `8138536` | 2517 | 132 | 112 | `001,703,704` | Overlong variant. It gets Yuan evidence but loses budget/score. |
| `n560e` match `8138676` | 2757 | 120 | 103 | `001,703,704` | Short Poker plus Yuan expansion, but current sample only averages 2743.667. |
| `sk548e0910pyo` room `20260509_163548` | avg 2730.333 | 121-ish | 103 | `001,703,704` | Dynamic Yuan suspect parsing works structurally but does not beat `pyh`. |
| `sk548e0910pyq` match `8139121` | 2757 | 121 | 103 | `001,703,704,705` | Confirms Yuan can occasionally expose `705` 李海天尸检报告, but still remains stage1. |
| `sk548e0910pys` match `8139298` | 2757 | 125 | 107 | `001,703,704` | Poker monitor probe exposes `401/402`; no Poker stage4 and no score lift. |
| `sk548e0910pyt` room `20260509_171635` | avg 2757 | 124 | 103 | `001,703,704` | Role-targeted Yuan followup after `703/704` did not unlock `705/706` in 2 rooms. |
| `sk548e0910pzb` room `20260509_180435` | avg 2797 | 125 | 117 | `001,703,704` | Current Poker breakthrough. After `401/402`, timeline plus password chain unlocked `404` in one room and `501` in one room. |
| `sk548e0910qbb` room `20260510_025548` | avg 2777 | - | - | `001,703,704,707,708` | Best mixed Yuan-memory sample: both runs reached Poker `502`, one reached Yuan `708`; no `606`. |
| `sk548e0910qbc` room `20260510_031353` | avg 2777 | - | - | `001,703,704,707` | Best own normal-score Poker continuation sample: one run reached `501/502/505/601-604/606`; both runs reached Yuan `707`; no `708`. |
| `sk548e0910qbj` rooms through `20260510_050613` | avg 2763.7 | - | - | `001,703,704,707,708` | Yuan concrete-fact branch; reached `708` twice and late Poker in two rooms, but no score above `2797`. |
| `sk548e0910qbk` room `20260510_051023` | avg 2783.7 | - | - | `001,703,704,707` | Best structural own probe so far: reached `501/502/503/504/601-604` in 2/3 rooms and `606` in 2/3, but still maxed at `2797`. |
| `sk548e0910qbl` room `20260510_051023` | avg 2757 | - | - | `001,703,704,707,708` | Companion Yuan concrete branch; reopened `708` once, no score gain. |
| `sk548e0910qbm` room `20260510_052329` | avg 2737 | - | - | `001,703,704,707` | First forced complement branch for missing `404`/`501`; did not open new late evidence. |
| `sk548e0910qbn` room `20260510_052329` | avg 2757 | - | - | `001,703,704,707` | Yuan companion to qbm; stayed in the old score/evidence band. |
| `n621a` match `8144352` | 2797 | - | - | `001,703,704,707` | Other-session sample after `n620`; no new late ceiling beyond repeated Yuan `707`. |

## Poker Plot

Reliable information chain:

- The death scene is Poker Mansion: a male corpse in the cloakroom, wearing the Club 5 mask, with three knives through the back.
- The mask rule creates identity confusion. The victim is tied to Joker and Lin Yuzhi.
- The reception NPC can produce Joker chat records, invitation/address/table records, and the arrival mapping.
- The important physical chain is computer search about freezing knife handles, a square plastic box by the freezer, and three missing kitchen knives.
- The useful trigger set is short: ask the information source twice, ask the reception NPC for Joker records/timetable, then ask the reception NPC for the computer/plastic-box/missing-knife abnormalities.
- The current observable upper evidence set is `101,102,103,104,201,202,203,204,205,401,402,404,501,502,503,504,505,601,602,603,604,606`. `401` is the 11:00-13:00 restaurant camera: one guest eats at 11:50, Club 5 appears 12:00-12:05, the reception/cleaning role enters 12:10-12:30. `402` is the gate camera: 7:30 unknown person arrives with Joker, 8:20 unknown person leaves, 8:50 Club 5 arrives. `405/605/607/608` remain unseen as Poker evidence.
- The post-monitor chain is real: identify the 7:30/12:00 Club 5 as the true living Club 5/Lin Yuzhi, identify the cloakroom victim as Joker, then satisfy the password/timeline gate. The NPC may reveal password `0512` or name a password holder. The cloakroom flaw is blood distribution, body position, and a mask forced on after death.
- `404` is vehicle evidence: license plate `京F·A7590`, matching the 7:20 gate vehicle. `501` is a large transfer record: the consultation recipient received `500000` anonymously within three days after a medical visit. `502` is the dead phone's Club 5/Joker chat; `503` is the dead person's special invitation; `504` is the `LYZ` item; `505` is the Huawen Village arrest/material branch; `601-604` are the old missing-girl, trafficking, surgery-accident, and Zhang Zihan identity materials; `606` is the three-person photo / left-arm `POKER` tattoo proof. These are not guaranteed in the same room.
- A useful `501` clue from `sk548e0910pza` match `8140201`: one reply says the doctor/`王泽` is not Lin Yuzhi, only a used doctor; Lin Yuzhi is the true living Club 5 under another current identity. `qbc` match `8144251` adds that a narrow `502` bridge can reach `505/606` at normal score, but still does not reveal `605/607/608`.
- `qbk` and `qbm` clarify the remaining structural issue: one room can reach the `404/502/503/504` lane and another can reach `501/505/601-604/606`; forcing a simple complementary follow-up for the missing side did not merge them into a higher-scoring or stage-advancing run.

Risk:

- Hard-coding the Poker murderer as Lin Yuzhi is bad. `n560a` fell to `2517/2557` territory. Keep the existing dynamic suspect mapping and only improve method wording if needed.
- Extra Poker summary questions after stage3 consume the budget that Yuan needs. `sk548e0910pys` can unlock `401/402`, but still stays at stage3 and one sample fell to 2617 because the stage2 identity trigger failed. The better pattern is the `pzb` chain: monitor -> true Club 5/Joker identity -> password/timeline -> `404` or `501`.

## Yuan Plot

Reliable information chain:

- The competitor resembles Yuan Yingtong and competes with her for the teacher's abroad quota.
- Yuan repeatedly says to wait until Friday, implying she plans to reveal something.
- The competitor finds/holds Yuan's phone. The phone has been mostly cleared but keeps a 1am dark photo of a female corpse in lolita dress with a chestnut wig.
- The yellow suitcase is a repair/misdirection object tied to the competitor.
- The teacher's vote sheet is abnormal: 49 total students, presenters excluded, one-vote win, and at least one tally with different handwriting.
- A third student can supply broader scene links: 1919 black car, guard watching a strange website, someone fleeing the biology building, and Century Woods body parts.
- `705` is real but rare: 李海天尸检报告. It says Li Haitian died from back stabbing and massive blood loss, had severed limbs, and a blue-backpack dolphin pendant was left near the body. This connects the Yuan case to the older Li Haitian case, but observed `705` samples still remain Yuan stage1.
- `706` is the Li Haitian U-disk branch: it contains the electronics-department recommendation list plus abuse videos/photos involving Yuan and other girls. It has appeared in `n606a`, `n611a`, and own `qaz`, but not robustly in the newest mixed path.
- `707` is Wang Ze's contact method, usable for the Zhang Zihan information exchange around the "athletic girl" and killer secret. It is reproducible in both `qbb` and `qbc`, but often stalls when the next question is phrased as an abstract exchange.
- `708` is the recovered-memory clue: after a confession, the player remembers a murder-for-hire email, a bloody bathtub, and gloved hands with a knife. It has appeared in own `qar/qas/qba/qbb`, but `qbc` did not reproduce it.

What seems to matter:

- Unlocking or at least surfacing `703` (Yuan phone) and `704` (vote sheet).
- Unlocking `705` appears to require early exposure of the biology-building witness / Li Haitian context, but `705` alone has not produced stage2.
- `707` can be reached without `706`, so the Yuan chain is probably order/source-sensitive rather than a simple numerical sequence. The next useful work is reconstructing the concrete source order that reproduces `706 -> 707 -> 708`, not asking every visible NPC to explain "708".
- Asking all visible Yuan NPCs one broad line, then one "personally confirmed facts" line, then using `703/704` for a final evidence-chain question.
- Keeping total Yuan work near the 17-record range seen in `2797` samples.

Risk:

- Asking one extra preface plus four all-NPC sweeps is too expensive when Poker has already used the longer `pyh` route. `sk548e0910pyk` reached 132 records and dropped to 2517/2557.
- A fixed final murderer in Yuan is not proven. The current data suggests answer text is less important than information exposure, but this is not fully isolated.

## Earlier Variant Shape

This section is historical context for why the current `q*` probes exist. The active candidate decision is below.

Use an own namespace, not `n*`:

- `sk548e0910pym`: short Poker, Yuan expansion, concrete Yuan final answer.
- `sk548e0910pyn`: same short Poker and Yuan expansion, neutral `无名氏` final answer.
- `sk548e0910pyo`: same short Poker and Yuan expansion, but parses the Yuan winner dynamically from replies such as "24比23险胜", "一票之差", "获利者显然是", or a non-teacher NPC saying they just beat Yuan Yingtong. Tested 3 rooms: `2717,2717,2757`; not a keeper, but it confirms the dynamic answer does not collapse the run.
- `sk548e0910pys`: `pyq` plus a compact Poker monitor request. Tested 2 rooms: `2617,2757`. It can unlock `401/402`, but does not exceed Poker stage3.
- `sk548e0910pyt`: `pyq` with Yuan role-targeted questions after `703/704` around Li Haitian, dolphin pendant, biology building, and the hidden evidence source. Tested 2 rooms: `2757,2757`; no `705/706` in those samples and no Yuan stage2.

Do not expand `pyo` unless a new trace shows that Yuan final answer text is being scored separately. Current evidence says the ceiling is controlled more by record budget and evidence exposure than by final Yuan name wording.

Next useful direction: if probing continues, do not add more all-NPC sweeps. Use a conditional path: after the first two Yuan sweeps, if `705` appears, spend only two or three questions on the witness/teacher about the blue backpack dolphin pendant, the exact biology-building runner, and who holds school/police records. If `705` does not appear, avoid spending more budget on Li Haitian.

Poker follow-up now has priority over Yuan: test one conditional follow-up after `404` about the 7:20 car, driver, actual murder location, body movement, and vehicle records; test one conditional follow-up after `501` about the anonymous transfer, medical record, Joker, and Lin Yuzhi/human trafficking link. Do not add broad chatter before Yuan unless it opens `405/502` or stage4.

## Current Candidate Decision

- `sk548e0910qbb`: keep as the current mixed-path reference for preserving Yuan `708`. It scored `2757/2797`, reached `502` in both samples, and reached `708` once.
- `sk548e0910qbc`: keep as a useful plot-ceiling probe, not as an activation candidate. Across six valid rooms it scored `2757x4,2797x2`; match `8144078` reached `404/502/503/504 + 707`, match `8144251` reached `501/502/505/601-604/606 + 707`, and one later sample reopened `708`. It is still better evidence for the `606` bridge than for a robust Yuan memory path.
- `sk548e0910qbj`: keep only as evidence that Yuan `708` can be reopened from a concrete-fact branch. Six samples produced `2717x1,2757x3,2797x2`; `708` appeared twice, but the branch did not exceed `2797`.
- `sk548e0910qbk`: current best own structural Poker probe. Three samples produced `2757x1,2797x2`, with `501` in all rooms, `502/503/504` in two rooms, `601-604` in all rooms, and `606` in two rooms. It still failed to merge the `404` lane with the `501/606` lane into a `2837+` run, so do not treat it as the stable candidate yet.
- `sk548e0910qbl`: qbj plus the qbk bridge. It reopened Yuan `708` once but stayed at `2757x3`, so it is not a keeper except as confirmation that `708` alone is not the missing score jump.
- `sk548e0910qbm` / `sk548e0910qbn`: reject as candidate bases. The forced missing-`404/501` complement wording did not add new late evidence and only produced `2717/2757` or flat `2757`.
- `n621a`: tracked as other-session output only. It scored `2797` with `401/402/703/704/707`, but adds no new plot axis.

## Active Ceiling Hypotheses

Keep future probes on distinct plot axes instead of changing wording inside the same axis:

- Poker vehicle/body-move axis: `404` license plate plus `402` gate monitor plus `104` rear parking/window should lead to actual murder site, body transfer route, trunk/blood/tire/drive-record proof, or Poker `405`.
- Poker doctor/transfer axis: `501` likely points to Wang Ze / Yu Shuhua as a used doctor, anonymous 500000 transfer, daughter-location leverage, medical registration, extortion chat, transfer-source account, and possibly Poker/Yuan `502`.
- Poker true-Club-5 holder axis: once replies reveal the current identity of living Lin Yuzhi / true Club 5, ask that NPC directly instead of only asking the information source or evidence-name holder.
- Poker police-dossier axis: if the information holder reveals the criminal-police identity "景观", the next source may be an official police dossier rather than a suspect-held clue: Lin Yuzhi disappearance, Joker trafficking, vehicle high-resolution surveillance, DNA/fingerprint ID, bank flow, and Yu Shuhua records.
- Yuan security/guard axis: `705` plus repeated guard/strange-site/Sunday-absence/Senlin/Biology-building clues point toward security-room screenshots, patrol logs, school surveillance, or police/guard official files as possible `706`.
- Yuan biology-runner axis: the runner seen leaving the biology building may be the direct holder for the Li Haitian/Yuan bridge; ask only after the runner is parsed or after `705`.
- Cross-script trafficking axis: if Poker exposes `501`, Yuan may need a cross-case question connecting Joker, human trafficking, Yu Shuhua transfer, Li Haitian, Yuan Yingtong, 1919 black car, biology building, and the guard website.
- Identity/DNA/source-body axis: both scripts stall on identity ambiguity. Poker may need Joker-vs-Lin identity proof; Yuan may need corpse-source/DNA/phone-original-metadata proof for Yuan, the 1am photo, Li Haitian, and Century Woods body parts.

Prepared probes:

- `sk548e0910pzd`: broad `404/501` conditional follow-up after `pzb`.
- `sk548e0910pze` / `sk548e0910pzg`: stronger `501` wording around daughter leverage and the population-trafficking link.
- `sk548e0910pzh`: shorter `404/501` follow-up: car/window/backyard/boot logs for `404`, used-doctor/medical-record/transfer-source for `501`. Prefer this first when upload works again.
- `sk548e0910pzi`: `pzh` plus a Yuan-only conditional branch. If `705` appears, ask the report holder about the blue-backpack dolphin pendant, Li Haitian vs Yuan Yingtong similarity/difference, biology-building runner, Century Woods body parts, and the next official evidence. This does not spend budget unless `705` is already visible.
- `sk548e0910pzj`: stage-ceiling variant based on `pzi`. It spends extra conditional budget only after high-value gates: after Poker `404`, it asks the information holder for the exact murder site, body route, car blood/trunk/tire/drive-record proof; after Poker `501`, it asks for the medical record, extortion chat, daughter-location leverage, transfer-source account, and Lin Yuzhi disappearance closure. After Yuan `705`, it asks both the report holder and the observed biology-building runner for the blue-backpack/dolphin-pendant link and next official evidence.
- `sk548e0910pzk`: `pzj` plus a Yuan `705` follow-up to the parsed guard/security-room lead. This uses the repeated local reply pattern that official follow-up evidence is likely in school security/police custody: the guard's strange website, Sunday absence, Century Woods body parts, 1919 car, and biology-building surveillance. It only spends this extra question after `705` is already visible and `706` has not appeared.
- `sk548e0910pzl`: `pzk` plus a more structural Poker ceiling probe. It parses the revealed current identity of the true living Club 5 / Lin Yuzhi from replies such as "现在的叶青衡就是她" or "楚戎臻就是她", then asks that person directly after `404` or `501` if `405/502` still has not appeared. Yuan also gets one conditional all-NPC "which next evidence opens the next stage" question after `705` if `706` is still missing.
- `sk548e0910pzm`: `pzl` plus a more aggressive Yuan pre-`705` probe. If the first two Yuan sweeps do not expose `705`, it targets the parsed biology-building runner, parsed guard, and one false-marked role for the official physical evidence bucket: Li Haitian autopsy report, dolphin pendant, corpse-block DNA, 1919 car record, or biology-building surveillance. This is deliberately higher budget and should be judged on whether it raises the stage/evidence ceiling, not just average score.
- `sk548e0910pzn`: `pzm` plus a cross-script stage-ceiling probe. If the Poker case exposed `501`, it records that fact and asks Yuan NPCs whether Yuan Yingtong, Li Haitian, the 1919 car, biology building, guard website, Joker, human trafficking, and the anonymous transfer belong to the same hidden chain. This is conditional on `501` so it should only spend budget in runs already touching the late Poker branch.
- `sk548e0910pzo`: `pzn` plus an identity/DNA axis. Local traces include a reply that the Poker identity chain still needs DNA comparison or a more direct physical identifier; Yuan traces repeatedly stall on actual corpse identity, the 1am photo, Century Woods body parts, Li Haitian, and possible stand-in/body reuse. This variant asks for Poker identity/DNA/face-mask/records proof after `404/501`, and asks Yuan for DNA/source-body/metadata/surveillance proof after `705` or a prior Poker `501`.
- `sk548e0910pzp`: `pzo` plus a police-dossier source probe. In the `404` branch the information holder can reveal he is a criminal police captain codenamed "景观"; this variant asks him, only after that reveal, for the official police file covering Lin Yuzhi disappearance, Joker human trafficking, vehicle high-resolution surveillance, DNA/fingerprint ID, bank flow, and Yu Shuhua medical records.
- `sk548e0910pzq`: `pzp` plus a Yuan security/webpage branch. It parses the likely guard from replies, follows the opening "amnesia + blurred webpage screenshot" clue, and asks for guard website screenshots, login/visit records, 1919 vehicle records, Century Woods reports, and school/security records. Poker also directly restates the full monitor/password/timeline and asks the police-dossier holder for vehicle, transfer, DNA/fingerprint, medical and bank-flow evidence.
- `sk548e0910pzr`: stage-ceiling variant after observing the other session's `n584/n585/n586` directions. It keeps `pzq`'s targeted holder logic but explicitly names hidden Poker `405/502` after the `404/501` gate, expands Yuan submitted evidence IDs to `706/707/708`, and asks the guard, biology-building runner, and `705` report holder for "物证06/706" or later official evidence. It also fixes the `501` branch to parse the transfer recipient from evidence content such as "王泽（于书华）" instead of only from the generic evidence name. This is intentionally higher-budget and should be evaluated for new evidence/stage, not average score.
- `sk548e0910pzs`: `pzr` plus three distinct ceiling axes from the latest local trace review: after late Poker gates it asks the reception/space holder for space-permission, door/password usage, kitchen/freezer/knife/toolmark, hidden-room, and victim-phone evidence if `405/502` still did not appear; in Yuan it targets the likely competitor with `703` phone digital forensics (EXIF, deletion, location, last operation, login) and the parsed teacher with `704` original-ballot custody (ballot box, original votes, handwriting, classroom/office video, admin logs). This is more exploratory than `pzr`.
- `sk548e0910pzt`: `pzs` plus the newest useful `n591/n592` plot axes, without editing any `n*` code. Poker now adds a late conditional Joker digital/payment chain after `404/501` if `405/502` still does not appear: account real-name, login IP, device fingerprint, payment account, reception deposit/promise, invitation/address-table source, shipping records, and mask distribution. Yuan now strengthens the lost-detective/webpage branch by asking why the guard knows the detective and where the detective identity file is, and adds an official abroad-quota administration branch around recommendation forms, system logs, list changes, signatures, office mail/monitoring, and the record Yuan planned to expose. Locally compiled on 2026-05-10; not uploaded because the Saiblo code endpoint is still unresponsive.
- `sk548e0910pzu`: `pzt` plus the useful `n593` fanout, still in the own namespace. It adds a higher-budget Poker late-stage fanout to password holder and true Club 5/Lin Yuzhi after the reception/info digital chain if `405/502` remains hidden, asking for password-use records, hidden room/death-site route, Joker phone, population-trafficking list, Yu Shuhua daughter leverage, and police dossier links. It also broadens the Yuan cross-case trigger from only `501` to `404` or `501`, so a run that exposes the vehicle branch can immediately ask whether Yuan, Li Haitian, the 1919 car, biology building, guard website, Joker, trafficking, and transfer chain share one official evidence source.
- `sk548e0910pzv`: `pzu` plus an explicit hidden-holder probe for Yuan `705`. Old `705` samples show the report holder named in the evidence content is often not one of the current visible three NPCs, so visible-only targeting may never reach the true holder. `pzv` first tries the visible NPC list and then falls back to the global Chinese-name map for the `705` holder, biology-building runner, and guard before asking for `706`/next official evidence. This may spend calls on an invalid/invisible target if the engine rejects it, so evaluate it as an aggressive ceiling probe rather than a keeper candidate.
- `sk548e0910pzw`: `pzv` plus a deeper late-stage continuation probe, created after the 2026-05-10 reminder to stop micro-tuning and expand the last two scripts' plot/stage ceiling. Poker now escalates after `404` to the likely vehicle-chain holder `罗方琛`, after `501` to `王泽/于书华`, and if `405` or `502` appears it continues asking for the next official/final-stage evidence rather than stopping. Yuan now performs a limited hidden-source fanout after `705` to likely old-case names (`张子韩`, `陆亦初`, `楚戎臻`, `王泽`, `张壹`) and, if `706` appears, immediately asks for `707/708` through DNA, phone metadata, security webpage backend, 1919 vehicle registration, biology/Senlin surveillance, vote originals, and Li Haitian dossier. After raw logs showed invalid hidden NPC chats can waste retries, `pzw` uses one-shot probes for non-visible hidden targets and normal chat for visible NPCs. Compiled locally; not uploaded because the Saiblo code endpoint still times out.
- `sk548e0910pzx`: `pzw` plus a distinct Yuan vote-administration ceiling branch from raw `pzb`/old-`705` trace review. Multiple Yuan replies mention an absent or confused voter (`张壹`/`张朔`), 46 actual attendees versus 47 votes, and a forged extra ballot. `pzx` parses the absent-voter name and asks that person, or the teacher if no name is parsed, for attendance sheets, classroom monitoring, voter list, replacement/invalid ballot originals, recommendation-system logs, identity confusion, and `706/707/708`. This is not final-answer tuning; it tests whether the next Yuan stage is hidden behind the official vote/admin record rather than the Li Haitian branch.
- `sk548e0910pzy`: `pzx` plus the only genuinely new useful `n596` plot axis not already covered by `pzw/pzx`: the yellow suitcase as a尸源/转运 evidence chain. It targets the likely phone/suitcase holder and one fallback suspect for suitcase purchase/borrowing, repair-shop records, dorm monitoring, blood/fingerprint/fiber traces inside the suitcase, lo-dress/chestnut-wig photo source, 1919 black-car transport route, and `706/707/708`. This absorbs the `n596f` body-luggage-DNA idea without copying the `n*` namespace or replacing our broader cross-case branches.
- `sk548e0910pzz`: `pzy` plus the useful part of `n597`: generic Chinese entity extraction and half-name/external-name resolution. It does not copy the broad all-global sweep. Poker now uses parsed story names after `404/501` only if `405/502` remains hidden; Yuan resolves `705` report holders, guard names, biology-building runners, and externally named old-case sources through both visible and hidden NPC ids before asking for `706/707/708`. While creating it, the `pzy` runtime bug around uninitialized `current_npcs/false_ids` in the suitcase branch was fixed.

Upload/eval status: `sk548e0910pzc` compiled but produced no valid room because Saiblo room/match requests timed out. Uploads for `pzd/pzg/pzj` were blocked by Saiblo `/profile/` and `/entities/` timeouts, so the local upload tools now support explicit username and configurable API timeout. Retry when API recovers.

2026-05-10 upload follow-up: new probes `pzl/pzm/pzn/pzo/pzp` could not be evaluated yet because Saiblo timed out both on `/api/users/thebeginning/games/53/entities/` and on direct existing-entity code upload `/api/entities/21493/codes/`. Local tooling now also supports `SAIBLO_SKIP_ENTITY_LIST` and `--skip-entity-list` to bypass profile/entity listing where possible; the remaining blocker is the code upload endpoint itself. A bounded background retry attempted the latest viable probe via existing entity `21493` and exhausted six attempts; the final attempt used the fixed `SAIBLO_API_TIMEOUT=120` path and still timed out on `/api/entities/21493/codes/`.

2026-05-10 upload follow-up: direct upload of `sk548e0910pzq` with `SAIBLO_API_TIMEOUT=180`, explicit `--username thebeginning`, and `--skip-entity-list` also timed out on `/api/entities/21493/codes/`. This confirms the current blocker is the code upload endpoint, not profile/entity listing or local compile. `sk548e0910pzr` and `sk548e0910pzs` are prepared and locally compiled, but should not be blindly retried until the upload endpoint recovers or a different entity/upload route is available.

2026-05-10 API health check: even the lighter `codes --entity-id 21493` call with `SAIBLO_API_TIMEOUT=25` timed out on `/api/entities/21493/codes/`. Do not start another upload loop until this endpoint responds.

2026-05-10 API recheck: `timeout 35s env SAIBLO_API_TIMEOUT=25 python3 saiblo_tools.py codes --entity-id 21493` still exited with code `124` and no API payload. Upload/eval remains blocked by the endpoint, not by local compile or profile/entity listing.

2026-05-10 later API recheck: `timeout 30s env SAIBLO_API_TIMEOUT=20 python3 saiblo_tools.py codes --entity-id 21493` also exited with code `124`. Keep uploads paused; the next useful upload order when the endpoint responds is `pzt` for balanced late-stage breadth, then `pzu`/`pzv`, then `pzw` for post-`405/502/706` continuation, then `pzx` for the distinct Yuan absent-voter/admin-log branch, then `pzy` for the suitcase/transport/DNA branch, then `pzz` for half-name/source-resolution coverage.

2026-05-10 queue tooling: added `scripts/game2_poker_yuan_ceiling_queue.sh`. It first health-checks `codes --entity-id 21493`; only if that responds does it upload/evaluate `sk548e0910pzt sk548e0910pzu sk548e0910pzv sk548e0910pzw sk548e0910pzx sk548e0910pzy sk548e0910pzz` through the known entity id with explicit username and skip-entity-list. A 5-second health-check smoke test exited cleanly with code `75` and no upload while the endpoint was down, so this gives a ready upload path without starting another blind retry loop.

2026-05-10 tool follow-up: `Game2/tools/run_room_eval.py` now accepts `--username` and `--entity-id` and propagates `--request-timeout` through `SAIBLO_API_TIMEOUT`, so future entity-name room probes can skip `/api/profile/` and entity listing when the known entity id is available. This does not bypass the currently failing `/api/entities/21493/codes/` endpoint, but removes one avoidable blocker once it responds.

2026-05-10 follow-up: raw `match_download.json` contains many `405` ids, but those are Rose-case `visible_testimony` entries like "早来遇见某人", not Poker evidence. At that checkpoint the decoded evidence scan had not yet found Poker `502` or Yuan `706`. Later `pzz/qbb/qbc/qaz` runs superseded that part of the finding, but Poker `405` remains unconfirmed.

2026-05-10 trace audit of the two `pzb` 2797 rooms: neither room spent any question after unlocking `404` or `501`; both immediately entered Yuan. That means the post-gate branches in `pzt/pzu` are not micro-tuning already-failed wording, but first real probes beyond the observed ceiling. In match `8140211`, the information holder revealed "景观", true Club 5/Lin Yuzhi as Ye Qingheng, then `404` (`京F·A7590`); the Yuan witness then named guard Jiang and runner Wang Ze. In match `8140236`, true Club 5/Lin Yuzhi was Chu Rongzhen, the password holder was Xu Qinghe, then `501` named `王泽（于书华）`; the Yuan witness named guard Gu and runner Lu Yichu, while the teacher's vote reply mentioned an absent Zhang Yi/count contradiction. These support the current axes: police dossier, password holder, true Club 5, car/transfer holder, guard-webpage, runner, and official vote-administration records.

2026-05-10 trace audit of old `705` samples: observed rooms that unlocked Li Haitian's autopsy report still did not perform a true `705` follow-up; they generally asked broad final-summary questions after the evidence appeared. The `705` content repeatedly names a report source such as Zhang Zihan, Lu Yichu, Chu Rongzhen, or Wang Ze, but that holder can be outside the currently visible Yuan NPC list. This supports testing a hidden-holder direct question (`pzv`) and not only visible false-NPC sweeps.

Monitoring note: the other session's newest local code has advanced into `n595`, but there are still no matching `room_matches` directories for `n591+`. Useful `n591/n592` ideas were absorbed into `pzt`; useful `n593` fanout/cross-case ideas were absorbed into `pzu`; the `n594` all-visible-NPC stage4 fanout and Yuan 703-708 BFS mostly overlap with `pzu/pzv` while spending much more budget; `n595` mostly changes final-answer attribution rather than opening new evidence. Do not create another own copy unless a real room validates one of those directions. Continue watching for real room outputs before treating any `n*` label as validated. Do not edit or depend on the `n*` directories.

2026-05-10 status recheck: latest local `n*` is still `n595a-d`; no `n596+` directories and no `room_matches` for `n594/n595`. A fresh `codes --entity-id 21493` health check with a 45s outer timeout still exited `124`, so upload/eval remains blocked. Based on the user's reminder, the next local work moved beyond `n595`'s final-answer changes and created `sk548e0910pzw` as a plot/stage ceiling probe for post-`405/502/706` continuation. A second raw-trace pass then added `sk548e0910pzx`, targeting Yuan's absent-voter/admin-log route (`张壹/张朔` confusion, 46 actual attendees, extra forged ballot) as a separate possible `706+` gate.

2026-05-10 generated unlock audit: `Game2/tools/extract_story_unlocks.py` now tracks `707/708` as well as `706`. At that checkpoint, regenerated `docs/generated/game2_story_unlocks.*` over 3939 analysis files only showed the older `404/501/705` ceiling; later uploads superseded that ceiling for `502/706/707/708`. Regenerated `docs/generated/game2_late_probe_results.*` included own labels through `sk548e0910pzz`: `pzb` remained `2797x2`; `pzt-pzz` had `0` valid samples because upload was blocked. A 10-second queue health check again exited `75` before upload, with logs under `Game2/runtime/ceiling_queue_logs/20260509_210454`.

2026-05-10 watcher follow-up: added `scripts/game2_poker_yuan_watch_start.sh`, `scripts/game2_poker_yuan_watch_status.sh`, and `scripts/game2_poker_yuan_watch_stop.sh`. This runs a separate lightweight watcher under `Game2/runtime/game2_poker_yuan_watch` using the existing session/room scanner with `--run-tools never` and an action command pointed at `scripts/game2_poker_yuan_ceiling_queue.sh`. The queue now skips labels that already have room dirs, so a recovered API should not repeatedly upload the same completed probe. The watcher was started with pid `423801`; first cycle ran the queue health check, got exit `75`, and performed no upload.

2026-05-10 `n596` tracking: new local `n596a-h` appeared, still with no room dirs and generated summary `0 valid` for all eight labels. Useful axes were audited instead of copied: `n596`'s Poker official-chain/space-toolmark, Yuan Friday/admin, hidden `705`, and cross-official branches overlap with `pzw/pzx`; the one distinct under-covered axis is the suitcase/repair/transport/DNA chain from `n596f`, so it was absorbed independently into `sk548e0910pzy`.

2026-05-10 watcher fix: the first watcher version only scanned rollout sessions and room dirs, so it could miss local candidate directories such as `n596a-h` before any room existed. `Game2/tools/skeptic_watch_codex_progress.py` now also scans `Game2/deepclue_ai` candidate directories via `--candidate-dir` and reports `candidates.new_candidate_dir_count`. The Poker/Yuan watcher was restarted with pid `424581`; its first post-fix status shows candidate scanning active (`new_candidate_count=427` on initial adoption) and no upload action due action cooldown, not due a script error.

2026-05-10 completion audit: added `docs/game2_poker_yuan_completion_audit.md`, mapping every explicit objective requirement to concrete artifacts and evidence available at that checkpoint. Later uploads superseded the "unseen `502/706/707/708`" state; the current audit still remains "not complete" for Poker `405/605/607/608`, fragile Yuan `706/708`, and no Yuan stage2.

2026-05-10 latest API recheck: manual `timeout 25s env SAIBLO_API_TIMEOUT=20 python3 saiblo_tools.py codes --entity-id 21493` again exited `124` with no payload. No `n596/n597` or `sk548e0910pzt-pzz` room dirs exist yet. Continue relying on the watcher/queue path rather than starting blind uploads.

2026-05-10 `n597` absorption: created `sk548e0910pzz` after auditing `n597a-e`. The broad all-global sweep was rejected as too budget-heavy; the useful generic source resolver was absorbed into our own candidate. `pzz` compiles, is included in `summarize_late_probe_results.py`, and is now part of `scripts/game2_poker_yuan_ceiling_queue.sh`. A focused `pzz` queue health check still exited `75` before upload because `codes --entity-id 21493` did not return. The older `game2_late_probe_retry.sh` process was stopped so API recovery does not automatically spend budget on a broad `n*` flood before our focused `pzt-pzz` queue.

2026-05-10 transcript mining: added `Game2/tools/extract_late_story_transcripts.py`, generating `docs/generated/game2_late_story_transcripts.*` from 3711 `analysis.json` files. At that mining checkpoint the structured first-seen audit only showed the older `404/501/705` ceiling; later uploads superseded the `502/706/707/708` counts. More importantly, every `705` sample showed the same failure mode: after 李海天尸检报告 appears, the next questions are broad final-summary prompts, not targeted follow-ups to the report holder, biology-building runner, guard/security source, or vote-admin source. The extracted `705` report holders are `楚戎臻`, `王泽`, `沈知遥`, `陆亦初`, and `张子韩`; observed runners include `沈知遥`, `叶青衡`, `张子韩`, `周林君`, and `陆亦初`; vote anomalies include 48 ballots vs 47 expected and 47 ballots vs 46 actual due `张朔` absence. This strengthens the current `pzx/pzy/pzz` direction: chase source holders and official systems after `705`, not more final-answer wording.

2026-05-10 `pzz` refinement from transcript evidence: adjusted the post-`705` path so it no longer spends the first post-report continuation on an all-NPC summary sweep. It now builds a `post705_targets` list from the report holder, biology-building runner, guard/security lead, teacher/admin lead, absent-voter lead, and phone/suitcase suspect, then asks those targets for the specific source systems: original autopsy archive, blue-backpack dolphin-pendant ownership, Century Woods DNA, biology/security monitoring, 1919 vehicle registration, vote originals, and phone original metadata. This keeps the probe aimed at opening `706/707/708`.

2026-05-10 API recovered / ceiling update: `sk548e0910pzz` uploaded and produced the first own Poker `502/503/504` plus `601/602/603/604` in match `8140258` (`2757`). The key unlocked content is: 梅花5/Joker 8:50聊天、特殊邀请函、LYZ项链、2010失踪少女、2015花纹村人口贩卖、张子韩/刘丽雯旧身份。 This is a real story-ceiling expansion even though it did not beat `pzb`'s average score.

2026-05-10 own follow-up probes: `sk548e0910qaa-qae` were created to stabilize the late Poker/Yuan path. `qab/qac` fixed earlier random front-door stalls where the reception holder verbally confirmed Joker chat/arrival tables but did not hand over evidence, and where stage 3 required a police/official authorization path. `sk548e0910qad` is the current best own plot probe: match `8140288` reached `501 + 601/602/603/604` and also reopened Yuan `705` in the same run. `qae` attempted to decouple the `601-604` continuation from requiring `502`, but two samples only reached `401/402` plus Yuan `703/704`; keep `qad` as the own candidate to build from.

2026-05-10 other-session tracking: `n600a` produced the first observed Poker `606` in match `8140284`, but with a very low score (`547`) because it is a Poker-only/broad probe. The useful axis is not its answer patch; it is the post-`601-604` question about left-arm `POKER` tattoos, 花纹村 organization membership, 三人照片, and official final dossier. `n601a-f` mostly explored this same axis and Yuan source-system variants; current summaries show no new `605/607/608` and no Yuan `706+`. Absorb the `606` tattoo/photo axis into the own `qad` line, but do not adopt the low-score broad `n600/n601` structure as keeper.

Current hard ceiling after regeneration at that checkpoint: observed late evidence included Poker `606x1`, but still no Poker `405/605/607/608`; Yuan late evidence remained unstable and had not opened Yuan stage2. The next real target was therefore: from `qad`'s `501+601-604+705` path, ask the true Club 5 / doctor / Yu Shuhua / police source for `606` and then for the missing `605` or final dossier; for Yuan, keep post-`705` pressure on report holder + runner + guard/security + source systems.

2026-05-10 n619/n620 update: the later n619 rooms clarify two points. First, Yuan `707` is not an endpoint problem: it appeared repeatedly in `n619a/b/c`, but no local n619/n620 sample converted it into `708`. Second, Poker can reach the full visible late chain `501/502/503/504/505/601-604/606` in a normal-score code path, but `n620a` showed that changing the final answer immediately after `606` does not open `605/607/608` and can drop the score to `2557`. This makes "answer wording after 606" a lower-priority axis than source/holder/order discovery.

Current corrected hard ceiling from regenerated runtime scan after `qbc` and `n621a`: Poker has observed `502x47`, `503x40`, `504x41`, `505x22`, `601-604x31`, and `606x18`, still no `405/605/607/608`. Yuan has `705x10`, true `706` U-disk samples (`n606a`, `n611a`, and one `sk/qaz` sample), `707x67`, and true `708` memory samples in own `qar/qas/qba/qbb` paths. `qbc` reproduced `606` and `707` at normal score but not `708`; `n621a` only repeated `707`. The promising next probes are structural: for Poker, identify who can actually hand over `605` or police/final-dossier records after `606`; for Yuan, reconstruct the exact source order that produced `706 -> 707 -> 708` rather than asking the contact target for an abstract exchange.

2026-05-10 `qbc`/`n621` update: `sk548e0910qbc` uploaded as version `49` (`c60200c9cdd945bf9a936a022ada5fb6`) with neutral remark `r` and was evaluated only through direct room eval, not activated. It is useful because the narrow post-`502` bridge opened `505/606` in one normal-score run without killing Yuan `707`; it is not a replacement for `qbb` if the goal is preserving `708`. `n621a` was added to the generated label list after inspection; it gives one more `2797`/`707` sample and no new hidden evidence.

2026-05-10 `qbi-qbn` follow-up: `qbi`'s post-`606` authorization/holder parser and the combined `qbh` path did not improve the ceiling. `qbj`/`qbl` reopened Yuan `708`, but every `708` sample stayed at or below `2757`, so `708` alone is not the hidden score gate. `qbk` is the strongest new structural signal because it can reliably reach `501/601-604` and often `502/503/504/606`, but it loses the `404` branch that appears in some other high samples. `qbm/qbn` show that simply asking a complementary "missing side" question after the branch is known does not merge the lanes. The next Poker work should compare the exact `n607a` `2837` trace against qbk's `2797` traces for source/order differences around `404`, `501`, and `503/504`, rather than adding broader late questions.
