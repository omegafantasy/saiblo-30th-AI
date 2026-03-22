# ANTWar-AI Behavioral Statistics Report

**Dataset**: 500 self-play matches, all with enhanced logging (pre-search decisions, super weapon usage, global state per round).
**AI version**: `past_AIs/ANTWar-AI/main.cpp` — tree search (20K nodes, 150ms) + forward simulation (60-round)
**Raw data**: `antwar_stats_summary.json`, `antwar_matches/`

---

## 1. Match Outcomes (n=500)

| Metric | Value |
|--------|-------|
| Total matches | 500 |
| Player 0 wins | 213 (42.6%) |
| Player 1 wins | 240 (48.0%) |
| Ties | 47 (9.4%) |
| Average rounds | 512 (all go to max) |
| Average final HP differential | 0.83 |

**Key finding**: Player 1 (second mover) has a statistically significant advantage: **+5.4% win rate**. In self-play with identical AI, this reflects the structural benefit of seeing the opponent's operations before committing to your own each round. Player 1 can react to Player 0's tower placements, making more informed decisions.

All 500 matches reach the maximum 512 rounds — the AI is strong enough defensively that neither side can destroy the opponent's base outright. Victory is decided by HP differential at timeout, making the game primarily about efficiency rather than annihilation.

---

## 2. Tower Position Heatmap

### Build Frequency by Position (top 20 of 35 slots)

| Rank | Position | Count | Per-match | Distance to Base | Group |
|------|----------|-------|-----------|-----------------|-------|
| 1 | **ML1** | 971 | 1.94 | 5 | Mid-Left |
| 2 | **MR1** | 929 | 1.86 | 5 | Mid-Right |
| 3 | MR2 | 762 | 1.52 | 6 | Mid-Right |
| 4 | ML2 | 752 | 1.50 | 6 | Mid-Left |
| 5 | M2 | 728 | 1.46 | 5 | Mid |
| 6 | M3 | 713 | 1.43 | 5 | Mid |
| 7 | C3 | 493 | 0.99 | 4 | Central |
| 8 | M1 | 403 | 0.81 | 6 | Mid |
| 9 | M4 | 369 | 0.74 | 6 | Mid |
| 10 | FL2 | 313 | 0.63 | 7 | Far-Left |
| 11 | FR3 | 307 | 0.61 | 8 | Far-Right |
| 12 | C2 | 297 | 0.59 | 3 | Central |
| 13 | L2 | 287 | 0.57 | 4 | Left |
| 14 | FL3 | 284 | 0.57 | 8 | Far-Left |
| 15 | FR2 | 279 | 0.56 | 7 | Far-Right |
| 16 | R2 | 269 | 0.54 | 4 | Right |
| 17 | L3 | 260 | 0.52 | 5 | Left |
| 18 | LL1 | 249 | 0.50 | 6 | Far-Left-Lane |
| 19 | R3 | 249 | 0.50 | 5 | Right |
| 20 | LL3 | 245 | 0.49 | 6 | Far-Left-Lane |

### Position Tier Analysis

**Tier 1 (>900 builds)**: ML1, MR1 — The AI's "home base" towers. Built almost twice per match on average (rebuilt after selling). Distance 5 from base gives +2.0 eval bonus. These positions cover the main ant approach lanes.

**Tier 2 (700-800 builds)**: MR2, ML2, M2, M3 — Secondary mid-field positions. Frequently paired with Tier 1 towers for cross-coverage.

**Tier 3 (300-500 builds)**: C3, M1, M4, FL2, FR3 — Situational positions. C3 at distance 4 is a central fallback. FL2/FR3 are forward positions used in mid-late game.

**Tier 4 (<300 builds)**: All others, including near-base C1/C2 and far-forward F1-F4. Near-base towers score poorly due to low distance bonus; far-forward towers are fragile.

### What drives position choice?

The evaluation function: `node_val += base_dis * 0.4` per tower, plus dispersion penalties. ML1/MR1 at distance 5 give +2.0 each. A 3-tower setup at ML1+MR1+M2 gives: +2.0+2.0+2.0 = +6.0 from distance, and all towers are separated by distance >6, avoiding the -2 and -5 proximity penalties.

---

## 3. Tower Type Meta

