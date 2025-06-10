from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Dict, List, Any, Optional
import re as _re

from console_utils import (
    print_subsection,
    print_build_info,
    print_warning,
    print_error,
    print_result,
)

# NOTE: This is extracted wholesale from run_eisodos_benchmarks.py so that the
#       main script is shorter. Only minimal tweaks were made (type hints, minor
#       refactoring) to keep behaviour identical.

__all__ = ["perform_benchmark_runs"]


def _serialize_payload(payload: Dict[str, Any], bench_id: str) -> bytes:
    """Helper that maps *instruction_payload* dicts into raw instruction bytes."""
    if not payload or not isinstance(payload, dict):
        print_warning(
            f"instruction_payload for {bench_id} is malformed. Using default byte."
        )
        return b"\xff"

    tag = payload.get("tag")
    if tag is None:
        print_warning(
            f"instruction_payload missing 'tag' for {bench_id}. Using default byte."
        )
        return b"\xff"

    data_bytes = bytearray()
    data_bytes.append(int(tag))

    # Currently supported payload variants
    if "amount" in payload:  # Transfer
        amount = payload.get("amount", 0)
        data_bytes.extend(int(amount).to_bytes(8, byteorder="little"))
    elif "lamports" in payload and "space" in payload:  # CreateAccount
        lamports = payload.get("lamports", 0)
        space = payload.get("space", 0)
        data_bytes.extend(int(lamports).to_bytes(8, byteorder="little"))
        data_bytes.extend(int(space).to_bytes(8, byteorder="little"))

    # Add more payload encodings as needed.
    return bytes(data_bytes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def perform_benchmark_runs(
    *,
    bench_id: str,
    bench_config: Dict[str, Any],
    entrypoint_name: str,
    entrypoint_features: List[str],
    artifact_path: pathlib.Path,
    program_id: str,
    actual_benched_crate_name: str,
    build_time_seconds: Optional[float],
    program_size_bytes: Optional[int],
    eisodos_root: pathlib.Path,
) -> List[Dict[str, Any]]:
    """Run all benchmark *variants* (e.g. different account counts) for the given
    compiled artifact and return a list of metric dictionaries.
    """
    results: List[Dict[str, Any]] = []

    instruction_payload = bench_config.get("instruction_payload")
    account_setups = bench_config.get("account_setups")
    runs_to_perform: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------------
    # Build the *runs_to_perform* matrix
    # ---------------------------------------------------------------------
    if instruction_payload:
        # Single custom payload run
        if "create_account" in bench_id:
            num_accounts = 3
        elif "transfer" in bench_id:
            num_accounts = 3
        elif "log" in bench_id:
            num_accounts = 0
        elif "slot_hashes" in bench_id:
            num_accounts = 1
        else:
            num_accounts = 1

        serialized = _serialize_payload(instruction_payload, bench_id)
        runs_to_perform.append(
            {
                "num_accounts": num_accounts,
                "instruction_hex": serialized.hex(),
                "run_id_suffix": "_custom_payload",
            }
        )
    elif account_setups and isinstance(account_setups, list):
        for setup in account_setups:
            count = setup.get("count")
            if isinstance(count, int) and 0 < count <= 255:
                runs_to_perform.append(
                    {
                        "num_accounts": count,
                        "instruction_hex": f"{count:02x}",
                        "run_id_suffix": f"_accounts_{count}",
                    }
                )
            else:
                print_warning(
                    f"Invalid count in account_setups for {bench_id}: {setup}. Skipping."
                )
    else:
        # Default ping-like run
        runs_to_perform.append(
            {
                "num_accounts": 1,
                "instruction_hex": "01",
                "run_id_suffix": "_default_run",
            }
        )

    # ---------------------------------------------------------------------
    # Execute each run variant
    # ---------------------------------------------------------------------
    for run_params in runs_to_perform:
        num_accounts = run_params["num_accounts"]
        instruction_hex = run_params["instruction_hex"]

        current_run_metrics: Dict[str, Any] = {
            "id": f"{bench_id}{run_params['run_id_suffix']}",
            "entrypoint": entrypoint_name,
            "features": entrypoint_features,
            "artifact": str(artifact_path),
            "program_id": program_id,
            "AccountsProcessed": num_accounts,
            "crate": actual_benched_crate_name,
            "instruction": (
                "create_account"
                if "create_account" in bench_id
                else "transfer"
                if "transfer" in bench_id
                else "ping"
                if "ping" in bench_id
                else "log"
                if "log" in bench_id
                else bench_id
            ),
            "BuildTimeSeconds": build_time_seconds,
            "ProgramSizeBytes": program_size_bytes,
        }

        print_subsection(f"=== Starting benchmark run: {current_run_metrics['id']} ===")
        print_build_info(
            f"--- Executing {entrypoint_name} benchmark for: {artifact_path} ---"
        )

        account_spec_args: List[str] = []
        if instruction_payload:
            if "create_account" in bench_id:
                account_spec_args.extend(
                    [
                        "--account-spec",
                        "funder:funder_key:true:true:10000000000:0:system",
                        "--account-spec",
                        "new_account:new_account_key:true:true:0:0:system",
                        "--account-spec",
                        "system_program:system_key:false:false:0:0:system",
                    ]
                )
            elif "transfer" in bench_id:
                account_spec_args.extend(
                    [
                        "--account-spec",
                        "source:source_key:true:true:20000000000:0:system",
                        "--account-spec",
                        "destination:dest_key:false:true:0:0:system",
                        "--account-spec",
                        "system_program:system_key:false:false:0:0:system",
                    ]
                )
            elif "slot_hashes" in bench_id:
                account_spec_args.extend(
                    [
                        "--account-spec",
                        "slot_hashes:SysvarS1otHashes111111111111111111111111111:false:false:1:20488:Sysvar1111111111111111111111111111111111111",
                    ]
                )
        # account_setups branch intentionally omitted – executor binary handles defaults.

        exec_command = [
            "cargo",
            "run",
            "-p",
            "eisodos",
            "--bin",
            "eisodos-bench-executor",
            "--",
            str(artifact_path),
            program_id,
            "--instruction-data",
            instruction_hex,
        ] + account_spec_args

        print(f"Executing: {' '.join(exec_command)}")
        try:
            exec_result = subprocess.run(
                exec_command,
                cwd=eisodos_root,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            print("--- Benchmark Executor Output ---")
            print(exec_result.stdout)
            if exec_result.stderr:
                print("--- Benchmark Executor Stderr (for metrics check) ---")
                print(exec_result.stderr)
            print("--- End Executor Output ---")

            # Parse metrics from stdout
            in_metrics = False
            for line in exec_result.stdout.splitlines():
                if line.strip() == "--- Benchmark Metrics ---":
                    in_metrics = True
                    continue
                if line.strip() == "--- End Metrics ---":
                    in_metrics = False
                    break
                if in_metrics:
                    if ":" in line:
                        k, v = [p.strip() for p in line.split(":", 1)]
                        try:
                            current_run_metrics[k] = int(v)
                        except ValueError:
                            current_run_metrics[k] = v

            # Only store result if we have compute units
            if "MedianComputeUnits" in current_run_metrics:
                print_result(
                    f"Storing result for: {current_run_metrics['id']} -> {current_run_metrics['MedianComputeUnits']} CUs"
                )
                results.append(current_run_metrics)
            else:
                # Fallback 1: parse Mollusk markdown produced by bench harness
                md_path = pathlib.Path(eisodos_root) / "benchmark" / "benches" / "compute_units.md"
                if md_path.is_file():
                    base_name = current_run_metrics["id"].split("_default_run")[0].split("_accounts_")[0].split("_custom_payload")[0]
                    ep_token = entrypoint_name.replace("-", "_")
                    try:
                        with md_path.open("r", encoding="utf-8") as md_f:
                            for md_line in md_f:
                                md_line = md_line.strip()
                                if md_line.startswith("| ") and "|" in md_line[1:] and not md_line.startswith("| ---"):
                                    cols = [c.strip() for c in md_line.strip("|").split("|")]
                                    if len(cols) >= 2:
                                        bench_name_col = cols[0]
                                        if base_name in bench_name_col and ep_token in bench_name_col:
                                            try:
                                                cu_val = int(cols[1].replace(",", ""))
                                                current_run_metrics["MedianComputeUnits"] = cu_val
                                                current_run_metrics["BenchmarkName"] = bench_name_col
                                                print_result(
                                                    f"Storing result for: {current_run_metrics['id']} -> {cu_val} CUs (markdown fallback)"
                                                )
                                                results.append(current_run_metrics)
                                            except ValueError:
                                                pass
                                            break
                    except Exception as md_exc:
                        print_warning(f"Failed to parse {md_path}: {md_exc}")

                # Fallback 2: scan logs for 'consumed N of' if still missing
                if "MedianComputeUnits" not in current_run_metrics:
                    for _stream in (exec_result.stdout, exec_result.stderr):
                        match = _re.search(r"consumed\s+(\d+)\s+of", _stream)
                        if match:
                            current_run_metrics["MedianComputeUnits"] = int(match.group(1))
                            current_run_metrics["BenchmarkName"] = current_run_metrics["id"]
                            print_result(
                                f"Storing result for: {current_run_metrics['id']} -> {current_run_metrics['MedianComputeUnits']} CUs (log fallback)"
                            )
                            results.append(current_run_metrics)
                            break

                if "MedianComputeUnits" not in current_run_metrics:
                    print_warning(f"No compute unit data found for: {current_run_metrics['id']}")

        except subprocess.CalledProcessError as exc:
            print_error(f"executing benchmark for {artifact_path}:")
            print("Stdout:", exc.stdout, file=sys.stderr)
            print("Stderr:", exc.stderr, file=sys.stderr)
        except Exception as exc:
            print_error(f"An unexpected error occurred during benchmark execution: {exc}")

    return results 