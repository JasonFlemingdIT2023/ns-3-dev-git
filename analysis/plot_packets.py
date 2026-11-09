"""Plot two packet-log experiments using a common observation window.
 Example: 
 python analysis/plot_packets.py \
  --off results/011*tx-rx.txt \
  --on results/012*tx-rx.txt \
  --prefix results/011-012__discard-comparison \
  --bin-ms 10

"""

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from summarize_packets import load_records, summarize


def main():
    """Create delay, empirical CDF, and application-byte rate comparisons."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--off", required=True, type=Path, help="Discard-OFF report")
    parser.add_argument("--on", required=True, type=Path, help="Discard-ON report")
    parser.add_argument("--prefix", required=True, type=Path, help="New output prefix")
    parser.add_argument("--start", type=float, default=0.4, help="Window start, seconds")
    parser.add_argument("--stop", type=float, default=1.0, help="Traffic stop, seconds")
    parser.add_argument("--end", type=float, default=1.5, help="Observation end, seconds")
    parser.add_argument("--bin-ms", type=float, default=10.0, help="Rate-bin width, ms")
    args = parser.parse_args()
    start = round(args.start * 1e9)
    stop = round(args.stop * 1e9)
    end = round(args.end * 1e9)
    width = round(args.bin_ms * 1e6)
    if not (0 <= start < stop < end and width > 0):
        parser.error("Require 0 <= start < stop < end and a positive bin width")

    kinds = ("delay-time", "delay-cdf", "rate-time")
    outputs = [Path(f"{args.prefix}__{kind}.{ext}")
               for kind in kinds for ext in ("png", "pdf")]
    if any(path.exists() for path in outputs):
        parser.error("Output already exists; select a new prefix")
    args.prefix.parent.mkdir(parents=True, exist_ok=True)

    datasets = []
    for report, label, color in ((args.off, "Discard OFF", "tab:blue"),
                                 (args.on, "Discard ON", "tab:orange")):
        summarize(report)  # Validate packet matching before plotting.
        tx = load_records(Path(str(report) + ".sender.csv"))
        rx = load_records(Path(str(report) + ".packets.csv"))
        datasets.append((tx, rx, label, color))
    flows = sorted({key[0] for tx, _, _, _ in datasets for key in tx})

    def figure():
        fig, axes = plt.subplots(len(flows), 1, figsize=(9, 3.5 * len(flows)),
                                 squeeze=False, layout="constrained")
        return fig, axes[:, 0]

    def save(fig, kind):
        for ext in ("png", "pdf"):
            target = Path(f"{args.prefix}__{kind}.{ext}")
            fig.savefig(target, dpi=180)
            print(target)
        plt.close(fig)

    fig, axes = figure()
    for ax, flow in zip(axes, flows):
        for _, rx, label, color in datasets:
            rows = sorted((r for k, r in rx.items() if k[0] == flow),
                          key=lambda r: r["tx_time_ns"])
            ax.scatter([r["tx_time_ns"] / 1e9 for r in rows],
                       [r["delay_ns"] / 1e6 for r in rows],
                       s=3, alpha=0.5, color=color, label=label, rasterized=True)
        ax.set(title=f"Application flow {flow}: received packets only",
               xlabel="Packet generation time (s)", ylabel="Application delay (ms)")
        ax.grid(alpha=0.25)
        ax.legend()
    save(fig, "delay-time")

    fig, axes = figure()
    for ax, flow in zip(axes, flows):
        for tx, rx, label, color in datasets:
            delays = sorted(r["delay_ns"] / 1e6 for k, r in rx.items() if k[0] == flow)
            sent = sum(k[0] == flow for k in tx)
            if delays:
                ax.step([delays[0]] + delays,
                        [0] + [(i + 1) / len(delays) for i in range(len(delays))],
                        where="post", color=color,
                        label=f"{label}: {len(delays)}/{sent} received")
        ax.set(title=f"Application flow {flow}: CDF conditional on reception",
               xlabel="Application delay (ms)", ylabel="Fraction of received packets",
               ylim=(0, 1.02))
        ax.grid(alpha=0.25)
        ax.legend()
    save(fig, "delay-cdf")

    def rates(rows, timestamp):
        counts = [0] * math.ceil((end - start) / width)
        for row in rows:
            time = row[timestamp]
            if start <= time < end:
                counts[(time - start) // width] += row["app_packet_bytes"]
        edges = [start + i * width for i in range(len(counts))] + [end]
        values = [count * 8 * 1e3 / (edges[i + 1] - edges[i])
                  for i, count in enumerate(counts)]
        return values, [edge / 1e9 for edge in edges]

    fig, axes = figure()
    for ax, flow in zip(axes, flows):
        for tx, rx, label, color in datasets:
            for records, timestamp, style, name in (
                (tx, "ip_tx_time_ns", "--", "IP-emitted application bytes"),
                (rx, "rx_time_ns", "-", "Received application bytes"),
            ):
                rows = [r for k, r in records.items() if k[0] == flow]
                values, edges = rates(rows, timestamp)
                ax.stairs(values, edges, color=color, linestyle=style,
                          label=f"{label}: {name}")
        ax.axvline(stop / 1e9, color="black", linestyle=":", label="Generation stops")
        ax.set(title=f"Application flow {flow}: {args.bin_ms:g} ms rate bins",
               xlabel="Simulation time (s)", ylabel="Application-byte rate (Mbps)",
               xlim=(start / 1e9, end / 1e9))
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    save(fig, "rate-time")


if __name__ == "__main__":
    main()