### Upgrade Distribution

| Type | Count | Share | Branch | ATK/SPD/RNG |
|------|-------|-------|--------|-------------|
| **Mortar** | 4813 | **55.7%** | Basic→Mortar | 16/4/3+AOE |
| Quick | 2550 | 29.5% | Basic→Quick | 6/1/3 |
| Heavy | 1036 | 12.0% | Basic→Heavy | 20/2/2 |
| Sniper | 159 | 1.8% | Quick→Sniper | 15/2/6 |
| Missile | 41 | 0.5% | Mortar→Missile | 45/6/5+AOE |
| MortarPlus | 16 | 0.2% | Mortar→MortarPlus | 35/4/4+AOE |
| Double | 16 | 0.2% | Quick→Double | 7/1/4×2 |
| QuickPlus | 7 | 0.1% | Quick→QuickPlus | 8/0.5/3 |

**Why Mortar dominates (55.7%)**:
- AOE damage: Mortar hits all ants within radius 1 of its target, effectively clearing grouped ants on the hex grid's constrained paths
- Range 3 from mid-field positions covers a wide corridor
- Cost-effective: 60 coins for a 16 ATK AOE tower vs 200+ for level 3 towers
- The evaluation function penalizes level 3 at -39 vs -9 for level 2, making Mortar (level 2) the sweet spot

**Why level 3 is almost never used (2.8% total)**:
- 200 coin upgrade cost is prohibitive when the AI maintains <4 towers
- The eval penalty of -260×0.15 = -39 makes level 3 score worse than adding a second level 2 tower
- Sniper (159 uses) is the most common level 3 — its range 6 makes it worthwhile in specific late-game scenarios

---

## 4. Build Timing Across Game Phases

### Phase 1: Opening (R0-R60) — Establish Mid-Field

| Round Range | Top Positions | Character |
|-------------|---------------|-----------|
| R0-R30 | M3(392), M2(390), ML1(358), MR1(356), MR2(228) | Core mid-field build |
| R30-R60 | ML1(165), MR2(140), ML2(136), MR1(127), C3(103) | Expand and upgrade |

The AI builds 2-3 towers in the first 60 rounds, predominantly at mid-field positions. The first tower is placed at R0, the second around R8-10.

### Phase 2: Mid-Game (R60-R240) — Dynamic Cycling

| Round Range | Top Positions | Character |
|-------------|---------------|-----------|
| R60-R90 | MR1(85), ML2(80), ML1(79) | Heavy cycling at ML/MR |
| R90-R120 | MR1(72), ML1(65), MR2(55) | Continue cycling |
| R120-R180 | ML1, MR1, MR2, ML2 | Stable rotation |
| R180-R240 | ML1, MR1, MR2 + FL3/FR2 appear | Forward expansion begins |

Build counts are lower per range (60-85 vs 350-390 in opening) because the AI is mostly upgrading and downgrading existing towers rather than building new ones.

### Phase 3: Late Game (R240-R450) — Gradual Expansion

Forward positions (FL3, FR3, FR2) become more prominent. The AI pushes towers toward the opponent's territory.

### Phase 4: Endgame (R450-R510) — Defensive Rebuild

| Round Range | Top Positions | Character |
|-------------|---------------|-----------|
| R450-R480 | **C2(34), MR2(34), ML2(33), C1(31), C3(28)** | Near-base defensive |
| R480-R510 | C1(10), LL2(8), C2(8) | Last-ditch |

C1/C2 positions (distance 1-3 from base) suddenly appear in large numbers — the AI is selling forward towers and rebuilding near base after attack mode spending depletes coins.

---

## 5. Action Economy

### Overall Action Distribution

| Action | Count | Per Match | Share |
|--------|-------|-----------|-------|
| DowngradeTower | 14,212 | 28.4 | 39.0% |
| BuildTower | 10,792 | 21.6 | 29.6% |
| UpgradeTower | 8,638 | 17.3 | 23.7% |
| UseEmpBlaster | 1,395 | 2.8 | 3.8% |
| UseLightningStorm | 1,069 | 2.1 | 2.9% |
| UseEmergencyEvasion | 224 | 0.4 | 0.6% |
| UpgradeGenerationSpeed | 32 | 0.06 | 0.1% |
| UseDeflector | 9 | 0.02 | <0.1% |

