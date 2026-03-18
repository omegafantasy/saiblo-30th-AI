# ANTWar-AI Deep Analysis

**Source**: `past_AIs/ANTWar-AI/main.cpp` (1671 lines)
**Game**: Tower defense / ant colony competitive game on Saiblo platform
**Language**: C++ with tree search, forward simulation, and heuristic evaluation

---

## 1. Executive Summary

ANTWar-AI is a competitive tower defense AI built around a bounded tree search (20K nodes, 150ms) over a space of tactical tower placement/upgrade moves. Its core loop is:

1. Check if attack mode or super weapons should preempt the search.
2. If not, expand a search tree of tower configurations using 8 move-generation patterns.
3. Evaluate each leaf by forward-simulating 60 rounds of ant movement and tower combat.
4. Score leaves with a multi-term heuristic combining HP preservation, kill efficiency, tower economy, spatial dispersion, and ant proximity threat.
5. Apply a do-nothing bias (+2.0) to avoid overreacting.

The AI layers a global state machine on top (attack/defend/neutral) with dedicated decision trees for four super weapons (Lightning Storm, EMP Blaster, Deflector, Emergency Evasion). Economy management includes tower selling optimization via permutation search and opponent coin estimation for EMP threat assessment.

Key design choices: exponential tower cost awareness, heavy danger penalties (-500/-300) for imminent HP loss, spatial dispersion incentives to avoid clustering, and a conservative do-nothing preference that prevents thrashing. The architecture cleanly separates strategic decisions (attack mode, super weapons) from tactical decisions (tower search tree).

---

## 2. Architecture Overview

### Control Flow

```
run_with_ai(advanced_ai)
  -> advanced_ai(player_id, game_info)
       |
       +-- Check attack mode (kill differential logic)
       |     |-- try_attack() -> ant upgrades, gen_speed, super weapons
       |     |-- If actions returned: SKIP tree search entirely
       |
       +-- Tree Search (fallback for tactical tower management)
       |     |-- Root expansion: do-nothing child + 8 tac patterns
       |     |-- select_expand() loop until time/node budget exhausted
       |     |-- evaluate() each leaf via 60-round forward sim
       |     |-- Pick best max_val path, apply do-nothing bias
       |
       +-- Post-search emergency checks
             |-- Emergency storm (if val < -400/-700)
             |-- Endgame storm (round >= 488 winning, or 510 tied)
```

### Resource Budgets

| Resource | Limit |
|----------|-------|
| Time | 150ms (TIME1=0.15f) |
| Nodes | 20,000 (MAX_NODE_COUNT) |
| Forward simulation | 60 rounds per evaluation |
| Storm simulation | 32 rounds per position |
| EMP simulation | 24 rounds per candidate |

### Simulation Engine

The `Simulator` class maintains a copy of the full game state (towers, ants, coins, HP, cooldowns). The key method is `fast_next_round()`, which simulates only one side's towers attacking and ants moving -- a deliberate simplification that halves computation cost at the expense of ignoring opponent tower changes during the evaluation window.

---

## 3. Tower Position System

### Map Geometry

- 19x19 hexagonal grid
- 2 players with mirrored positions
- Each player's base has HP=50
- 35 named tower slots per player

### Player 0 Position Map

```
BASE = (2,9)     -- Home base
STORM = (3,9)    -- Lightning storm defensive slot

Near defense:
  C1=(4,9)  C2=(5,9)  C3=(6,9)      -- Central column
  L1=(5,7)  L2=(5,6)  L3=(6,7)      -- Left near
  R1=(5,11) R2=(5,12) R3=(6,11)     -- Right near

Mid-field:
  LL1=(4,3)  LL2=(4,2)  LL3=(5,3)   -- Far left
  RR1=(4,15) RR2=(4,16) RR3=(5,15)  -- Far right
  ML1=(6,4)  ML2=(7,5)              -- Mid-left
  MR1=(6,14) MR2=(7,13)            -- Mid-right
  M1=(8,7)  M2=(7,8)  M3=(7,10)  M4=(8,11)  -- Mid-field center

Forward:
  FL1=(6,1)  FL2=(6,2)  FL3=(7,1)   -- Far left forward
  FR1=(6,17) FR2=(6,16) FR3=(7,17)  -- Far right forward
  F1=(8,2)  F2=(8,4)                -- Far left extreme
  F3=(8,14) F4=(8,16)              -- Far right extreme
```

### 13 Mutual-Exclusion Groups

Each group allows at most 1 tower. This is the primary structural constraint on tower placement:

| Group | Slots | Strategic Role |
|-------|-------|----------------|
| C | C1, C2, C3 | Central column defense |
| L | L1, L2, L3 | Left near-base coverage |
| R | R1, R2, R3 | Right near-base coverage |
| LL | LL1, LL2, LL3 | Left flank |
| RR | RR1, RR2, RR3 | Right flank |
| M | M1, M2, M3, M4 | Mid-field (4 options) |
| ML | ML1, ML2 | Mid-left bridge |
| MR | MR1, MR2 | Mid-right bridge |
| FL | FL1, FL2, FL3 | Forward left |
| FR | FR1, FR2, FR3 | Forward right |
| F1/F2 | F1, F2 | Extreme left forward |
| F3/F4 | F3, F4 | Extreme right forward |

Maximum theoretical towers: 13 (one per group), but exponential cost makes >4 impractical.

### Spatial Strategy Implications

The group system forces choice between depth (closer to base, safer coverage) and breadth (farther out, earlier interception). The evaluation function explicitly rewards spatial dispersion:

