#! /usr/bin/env python3

import argparse
import toml
import pathlib
import shutil
import subprocess
import sys
import os
import json
import time
import textwrap
import re

# --- Color Constants ---
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Standard colors
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'

def print_section(message):
    """Print a section header in bright cyan with bold."""
    print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}{message}{Colors.RESET}")

def print_subsection(message):
    """Print a subsection header in cyan."""
    print(f"{Colors.CYAN}{message}{Colors.RESET}")

def print_success(message):
    """Print a success message in green."""
    print(f"{Colors.GREEN}{message}{Colors.RESET}")

def print_warning(message):
    """Print a warning message in yellow."""
    print(f"{Colors.YELLOW}Warning: {message}{Colors.RESET}", file=sys.stderr)

def print_error(message):
    """Print an error message in red."""
    print(f"{Colors.RED}Error: {message}{Colors.RESET}", file=sys.stderr)

def print_result(message):
    """Print a result message in bright green with bold."""
    print(f"{Colors.BRIGHT_GREEN}{Colors.BOLD}{message}{Colors.RESET}")

def print_build_info(message):
    """Print build-related info in blue."""
    print(f"{Colors.BLUE}{message}{Colors.RESET}")

# --- Constants ---
EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKSPACE_ROOT = EISODOS_ROOT
TEMPLATES_DIR = EISODOS_ROOT / "scripts" / "benchmark_templates"
TARGET_DIR = EISODOS_ROOT / "target" / "bench_gen"
BENCHED_CRATE_COPY_DIR_NAME = "benched_crate_src" # Dir name for the copied source

# Placeholder line to find and replace in the template Cargo.toml
PINOCCHIO_PLACEHOLDER_LINE = "pinocchio = { workspace = true }"

# --- Rewrite Matrix for Import Path Translation ---
REWRITE_TABLE = {
    # BUILD TARGET  →  { pattern : replacement }
    "pinocchio": {
        # monolithic sdk
        r"\bsolana_program::":          "pinocchio::",
        # breakout crates
        r"\bsolana_account_info::":     "pinocchio::account_info::",
        r"\bsolana_pubkey::":           "pinocchio::pubkey::",
        r"\bsolana_program_error::":    "pinocchio::program_error::",
        r"\bsolana_entrypoint::":       "pinocchio::",
        r"\bsolana_msg::":              "pinocchio::log::",
        # Handle specific types that may need path changes
        r"\bProgramResult":             "ProgramResult",
        r"\bAccountInfo":               "AccountInfo", 
        r"\bPubkey":                    "Pubkey",
    },
    "solana-program": {  # breakout → breakout, pinocchio → breakout
        r"\bpinocchio::account_info::": "solana_account_info::",
        r"\bpinocchio::pubkey::":       "solana_pubkey::",
        r"\bpinocchio::program_error::": "solana_program_error::",
        r"\bpinocchio::":               "solana_entrypoint::",
        r"\bpinocchio::log::":          "solana_msg::",
        # Keep solana breakout crates as-is (no replacement needed)
    },
    "solana-program-mono": {  # breakout → mono, pinocchio → mono
        r"\bsolana_account_info::":     "solana_program::account_info::",
        r"\bsolana_pubkey::":           "solana_program::pubkey::",
        r"\bsolana_program_error::":    "solana_program::program_error::",
        r"\bsolana_entrypoint::":       "solana_program::entrypoint::",
        r"\bsolana_msg::":              "solana_program::msg::",
        r"\bpinocchio::account_info::": "solana_program::account_info::",
        r"\bpinocchio::pubkey::":       "solana_program::pubkey::",
        r"\bpinocchio::program_error::": "solana_program::program_error::",
        r"\bpinocchio::":               "solana_program::entrypoint::",
        r"\bpinocchio::log::":          "solana_program::msg::",
    },
    "solana-nostd-entrypoint": {
        # Convert to nostd-entrypoint equivalents
        r"\bsolana_account_info::AccountInfo": "solana_nostd_entrypoint::NoStdAccountInfo",
        r"\bpinocchio::account_info::AccountInfo": "solana_nostd_entrypoint::NoStdAccountInfo",
        r"\bsolana_pubkey::":           "solana_pubkey::",
        r"\bpinocchio::pubkey::":       "solana_pubkey::",
        r"\bsolana_program_error::":    "solana_program_error::",
        r"\bpinocchio::program_error::": "solana_program_error::",
        r"\bsolana_entrypoint::ProgramResult":     "solana_program_error::ProgramResult",
        r"\bpinocchio::ProgramResult":            "solana_program_error::ProgramResult",
    },
}

# --- Entrypoint Dependency Definitions ---
ENTRYPOINT_DEPS = {
    "pinocchio": '''pinocchio = { workspace = true, default-features = false }''',
    
    "solana-program": '''solana-account-info = { version = "^2.2", default-features = false }
solana-entrypoint = { package = "solana-program-entrypoint", version = "^2.2", default-features = false }
solana-program-error = { version = "^2.2", default-features = false }
solana-pubkey = { version = "^2.2", default-features = false }
solana-msg = { version = "^2.2", default-features = false }''',
    
    "solana-program-mono": '''solana-program = { version = "^2.2", default-features = false }''',
    
    "solana-nostd-entrypoint": '''solana-nostd-entrypoint = { version = "0.6", default-features = false }
solana-program-error = { version = "^2.2", default-features = false }
solana-pubkey = { version = "^2.2", default-features = false }''',
}

# Define dependencies that must be ensured inside the *benched crate* Cargo.toml for each entrypoint
BENCHED_CRATE_DEPS = {
    "pinocchio": {
        "pinocchio": {
            "version": "0.8",
            "git": "https://github.com/rustopian/pinocchio.git",
            "branch": "rustopian/slot-hashes-sysvar",
            "default-features": False,
        }
    },
    "solana-program": {
        "solana-account-info": {
            "version": "^2.2",
            "default-features": False,
        },
        "solana-entrypoint": {
            "package": "solana-program-entrypoint",
            "version": "^2.2",
            "default-features": False,
        },
        "solana-program-error": {
            "version": "^2.2",
            "default-features": False,
        },
        "solana-pubkey": {
            "version": "^2.2",
            "default-features": False,
        },
        "solana-msg": {
            "version": "^2.2",
            "default-features": False,
        },
    },
    "solana-program-mono": {
        "solana-program": {
            "version": "^2.2",
            "default-features": False,
        }
    },
    "solana-nostd-entrypoint": {
        "solana-nostd-entrypoint": {
            "version": "0.6",
            "default-features": False,
        },
        "solana-program-error": {
            "version": "^2.2",
            "default-features": False,
        },
        "solana-pubkey": {
            "version": "^2.2",
            "default-features": False,
        }
    },
}

