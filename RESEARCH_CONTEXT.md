# Research context and implementation status

Reviewed on 2026-11-09 against the earlier ns-3 chat and local files.

## Current research setting

One wireless cell with one gNB and heterogeneous application traffic: XR/gaming,
RTSR super resolution, and LLM inference. Communication for updating an
LLM-based scheduling controller may compete with those applications. Both
uplink and downlink matter. The application LLM and scheduler LLM have different
roles. XR and RTSR need not form one coupled application pipeline.

The research question concerns when and how much radio service to allocate to
controller-learning communication, trading current application QoS against
possible future gains from adaptation. A slower learning-budget controller over
a fast radio scheduler is a working proposal, not a finalized architecture.
FL, model architecture, learning method, and controller action space remain open.
Replaying training traffic alone measures interference; demonstrating learning
benefit requires actual model updates and subsequent service improvement.

The earlier chat reports an available XR trace and another student reconstructing
RTSR. Their current availability and formats have not been verified here.
No particular paper has yet been established here as an exact reproduction target.

## Implemented foundation

- ns-3.48 with contrib/nr (5G-LENA); examples and tests enabled in CMake.
- scratch/single-cell-baseline.cc, derived from cttc-nr-demo.
- Current defaults: one gNB, two UEs, shared 50 MHz BWP at 28 GHz,
  numerology 4, 35 dBm gNB transmit power, TDMA round robin.
- Two periodic UDP downlink sources: 100-byte and 1252-byte application packets.
  Both default to 10000 packets/s; Flow 2 load is configurable via lambdaBe.
- Generation from 0.4 to 1.0 s, followed by 0.5 s draining.
- Configurable delay-based RLC UM discarding.
- FlowMonitor reports distinguish active-window receptions and drain deliveries.
- Sender IP-emission and application-reception CSVs match flow/sequence IDs.
- analysis/summarize_packets.py validates matching and computes received fraction,
  mean delay, p50/p95/p99 and maximum received delay.
- analysis/plot_packets.py generates delay-time, delay-CDF and application-rate
  comparisons as PNG and PDF, with two subplots and overlaid conditions.

## Existing experiments

001-005 explore separate/shared BWPs, load, and draining. 006-012 investigate
discarding and improve measurements. 013-017 sweep Flow 2 through 5k, 10k, 15k,
20k and 25k packets/s, with discarding enabled and RngRun 1.

At 20k packets/s, discard OFF delivers 12000/12000 Flow 2 packets with mean
received delay about 72.18 ms. Discard ON delivers 10291/12000 with mean
received delay about 63.17 ms. Lower received-only delay does not establish
better service when fewer packets arrive.

The sweep shows low delay and full eventual delivery through 15k packets/s;
20k and 25k show substantial delay and incomplete eventual delivery. These are
single-realization, short-window results, not universal capacity estimates.

On this review, all seven paired logs (011-017) passed the existing packet
consistency validation. No new simulation, build, or full test suite was run.

## Outstanding work

- Trace-driven XR, RTSR and inference workloads; training/update transfers.
- Uplink traffic and an explicit UL/DL resource-sharing configuration.
- QoS/PF/RR comparisons and application deadline/completion metrics.
- Controller observations/actions, actual learning, update deployment and timing.
- Longer experiments, independent random runs and uncertainty estimates.
- Complete commands, configurations, revisions and workload provenance per run.
- Direct drop/queue/scheduler traces where mechanism attribution is needed.

Follow-up implementation: configs/shared-cell-load.json and
analysis/run_experiment.py now support explicit recipes, unique run IDs,
individual timestamped saved configurations in configs/experiment-history/ and console logs. Run 018 reproduces run
016's packet summary exactly; overwrite protection was checked. appStartTime
and drainTime are now command-line parameters. The scratch ignore rule now
allows the main scenario to be tracked, but files have not been staged or
committed. Source copies are not made. Reusable configurations stay at the top of configs/;
each execution saves its own configuration in configs/experiment-history/. Git revisions and a source hash identify code; commits
are needed to restore versions. See configs/README.md for the workflow.

## Collaboration preferences

Explain concepts, abbreviations, C++ constructs, purposes and evidence step by
step, with examples. Earlier work favored the user making and running changes
while receiving guidance; do not assume every proposed implementation change
has been authorized. Keep reports, CSVs and summaries directly in results/;
only plots go into grouped results/plots/ folders. Use descriptive IDs and
condition names; preserve existing outputs. Prefer PNG and PDF, two subplots
with conditions overlaid. Avoid unnecessary infrastructure and workload/model
complexity before the conventional baseline is understood.