- Tower pairs within distance 3: **-5 penalty**
- Tower pairs within distance 6: **-2 penalty**
- 3+ towers with none spread out: **-20 penalty**
- Each tower gets **+0.4 per hex distance from base**

This pushes the AI away from defensive clustering and toward a spread formation that intercepts ants earlier along multiple paths.

---

## 4. Move Generation

### 8 Tactical Patterns (`series_action`, tac parameter)

| tac | Description | Actions |
|-----|-------------|---------|
| 0 | Build 1 tower | Place at any valid empty slot |
| 1 | Upgrade 1 tower | 3 upgrade paths per tower type |
| 2 | Downgrade 1 + Build 1 | Combo: recoup funds + redeploy |
| 3 | Destroy 1 basic tower | Remove a level-0 tower entirely |
| 4 | Destroy 1 + Upgrade 1 | Combo: remove tower + upgrade another |
| 5 | Downgrade 1 non-basic | Revert an upgraded tower |
| 6 | Destroy 1 + Build 1 | Combo with ignorecode flag |
| 7 | Downgrade 1 + Upgrade 1 | Combo: economic rebalancing |

### Pruning Rules in `expand()`

These rules significantly reduce the branching factor:

1. **Non-root children skip pure destroy/downgrade** (tac 3, 5): destructive-only moves are only considered at the root level, preventing deep chains of demolition.

2. **Post-build restriction**: after a build action, skip destroy combos initially. Rationale: just built something, unlikely to immediately want to destroy.

3. **Post-upgrade restriction**: after an upgrade, skip downgrade+build combos initially. Prevents oscillation.

4. **Hard cap at 4 towers**: if tower_count >= 4, skip all build and build-combo patterns. This reflects the exponential cost reality:
   - Tower 1: 15 coins
   - Tower 2: 30 coins
   - Tower 3: 60 coins
   - Tower 4: 120 coins
   - Tower 5: 240 coins (prohibitive)

5. **EMP flag**: skip positions currently affected by an active enemy EMP (towers there are disabled anyway).

### Branching Factor Estimate

With 13 groups, 4 tower types, 3 upgrade paths, and the pruning rules:
- Build: ~13 positions x 4 types = ~52 children (minus occupied groups)
- Upgrade: ~4 towers x 3 paths = ~12 children
- Combos multiply two operations but are pruned aggressively

Effective branching factor is likely 20-60 at root, dropping to 10-30 at deeper nodes due to pruning.

---

## 5. Evaluation Function

### Overview

`Node::evaluate()` performs the heaviest computation in the AI. For each leaf node, it:

1. Runs `fast_next_round()` for 60 rounds (one-sided simulation)
2. Tracks three key events across the simulation
3. Computes a weighted sum of ~10 scoring terms

### Simulation Tracking

During the 60-round forward simulation, the evaluator records:

- **`fail_round`**: first round where the player loses any HP (capped at current_round + 60 if no HP loss)
- **`ruin_round`**: first round where the player loses 2+ HP in a single round (indicates cascading failure)
- **`nearest_ant_dis[round]`**: distance of the closest enemy ant to the player's base, per round

### Core Scoring Formula

```
node_val = hp_change
         + (fail_round - current_round) * 0.8
         + (ruin_round - fail_round) * 0.1
         - loss * 1.5
         + 20
```

Where:
- `hp_change`: net HP change during simulation (positive = gained HP, rare)
- `fail_round - current_round`: rounds of safety before first leak, weighted heavily at 0.8
- `ruin_round - fail_round`: gap between first leak and cascade, weighted lightly at 0.1
- `loss`: accumulated cost of any downgrades/destroys in the action sequence
- `+20`: baseline offset to keep values positive

**Interpretation**: The AI primarily optimizes for "how many rounds can I go without leaking?" (the fail_round term dominates). The ruin_round term is a tiebreaker that prefers configurations where even if a leak occurs, it doesn't cascade.

### Danger Penalties

```
if (fail_round - current_round) <= 16:
    node_val -= 500                    // DANGER: leak imminent

if (ruin_round - fail_round) <= 8:
    node_val -= 300                    // CRITICAL: cascade imminent
```

These are hard cliffs, not smooth gradients. A configuration that leaks in round 16 scores ~800 points worse than one that leaks in round 17. This creates strong pressure to find *any* configuration that pushes the fail_round past the 16-round horizon.

### Neutral State Scoring (global_state == 0)

When HP is tied, the AI adds kill-efficiency terms:

```
node_val += -(opponent_old_count_increase) * ant_ratio * 2
          + (opponent_die_count_increase) * ant_ratio * 1.5
```

Where `ant_ratio` = 3.0, 5.0, or 7.0 based on opponent ant level (matching the coin reward for killing that level).

