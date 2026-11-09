"""Validate and summarize this scenario's paired sender/receiver CSV logs."""

import argparse
import csv
import json
import math
from pathlib import Path


def load_records(path):
    """Read integer-valued packet records and reject duplicate keys."""
    records = {}
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            row = {name: int(value) for name, value in row.items()}
            key = (row["app_flow_id"], row["sequence"])
            if key in records:
                raise ValueError(f"Duplicate packet {key} in {path}")
            records[key] = row
    return records


def summarize(report):
    """Match emitted packets to receptions and calculate per-flow metrics."""
    sent = load_records(Path(str(report) + ".sender.csv"))
    received = load_records(Path(str(report) + ".packets.csv"))
    if received.keys() - sent.keys():
        raise ValueError("Receiver records contain packets absent from sender records")
    for key, rx in received.items():
        tx = sent[key]
        if (tx["generation_time_ns"] != rx["tx_time_ns"]
                or tx["app_packet_bytes"] != rx["app_packet_bytes"]
                or rx["rx_time_ns"] < tx["ip_tx_time_ns"]
                or tx["ip_tx_time_ns"] < tx["generation_time_ns"]
                or rx["delay_ns"] != rx["rx_time_ns"] - rx["tx_time_ns"]):
            raise ValueError(f"Inconsistent packet records for {key}")

    flows = []
    for flow in sorted({key[0] for key in sent}):
        tx_rows = [row for key, row in sent.items() if key[0] == flow]
        rx_rows = [row for key, row in received.items() if key[0] == flow]
        delays = sorted(row["delay_ns"] / 1e6 for row in rx_rows)

        def percentile(fraction):
            return delays[math.ceil(fraction * len(delays)) - 1] if delays else None

        flows.append({
            "app_flow_id": flow,
            "ip_emitted_packets": len(tx_rows),
            "received_packets": len(rx_rows),
            "unreceived_by_end_packets": len(tx_rows) - len(rx_rows),
            "received_fraction": len(rx_rows) / len(tx_rows),
            "received_delay_mean_ms": sum(delays) / len(delays) if delays else None,
            "received_delay_p50_ms": percentile(0.50),
            "received_delay_p95_ms": percentile(0.95),
            "received_delay_p99_ms": percentile(0.99),
            "received_delay_max_ms": max(delays) if delays else None,
        })
    return {
        "report": str(report),
        "percentile_method": "nearest rank: sorted[ceil(p * N) - 1]",
        "limitations": [
            "Delay statistics describe received packets only.",
            "Unreceived packets are not automatically attributed to a drop mechanism.",
            "Sender records observe IP emission, not all application generation attempts.",
            "Application IDs are valid for the current two-UE port mapping.",
        ],
        "flows": flows,
    }


def main():
    """Print JSON summaries without modifying the original experiment files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path,
                        help="Report paths; matching .sender.csv and .packets.csv must exist")
    args = parser.parse_args()
    print(json.dumps([summarize(report) for report in args.reports], indent=2))


if __name__ == "__main__":
    main()