# --- Helper Functions ---

def discover_crates(path: pathlib.Path) -> list[pathlib.Path]:
    """
    Discovers crates in a directory by looking for eisodos_benchmarks.toml files.
    If the path points directly to a crate (has eisodos_benchmarks.toml), returns just that path.
    If the path is a directory, searches for subdirectories containing eisodos_benchmarks.toml.
    """
    path = path.resolve()  # Get absolute path
    
    # If the path directly contains eisodos_benchmarks.toml, it's a crate
    if (path / "eisodos_benchmarks.toml").is_file():
        return [path]
    
    # If it's a directory, search for crates in subdirectories
    if path.is_dir():
        crates = []
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "eisodos_benchmarks.toml").is_file():
                crates.append(subdir)
        return sorted(crates)  # Sort for consistent ordering
    
    return []  # Not a crate or directory

def parse_function_path(full_path):
    """Parses 'crate::module::function' into parts."""
    try:
        parts = full_path.split('::')
        if len(parts) < 2:
            raise ValueError("Function path must include crate name and function name.")
        crate_name = parts[0]
        func_name = parts[-1]
        module_path = "::".join(parts[1:-1]) if len(parts) > 2 else "" # Join intermediate parts if they exist
        return crate_name, module_path, func_name
    except Exception as e:
        print_error(f"parsing function path '{full_path}': {e}")
        return None, None, None

def format_features(features_list):
    """Formats a list of features into a TOML-compatible string."""
    if not features_list:
        return ""
    return ", ".join([f'"{feat}"' for feat in features_list])

def replace_placeholders(content, replacements):
    """Replaces placeholders in the template content."""
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, str(value))
    return content