- **old_count_increase**: enemy ants that survived past age limit (leaked through but didn't reach base). Penalized at 2x because it means your towers failed to kill them.
- **die_count_increase**: enemy ants killed by your towers. Rewarded at 1.5x.

This asymmetry (2x penalty for surviving ants vs 1.5x reward for kills) makes the AI prioritize preventing leaks over maximizing kills.

### Safety Penalty (EMP Threat Awareness)

When not in immediate danger but the opponent has EMP coin advantage:

```
if not_safe and not danger and current_round > 60:
    time_scale = min((current_round - 60) / 30, 1.0)
    node_val += (-40 + safe_val / 5) * time_scale
```

This gradually ramps up (over rounds 60-90) a penalty for configurations vulnerable to EMP disruption. `safe_val` is derived from `safe_coin()` -- the estimated opponent EMP budget. A large opponent coin reserve means a larger penalty.

### Tower Economy Penalty

```
// Base tower cost (exponential)
node_val -= (2^tower_count - 1) * 15 * 0.15

// Per-tower upgrade costs
for each tower:
    if level 2: node_val -= 60 * 0.15
    if level 3: node_val -= 260 * 0.15    // 60 + 200 cumulative
```

Note: 0.15 = 0.2 * 0.75. The 0.2 factor represents "opportunity cost as fraction of tower value" and 0.75 is a damping factor.

For 4 towers: `(16-1) * 15 * 0.15 = 33.75` points of penalty. This is modest compared to danger penalties (-500) but significant compared to kill scoring.

### Spatial Dispersion Bonus

```
for each pair of towers (i, j):
    d = hex_distance(tower_i, tower_j)
    if d <= 3: node_val -= 5
    if d <= 6: node_val -= 2       // Note: cumulative with d<=3

if tower_count >= 3 and no pair has d > 6:
    node_val -= 20                  // All clustered penalty

for each tower:
    node_val += 0.4 * hex_distance(tower, base)
```

This scoring creates a force field that pushes towers apart and away from the base, rewarding forward positioning that intercepts ants earlier.

### Ant Proximity Penalties (Per Simulated Round)

```
for each round in simulation:
    d = nearest_ant_dis[round]
    switch(d):
        case 5: node_val -= 0.2
        case 4: node_val -= 0.5    // NOTE: falls through to case 3!
        case 3:
        case 2:
        case 1: node_val -= 2.0

    if d <= 3:
        node_val -= 20             // One-time flag per occurrence
```

**Critical bug note**: The case 4 falls through to case 3, meaning distance 4 gets BOTH -0.5 AND -2.0 = -2.5 total. This may be intentional (distance 4 is nearly as dangerous as 3) or a missing `break`.

Over 60 rounds, if an ant stays at distance 3 for 10 rounds: `10 * (-2.0) + (-20) = -40` points. Significant but not dominant.

### Remaining Ant Threat

```
mis_val = 0
for each enemy ant still alive after simulation:
    mis_val += 32 - ant.age - distance_to_base * 1.5

node_val += mis_val / ant_count * 0.5
```

This estimates the future threat of surviving ants. An ant with age 0 at distance 10 contributes `32 - 0 - 15 = 17`. The division by ant_count normalizes for swarm size, and the 0.5 coefficient keeps it as a secondary factor.

---

## 6. Super Weapon Decision Trees

The AI has four super weapons, each with a dedicated decision procedure. Super weapon decisions preempt the tree search -- if a weapon fires, tree search is skipped that turn.

### 6.1 Lightning Storm

**Function**: `try_use_storm()` (offensive/defensive), `try_end_storm()` (endgame)

**Mechanic**: Area damage on the hex grid.

**Decision logic**:
1. Exhaustive search over all valid placement positions.
2. For each position: simulate 32 rounds.
3. Require `fail_round >= 24` (storm must not leave you vulnerable).
4. Score: `die_count[opponent] + fail_round`.
5. Can invoke `try_sell` / `try_sell_all` to afford the weapon by liquidating towers.

**Endgame variant** (`try_end_storm`):
- Triggered at round >= 488 when winning, or round >= 510 when tied.
- Places storm at the STORM position (3,9) -- adjacent to base for maximum defensive coverage.
- Purely defensive: protect the lead in the final rounds.

**Selling optimization** (`try_sell`):
- Enumerates ALL permutations of tower selling order.
- For each permutation: simulate 48 rounds post-sale.
- Select the permutation that maximizes rounds-before-HP-loss.
- Reject if best result < min(24, baseline_fail_round).
- This ensures the AI doesn't sell towers that were the only thing preventing an immediate leak.

### 6.2 EMP Blaster

**Functions**: `try_use_superweapon()` (offensive), `try_emp()` (defensive)

**Mechanic**: Disables all enemy towers in an area.

**Offensive decision logic** (`can_emp` section):
1. Score each candidate position:
   - +50 per Basic tower in range
   - +60 per mid-level tower in range (implied by the 50/80 split)
   - +80 per upgraded (level 2-3) tower in range
2. Pre-filter: require total value >= 100 before running simulation.
3. Simulate 24 rounds on opponent's side (with their towers disabled).
4. HP loss thresholds (adaptive by game phase):
   - Normal: require >= 5 HP loss
   - Late game: require >= 3 HP loss
   - Very late game: require >= 1 HP loss
5. Final score: `tower_value + 100 * hp_loss + proximity_bonus`.

**Defensive EMP** (`try_emp`):
- Requires enemy ants within distance 5 of own base.
- Requires coin advantage over opponent.
- Used reactively when under ant pressure.

### 6.3 Deflector

**Function**: `try_use_superweapon()` (`can_deflect` section)

**Mechanic**: Placed near opponent's base to redirect/enhance ant attacks.

**Decision logic**:
1. Place within distance 4 of opponent's base.
2. Simulate 24 rounds.
3. Score: `100 * hp_loss - distance_to_opponent_STORM_position`.
4. The STORM distance penalty is a tiebreaker: prefer placement that also blocks opponent's defensive storm option.

### 6.4 Emergency Evasion

**Function**: `try_use_superweapon()` (`can_eva` section)

**Mechanic**: Teleports/protects friendly ants near opponent base.

**Decision logic**:
1. Require >= 3 friendly ants in range (>= 2 in late game).
2. Ants must be close to opponent base (distance <= 5).
3. Score: `ant_value + 100 * hp_loss`.

### Priority Resolution

```
try_use_superweapon():
    1. If EMP available AND enemy doesn't have storm ready:
         -> Use EMP immediately (return)
    2. If enemy has storm ready:
         -> Defer EMP
         -> Try Emergency Evasion first
         -> Try Deflector second
    3. If no eva/deflect found:
         -> Fall back to EMP even with enemy storm threat
```

The logic here is sound: EMP is the strongest offensive weapon, but if the enemy has storm ready, they might use it reactively after your EMP. Better to spend your weapon slot on eva/deflect first.

---

## 7. Global State Machine

### State Definition

```
global_state = 0   if player HP == opponent HP  (neutral)
global_state = 1   if player HP > opponent HP   (winning)
global_state = -1  if player HP < opponent HP   (losing)
```

### Attack Mode Triggering

The attack decision uses a kill differential with adaptive thresholds:

```
kill_diff = kill1 - kill2    // my kills - their kills

// Living ants counted as fractional kills
fractional = live_ant_count * min(1, (512 - current_round) / 20)
effective_diff = kill_diff + fractional adjustments

if kill_diff >= 4:
    DON'T attack (already ahead enough)

threshold = -3 - max((450 - current_round) / 50, 0)
if kill_diff <= threshold:
    ATTACK (falling too far behind)

if attack_flag already set:
    CONTINUE attacking (hysteresis)

if current_round >= 450 and kill_diff <= 1:
    ATTACK (endgame push, can't afford to be passive)
```

The threshold formula means:
- Round 0: threshold = -3 - 9 = -12 (very reluctant to attack early)
- Round 200: threshold = -3 - 5 = -8
- Round 400: threshold = -3 - 1 = -4
- Round 450+: threshold = -3 (most aggressive)

This creates gradually increasing attack pressure as the game progresses.

### Attack Actions (`try_attack`)

Behavior depends on global_state:

**global_state == 0 (tied HP):**
- Only try super weapons. No economic actions.

**global_state == -1 (losing):**

Early/mid game (round <= 460):
1. Upgrade ants: level 0 -> 1 (200 coins)
2. Then level 1 -> 2 (250 coins)
3. Then gen_speed upgrade (200 coins)
4. Will sell towers to afford upgrades

Late game (round 460-470):
- Only upgrade to level 1 (conservative, preserve economy)

Otherwise:
- Try super weapons only

The progression makes sense: ant upgrades are long-term investments that need time to pay off, so they're prioritized early. Late game, there isn't enough time for upgrades to matter.

### Emergency Storm (Post-Search)

Three triggers for emergency defensive storm after the tree search completes:

```
Trigger 1: Enemy EMP active AND fail_round very close AND val < -400
Trigger 2: val < -700 AND fail_round within 2 rounds
Trigger 3: HP tied AND opponent has 8+ more kills AND fail_round within 1
```

These are last-resort actions when the search tree found no good options and the position is critical.

### Endgame Protocol

```
if global_state == 1 and current_round >= 488:
    try_end_storm()    // Defensive storm to protect the lead

if global_state == 0 and current_round >= 510:
    try_use_storm()    // Offensive storm, only 2 rounds left, go all-in
```

---

## 8. Economy Model

### Tower Cost Structure

Exponential cost is THE defining economic constraint:

| Tower # | Build Cost | Cumulative | Cumulative + Level 2 Upgrade |
|---------|-----------|------------|------------------------------|
| 1 | 15 | 15 | 75 |
| 2 | 30 | 45 | 165 |
| 3 | 60 | 105 | 285 |
| 4 | 120 | 225 | 465 |
| 5 | 240 | 465 | 705 |

With 50 starting coins and 1/round income, tower 4 alone costs 120 coins = 120 rounds of income. The AI hard-caps at 4 towers for this reason.

### Opponent Coin Estimation (`safe_coin`)

Estimates how much the opponent can spend on EMP:

```
if opponent_emp_cooldown >= 90:
    return 0                    // Can't use EMP soon, ignore

if cooldown > 0:
    return min(coins[opponent], 149) - cooldown * 1.66

if cooldown == 0:
    return min(coins[opponent], 149)
```

The 149 cap and 1.66 multiplier are tuned constants. The cooldown discount assumes the opponent will spend coins on other things while waiting for EMP to come off cooldown.

### Tower Selling Optimization (`try_sell`)

This is one of the most computationally expensive subroutines:

1. Generate all permutations of the current tower set.
2. For each permutation, sell towers in that order (each sale refunds 80% of total invested cost).
3. After each intermediate state, simulate 48 rounds.
4. Track the selling sequence that maximizes `fail_round` (rounds before HP loss).
5. Accept only if the best sequence yields fail_round >= min(24, baseline).

Why permutation order matters: selling tower A first might open a lane that tower B was covering. Selling B first might not. The 80% refund means selling is expensive but sometimes necessary to afford a super weapon.

With 4 towers, that's 4! = 24 permutations x 48 rounds of simulation each = ~1152 simulation steps. This is why the AI has a generous time budget.

---

## 9. Search Tree Details

### Node Structure

```cpp
struct Node {
    Simulator state;        // Full game state copy
    Node* parent;
    vector<Node*> children;
    Action actions[3];      // Up to 3 chained actions (for combos)
    float node_val;         // This node's evaluation score
    float max_val;          // Best score in subtree
    int fail_round;         // Rounds until first HP loss
    bool danger;            // fail_round within 16 rounds
    int expand_count;       // Times this node was expanded
};
```

### Root Expansion

The root always creates children in this order:
1. **Do-nothing child** (empty action) -- always first
2. **tac=0 children**: all valid build actions
3. **tac=1 children**: all valid upgrade actions
4. **tac=2 through tac=7**: combo actions (subject to pruning)

### Selection Policy (`select_expand`)

Priority score for selecting which child to expand next:

```
priority = -expand_count           // Prefer less-explored nodes
         + 1000 * (unexpanded?)    // Strongly prefer unexpanded
         + 20 * (danger?)          // Explore danger nodes more
         - 20 * (unsafe?)          // Deprioritize unsafe nodes
```

The `reserved` bonus: the do-nothing option carries forward the previous round's best score. This provides continuity -- if the AI found a good configuration last round, the do-nothing option starts with that score, and new actions must beat it.

### Do-Nothing Bias

```
if best_action.max_val < do_nothing.max_val + 2.0:
    return do_nothing
```

The +2.0 bias means the AI prefers inaction unless a concrete action scores at least 2 points better. This prevents:
- Thrashing (build/destroy cycles)
- Marginal "improvements" that waste coins
- Overreaction to transient ant positions

Given that most scoring terms are in the range of 0.1-5.0 per round, a 2.0 bias is approximately 2-3 rounds of marginal advantage required to justify action.

### Time Management

The search runs until either:
- TIME1 (150ms) is exhausted
- MAX_NODE_COUNT (20,000) nodes are allocated
- All expandable nodes have been explored

With ~30 children per expansion and evaluation costing ~60 forward sim rounds each, the practical search depth is typically 2-3 levels, occasionally 4 for narrow branches.

---

## 10. Hyperparameter Catalog

### Time and Resource Limits

| Parameter | Value | Description |
|-----------|-------|-------------|
| TIME1 | 0.15s | Primary search time budget |
| TIME2 | 0.2s | Extended budget (commented out) |
| MAX_NODE_COUNT | 20,000 | Maximum nodes in search tree |

### Simulation Horizons

| Parameter | Value | Context |
|-----------|-------|---------|
| Evaluation horizon | 60 rounds | Main evaluation forward sim |
| Storm sim horizon | 32 rounds | Lightning storm position search |
| EMP sim horizon | 24 rounds | EMP effectiveness estimation |
| Sell sim horizon | 48 rounds | Tower selling optimization |
| Storm min safe | 24 rounds | Minimum fail_round for storm placement |

### Game Constants

| Parameter | Value |
|-----------|-------|
| Map size | 19x19 hexagonal |
| MAX_ROUND | 512 |
| Base HP | 50 |
| Initial coins | 50 |
| Basic income | 1/round |
| Ant gen interval | 4/2/1 rounds (speed levels 0/1/2) |
| Ant HP | 10/25/50 (levels 0/1/2) |
| Ant reward | 3/5/7 coins (levels 0/1/2) |
| Ant age limit | 32 |
| Tower build cost | 15 * 2^tower_count |
| Tower upgrade (L2) | 60 coins |
| Tower upgrade (L3) | 200 coins |
| Downgrade refund | 80% |
| Max practical towers | 4 (hard-coded limit in expand) |

### Evaluation Weights

| Term | Weight | Notes |
|------|--------|-------|
| HP change | 1.0 | Direct HP impact |
| fail_round gap | 0.8 per round | Rounds until first leak |
| ruin_round gap | 0.1 per round | Fail-to-cascade gap |
| loss penalty | 1.5x | Cost of downgrades/destroys |
| Baseline offset | +20 | Keeps values positive |
| Danger penalty | -500 | fail_round within 16 rounds |
| Critical danger | -300 (additional) | ruin_round within 8 of fail |
| Safety penalty cap | -40 | Base EMP vulnerability penalty |
| Safety scaling | safe_val/5 | Opponent coin influence |
| Safety time ramp | (round-60)/30, capped at 1 | Gradual activation after round 60 |

### Tower Economy Weights

| Term | Weight | Notes |
|------|--------|-------|
| Tower cost factor | 0.15 (= 0.2 * 0.75) | Opportunity cost multiplier |
| Level 2 cost charge | 60 * 0.15 = 9.0 | Per tower |
| Level 3 cost charge | 260 * 0.15 = 39.0 | Per tower (cumulative) |

### Spatial Scoring

| Term | Value | Condition |
|------|-------|-----------|
| Close pair penalty | -5 | Tower pair distance <= 3 |
| Medium pair penalty | -2 | Tower pair distance <= 6 |
| Cluster penalty | -20 | 3+ towers, none spread |
| Base distance bonus | +0.4 per hex | Per tower, from base |

### Ant Proximity (Per Simulated Round)

| Distance | Penalty | Notes |
|----------|---------|-------|
| 5 | -0.2 | Mild concern |
| 4 | -2.5 | -0.5 + fallthrough -2.0 |
| 3 | -2.0 | Serious threat |
| 2 | -2.0 | Critical |
| 1 | -2.0 | Adjacent to base |
| Any d <= 3 flag | -20 | One-time per occurrence |

### Remaining Ant Threat

| Parameter | Value |
|-----------|-------|
| Age factor | 32 - ant.age |
| Distance factor | distance * 1.5 |
| Normalization | / ant_count |
| Final weight | * 0.5 |

### Kill Scoring (Neutral State)

| Term | Weight | Notes |
|------|--------|-------|
| Surviving enemy ants | -2.0 * ant_ratio | Penalize leaks |
| Killed enemy ants | +1.5 * ant_ratio | Reward kills |
| ant_ratio | 3.0 / 5.0 / 7.0 | By opponent ant level |

### Attack Mode Thresholds

| Parameter | Value | Notes |
|-----------|-------|-------|
| Don't attack threshold | kill_diff >= 4 | Already ahead |
| Attack threshold base | -3 | Base deficit to trigger attack |
| Early game adjustment | -(450-round)/50 | More reluctant early |
| Endgame trigger | round >= 450, diff <= 1 | Force aggression |
| Fractional kill weight | min(1, (512-round)/20) | Living ant discount |

### Super Weapon Scoring

| Parameter | Value | Context |
|-----------|-------|---------|
| EMP Basic tower value | +50 | Per tower in range |
| EMP Upgraded tower value | +80 | Per tower in range |
| EMP minimum threshold | 100 | Pre-filter before simulation |
| EMP HP loss (normal) | >= 5 | Required effectiveness |
| EMP HP loss (late) | >= 3 | Relaxed requirement |
| EMP HP loss (very late) | >= 1 | Minimal threshold |
| EMP HP score multiplier | 100 | Per HP lost |
| Deflector HP multiplier | 100 | Per HP lost |
| Eva min ants (normal) | >= 3 | Friendly ants in range |
| Eva min ants (late) | >= 2 | Relaxed requirement |
| Eva max distance | 5 | Ants to opponent base |

### Search Biases

| Parameter | Value | Notes |
|-----------|-------|-------|
| Do-nothing preference | +2.0 | Must beat do-nothing by this margin |
| Unexpanded bonus | +1000 | Selection priority for unexplored |
| Danger exploration bonus | +20 | Explore threatening positions |
| Unsafe penalty | -20 | Deprioritize EMP-vulnerable |
| Emergency storm val | < -400 or -700 | Trigger thresholds |
| Emergency kill diff | 8+ kills behind | Trigger for desperate storm |

---

## 11. Strengths and Weaknesses Analysis

### Strengths

**1. Robust defensive play.** The evaluation function is heavily weighted toward fail_round (0.8 per round) with massive danger penalties (-500/-300). The AI will almost never "forget" to defend. The 60-round forward simulation is deep enough to catch most slow-developing threats.

**2. Economic awareness.** The exponential tower cost penalty, the 4-tower hard cap, and the tower selling permutation search all show sophisticated economic reasoning. The AI won't bankrupt itself building unnecessary towers.

**3. Super weapon integration.** Four distinct decision trees with adaptive thresholds (normal/late/very late) and proper priority ordering (EMP first, but defer if enemy has storm). The try_sell optimization for affording weapons is particularly clever.

**4. Anti-thrashing mechanisms.** The do-nothing bias (+2.0), pruning of destroy/downgrade at non-root nodes, and post-action restrictions prevent the AI from oscillating between configurations.

**5. Spatial reasoning.** The dispersion bonuses and proximity penalties create emergent behavior: towers spread out to cover multiple lanes, positioned forward for early interception.

**6. Adaptive aggression.** The attack mode threshold smoothly transitions from very conservative (early game, threshold -12) to aggressive (late game, threshold -3), with proper hysteresis.

### Weaknesses

**1. One-sided simulation.** `fast_next_round()` only simulates the AI's own towers. This means the evaluation cannot account for:
- Opponent building new towers during the 60-round window
- Opponent using super weapons reactively
- Dynamic tower interactions

This is a major simplification that saves computation but misses opponent adaptation.

**2. No opponent modeling.** The AI has no model of what the opponent might do. `safe_coin()` estimates opponent resources but doesn't predict opponent actions. Against a predictable opponent this is fine; against an adaptive one, it's a liability.

**3. Shallow effective search depth.** With 20K nodes and ~30 branching factor, the tree is only 2-3 levels deep. Each level represents one tactical action. The AI cannot plan multi-step build sequences like "build tower A now, upgrade next turn, then build tower B."

**4. Case 4 fallthrough (possible bug).** The proximity penalty switch statement has case 4 falling through to case 3, making distance-4 ants score -2.5 instead of -0.5. If unintentional, this overweights the mid-range threat. If intentional, it should use explicit fallthrough.

**5. Hardcoded position map.** The 35 named positions and 13 groups are entirely hardcoded for the specific ANTWar map. No adaptability to map variations or procedural generation.

**6. Permutation selling is expensive.** With 4 towers, try_sell evaluates 24 permutations x 48 rounds. With 5+ towers (if the cap were raised), this becomes factorial-explosive. The approach doesn't scale.

**7. Binary danger thresholds.** The -500/-300 penalties are hard cliffs at exactly 16 and 8 rounds. A configuration failing at round 17 scores 500 points better than one failing at round 16, but only 0.8 points better than one failing at round 18. This creates scoring discontinuities that may cause unstable behavior near the threshold.

**8. No learning.** All parameters are hand-tuned. The AI cannot adapt its weights based on opponent behavior or game outcome. The hyperparameter space is large enough (30+ parameters) that manual tuning is unlikely to find the global optimum.

---

## 12. Transferable Patterns for AntGame2

AntGame2 (Ant Colony Strategy 2) differs significantly from ANTWar: it features softmax-based ant routing, teleportation mechanics, emergent ant behaviors, and congestion effects. However, several architectural patterns from this AI transfer well.

### Directly Transferable

**1. Bounded tree search with forward simulation.** The core pattern of "generate candidate actions, simulate forward N rounds, score with heuristic" is game-agnostic. For AntGame2:
- Candidate actions: tower placements, pheromone adjustments, teleporter configurations
- Forward simulation: must model softmax routing (ants choose paths probabilistically based on pheromone weights)
- Scoring: adapt the multi-term heuristic to AntGame2's objectives

**2. Do-nothing bias.** AntGame2 likely has similar issues with action thrashing, especially for pheromone adjustments. A +N bias toward inaction prevents oscillation and is cheap to implement.

**3. Danger penalty cliffs.** The concept of massive penalties for imminent base penetration transfers directly. The threshold values need recalibration for AntGame2's timing, but the structure works.

**4. Adaptive aggression thresholds.** The smooth early-conservative-to-late-aggressive transition is applicable to any competitive game with a fixed round limit.

**5. Economy penalty in evaluation.** Exponential or otherwise escalating costs should always be reflected in the evaluation function, not just in move legality checks.

### Needs Adaptation

**6. Spatial dispersion scoring.** ANTWar's hex-distance-based dispersion bonuses need rethinking for AntGame2's softmax routing. Instead of "spread towers to cover lanes," the scoring should account for how tower placement affects the softmax probability distribution of ant paths. Towers that create routing bottlenecks (high-congestion nodes in AntGame2) may be more valuable than spread towers.

**7. Forward simulation fidelity.** ANTWar's one-sided fast_next_round was a pragmatic shortcut. AntGame2's softmax routing means ant behavior depends on the full board state (both players' pheromones). One-sided simulation may miss critical routing interactions. Consider:
- Full simulation at reduced horizon (30 rounds instead of 60)
- Or probabilistic sampling of opponent actions

**8. Super weapon decision trees.** If AntGame2 has special abilities (teleportation triggers, behavior modifiers), each needs a dedicated decision tree with:
- Pre-filter (is this ability worth simulating?)
- Position/target search
- Forward simulation with adaptive thresholds
- Priority ordering among multiple abilities

### New Patterns Needed for AntGame2

**9. Probabilistic ant routing model.** ANTWar ants follow fixed paths. AntGame2 ants use softmax over pheromone-weighted edges, meaning routing is stochastic. The evaluation function needs to either:
- Simulate multiple routing samples and average scores (Monte Carlo)
- Or compute expected values analytically from the softmax distribution

**10. Congestion modeling.** AntGame2 has congestion effects where too many ants on one path reduce throughput. The evaluation function should penalize configurations that funnel all ants through a single bottleneck, even if that bottleneck is well-defended. This is the opposite of ANTWar's "cover all lanes" instinct.

**11. Pheromone manipulation as action space.** ANTWar's action space was discrete (build/upgrade/destroy tower at slot X). AntGame2 adds continuous pheromone adjustments. The tree search needs either:
- Discretization of pheromone values (e.g., low/medium/high per edge)
- Or a separate gradient-based optimizer for pheromone values, with tree search only for discrete actions

**12. Teleporter interaction effects.** Teleporters in AntGame2 create non-local spatial effects that ANTWar's hex-distance-based heuristics cannot capture. Tower placement evaluation needs to account for teleporter topology -- a tower "far" from the base in hex distance might be "close" via teleporter, and vice versa.

**13. Opponent pheromone estimation.** ANTWar's safe_coin() estimated opponent resources. AntGame2 needs an analog that estimates opponent pheromone distributions, which directly affect how your ants route through their defenses. This is harder because pheromones are continuous and partially observable.

### Key Takeaway

The ANTWar-AI's greatest transferable asset is its **evaluation function architecture**: a multi-term weighted sum combining safety (fail_round), economy (tower costs), spatial quality (dispersion), and threat assessment (ant proximity). This template -- with different terms and weights -- can structure any tower-defense-style AI's decision-making. The specific weights are game-dependent and should be tuned per game, but the categories of concern (safety, economy, space, threat) are universal.

---

## 13. Code → Behavior Correlation Report

*Based on 200 self-play matches with behavioral statistics. Full stats in `antwar_behavior_analysis.md` and `antwar_stats_summary.json`.*

### 13.1 Evaluation Function → Observed Tower Placement

**Code**: `node_val += base_dis * 0.4` (per tower) + dispersion penalties (-5 for d≤3, -2 for d≤6, -20 if ≥3 towers not spread)

**Observed**: Top tower slots are ALL mid-field positions: ML1(393), MR1(379), ML2(305), MR2(305), M3(298), M2(289). Near-base positions (C1, C2, L1, R1) are used rarely and mostly in late game.

**Correlation**: The +0.4/distance bonus from base is the dominant spatial signal. Mid-field positions at distance 4-6 from base score +1.6 to +2.4 over near-base positions at distance 1-2. Combined with the dispersion bonus (mid-field positions are naturally more spread), the evaluation strongly favors the MR/ML/M groups. The C/L/R groups appear mainly after round 450 when attack mode triggers rebuilding.

### 13.2 Tower Cost Penalty → Observed Tower Count

**Code**: `node_val -= (2^tower_count - 1) * 15 * 0.15` and `if tower_count >= 4: skip build`

**Observed**: Average ~31 tower actions per 512-round match, with more downgrades (4724) than builds (4332). Tower count is kept low through constant recycling.

**Correlation**: The exponential cost penalty grows rapidly: 2 towers costs -6.75, 3 towers costs -15.75, 4 towers costs -33.75. The hard cap at 4 plus the exponential penalty creates a "build 2-3 towers, upgrade, sell, rebuild" cycle. The downgrade > build ratio (1.09:1) confirms constant tower churn rather than accumulation.

### 13.3 Upgrade Preference → Mortar Dominance

**Code**: 3 upgrade paths from Basic — Heavy(20/2/2), Quick(6/1/3), Mortar(16/4/3+AOE). Evaluation uses forward simulation to assess kill efficiency.

**Observed**: Mortar 56% of upgrades, Quick 31%, Heavy 10%. Level 3 upgrades extremely rare (<2%).

**Correlation**: Mortar's AOE (damages ants within radius 1 of target) makes it efficient against grouped ants on the hex grid's constrained paths. Quick's 1-round cooldown with range 3 makes it the backup choice. Heavy's range-2 limitation restricts its utility. Level 3 tower penalty (-260*0.15 = -39 vs -60*0.15 = -9 for level 2) makes level 3 upgrades almost never worth the evaluation cost.

### 13.4 Attack Mode Logic → Late-Game Trigger

**Code**: Attack when `kill1 - kill2 <= -3 - max((450-round)/50, 0)` or `round >= 450 && kill1 - kill2 <= 1`

**Observed**: Attack mode triggers in 100% of matches at average round 411.5. Economy drops from ~273 coins (R450) to ~130 (R470).

**Correlation**: In self-play, kill differentials hover near 0. The threshold becomes `-3 - 0 = -3` at round 450, and the `round >= 450 && kill_diff <= 1` clause triggers when even slightly behind. At round 411 (the average trigger), the threshold is `-3 - max(39/50,0) = -3`. A 3-kill deficit in self-play is common enough that 100% trigger rate is expected. The coin drop at R450-470 corresponds to ant upgrade purchases (200 for level 1, 250 for level 2, 200 for gen speed).

### 13.5 Emergency Storm → Defensive Frequency

**Code**: Triggers when `(val < -400 && fail_round - current ≤ 8)` or `(val < -700 && fail_round ≤ 2)`

**Observed**: 814 emergency storm events across 200 matches (4.07 per match), avg round 308.8.

**Correlation**: Round 308 is mid-game when both sides have established defenses and periodic ant waves can threaten HP. The 150ms search budget means the AI sometimes commits to configurations that are evaluated as safe but become dangerous as ants advance. Emergency storm is the safety valve — the AI detects the danger post-search and fires storm defensively. The frequency (4/match) suggests this isn't rare but a routine part of gameplay.

### 13.6 Opening Patterns → Optimal First Moves

**Code**: Round 0 AI receives state with 50 coins, no towers. `build_tower_cost(0) = 15`. Tree search evaluates all 29 valid slot positions.

**Observed**: First tower at MR1 (38.3%) or ML1 (34.9%). Second tower at M2/M3 around rounds 8-10.

**Correlation**: MR1 at (6,14)/(11,14) and ML1 at (6,4)/(11,4) are symmetrically placed mid-field positions in the ML/MR groups. They score highest because: (a) distance from base = 5, giving +2.0 from spatial bonus; (b) range-3 towers at this position cover the main ant path; (c) the M2/M3 positions at (7,8)/(7,10) are then opened (different groups, no adjacency conflict). The ~9-round gap before second build matches the coin recovery from 50-15=35 → 35+9=44 → 44-30=14 (second tower costs 30).

### 13.7 Search Depth → Action Quality

**Code**: 20K node limit, 150ms budget, branching factor from 8 tac patterns × ~29 positions.

**Observed**: Average 4363 nodes, 81.2 children per root. Effective depth ~1.5-2 levels.

**Correlation**: With 81 children per expansion and 4363 nodes, only ~54 grandchildren are explored (4363 - 81 - 1 root = 4281 grandchildren / 81 children = ~53 per expanded child). This means each first-level choice gets minimal second-level exploration. The do-nothing bias (+2.0) ensures the AI doesn't make marginally-beneficial moves that it hasn't deeply validated. The 150ms budget (not node count) is the binding constraint — the AI uses only 22% of its node pool on average.

### 13.8 Most Impactful Strategies (by implied win rate)

While self-play can't directly measure "best" strategies, the behavioral patterns reveal which strategies the AI consistently converges on:

1. **Mid-field Mortar placement** — the dominant strategy, used in 100% of matches
2. **Tower recycling over accumulation** — the 1.09:1 downgrade:build ratio shows active portfolio management
3. **Late-game attack mode investment** — reliably triggered for endgame push
4. **Emergency storm as defensive safety valve** — prevents catastrophic HP loss
5. **Conservative early game** — first tower at round 0, second at ~round 9, slow build-up

### 13.9 Patterns Needing Adaptation for AntGame2

| ANTWar Pattern | AntGame2 Adaptation |
|----------------|-------------------|
| Fixed 35 position slots | AntGame2 has different map topology; positions must be derived from map analysis |
| Mortar AOE meta | AntGame2 ant routing is probabilistic (softmax); AOE effectiveness depends on congestion patterns |
| Mid-field forward positioning | Teleporters may make "distance from base" non-linear; need teleporter-aware distance metric |
| Emergency storm for defense | AntGame2's equivalent abilities need similar "safety valve" logic |
| Kill differential attack trigger | AntGame2 scoring may differ; adapt thresholds to new game's victory conditions |
| Do-nothing bias | Directly transferable; prevents pheromone/tower thrashing |
| 60-round forward simulation | May need shorter horizon (30 rounds) if simulating both players' softmax routing |
| Exponential tower cost in eval | AntGame2's cost structure should be reflected similarly in evaluation |