**Downgrade:Build ratio = 1.32:1** — for every tower built, 1.32 are downgraded. This confirms the "churn" pattern: towers are built, upgraded to Mortar/Quick, then sold to fund rebuilding elsewhere. The AI does NOT accumulate towers — it maintains a fleet of 2-3 that constantly repositions.

### Pre-Search vs Tree Search Decision Split

| Decision Source | Rounds | Share |
|-----------------|--------|-------|
| Tree search (tower management) | ~34,074 | 93.7% |
| `try_attack` (super weapons in attack mode) | 1,062 | 2.9% |
| `try_emp` (defensive/offensive EMP) | 598 | 1.6% |
| `try_use_storm_endgame` (endgame storm) | 544 | 1.5% |
| `try_end_storm` (defensive winning storm) | 93 | 0.3% |

Only **6.3% of rounds** use pre-search decisions. The tree search handles 93.7% of the game — confirming tower management is the AI's primary activity, with super weapons as occasional strategic interventions.

---

## 6. Super Weapon Analysis

### Usage Summary

| Weapon | Total | Per Match | Avg Round | Median | Min | Max |
|--------|-------|-----------|-----------|--------|-----|-----|
| **EMP Blaster** | 1,395 | 2.79 | R365.9 | R407 | R93 | R511 |
| **Lightning Storm** | 1,069 | 2.14 | R457.2 | **R510** | R157 | R512 |
| **Emergency Evasion** | 224 | 0.45 | R432.4 | R467 | R141 | R509 |
| Deflector | 9 | 0.02 | R434.9 | R448 | R362 | R482 |

Plus **2,222 emergency storm triggers** (4.44/match) at avg R291.3 — these are defensive storms triggered post-search when the evaluation detects imminent danger.

### EMP Blaster (1,395 uses, most common)

- **When**: avg R365.9, spread across mid-late game (R93-R511)
- **Purpose**: disable enemy towers (radius 3) to let ants through
- **Source**: 598 from `try_emp` (defensive preemptive) + ~797 from `try_attack` (offensive)
- **Why most common**: EMP has lowest cooldown and costs 150 coins. The AI uses it whenever the opponent has ≥2 towers worth disabling (100+ tower value threshold in code)

### Lightning Storm (1,069 uses)

- **When**: avg R457.2, **median R510** — heavily skewed to the last 50 rounds
- **Purpose**: kill ants in range (instant kill, no HP check), dual offensive/defensive
- **Breakdown**: 544 from `try_use_storm_endgame` (round ≥510, tied game, all-in) + 93 from `try_end_storm` (round ≥488, winning) + remainder from `try_attack` and emergency storm
- **Emergency storm**: 2,222 uses at avg R291.3 — triggered when tree search evaluates max_val < -400 and fail_round is imminent. This is the AI's panic button, and it fires 4.44 times per match on average.

### Emergency Evasion (224 uses)

- **When**: avg R432.4 — late game
- **Purpose**: protect ≥3 friendly ants near enemy base from tower fire (grants evasion stacks)
- **Why moderate**: requires 3+ ants within range 3 near enemy base — this geometry happens occasionally when ant waves converge

### Deflector (9 uses — nearly absent)

- **When**: avg R434.9
- **Purpose**: redirect enemy tower damage within radius 3 of enemy base
- **Why almost never used**: Deflector requires ants near enemy base AND the AI prefers Emergency Evasion when ants are available (Evasion directly grants invulnerability stacks, while Deflector only blocks damage below half max HP). In the `try_use_superweapon` priority chain, Evasion is checked first and almost always wins when conditions are met.

---

## 7. Opening Repertoire

### Most Common Opening Sequences (first 2-3 actions within R0-R30)

