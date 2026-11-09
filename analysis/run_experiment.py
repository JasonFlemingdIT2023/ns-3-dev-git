"""Run the single-cell scenario from JSON and preserve execution provenance."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scratch/single-cell-baseline.cc"


def git_output(directory, *arguments):
    """Read Git metadata, returning None when unavailable."""
    result = subprocess.run(["git", "-C", str(directory), *arguments],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def timestamp():
    """Return a timezone-qualified UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def read_config(path):
    """Validate a recipe against parameters exposed by the scenario."""
    config = json.loads(path.read_text())
    if not isinstance(config, dict) or set(config) - {"name", "description", "parameters", "run"}:
        raise ValueError("Config must contain name, parameters and optional description")
    if not isinstance(config.get("name"), str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", config["name"]):
        raise ValueError("Use a lowercase name with letters, digits and hyphens")
    parameters = config.get("parameters")
    allowed = set(re.findall(r'cmd.AddValue\("([^"]+)"', SOURCE.read_text()))
    allowed -= {"outputDir", "simTag"}
    allowed |= {"RngSeed", "RngRun"}
    if not isinstance(parameters, dict) or set(parameters) != allowed:
        actual = set(parameters) if isinstance(parameters, dict) else set()
        raise ValueError(f"Parameters must be explicit. Missing: {sorted(allowed - actual)}; "
                         f"unknown/reserved: {sorted(actual - allowed)}")
    for key, value in parameters.items():
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Invalid value for {key}")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Non-finite value for {key}")
        if isinstance(value, str) and (not value or any(c.isspace() for c in value)):
            raise ValueError(f"{key} must be a nonempty value without whitespace")
    return config


def main():
    """Reserve a unique run ID, execute ns-3, and record its outcome."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--id", required=True, help="Unused numeric run ID, e.g. 018")
    parser.add_argument("--rng-run", type=int, help="Override the random realization")
    parser.add_argument("--dry-run", action="store_true", help="Check and preview without writing")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{3,}", args.id):
        parser.error("ID must have at least three digits, e.g. 018")
    # Serialize launches so histories and IDs cannot race across recipes.
    lock = (ROOT / "configs/.run.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        config = read_config(args.config)
        config["parameters"] = dict(config["parameters"])
        if args.rng_run is not None:
            if args.rng_run < 1:
                raise ValueError("rng-run must be positive")
            config["parameters"]["RngRun"] = args.rng_run
    except (OSError, ValueError) as error:
        parser.error(str(error))

    results = ROOT / "results"
    history = ROOT / "configs/experiment-history"
    if (any(history.glob(f"{args.id}__*.json")) or any(results.glob(f"{args.id}__*"))
            or any(results.glob(f"{args.id}-*"))):
        parser.error(f"Run ID {args.id} already exists; choose a new ID")
    stem = f"{args.id}__{config['name']}"
    parameters = {**config["parameters"], "outputDir": "results", "simTag": stem + ".txt"}
    def value_text(value):
        return str(value).lower() if isinstance(value, bool) else str(value)
    target = shlex.join(["single-cell-baseline"] +
                        [f"--{key}={value_text(value)}" for key, value in parameters.items()])
    command = [str(ROOT / "ns3"), "run", target]
    print(shlex.join(command), flush=True)
    if args.dry_run:
        return 0

    results.mkdir(exist_ok=True)
    log_path = results / f"{stem}.log"
    record = {
        "id": args.id, "name": config["name"],
        "description": config.get("description", ""),
        "recipe_path": str(args.config.resolve()), "parameters": parameters,
        "command": command, "working_directory": str(ROOT),
        "started_at": timestamp(), "status": "running",
        "revisions": {str(path.relative_to(ROOT)) or ".": {
            "commit": git_output(path, "rev-parse", "HEAD"),
            "status": git_output(path, "status", "--short")}
            for path in (ROOT, ROOT / "contrib/nr")},
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "scope": "Explicit scenario arguments; module defaults depend on recorded revisions."
    }
    history.mkdir(exist_ok=True)
    history_path = history / f"{stem}.json"
    saved_config = {
        "name": config["name"],
        "description": config.get("description", ""),
        "parameters": dict(config["parameters"]),
        "run": record,
    }
    # Parameters above are directly reusable; generated output paths live in run.
    record.pop("parameters")
    record["outputs"] = {"outputDir": "results", "simTag": stem + ".txt"}

    def save_history():
        """Save this execution separately without changing its input recipe."""
        with tempfile.NamedTemporaryFile(mode="w", dir=history,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(saved_config, stream, indent=2)
            stream.write("\n")
        temporary.replace(history_path)

    save_history()
    exit_code = 1
    try:
        with log_path.open("x") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                exit_code = process.wait()
            except BaseException:
                process.terminate()
                process.wait()
                raise
        record["status"] = "completed" if exit_code == 0 else "failed"
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        exit_code = 130
    except OSError as error:
        record["status"] = "failed"
        record["error"] = str(error)
        print(error, file=sys.stderr)
    finally:
        record.update(finished_at=timestamp(), exit_code=exit_code)
        save_history()
    print(f"Run {args.id}: {record['status']}. Saved config: {history_path}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
