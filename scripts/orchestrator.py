from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import toml
from typing import List, Tuple, Dict, Any

from builder import run_cargo_build
from console_utils import (
    print_section,
    print_subsection,
    print_success,
    print_warning,
    print_error,
)
from entrypoint_config import ENTRYPOINT_DEPS
from executor import perform_benchmark_runs
from helpers import (
    discover_crates,
    parse_function_path,
    format_features,
    replace_placeholders,
    get_workspace_dependencies_block,
    get_package_name_from_manifest,
)
from reporter import generate_markdown_report, print_console_summary
from rewriter import rewrite_sources_for_entrypoint

# Re-export for caller convenience
__all__ = ["run"]

EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
TEMPLATES_DIR = EISODOS_ROOT / "scripts" / "benchmark_templates"
TARGET_DIR = EISODOS_ROOT / "target" / "bench_gen"
BENCHED_CRATE_COPY_DIR_NAME = "benched_crate_src"

# ---------------------------------------------------------------------------
# CLI / entry helpers
# ---------------------------------------------------------------------------

def _parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate and build Eisodos benchmarks.")
    p.add_argument("--crate", required=True, type=pathlib.Path, nargs="+", help="Crate(s) or dirs to search.")
    p.add_argument(
        "--entrypoints",
        type=str,
        default="pinocchio",
        help="Comma-separated list of entrypoint implementations to benchmark.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Crate / benchmark processing helpers
# ---------------------------------------------------------------------------

def _copy_and_prepare_benched_crate(crate_dir: pathlib.Path, entrypoint_name: str, dest_dir: pathlib.Path) -> None:
    """Copy *crate_dir* into *dest_dir* and apply import rewrites etc."""
    print(f"Copying benchmarked crate from {crate_dir} to {dest_dir}")
    shutil.copytree(
        crate_dir, dest_dir, ignore=shutil.ignore_patterns("target"), dirs_exist_ok=True
    )

    manifest_path = dest_dir / "Cargo.toml"
    if manifest_path.is_file():
        try:
            manifest = toml.loads(manifest_path.read_text("utf-8"))
            changed = False
            if "workspace" in manifest:
                manifest.pop("workspace", None)
                changed = True
            lib_table = manifest.setdefault("lib", {})
            crate_types = lib_table.get("crate-type")
            if crate_types is None:
                lib_table["crate-type"] = ["cdylib", "lib"]
                changed = True
            elif isinstance(crate_types, str):
                lib_table["crate-type"] = [crate_types, "cdylib", "lib"]
                changed = True
            elif isinstance(crate_types, list):
                for t in ("cdylib", "lib"):
                    if t not in crate_types:
                        crate_types.append(t)
                        changed = True
            if changed:
                manifest_path.write_text(toml.dumps(manifest), "utf-8")
        except Exception as exc:
            print_warning(f"Failed to sanitise manifest {manifest_path}: {exc}")

    # Rewrite imports + ensure deps
    rewrite_sources_for_entrypoint(entrypoint_name, dest_dir)

    # Ensure crates expose the appropriate features for each entrypoint
    try:
        manifest_data = toml.load(manifest_path)
        feats = manifest_data.setdefault("features", {})
        
        if entrypoint_name in ["pinocchio", "solana-nostd-entrypoint"] and "no_std" not in feats:
            feats["no_std"] = []
        elif entrypoint_name == "pinocchio-std" and "std" not in feats:
            feats["std"] = []
        elif entrypoint_name in ["solana-program", "solana-program-mono"] and "std" not in feats:
            feats["std"] = []
        elif entrypoint_name == "solana-nostd-entrypoint" and "no_std" not in feats:
            feats["no_std"] = []
        manifest_path.write_text(toml.dumps(manifest_data), "utf-8")
    except Exception:
        pass


def _build_runner_workspace(
    bench_id: str,
    crate_name: str,
    entrypoint_name: str,
    entrypoint_features: List[str],
    complete_ws_dep_block: str,
    bench_module: str,
    bench_func: str,
    rust_import_crate_name: str,
) -> pathlib.Path:
    """Create a temporary workspace for a single benchmark/entrypoint combo and return its path."""
    temp_dir_name = f"{bench_id}_{entrypoint_name}_{'_'.join(entrypoint_features) if entrypoint_features else 'nofeatures'}"
    temp_project_dir = TARGET_DIR / temp_dir_name
    temp_src_dir = temp_project_dir / "src"
    benched_crate_dest_path = temp_project_dir / BENCHED_CRATE_COPY_DIR_NAME

    shutil.rmtree(temp_project_dir, ignore_errors=True)
    temp_project_dir.mkdir(parents=True)

    # 1. Copy benched crate & apply rewrites (actual copy handled by caller)

    # 2. Generate runner Cargo.toml and lib.rs from templates
    cargo_tmpl = {
        "pinocchio": "template.pinocchio.cargo.toml",
        "solana-program": "template.solana_program.cargo.toml",
        "solana-program-mono": "template.solana_program_mono.cargo.toml",
        "solana-nostd-entrypoint": "template.solana_nostd_entrypoint.cargo.toml",
        "pinocchio-std": "template.pinocchio.cargo.toml",
    }[entrypoint_name]
    main_tmpl = cargo_tmpl.replace("cargo.toml", "lib.rs")

    cargo_template_path = TEMPLATES_DIR / cargo_tmpl
    main_template_path = TEMPLATES_DIR / main_tmpl

    replacements = {
        "%%BENCH_ID%%": temp_dir_name,
        "%%BENCHED_CRATE_COPY_DIR_NAME%%": BENCHED_CRATE_COPY_DIR_NAME,
        "%%WORKSPACE_DEPENDENCIES_BLOCK%%": complete_ws_dep_block,
        "%%CRATE_NAME%%": crate_name,
        "%%CRATE_FEATURES%%": format_features(entrypoint_features),
        "%%ENTRYPOINT_SDK_DEPENDENCY_LINE%%": ENTRYPOINT_DEPS[entrypoint_name],
        "%%RUST_IMPORT_CRATE_NAME%%": rust_import_crate_name,
        "%%BENCHMARK_FUNCTION_MODULE%%": bench_module,
        "%%BENCHMARK_FUNCTION_NAME%%": bench_func,
    }

    cargo_content = replace_placeholders(cargo_template_path.read_text(), replacements)
    (temp_project_dir / "Cargo.toml").write_text(cargo_content)
    temp_src_dir.mkdir()
    main_content = replace_placeholders(main_template_path.read_text(), replacements)
    (temp_src_dir / "lib.rs").write_text(main_content)

    # stub env_logger crate
    noop_dir = temp_project_dir / "noop_env_logger" / "src"
    noop_dir.mkdir(parents=True, exist_ok=True)
    (noop_dir.parent / "Cargo.toml").write_text(
        """[package]
name = "env_logger"
version = "0.10.2"
edition = "2021"
[lib]
crate-type = ["rlib"]
[dependencies]
log = { version = "0.4", default-features = false }
"""
    )
    (noop_dir / "lib.rs").write_text("#![no_std]\npub use log::*;\n")

    return temp_project_dir, benched_crate_dest_path


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def run() -> None:
    args = _parse_cli()
    requested_entrypoints = {ep.strip().lower() for ep in args.entrypoints.split(",") if ep.strip()}
    if not requested_entrypoints:
        requested_entrypoints = {"pinocchio"}

    print(f"Requested entrypoints: {', '.join(sorted(requested_entrypoints))}\n")

    crates_to_process: List[pathlib.Path] = []
    for p in args.crate:
        crates_to_process.extend(discover_crates(p))

    if not crates_to_process:
        print_error("No valid crates found to process")
        sys.exit(1)

    print_section("Crates to process:")
    for c in crates_to_process:
        print(f" - {c}")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    all_results: List[Dict[str, Any]] = []
    built_artifacts: List[pathlib.Path] = []

    ws_dep_block = get_workspace_dependencies_block(["pinocchio"])

    if "pinocchio-std" in requested_entrypoints:
        # strip any existing pinocchio line
        ws_dep_block = "\n".join([
            ln for ln in ws_dep_block.splitlines() if not ln.strip().startswith("pinocchio =")
        ]) or "[workspace.dependencies]"
        pin_path = pathlib.Path(__file__).parent.parent / "sdk" / "pinocchio"
        ws_dep_block += """
pinocchio = { version = "0.8", git = "https://github.com/rustopian/pinocchio.git", branch = "rustopian/slot-hashes-sysvar", default-features = false, features = [\"std\"] }"""
    # If only pinocchio requested (no std), the original block already correct.

    for crate_dir in crates_to_process:
        print_section(f"\n=== Processing crate: {crate_dir} ===")
        crate_name = get_package_name_from_manifest(crate_dir) or crate_dir.name

        config_path = crate_dir / "eisodos_benchmarks.toml"
        try:
            config = toml.loads(config_path.read_text("utf-8"))
        except Exception as exc:
            print_error(f"Failed to parse {config_path}: {exc}")
            continue

        for bench_cfg in config.get("benchmark", []):
            bench_id = bench_cfg.get("id")
            func_path = bench_cfg.get("function")
            entrypoints = bench_cfg.get("entrypoints", [])
            feats_cfg = bench_cfg.get("features", [])
            if not bench_id or not func_path:
                print_warning(f"Skipping invalid benchmark config: {bench_cfg}")
                continue
            crate_mod, bench_mod, bench_fn = parse_function_path(func_path)

            for ep_cfg in entrypoints:
                # Determine if this benchmark should run under current request set.
                if ep_cfg in requested_entrypoints:
                    ep_runtime = ep_cfg
                elif ep_cfg == "pinocchio" and "pinocchio-std" in requested_entrypoints:
                    ep_runtime = "pinocchio-std"  # alias: run pinocchio benches in std mode
                else:
                    continue

                print_subsection(f"--> Benchmark {bench_id} | entrypoint {ep_runtime}")

                ep_feats = next((fc.get("features", []) for fc in feats_cfg if fc.get("entrypoint") == ep_cfg), [])

                # Drop features not declared in the benched crate's manifest to avoid build failures
                try:
                    manifest_feats = list(
                        toml.loads((crate_dir / "Cargo.toml").read_text("utf-8")).get("features", {}).keys()
                    )
                except Exception:
                    manifest_feats = []

                valid_ep_feats = [f for f in ep_feats if f in manifest_feats]
                if ep_feats and not valid_ep_feats:
                    print_warning(
                        f"Requested features {ep_feats} for {ep_runtime} not present in crate; omitting."
                    )
                ep_feats = valid_ep_feats

                # Clean feature list & auto-add
                if ep_runtime == "pinocchio":
                    if "std" in ep_feats:
                        ep_feats.remove("std")
                    if "no_std" not in ep_feats:
                        ep_feats.append("no_std")
                elif ep_runtime == "pinocchio-std":
                    ep_feats = [f for f in ep_feats if f != "no_std"]
                    if "std" not in ep_feats:
                        ep_feats.append("std")
                elif ep_runtime in ["solana-program", "solana-program-mono"] and "std" not in ep_feats:
                    ep_feats.append("std")
                elif ep_runtime == "solana-nostd-entrypoint":
                    ep_feats = [f for f in ep_feats if f != "std"]
                    if "no_std" not in ep_feats:
                        ep_feats.append("no_std")

                # 1. Prepare temp workspace
                temp_project_dir, benched_copy_path = _build_runner_workspace(
                    bench_id,
                    crate_name,
                    ep_runtime,
                    ep_feats,
                    ws_dep_block,
                    bench_mod,
                    bench_fn,
                    crate_mod,
                )

                # 2. Copy & rewrite benched crate
                _copy_and_prepare_benched_crate(crate_dir, ep_runtime, benched_copy_path)

                # 3. Build
                artifact, program_id, build_secs, prog_size = run_cargo_build(temp_project_dir)
                if not (artifact and program_id):
                    continue
                print_success(f"Built {artifact}")
                built_artifacts.append(artifact)

                # 4. Execute benchmarks via helper
                results = perform_benchmark_runs(
                    bench_id=bench_id,
                    bench_config=bench_cfg,
                    entrypoint_name=ep_runtime,
                    entrypoint_features=ep_feats,
                    artifact_path=artifact,
                    program_id=program_id,
                    actual_benched_crate_name=crate_name,
                    build_time_seconds=build_secs,
                    program_size_bytes=prog_size,
                    eisodos_root=EISODOS_ROOT,
                )
                all_results.extend(results)

    # -------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------
    if all_results:
        generate_markdown_report(all_results, EISODOS_ROOT / "benchmark_results.md")
        print_console_summary(all_results)
    else:
        print("\nNo benchmark results to report.")

    print_section("\n=== Summary ===")
    if built_artifacts:
        for art in built_artifacts:
            print_success(f"Built artifact: {art}")
    else:
        print("No artifacts were built successfully.") 