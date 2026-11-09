# Experiment workflow

Reusable recipes live directly in `configs/`. Each execution saves its own
configuration and timestamps in `configs/experiment-history/`. The input recipe
is never modified. No source files are copied.

```text
configs/
    shared-cell-load.json
    experiment-history/
        018__shared-cell-load.json
results/
    018__shared-cell-load.txt
    018__shared-cell-load.txt.sender.csv
    018__shared-cell-load.txt.packets.csv
    018__shared-cell-load.log
    plots/
```

Run from the ns-3 repository root:

```bash
python3 analysis/run_experiment.py --config configs/shared-cell-load.json --id 019
```

Preview with `--dry-run`. Select an independent random realization with
`--rng-run 2`. An ID identifies one execution; the random-run number selects
its random realization. Existing IDs, including failed runs, cannot be reused.

Each saved configuration contains `parameters` with the actual settings used,
including overrides, and `run` with the ID, start/end timestamps (UTC), completion
status, exact command, output paths, Git revisions/status and source hash.
It is created before execution and finalized afterward, so failures are recorded.
Editing the reusable recipe later leaves previous saved configurations intact.

A saved configuration can also be replayed with a new ID:

```bash
python3 analysis/run_experiment.py --config configs/experiment-history/018__shared-cell-load.json --id 020
```

This uses its saved parameters, generates new output names, and leaves the old
record intact. Reproducing code also requires the corresponding Git commits;
a hash identifies source content but cannot restore uncommitted edits. Module
defaults depend on the recorded simulator/module revisions.

Keep all scenario parameters explicit. Unknown/missing keys are rejected. Time
values use strings such as `400ms`; frequencies/bandwidth are in Hz and power in
dBm. `simTime` is the absolute generation-stop time. The current packet logging
requires one gNB and two UEs. Launches are serialized to protect IDs.

Use the existing analysis scripts on the `.txt` report path. Keep generated
figures in `results/plots/`. The launcher protects existing IDs; direct simulator
commands can still overwrite outputs.
