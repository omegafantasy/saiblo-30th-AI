# Game2 Automation System

Automated iteration loop for the DeepClue AI on Saiblo.

## Components

| File | Purpose |
|---|---|
| `run_cycle.py` | Orchestrator: upload, compile, activate, batch, poll, download replays |
| `analyze_results.py` | Parse replays and print a comparison report |
| `iterate.sh` | Bash wrapper that reads `state.json` and drives one full cycle |
| `state.json` | Persistent state machine (tracks current phase and version) |
| `logs/` | Timestamped log output |

## Quick start

```bash
# From repo root:
bash Game2/automation/iterate.sh
```

The script is idempotent. Run it repeatedly (or on a schedule) and it will
pick up wherever it left off:

- **idle / completed** -- starts a new iteration using the latest `vN/ai.py`.
- **submitted / batch_created / batch_polling** -- resumes polling the batch.
- **failed** -- prints the error and exits without retrying.

## Running manually

```bash
# Start a fresh cycle with a specific AI source:
python Game2/automation/run_cycle.py --source Game2/deepclue_ai/v13/ai.py \
    --entity-name g2auto --top-k 2 --timeout 600

# Resume a pending batch:
python Game2/automation/run_cycle.py --resume --timeout 600

# Print analysis of the most recent results:
python Game2/automation/analyze_results.py --print
```

## State machine

```
idle -> submitted -> batch_created -> batch_polling -> completed
                                                   \-> failed
```

After "completed", the next `iterate.sh` invocation starts a new cycle.
"failed" requires manual review before resetting.