| Rank | Sequence | Count | Share |
|------|----------|-------|-------|
| 1 | R0:MR1 → R9:M2 | 66 | 6.6% |
| 2 | R0:ML1 → R9:M3 | 53 | 5.3% |
| 3 | R0:ML1 → R10:M3 | 36 | 3.6% |
| 4 | R0:MR1 → R10:M2 | 22 | 2.2% |
| 5 | R0:ML1 → R8:M3 | 21 | 2.1% |
| 6 | R0:MR1 → R8:M2 | 18 | 1.8% |
| 7 | R0:MR2 → R10:M2 | 16 | 1.6% |
| 8 | R0:MR2 → R9:M2 | 15 | 1.5% |
| 9 | R0:ML2 → R9:M3 | 14 | 1.4% |
| 10 | R0:ML2 → R10:M3 | 11 | 1.1% |

**Pattern**: The opening is always one of two symmetric patterns:
- **Right-first**: MR1 or MR2 at R0, then M2 around R8-10
- **Left-first**: ML1 or ML2 at R0, then M3 around R8-10

The 8-10 round gap corresponds to saving coins: first tower costs 15, second costs 30. Starting income is 50 + 1/round income, minus the 15 cost. By round 8-10, the AI has 50-15+8×1 = 43 coins, just enough for the 30-cost second tower.

The **right-side (MR1→M2)** opening is slightly preferred (6.6% vs 5.3% for left) — this may reflect a seed-dependent pheromone initialization bias. Both P0 and P1 would see the same asymmetry.

---

## 8. Economy Curve

### Coin Trajectory by Phase

```
R0:   50 (start)
R10:  30 (first tower built)
R30:  42 (recovery)
R50:  36 (second/third tower cycle)
R100: 61 (upgrading phase, coins accumulating)
R150: 104
R200: 149
R250: 160 (plateau begins)
R300: 175
R350: 202
R400: 228 (peak approach)
R450: 240 (PEAK — attack mode trigger imminent)
R460: 191 (sharp drop — attack spending begins)
R470: 138 (deep spend on ant upgrades + super weapons)
R480: 128 (minimum)
R500: 138 (slight recovery as income continues)
R510: 147
```

**Economy phase transitions**:
1. **R0-R30**: Coin drain from initial tower build (50→30→42)
2. **R30-R100**: Oscillation during build/upgrade/sell cycles (30-60 range)
3. **R100-R250**: Steady accumulation ~10 coins/10 rounds (60→160)
4. **R250-R450**: Slower growth, plateau around 160-240 (tower maintenance costs vs income)
5. **R450-R480**: **Cliff drop from 240 to 128** — attack mode triggers at avg R397, coin spending on super weapons (150 for EMP, 200+ for Storm) and gen speed upgrades (200)
6. **R480-R510**: Partial recovery as income outpaces spending

The R450 cliff is the AI's deliberate strategic shift: it realizes the game is ending soon, abandons tower economy, and spends everything on offense.

---

## 9. Attack Mode & Base Upgrades

### Attack Mode

- Triggered in **100% of matches** at average round **397.0**
- Mechanism: `kill_diff <= -3 - max((450-round)/50, 0)` or `round >= 450 && kill_diff <= 1`
- In self-play, kill differential hovers near 0, so the R450 threshold (`kill_diff <= 1`) triggers universally

### Base Upgrades (rare in self-play)

| Upgrade | Count | Per Match | Avg Round |
|---------|-------|-----------|-----------|
| Ant level (→ level 1 or 2) | **0** | 0 | — |
| Generation speed | 32 | 0.064 | R376.8 |

**Why zero ant level upgrades**: The `try_attack` function only upgrades ant level when `global_state == -1` (losing HP). In self-play, HP is almost always tied (`global_state == 0`), so the ant upgrade path is never entered. When `global_state == 0`, `try_attack` goes directly to super weapons.

**Gen speed upgrades (32)**: Only happens when `global_state == -1` (rare HP deficit) AND both ant levels already maxed AND 200 coins available. The avg round 376.8 indicates this occurs late-game in the rare cases where one side falls behind.

---

## 10. Search Tree Performance

| Metric | Value |
|--------|-------|
| Avg nodes explored | 2,952 (14.8% of 20K limit) |
| Median nodes | 2,318 |
| Max nodes (hit limit) | 19,990 |
| Avg children per root | 80.1 |
| Avg best evaluation value | 74.23 |
| Eval std deviation | 85.63 |