def run_cargo_build(temp_project_dir):
    """Runs cargo-build-sbf and returns artifact path, program ID, build time, and program size."""
    print_build_info(f"--- Building benchmark project using cargo-build-sbf in: {temp_project_dir} ---")
    package_name = None
    program_id = None # Variable to store extracted program ID
    artifact_path = None # Variable to store artifact path
    build_time_seconds = None # Variable to store build time
    program_size_bytes = None # Variable to store program size
    
    try:
        with open(temp_project_dir / "Cargo.toml", "r", encoding="utf-8") as f:
            manifest_content = f.read()
        manifest = toml.loads(manifest_content)
        package_name = manifest.get("package", {}).get("name")
    except Exception as e:
        print_warning(f"Could not determine package name from temp Cargo.toml: {e}")
    
    if not package_name:
        print_error("Cannot determine package name for build artifact.")
        return None, None, None, None # Return None for all values

    canonical_filename_stem = package_name.replace('-', '_')
    expected_so_filename = f"{canonical_filename_stem}.so"
    expected_keypair_filename = f"{canonical_filename_stem}-keypair.json"
    deploy_dir = temp_project_dir / "target" / "deploy"
    expected_so_path = deploy_dir / expected_so_filename
    expected_keypair_path = deploy_dir / expected_keypair_filename

    try:
        build_command = ["cargo-build-sbf"]
        print(f"Running build command: {' '.join(build_command)} in {temp_project_dir}")
        
        # Measure build time
        build_start_time = time.time()
        result = subprocess.run(
            build_command,
            cwd=temp_project_dir,
            env=dict(os.environ, RUSTFLAGS='--cfg getrandom_backend="custom"'),
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8' 
        )
        build_end_time = time.time()
        build_time_seconds = round(build_end_time - build_start_time, 2)
        print_success(f"Build command finished in {build_time_seconds}s.")

        # Check for SO artifact
        print(f"Checking for expected artifact at: {expected_so_path}")
        if os.path.isfile(expected_so_path):
            print_success(f"  Artifact found: {expected_so_path}")
            artifact_path = expected_so_path
            # Get program size
            try:
                program_size_bytes = os.path.getsize(expected_so_path)
                print_success(f"  Program size: {program_size_bytes} bytes ({program_size_bytes / 1024:.1f} KB)")
            except Exception as size_err:
                print_warning(f"Could not determine program size: {size_err}")
                program_size_bytes = None
        else:
            print_error(f"  Artifact NOT found: {expected_so_path}")
            return None, None, None, None

        # Check for Keypair file and extract Program ID using solana-keygen
        print(f"Checking for keypair file at: {expected_keypair_path}")
        if os.path.isfile(expected_keypair_path):
            print(f"  Keypair file found: {expected_keypair_path}")
            try:
                # Use solana-keygen pubkey to get the base58 program ID
                keygen_command = ["solana-keygen", "pubkey", str(expected_keypair_path)]
                print(f"  Running: {' '.join(keygen_command)}")
                keygen_result = subprocess.run(
                    keygen_command,
                    check=True,       # Throw on error
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                program_id = keygen_result.stdout.strip() # Get stdout and remove surrounding whitespace/newline
                if program_id:
                    print_success(f"  Extracted Program ID via solana-keygen: {program_id}")
                else:
                    print_error("  solana-keygen command returned empty output.")

            except subprocess.CalledProcessError as e:
                print_error(f"running solana-keygen for {expected_keypair_path}:")
                print(f"Stderr: {e.stderr}", file=sys.stderr)
            except FileNotFoundError:
                print_error("'solana-keygen' command not found. Is the Solana toolchain installed and in PATH?")
            except Exception as e:
                print_error(f"extracting Program ID via solana-keygen for {expected_keypair_path}: {e}")
        else:
            print_error(f"  Keypair file NOT found: {expected_keypair_path}. Cannot determine Program ID.")

    except subprocess.CalledProcessError as e:
        print_error(f"building benchmark project in {temp_project_dir}:")
        print(e.stderr, file=sys.stderr)
        return None, None, None, None
    except FileNotFoundError:
         print_error("'cargo-build-sbf' command not found. Is the Solana toolchain installed and in PATH?")
         return None, None, None, None
    except Exception as e:
         print_error(f"An unexpected error occurred during build: {e}")
         return None, None, None, None

    # Return the found artifact path, program ID, build time, and program size
    return artifact_path, program_id, build_time_seconds, program_size_bytes

def format_toml_dict(data):
    """ Formats a dictionary into TOML syntax (basic implementation). """
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            items_str = ", ".join([f'{k} = "{v}"' for k, v in value.items()])
            lines.append(f'{key} = {{ {items_str} }}')
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        # Add other types if needed (bool, int, etc.)
        else:
             lines.append(f'{key} = {value}') # Basic fallback 
    return "\n".join(lines)

def get_workspace_dependencies_block(dep_names):
    """Reads the main workspace Cargo.toml and extracts specified dependencies into a TOML block."""
    root_cargo_path = WORKSPACE_ROOT / "Cargo.toml"
    try:
        with open(root_cargo_path, "r", encoding="utf-8") as f:
            root_manifest_content = f.read()
        root_manifest = toml.loads(root_manifest_content)
        
        workspace_deps = root_manifest.get("workspace", {}).get("dependencies", {})
        
        deps_to_include = {}
        for name in dep_names:
            if name in workspace_deps:
                deps_to_include[name] = workspace_deps[name]
            else:
                 print_warning(f"Dependency '{name}' requested but not found in [workspace.dependencies] in {root_cargo_path}")
        
        if not deps_to_include:
            # Return just the table header if no deps found/requested
            return "[workspace.dependencies]"
        
        # Format the dependencies into a TOML block
        deps_block_content = format_toml_dict(deps_to_include)
        return f"[workspace.dependencies]\n{deps_block_content}"
             
    except FileNotFoundError:
        print_error(f"Workspace root Cargo.toml not found at {root_cargo_path}")
        return None
    except Exception as e:
        print_error(f"reading or parsing workspace root Cargo.toml {root_cargo_path}: {e}")
        return None

def get_package_name_from_manifest(crate_dir):
    """Reads the Cargo.toml in the given directory and returns the [package].name."""
    manifest_path = crate_dir / "Cargo.toml"
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_content = f.read()
        manifest = toml.loads(manifest_content)
        package_name = manifest.get("package", {}).get("name")
        if not package_name:
            print_error(f"Could not find [package].name in {manifest_path}")
            return None
        return package_name
    except FileNotFoundError:
        print_error(f"Manifest file not found at {manifest_path}")
        return None
    except Exception as e:
        print_error(f"reading or parsing manifest {manifest_path}: {e}")
        return None

def rewrite_sources_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    """
    Rewrite source files in the copied crate to use the correct import paths
    for the target entrypoint.
    """
    patterns = REWRITE_TABLE.get(entrypoint_name, {})
    if not patterns:
        print(f"No rewrite patterns defined for entrypoint '{entrypoint_name}'. Skipping source rewrite.")
        return
    
    print(f"Rewriting source imports for entrypoint: {entrypoint_name}")
    files_modified = 0
    
    for rust_file in crate_root.rglob("*.rs"):
        try:
            original_content = rust_file.read_text(encoding="utf-8")
            modified_content = original_content
            
            # Apply each pattern replacement
            for pattern, replacement in patterns.items():
                modified_content = re.sub(pattern, replacement, modified_content)
            
            # Only write back if content changed
            if modified_content != original_content:
                rust_file.write_text(modified_content, encoding="utf-8")
                files_modified += 1
                print(f"  Modified: {rust_file.relative_to(crate_root)}")
        
        except Exception as e:
            print_warning(f"Failed to rewrite {rust_file}: {e}")
    
    if files_modified > 0:
        print_success(f"Rewrote imports in {files_modified} source files for '{entrypoint_name}' entrypoint.")
    else:
        print(f"No source files needed import rewriting for '{entrypoint_name}' entrypoint.")

    # After replacements, possibly add pinocchio handlers
    if entrypoint_name == "pinocchio":
        ensure_pinocchio_handlers(crate_root)
    elif entrypoint_name == "solana-nostd-entrypoint":
        ensure_nostd_entrypoint_alias(crate_root)
    # Always ensure manifest deps
    ensure_manifest_deps_for_entrypoint(entrypoint_name, crate_root)

def ensure_pinocchio_handlers(crate_root: pathlib.Path):
    """Ensure crate is #![no_std] and has pinocchio no_allocator/nostd_panic_handler wiring."""
    lib_rs = crate_root / "src" / "lib.rs"
    if not lib_rs.is_file():
        return

    try:
        content = lib_rs.read_text(encoding="utf-8")
        needs_write = False

        # 1. Guarantee #![no_std]
        if "#![no_std]" not in content and "#![cfg_attr(" not in content:
            content = "#![no_std]\n" + content
            needs_write = True

        # 2. Ensure use + macro calls
        if "use pinocchio::{no_allocator, nostd_panic_handler}" not in content:
            content = content.replace("use {", "use pinocchio::{no_allocator, nostd_panic_handler};\nuse {", 1)
            needs_write = True

        # Determine insertion point for macro calls after closing of first use-group ending with '};'
        if "no_allocator!();" not in content or "nostd_panic_handler!();" not in content:
            # Remove any previous wrong macro placement inside use group
            content_lines = content.splitlines()
            content_lines = [l for l in content_lines if not l.strip().startswith("no_allocator!()") and not l.strip().startswith("nostd_panic_handler!()")]
            content = "\n".join(content_lines)

            insert_pos = content.find("};")
            if insert_pos != -1:
                insert_pos += 3  # after '};'
            else:
                # fallback: append after first use line group
                insert_pos = content.find("\n")  # after first line
            macros_to_insert = []
            if "no_allocator!();" not in content:
                macros_to_insert.append("no_allocator!();")
            if "nostd_panic_handler!();" not in content:
                macros_to_insert.append("nostd_panic_handler!();")
            macro_block = "\n" + "\n".join(macros_to_insert) + "\n"
            content = content[:insert_pos] + macro_block + content[insert_pos:]
            needs_write = True

        if needs_write:
            lib_rs.write_text(content, encoding="utf-8")
            print_success("Updated src/lib.rs for pinocchio handlers and no_std")
    except Exception as e:
        print_warning(f"Failed to patch {lib_rs}: {e}")

def ensure_nostd_entrypoint_alias(crate_root: pathlib.Path):
    """Add `as AccountInfo` alias for NoStdAccountInfo if missing."""
    lib_rs = crate_root / "src" / "lib.rs"
    if not lib_rs.is_file():
        return
    try:
        content = lib_rs.read_text(encoding="utf-8")
        if "NoStdAccountInfo as AccountInfo" not in content:
            content = content.replace("NoStdAccountInfo", "NoStdAccountInfo as AccountInfo")
            lib_rs.write_text(content, encoding="utf-8")
            print_success("Added alias `as AccountInfo` for NoStdAccountInfo")
    except Exception as e:
        print_warning(f"Failed to patch alias in {lib_rs}: {e}")

def ensure_manifest_deps_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    """Ensure benched crate Cargo.toml has the deps required for rewritten imports."""
    deps_to_add = BENCHED_CRATE_DEPS.get(entrypoint_name)
    if not deps_to_add:
        return
    manifest_path = crate_root / "Cargo.toml"
    if not manifest_path.is_file():
        return
    try:
        manifest_data = toml.load(manifest_path)
    except Exception as e:
        print_warning(f"Failed to parse manifest {manifest_path}: {e}")
        return

    deps_table = manifest_data.setdefault("dependencies", {})
    changed = False

    # Remove old sdk deps that might conflict
    ALL_KNOWN_SDK_DEPS = [
        "pinocchio",
        "solana-program",
        "solana-account-info",
        "solana-entrypoint",
        "solana-program-error",
        "solana-pubkey",
        "solana-msg",
        "solana-nostd-entrypoint",
    ]
    for key in list(deps_table.keys()):
        if key in ALL_KNOWN_SDK_DEPS:
            deps_table.pop(key)
            changed = True

    # Insert required deps
    for dep_name, dep_info in deps_to_add.items():
        if dep_name not in deps_table:
            deps_table[dep_name] = dep_info
            changed = True

    if changed:
        try:
            manifest_path.write_text(toml.dumps(manifest_data), encoding="utf-8")
            print_success(f"Patched dependencies in benched crate manifest for {entrypoint_name}")
        except Exception as e:
            print_warning(f"Failed to update manifest {manifest_path}: {e}")

# --- Main Logic ---

def main():
    parser = argparse.ArgumentParser(description="Generate and build Eisodos benchmarks.")
    parser.add_argument(
        "--crate",
        required=True,
        type=pathlib.Path,
        nargs='+',
        help="Path(s) to crate(s) or directories containing crates with eisodos_benchmarks.toml"
    )
    parser.add_argument(
        "--entrypoints",
        type=str,
        default="pinocchio",
        help=(
            "Comma-separated list of entrypoint implementations to benchmark "
            "(e.g. 'pinocchio,solana-program,solana-program-mono'). Default: 'pinocchio'"
        ),
    )
    args = parser.parse_args()

    # Parse the entrypoints list provided by the user (deduplicated, lower-cased)
    requested_entrypoints = {
        ep.strip().lower() for ep in args.entrypoints.split(',') if ep.strip()
    }
    if not requested_entrypoints:
        requested_entrypoints = {"pinocchio"}

    print(f"Requested entrypoints to benchmark: {', '.join(sorted(requested_entrypoints))}\n")

    all_benchmark_results = [] # To store results from all runs across all crates
    built_artifacts = []

    # Discover all crates to process
    crates_to_process = []
    for path in args.crate:
        discovered_crates = discover_crates(path)
        if not discovered_crates:
            print(f"Warning: No crates found in {path}", file=sys.stderr)
            continue
        crates_to_process.extend(discovered_crates)

    if not crates_to_process:
        print("Error: No valid crates found to process", file=sys.stderr)
        sys.exit(1)

    print(f"\nFound {len(crates_to_process)} crate(s) to process:")
    for crate_path in crates_to_process:
        print(f" - {crate_path}")
    print()

    # Process each crate
    for crate_dir in crates_to_process:
        config_path = crate_dir / "eisodos_benchmarks.toml"
        print_section(f"\n=== Processing crate: {crate_dir} ===")

        # Get the actual package name from the benchmarked crate's manifest
        actual_benched_crate_name = get_package_name_from_manifest(crate_dir)
        if not actual_benched_crate_name:
            continue # Skip this crate but continue with others
        print(f"Found benchmarked crate package name: {actual_benched_crate_name}")

        # Define the list of ALL workspace dependencies that *might* be needed
        # by the benchmarked crate OR the runner templates across any entrypoint.
        # Only include crates that really live in the workspace. SDK crates from crates.io
        # are added to the runner template with explicit versions instead of `workspace = true`.
        potentially_needed_workspace_deps = [
            "pinocchio",
        ]
        print(f"Fetching definitions for potentially needed workspace deps: {potentially_needed_workspace_deps}")

        # Get the definitions for ALL these potential dependencies from eisodos/Cargo.toml
        complete_workspace_deps_block = get_workspace_dependencies_block(potentially_needed_workspace_deps)
        if not complete_workspace_deps_block:
            print_error(f"Failed to get definitions for workspace dependencies: {potentially_needed_workspace_deps}")
            continue # Skip this crate but continue with others
        print(f"--- Using definitions for all potentially needed workspace dependencies:\n{complete_workspace_deps_block}")

        print(f"Processing benchmarks for crate: {crate_dir}")
        print(f"Reading config: {config_path}")

        try:
            # Read the file content as text first
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()
            # Parse the string content
            config = toml.loads(config_content)
        except Exception as e:
            print_error(f"reading or parsing {config_path}: {e}")
            continue # Skip this crate but continue with others

        # Ensure the base target directory exists
        TARGET_DIR.mkdir(parents=True, exist_ok=True)

        # Process each benchmark definition
        for bench_config in config.get("benchmark", []):
            bench_id = bench_config.get("id")
            function_path = bench_config.get("function")
            entrypoints = bench_config.get("entrypoints", [])
            features_config = bench_config.get("features", []) # List of {entrypoint, features} dicts

            if not bench_id or not function_path:
                print_warning(f"Skipping benchmark entry missing 'id' or 'function': {bench_config}")
                continue

            # Use crate name from function path ONLY for importing the rust function itself
            rust_import_crate_name, bench_module, bench_func = parse_function_path(function_path)
            if not rust_import_crate_name or not bench_func:
                continue # Skip if parsing failed

            print_section(f"=== Processing Benchmark: {bench_id} ===")

            # Generate for each specified entrypoint that the user requested
            for entrypoint_name in entrypoints:
                if entrypoint_name not in requested_entrypoints:
                    # Skip entrypoints that the user did not ask for
                    continue

                print_subsection(f"---> Entrypoint: {entrypoint_name}")

                # Find features for this specific entrypoint
                entrypoint_features_original = []
                for fc in features_config:
                    if fc.get("entrypoint") == entrypoint_name:
                        entrypoint_features_original = fc.get("features", [])
                        break

                # Validate features exist in benched crate; drop missing ones
                benched_manifest_features = []
                try:
                    with open((crate_dir/"Cargo.toml"), "r", encoding="utf-8") as mf:
                        benched_manifest_features = list(toml.loads(mf.read()).get("features", {}).keys())
                except Exception:
                    pass

                entrypoint_features = [f for f in entrypoint_features_original if f in benched_manifest_features]
                if entrypoint_features_original and not entrypoint_features:
                    print_warning(f"Requested features {entrypoint_features_original} for {entrypoint_name} not in crate; omitting.")

                # Choose template files based on entrypoint
                if entrypoint_name == "pinocchio":
                    cargo_template_path = TEMPLATES_DIR / "template.pinocchio.cargo.toml"
                    main_template_path = TEMPLATES_DIR / "template.pinocchio.lib.rs"
                elif entrypoint_name == "solana-program":
                    cargo_template_path = TEMPLATES_DIR / "template.solana_program.cargo.toml"
                    main_template_path = TEMPLATES_DIR / "template.solana_program.lib.rs"
                elif entrypoint_name == "solana-program-mono":
                    cargo_template_path = TEMPLATES_DIR / "template.solana_program_mono.cargo.toml"
                    main_template_path = TEMPLATES_DIR / "template.solana_program_mono.lib.rs"
                elif entrypoint_name == "solana-nostd-entrypoint":
                    cargo_template_path = TEMPLATES_DIR / "template.solana_nostd_entrypoint.cargo.toml"
                    main_template_path = TEMPLATES_DIR / "template.solana_nostd_entrypoint.lib.rs"
                else:
                    print_warning(f"Entrypoint '{entrypoint_name}' not yet supported. Skipping.")
                    continue

                if not cargo_template_path.is_file() or not main_template_path.is_file():
                    print_error(f"Template files not found for entrypoint '{entrypoint_name}' ({cargo_template_path}, {main_template_path}). Skipping.")
                    continue

                # Create unique temp directory name and paths
                temp_dir_name = f"{bench_id}_{entrypoint_name}_{'_'.join(entrypoint_features) if entrypoint_features else 'nofeatures'}"
                temp_project_dir = TARGET_DIR / temp_dir_name
                temp_src_dir = temp_project_dir / "src" # Src dir for the benchmark runner itself
                benched_crate_dest_path = temp_project_dir / BENCHED_CRATE_COPY_DIR_NAME

                print(f"Creating temporary project in: {temp_project_dir}")
                shutil.rmtree(temp_project_dir, ignore_errors=True) # Clean previous run
                temp_project_dir.mkdir(parents=True)

                # --- Copy the benchmarked crate source ---
                try:
                    print(f"Copying benchmarked crate from {crate_dir} to {benched_crate_dest_path}")
                    # Ignore the target directory of the source crate to avoid recursion and large copies
                    ignore_patterns = shutil.ignore_patterns('target')
                    shutil.copytree(crate_dir, benched_crate_dest_path, ignore=ignore_patterns, dirs_exist_ok=True) 

                    # Sanitize the copied crate's Cargo.toml to prevent nested workspace conflicts
                    benched_manifest_path = benched_crate_dest_path / "Cargo.toml"
                    if benched_manifest_path.is_file():
                        try:
                            manifest_text = benched_manifest_path.read_text(encoding="utf-8")
                            manifest_data = toml.loads(manifest_text)

                            # Track whether we make any modifications so we only rewrite the file when needed
                            changed = False

                            # --- Remove nested workspace section if present ---
                            if "workspace" in manifest_data:
                                print(f"Removing [workspace] section from copied crate manifest at {benched_manifest_path}")
                                manifest_data.pop("workspace", None)
                                changed = True

                            # --- Ensure a suitable [lib] section with the required crate-type ---
                            lib_table = manifest_data.get("lib")
                            if lib_table is None:
                                lib_table = {}
                                manifest_data["lib"] = lib_table
                                changed = True

                            crate_types = lib_table.get("crate-type")

                            # Normalize crate_types to a list and guarantee both "cdylib" and "lib" are present
                            if crate_types is None:
                                lib_table["crate-type"] = ["cdylib", "lib"]
                                changed = True
                            else:
                                # Convert single string to list for uniform handling
                                if isinstance(crate_types, str):
                                    crate_types = [crate_types]
                                if isinstance(crate_types, list):
                                    if "cdylib" not in crate_types:
                                        crate_types.append("cdylib")
                                        changed = True
                                    if "lib" not in crate_types:
                                        crate_types.append("lib")
                                        changed = True
                                    lib_table["crate-type"] = crate_types
                                else:
                                    # Unexpected type; overwrite with the desired list
                                    lib_table["crate-type"] = ["cdylib", "lib"]
                                    changed = True

                            # --- Persist manifest only if we actually changed it ---
                            if changed:
                                benched_manifest_path.write_text(toml.dumps(manifest_data), encoding="utf-8")
                        except Exception as sanitize_err:
                            print(f"Warning: Failed to sanitize copied crate manifest {benched_manifest_path}: {sanitize_err}", file=sys.stderr)
                    
                    # --- Rewrite source imports for the target entrypoint ---
                    rewrite_sources_for_entrypoint(entrypoint_name, benched_crate_dest_path)
                    
                except Exception as e:
                    print(f"Error copying crate source: {e}", file=sys.stderr)
                    continue

                # --- Calculate relative paths ---
                # Path from temp_project_dir (eisodos/target/bench_gen/...) to eisodos root is 3 levels up
                relative_to_eisodos_root = "../../../"
                # Use entrypoint_name to build the SDK path dynamically
                relative_eisodos_sdk_path = f"{relative_to_eisodos_root}/programs/{entrypoint_name}"
                
                # Determine SDK dependency line for the runner template using the ENTRYPOINT_DEPS mapping
                entrypoint_sdk_dep_line = ENTRYPOINT_DEPS.get(entrypoint_name)
                if not entrypoint_sdk_dep_line:
                    print_warning(f"No dependency definition found for entrypoint '{entrypoint_name}'. Skipping.")
                    continue

                # Prepare placeholder replacements
                replacements = {
                    "%%BENCH_ID%%": temp_dir_name,
                    "%%BENCHED_CRATE_COPY_DIR_NAME%%": BENCHED_CRATE_COPY_DIR_NAME,
                    "%%WORKSPACE_DEPENDENCIES_BLOCK%%": complete_workspace_deps_block,
                    "%%CRATE_NAME%%": actual_benched_crate_name,
                    "%%CRATE_FEATURES%%": format_features(entrypoint_features),
                    "%%ENTRYPOINT_SDK_DEPENDENCY_LINE%%": entrypoint_sdk_dep_line,
                    "%%RUST_IMPORT_CRATE_NAME%%": rust_import_crate_name,
                    "%%BENCHMARK_FUNCTION_MODULE%%": bench_module,
                    "%%BENCHMARK_FUNCTION_NAME%%": bench_func,
                }

                # Process Cargo.toml template
                try:
                    cargo_content = cargo_template_path.read_text()
                    # Replace placeholders relevant to Cargo.toml
                    cargo_replacements = {
                        k: v for k, v in replacements.items()
                        if k in ["%%BENCH_ID%%", "%%BENCHED_CRATE_COPY_DIR_NAME%%",
                                 "%%WORKSPACE_DEPENDENCIES_BLOCK%%", "%%CRATE_NAME%%",
                                 "%%CRATE_FEATURES%%", "%%ENTRYPOINT_SDK_DEPENDENCY_LINE%%"]
                    }
                    cargo_content = replace_placeholders(cargo_content, cargo_replacements)
                    (temp_project_dir / "Cargo.toml").write_text(cargo_content)
                except Exception as e:
                    print(f"Error processing Cargo template for {temp_dir_name}: {e}", file=sys.stderr)
                    continue

                # Process lib.rs template (for runner)
                try:
                    # Create the src dir for the runner *after* Cargo.toml is placed
                    temp_src_dir.mkdir()
                    main_content = main_template_path.read_text()
                    # Only replace placeholders relevant to lib.rs
                    main_replacements = {
                        k: v for k, v in replacements.items()
                        if k in ["%%RUST_IMPORT_CRATE_NAME%%", "%%BENCHMARK_FUNCTION_MODULE%%", "%%BENCHMARK_FUNCTION_NAME%%"]
                    }
                    main_content = replace_placeholders(main_content, main_replacements)
                    (temp_src_dir / "lib.rs").write_text(main_content)

                    # --- Add noop_env_logger stub crate ---
                    noop_dir = temp_project_dir / "noop_env_logger" / "src"
                    noop_dir.mkdir(parents=True, exist_ok=True)
                    (noop_dir.parent / "Cargo.toml").write_text(
                        '[package]\nname = "env_logger"\nversion = "0.10.2"\nedition = "2021"\n[lib]\ncrate-type = ["rlib"]\n[dependencies]\nlog = { version = "0.4", default-features = false }\n'
                    )
                    (noop_dir / "lib.rs").write_text('#![no_std]\npub use log::*;\n')
                except Exception as e:
                    print(f"Error processing Rust template for {temp_dir_name}: {e}", file=sys.stderr)
                    continue 

                # Build the temporary project workspace
                artifact_path, program_id, build_time_seconds, program_size_bytes = run_cargo_build(temp_project_dir)

                # Check if build was successful AND program_id was found
                if artifact_path and artifact_path.is_file() and program_id:
                     print(f"Successfully built: {artifact_path}")
                     print(f"Using Program ID: {program_id}")
                     built_artifacts.append(artifact_path)
                     
                     # Check for account_setups in bench_config
                     instruction_payload = bench_config.get("instruction_payload") # NEW: Get instruction_payload
                     runs_to_perform = []

                     # NEW: Helper function to serialize instruction_payload
                     def serialize_payload(payload, bench_id_for_warning):
                        if not payload or not isinstance(payload, dict):
                            print(f"Warning: instruction_payload for {bench_id_for_warning} is malformed. Using default byte.", file=sys.stderr)
                            return b"\xff" 

                        tag = payload.get("tag")
                        if tag is None: 
                            print(f"Warning: instruction_payload missing 'tag' for {bench_id_for_warning}. Using default byte.", file=sys.stderr)
                            return b"\xff"
                        
                        data_bytes = bytearray()
                        data_bytes.append(int(tag)) 

                        if "amount" in payload: # For Transfer
                            amount = payload.get("amount", 0)
                            data_bytes.extend(int(amount).to_bytes(8, byteorder='little'))
                        elif "lamports" in payload and "space" in payload: # For CreateAccount
                            lamports = payload.get("lamports", 0)
                            space = payload.get("space", 0)
                            data_bytes.extend(int(lamports).to_bytes(8, byteorder='little'))
                            data_bytes.extend(int(space).to_bytes(8, byteorder='little'))
                        # Add other payload types as needed
                        
                        return bytes(data_bytes)

                     if instruction_payload:
                        # If instruction_payload is defined, it dictates the instruction data
                        # and implies a single run configuration for that specific payload.
                        num_accounts_for_payload_run = 1 # Default, can be overridden
                        # Determine num_accounts based on benchmark type hint in id
                        if "create_account" in bench_id:
                            num_accounts_for_payload_run = 3 # Funder, New Account, System Program
                        elif "transfer" in bench_id:
                            num_accounts_for_payload_run = 3 # Source, Destination, System Program
                        elif "log" in bench_id: # Log bench doesn't strictly need accounts for its operation
                            num_accounts_for_payload_run = 0 
                        elif "slot_hashes" in bench_id:
                            # Set up SlotHashes sysvar account with proper ID and mock data
                            # Use the actual sysvar program ID: Sysvar1111111111111111111111111111111111111
                            num_accounts_for_payload_run = 1 # Just the SlotHashes sysvar account
                        # For account-read, it might use instruction_payload if we extend it, or stick to account_setups
                        
                        serialized_data = serialize_payload(instruction_payload, bench_id)
                        runs_to_perform.append({
                            "num_accounts": num_accounts_for_payload_run, 
                            "instruction_hex": serialized_data.hex(),
                            "run_id_suffix": "_custom_payload" 
                        })
                     else: # Fallback to account_setups or default if no instruction_payload
                        account_setups = bench_config.get("account_setups")
                        if account_setups and isinstance(account_setups, list):
                            for setup in account_setups:
                                count = setup.get("count")
                                if isinstance(count, int) and 0 < count <= 255:
                                    runs_to_perform.append({
                                        "num_accounts": count, 
                                        "instruction_hex": f"{count:02x}",
                                        "run_id_suffix": f"_accounts_{count}"
                                    })
                                else:
                                    print(f"Warning: Invalid count in account_setups for {bench_id}: {setup}. Skipping.", file=sys.stderr)
                        else:
                            # Default run if neither instruction_payload nor account_setups are present
                            runs_to_perform.append({
                                "num_accounts": 1, 
                                "instruction_hex": "01", # Default instruction_hex (e.g. for simple ping or old account-read)
                                "run_id_suffix": "_default_run"
                            })

                     for run_params in runs_to_perform:
                         num_accounts_to_provide = run_params["num_accounts"] # This is now more of a hint or legacy value
                         instruction_hex = run_params["instruction_hex"]

                         # Update current_run_metrics for this specific run
                         current_run_metrics = {
                             "id": f"{bench_id}{run_params['run_id_suffix']}", 
                             "entrypoint": entrypoint_name,
                             "features": entrypoint_features,
                             "artifact": str(artifact_path),
                             "program_id": program_id,
                             "AccountsProcessed": num_accounts_to_provide, # Metric
                             "crate": actual_benched_crate_name,
                             # Derive instruction name heuristically from bench_id
                             "instruction": (
                                 "create_account" if "create_account" in bench_id else
                                 "transfer" if "transfer" in bench_id else
                                 "ping" if "ping" in bench_id else
                                 "log" if "log" in bench_id else bench_id
                             ),
                             # NEW: Add build time and program size metrics
                             "BuildTimeSeconds": build_time_seconds,
                             "ProgramSizeBytes": program_size_bytes,
                         }

                         print_subsection(f"=== Starting benchmark run: {current_run_metrics['id']} ===")
                         print(f"--- Preparing to execute for {num_accounts_to_provide} account(s), instruction_hex: {instruction_hex} ---")
                         if entrypoint_name == "pinocchio":
                             print_build_info(f"--- Executing Pinocchio benchmark for: {artifact_path} ---")
                         elif entrypoint_name == "solana-program":
                             print_build_info(f"--- Executing Solana benchmark for: {artifact_path} ---")
                         elif entrypoint_name == "solana-program-mono":
                             print_build_info(f"--- Executing Solana (mono) benchmark for: {artifact_path} ---")
                         elif entrypoint_name == "solana-nostd-entrypoint":
                             print_build_info(f"--- Executing Solana NoStd Entrypoint benchmark for: {artifact_path} ---")
                         else:
                             print_warning(f"Unknown entrypoint {entrypoint_name} for execution.")
                             continue # Skip execution if entrypoint unknown

                         # NEW: Construct account_spec arguments for the executor
                         account_spec_args = []
                         if instruction_payload: 
                             if "create_account" in bench_id: 
                                 account_spec_args.extend([
                                     "--account-spec", "funder:funder_key:true:true:10000000000:0:system",
                                     "--account-spec", f"new_account:new_account_key:true:true:0:0:system",
                                     "--account-spec", "system_program:system_key:false:false:0:0:system"
                                 ])
                             elif "transfer" in bench_id:
                                 account_spec_args.extend([
                                     "--account-spec", "source:source_key:true:true:20000000000:0:system", # Ensure enough lamports
                                     "--account-spec", "destination:dest_key:false:true:0:0:system",
                                     "--account-spec", "system_program:system_key:false:false:0:0:system"
                                 ])
                             elif "log" in bench_id:
                                 pass # Log typically needs no accounts for the instruction itself
                             elif "slot_hashes" in bench_id:
                                 # Set up SlotHashes sysvar account with proper ID and mock data
                                 # Use the actual sysvar program ID: Sysvar1111111111111111111111111111111111111
                                 account_spec_args.extend([
                                     "--account-spec", "slot_hashes:SysvarS1otHashes111111111111111111111111111:false:false:1:20488:Sysvar1111111111111111111111111111111111111"
                                 ])
                             # Add other specific setups as new benchmark types are added
                         elif account_setups: # Logic for account_setups (e.g. account-read)
                             # The executor has a fallback for num_accounts if instruction_data is the old default "01"
                             # For more complex account_setups not fitting the new spec, this part might need adjustment
                             # or those benchmarks refactored to use instruction_payload and account_specs.
                             # For now, we'll rely on the executor's fallback for simple num_account cases.
                             pass # No specific account_spec_args, executor will use its default for num_accounts
                         else: # Default run (e.g. ping, or simple log with default instruction)
                             pass # No specific account_spec_args, executor handles zero/default accounts

                         exec_command = [
                             "cargo", "run",
                             "-p", "eisodos", # Specify the package name from benchmark/Cargo.toml
                             "--bin", "eisodos-bench-executor", 
                             "--", 
                             str(artifact_path), 
                             program_id, 
                             "--instruction-data", instruction_hex, 
                         ] + account_spec_args

                         print(f"Executing: {' '.join(exec_command)}")
                         try:
                             exec_result = subprocess.run(
                                 exec_command, 
                                 cwd=EISODOS_ROOT, # Ensure command is run from workspace root
                                 check=True, 
                                 capture_output=True, 
                                 text=True, 
                                 encoding='utf-8'
                             )
                             print("--- Benchmark Executor Output ---")
                             print(exec_result.stdout)
                             if exec_result.stderr:
                                print("--- Benchmark Executor Stderr (for metrics check) ---")
                                print(exec_result.stderr)
                             print("--- End Executor Output ---")

                             # Parse metrics from executor stdout
                             in_metrics_block = False
                             metrics_found_in_stdout = False
                             for line in exec_result.stdout.splitlines():
                                 if line.strip() == "--- Benchmark Metrics ---":
                                     in_metrics_block = True
                                     continue
                                 if line.strip() == "--- End Metrics ---":
                                     in_metrics_block = False
                                     metrics_found_in_stdout = True
                                     break  # Found metrics in stdout, stop parsing
                                 
                                 if in_metrics_block:
                                     parts = line.split(":", 1)
                                     if len(parts) == 2:
                                         key = parts[0].strip()
                                         value = parts[1].strip()
                                         # Convert to int if possible
                                         try:
                                             current_run_metrics[key] = int(value)
                                         except ValueError:
                                             current_run_metrics[key] = value
                             
                             # Fallback: if no metrics were captured, try Mollusk markdown
                             if not metrics_found_in_stdout and "MedianComputeUnits" not in current_run_metrics:
                                 # Look for markdown generated by Mollusk
                                 md_path = EISODOS_ROOT / "benchmark" / "benches" / "compute_units.md"
                                 if md_path.is_file():
                                    print(f"Fallback: Looking for benchmark results in {md_path}")
                                    print(f"Searching for benchmark matching: {current_run_metrics['id']}")
                                    try:
                                        # Parse the benchmark ID to extract key components
                                        benchmark_id = current_run_metrics["id"]
                                        # Extract the base benchmark name (e.g., "ping_example_pinocchio")
                                        base_name = benchmark_id.split("_default_run")[0].split("_accounts_")[0].split("_custom_payload")[0]
                                        entrypoint = current_run_metrics["entrypoint"]
                                        
                                        print(f"  Looking for base name: '{base_name}' with entrypoint: '{entrypoint}'")
                                        
                                        with open(md_path, "r", encoding="utf-8") as md_f:
                                            found_match = False
                                            for md_line in md_f:
                                                md_line = md_line.strip()
                                                if md_line.startswith("|") and not md_line.startswith("| ---") and "|" in md_line[1:]:
                                                    cols = [c.strip() for c in md_line.strip("|").split("|")]
                                                    if len(cols) >= 2:
                                                        bench_name = cols[0]
                                                        print(f"  Checking: '{bench_name}'")
                                                        # Match based on base name and entrypoint
                                                        if (base_name in bench_name and 
                                                            (entrypoint.replace("-", "_") in bench_name or entrypoint in bench_name)):
                                                            # Found the relevant row
                                                            print(f"  Found match: {bench_name} -> {cols[1]} CUs")
                                                            try:
                                                                cu_val = int(cols[1].replace(",", ""))
                                                                current_run_metrics["BenchmarkName"] = bench_name
                                                                current_run_metrics["MedianComputeUnits"] = cu_val
                                                                found_match = True
                                                                break  # Found a match, stop searching
                                                            except ValueError:
                                                                print(f"  Failed to parse CU value: {cols[1]}")
                                        if not found_match:
                                            print(f"  No matching benchmark found for '{base_name}' with entrypoint '{entrypoint}'")
                                    except Exception as md_err:
                                        print_warning(f"Failed to parse Mollusk markdown {md_path}: {md_err}")
                             
                             # Store the result if we have compute units data (either from stdout or markdown fallback)
                             if "MedianComputeUnits" in current_run_metrics:
                                 print_result(f"Storing result for: {current_run_metrics['id']} -> {current_run_metrics['MedianComputeUnits']} CUs")
                                 all_benchmark_results.append(current_run_metrics.copy())
                             else:
                                 print(f"No compute unit data found for: {current_run_metrics['id']}")
                         except subprocess.CalledProcessError as e:
                             print_error(f"executing benchmark for {artifact_path}:")
                             print("Stdout:", e.stdout, file=sys.stderr)
                             print("Stderr:", e.stderr, file=sys.stderr)
                         except Exception as e:
                             print_error(f"An unexpected error occurred during benchmark execution: {e}")
                elif artifact_path and artifact_path.is_file() and not program_id:
                    print_warning(f"Build successful but failed to extract Program ID for {artifact_path}. Skipping execution.")
                    # Optionally add to results with a 'failed_execution' status
                else:
                     print(f"Build failed for {temp_project_dir}")

    # --- Generate Markdown Report --- 
    if all_benchmark_results:
        md_path = WORKSPACE_ROOT / "benchmark_results.md"
        print_success(f"\nGenerating Markdown report: {md_path}")
        with open(md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Eisodos Benchmark Results\n\n")
            # Define headers - Added Build Time and Program Size
            headers = ["ID", "Entrypoint", "Features", "AccountsProcessed", "BuildTimeSeconds", "ProgramSizeBytes", "BenchmarkName", "MedianComputeUnits", "TotalComputeUnits", "InstructionsExecuted", "Program ID", "Artifact"]
            md_file.write("| " + " | ".join(headers) + " |\n")
            md_file.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            row_lines = []  # Collect rows for console output
            for result in all_benchmark_results:
                # Prepare a display-friendly mapping keyed by our headers
                features_val = result.get("features", [])
                if isinstance(features_val, list):
                    features_val = ", ".join(features_val) if features_val else "none"

                # Format program size for better readability
                program_size_bytes = result.get("ProgramSizeBytes", "N/A")
                if isinstance(program_size_bytes, (int, float)) and program_size_bytes is not None:
                    program_size_display = f"{program_size_bytes} ({program_size_bytes / 1024:.1f} KB)"
                else:
                    program_size_display = "N/A"

                display_map = {
                    "ID": result.get("id", "N/A"),
                    "Entrypoint": result.get("entrypoint", "N/A"),
                    "Features": features_val,
                    "AccountsProcessed": result.get("AccountsProcessed", "N/A"),
                    "BuildTimeSeconds": result.get("BuildTimeSeconds", "N/A"),
                    "ProgramSizeBytes": program_size_display,
                    "BenchmarkName": result.get("BenchmarkName", "N/A"),
                    "MedianComputeUnits": result.get("MedianComputeUnits", "N/A"),
                    "TotalComputeUnits": result.get("TotalComputeUnits", "N/A"),
                    "InstructionsExecuted": result.get("InstructionsExecuted", "N/A"),
                    "Program ID": result.get("program_id", "N/A"),
                    "Artifact": result.get("artifact", "N/A"),
                }

                # Shorten Program ID for readability
                pid_val = display_map["Program ID"]
                if isinstance(pid_val, str) and len(pid_val) > 8:
                    display_map["Program ID"] = f"{pid_val[:4]}...{pid_val[-4:]}"

                row = [str(display_map[h]) for h in headers]
                row_markdown = "| " + " | ".join(row) + " |"
                md_file.write(row_markdown + "\n")
                row_lines.append(row_markdown)
        print_success(f"Report generated: {md_path}")

        # Console summary in simplified format
        print_section("\n=== Benchmark Summary ===")
        simple_headers = ["crate", "instruction", "entrypoint", "build_time", "program_size", "CUs"]

        # Define column widths for proper alignment
        col_widths = [12, 12, 20, 12, 14, 8]
        
        def wrap_cell_content(content, width):
            """Wrap cell content to fit within the specified width."""
            if not content or content == "N/A":
                return [content] if content else [""]
            return textwrap.wrap(str(content), width=width) or [str(content)]
        
        def print_multiline_row(row_values, col_widths):
            """Print a table row that can span multiple lines."""
            # Wrap each cell's content
            wrapped_cells = []
            max_lines = 1
            
            for value, width in zip(row_values, col_widths):
                wrapped = wrap_cell_content(value, width)
                wrapped_cells.append(wrapped)
                max_lines = max(max_lines, len(wrapped))
            
            # Print each line of the row
            for line_idx in range(max_lines):
                line_parts = []
                for cell_lines, width in zip(wrapped_cells, col_widths):
                    if line_idx < len(cell_lines):
                        content = cell_lines[line_idx]
                    else:
                        content = ""  # Empty content for cells that don't span this many lines
                    line_parts.append(f"{content:<{width}}")
                print("| " + " | ".join(line_parts) + " |")

        # Print headers
        print_multiline_row(simple_headers, col_widths)
        
        # Print separator
        separator_parts = ["-" * w for w in col_widths]
        print("| " + " | ".join(separator_parts) + " |")

        # Print each result row with wrapping
        for result in all_benchmark_results:
            cu = result.get("MedianComputeUnits", "N/A")
            build_time = result.get("BuildTimeSeconds", "N/A")
            if isinstance(build_time, (int, float)):
                build_time = f"{build_time:.2f}s"
            
            program_size = result.get("ProgramSizeBytes", "N/A") 
            if isinstance(program_size, (int, float)):
                program_size = f"{program_size / 1024:.1f}KB"
            
            # Format values for display (no truncation)
            values = [
                result.get('crate', 'N/A'),
                result.get('instruction', 'N/A'),
                result.get('entrypoint', 'N/A'),
                str(build_time),
                str(program_size),
                str(cu)
            ]
            
            print_multiline_row(values, col_widths)
    else:
        print("\nNo benchmark results to report.")

    print_section("\n=== Summary ===")
    if built_artifacts:
        print_success("Successfully built artifacts:")
        for path in built_artifacts:
            print_success(f" - {path}")
        print("Note: Execution of these artifacts depends on the entrypoint environment (e.g., native, SVM).")
    else:
        print("No artifacts were built successfully.")


if __name__ == "__main__":
    main() 