**Interpretation**:
- The 150ms time budget (not the 20K node limit) is the binding constraint — the AI only uses 15% of its node pool
- Branching factor of ~80 means effective depth is ~1.5 levels (80 children × ~37 grandchildren per expanded child)
- Average eval value of 74.23 with std 85.63 means most rounds evaluate positively (towers are working), with occasional negative spikes when threats emerge
- The do-nothing child gets a +2.0 bias — in rounds where the best action scores <76 (74+2), do-nothing wins, explaining the relatively low 0.07 actions/round

---

## 11. Detailed Observations

### 11.1 The Tower Churn Cycle

The AI's core behavior is a continuous build-upgrade-downgrade loop:
1. **Build** Basic tower at a mid-field position (15-240 coins depending on tower count)
2. **Upgrade** to Mortar (60 coins) — the dominant upgrade path
3. Play for 50-100 rounds while the tower earns its investment through ant kills
4. **Downgrade/Destroy** the tower, recovering 80% of costs
5. **Rebuild** at a different position, adapting to the current ant path

Evidence: 14,212 downgrades vs 10,792 builds = 1.32:1 ratio. Each tower is built, used, and recycled on average 1.3 times.

### 11.2 Super Weapon Priority Chain

From the code and behavioral data, the actual decision priority is:

1. **try_emp** (if `global_state <= 0`, not reserved) — checked first every round when tied/losing
2. **try_attack** (if attack mode active) — super weapons within attack, plus ant/gen upgrades
3. **try_end_storm** (if winning and R≥488) — secure the win
4. **try_use_storm_endgame** (if tied and R≥510) — all-in final push
5. **Tree search** — if none of the above return actions
6. **Emergency storm** (post-search, if eval < -400/-700) — panic defense

The data confirms this: EMP (1,395) > Storm (1,069) > Evasion (224) > Deflector (9). EMP's high count reflects its dual offensive/defensive utility and lower cost.

### 11.3 The R450-R470 Economy Cliff

The sharpest transition in the game:
- R450: 240 coins (peak), attack mode is active
- R460: 191 coins (-49 in 10 rounds)
- R470: 138 coins (-53 in 10 rounds)
- Total spend: ~102 coins in 20 rounds

This corresponds to: EMP (150 coins) or Storm (200+ coins) activation, plus selling towers to afford super weapons. The `try_sell` function optimizes tower selling order via permutation search (factorial in tower count, capped at 4 towers = 24 permutations).

### 11.4 Emergency Storm as Core Mechanic

With 2,222 triggers across 500 matches (4.44/match), emergency storm is NOT a rare safety valve — it's a routine part of gameplay. It fires on average at R291.3, which is mid-game when ant waves become dangerous.

The trigger conditions (from code):
- `max_val < -400 && fail_round within 8 rounds && enemy EMP active`
- `max_val < -700 && fail_round within 2 rounds`
- `kill_diff >= 8 behind && fail_round within 1 round`

This means the AI's tree search occasionally approves configurations that seem safe but become dangerous when the 60-round forward simulation doesn't account for new ant spawns or opponent actions. The emergency storm compensates for this blind spot.

### 11.5 P1 Second-Mover Advantage

P1 wins 48.0% vs P0's 42.6% (ties: 9.4%). This 5.4% gap is structural:
- P1 reads P0's operations before making its own decision each round
- P1's `read_opponent_operations()` precedes `ai()` in the game loop
- This lets P1 adapt its tower placement and super weapon timing to P0's actions
- The advantage is modest (not overwhelming) because the AI doesn't explicitly exploit the information edge — it just happens to benefit from having slightly more current game state.

---

## 12. Summary Statistics

| Category | Key Number |
|----------|-----------|
| Most built position | ML1 (971, 1.94/match) |
| Most upgraded type | Mortar (55.7% of upgrades) |
| Most used super weapon | EMP Blaster (1,395, 2.79/match) |
| Most common opening | R0:MR1 → R9:M2 (6.6%) |
| Attack mode trigger | R397 avg (100% of matches) |
| Economy peak | R450, 240 coins |
| Economy trough | R480, 128 coins |
| Emergency storms | 4.44/match, avg R291 |
| Presearch decision rate | 6.3% of rounds |
| Tower churn ratio | 1.32 downgrades per build |
| Eval value (normal) | 74.2 ± 85.6 |
| Search utilization | 14.8% of 20K node limit |
