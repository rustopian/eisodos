import argparse
import toml
import pathlib
import shutil
import subprocess
import sys
import os
import time # Import time for a small delay

# --- Constants ---
EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKSPACE_ROOT = EISODOS_ROOT.parent # Assumes eisodos is direct child of workspace root
TEMPLATES_DIR = EISODOS_ROOT / "scripts" / "benchmark_templates"
TARGET_DIR = EISODOS_ROOT / "target" / "bench_gen"
BENCHED_CRATE_COPY_DIR_NAME = "benched_crate_src" # Dir name for the copied source

# Placeholder line to find and replace in the template Cargo.toml
PINOCCHIO_PLACEHOLDER_LINE = "pinocchio = { workspace = true }"

# --- Helper Functions ---

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
        print(f"Error parsing function path '{full_path}': {e}", file=sys.stderr)
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
    """Runs cargo-build-sbf in the specified directory."""
    print(f"--- Building benchmark project using cargo-build-sbf in: {temp_project_dir} ---")
    package_name = None
    try:
        with open(temp_project_dir / "Cargo.toml", "r", encoding="utf-8") as f:
            manifest_content = f.read()
        manifest = toml.loads(manifest_content)
        package_name = manifest.get("package", {}).get("name")
    except Exception as e:
        print(f"Warning: Could not determine package name from temp Cargo.toml: {e}", file=sys.stderr)
    
    if not package_name:
        print(f"Error: Cannot determine executable name for build artifact.", file=sys.stderr)
        return None

    try:
        # Use cargo-build-sbf. It implies --release by default or handles it internally.
        build_command = [
            "cargo-build-sbf", 
        ]
        print(f"Running build command: {' '.join(build_command)} in {temp_project_dir}")
        
        result = subprocess.run(
            build_command,
            cwd=temp_project_dir,
            check=True, # Raise exception on non-zero exit code
            capture_output=True,
            text=True,
            encoding='utf-8' 
        )
        print("Build command finished.")
        # print(result.stdout) # Optionally suppress verbose stdout if too noisy
        
        # Optional: Minimal listing if still needed for quick sanity check, otherwise remove.
        # temp_target_dir = temp_project_dir / "target"
        # print(f"--- Listing contents of temporary target directory: {temp_target_dir} ---")
        # if temp_target_dir.is_dir():
        #     for root, dirs, files in os.walk(temp_target_dir):
        #         relative_root = pathlib.Path(root).relative_to(temp_target_dir)
        #         if str(relative_root) == "deploy" and any(f.endswith(".so") for f in files):
        #             print(f"  Found .so in: {relative_root}")
        #             for name in files:
        #                 if name.endswith(".so"):
        #                     print(f"    - {name}")
        # else:
        #     print("  Temporary target directory does not exist.")
        # print("--- End listing ---")

        # cargo-build-sbf places the final deployable .so file in target/deploy/
        canonical_filename_stem = package_name.replace('-', '_')
        expected_filename = f"{canonical_filename_stem}.so"
        artifact_path_str = str(temp_project_dir / "target" / "deploy" / expected_filename)
        print(f"Checking for expected artifact at: {artifact_path_str}")
        
        # No need for time.sleep(0.1) if os.path.exists works reliably now
        # time.sleep(0.1)

        if os.path.exists(artifact_path_str):
            if os.path.isfile(artifact_path_str):
                print(f"  Artifact found: {artifact_path_str}")
                return pathlib.Path(artifact_path_str) 
            else:
                print(f"  Path exists but is NOT a file: {artifact_path_str}", file=sys.stderr)
                return None 
        else:
            print(f"  Artifact NOT found: {artifact_path_str}", file=sys.stderr)
            return None

    except subprocess.CalledProcessError as e:
        print(f"Error building benchmark project in {temp_project_dir}:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return None
    except FileNotFoundError:
         print("Error: 'cargo-build-sbf' command not found. Is the Solana toolchain installed and in PATH?", file=sys.stderr)
         return None
    except Exception as e: # Catch other potential errors
         print(f"An unexpected error occurred during build: {e}", file=sys.stderr)
         return None

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
                 print(f"Warning: Dependency '{name}' requested but not found in [workspace.dependencies] in {root_cargo_path}", file=sys.stderr)
        
        if not deps_to_include:
            # Return just the table header if no deps found/requested
            return "[workspace.dependencies]"
        
        # Format the dependencies into a TOML block
        deps_block_content = format_toml_dict(deps_to_include)
        return f"[workspace.dependencies]\n{deps_block_content}"
             
    except FileNotFoundError:
        print(f"Error: Workspace root Cargo.toml not found at {root_cargo_path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading or parsing workspace root Cargo.toml {root_cargo_path}: {e}", file=sys.stderr)
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
            print(f"Error: Could not find [package].name in {manifest_path}", file=sys.stderr)
            return None
        return package_name
    except FileNotFoundError:
        print(f"Error: Manifest file not found at {manifest_path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading or parsing manifest {manifest_path}: {e}", file=sys.stderr)
        return None

# --- Main Logic ---

def main():
    parser = argparse.ArgumentParser(description="Generate and build Eisodos benchmarks.")
    parser.add_argument(
        "--crate",
        required=True,
        type=pathlib.Path,
        help="Path to the root of the crate containing eisodos_benchmarks.toml"
    )
    args = parser.parse_args()

    crate_dir = args.crate.resolve() # Get absolute path
    config_path = crate_dir / "eisodos_benchmarks.toml"

    if not crate_dir.is_dir():
        print(f"Error: Crate directory not found: {crate_dir}", file=sys.stderr)
        sys.exit(1)

    if not config_path.is_file():
        print(f"Error: eisodos_benchmarks.toml not found in {crate_dir}", file=sys.stderr)
        sys.exit(1)

    # Get the actual package name from the benchmarked crate's manifest
    actual_benched_crate_name = get_package_name_from_manifest(crate_dir)
    if not actual_benched_crate_name:
        sys.exit(1)
    print(f"Found benchmarked crate package name: {actual_benched_crate_name}")

    print(f"Processing benchmarks for crate: {crate_dir}")
    print(f"Reading config: {config_path}")

    # Get the necessary workspace dependency definitions (just pinocchio for now)
    workspace_deps_block = get_workspace_dependencies_block(["pinocchio"]) 
    if not workspace_deps_block:
        sys.exit(1) # Error message printed in helper function
    print(f"Using workspace dependencies block:\n{workspace_deps_block}")

    try:
        # Read the file content as text first
        with open(config_path, "r", encoding="utf-8") as f:
            config_content = f.read()
        # Parse the string content
        config = toml.loads(config_content)
    except Exception as e:
        print(f"Error reading or parsing {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure the base target directory exists
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    built_artifacts = []
    all_benchmark_results = [] # To store results from all runs

    # Process each benchmark definition
    for bench_config in config.get("benchmark", []):
        bench_id = bench_config.get("id")
        function_path = bench_config.get("function")
        entrypoints = bench_config.get("entrypoints", [])
        features_config = bench_config.get("features", []) # List of {entrypoint, features} dicts

        if not bench_id or not function_path:
            print(f"Warning: Skipping benchmark entry missing 'id' or 'function': {bench_config}", file=sys.stderr)
            continue

        # Use crate name from function path ONLY for importing the rust function itself
        rust_import_crate_name, bench_module, bench_func = parse_function_path(function_path)
        if not rust_import_crate_name or not bench_func:
            continue # Skip if parsing failed

        print(f"=== Processing Benchmark: {bench_id} ===")

        # Generate for each specified entrypoint
        for entrypoint_name in entrypoints:
            print(f"---> Entrypoint: {entrypoint_name}")

            # Find features for this specific entrypoint
            entrypoint_features = []
            for fc in features_config:
                if fc.get("entrypoint") == entrypoint_name:
                    entrypoint_features = fc.get("features", [])
                    break # Found the features for this entrypoint

            # Choose template files based on entrypoint
            if entrypoint_name == "pinocchio":
                cargo_template_path = TEMPLATES_DIR / "template.cargo.toml"
                main_template_path = TEMPLATES_DIR / "template.pinocchio.lib.rs"
            # Add elif entrypoint_name == "solana-program": etc. here later
            else:
                print(f"Warning: Entrypoint '{entrypoint_name}' not yet supported. Skipping.", file=sys.stderr)
                continue

            if not cargo_template_path.is_file() or not main_template_path.is_file():
                print(f"Error: Template files not found for entrypoint '{entrypoint_name}'. Skipping.", file=sys.stderr)
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
            except Exception as e:
                print(f"Error copying crate source: {e}", file=sys.stderr)
                continue

            # --- Calculate relative paths --- 
            # Path from temp_project_dir (eisodos/target/bench_gen/...) to eisodos root is 3 levels up
            relative_to_eisodos_root = "../../../"
            relative_eisodos_prog_path = f"{relative_to_eisodos_root}/programs/{entrypoint_name}"
            
            # Prepare placeholder replacements
            replacements = {
                "%%BENCH_ID%%": temp_dir_name,
                "%%BENCHED_CRATE_COPY_DIR_NAME%%": BENCHED_CRATE_COPY_DIR_NAME,
                "%%WORKSPACE_DEPENDENCIES_BLOCK%%": workspace_deps_block,
                "%%EISODOS_PINOCCHIO_PATH%%": relative_eisodos_prog_path, 
                # Use the ACTUAL package name for the dependency key
                "%%CRATE_NAME%%": actual_benched_crate_name, 
                "%%CRATE_FEATURES%%": format_features(entrypoint_features),
                # Use the crate name from the function path for Rust 'use' statements
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
                    if k not in ["%%RUST_IMPORT_CRATE_NAME%%", "%%BENCHMARK_FUNCTION_MODULE%%", "%%BENCHMARK_FUNCTION_NAME%%"]
                }
                cargo_content = replace_placeholders(cargo_content, cargo_replacements)
                (temp_project_dir / "Cargo.toml").write_text(cargo_content)
            except Exception as e:
                print(f"Error processing Cargo template for {temp_dir_name}: {e}", file=sys.stderr)
                continue 

            # Process lib.rs template 
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
                # Write to lib.rs instead of main.rs
                (temp_src_dir / "lib.rs").write_text(main_content)
            except Exception as e:
                print(f"Error processing Rust template for {temp_dir_name}: {e}", file=sys.stderr)
                continue 

            # Build the temporary project workspace
            artifact_path = run_cargo_build(temp_project_dir)
            if artifact_path and artifact_path.is_file():
                 print(f"Successfully built: {artifact_path}")
                 built_artifacts.append(artifact_path)
                 
                 current_run_metrics = {
                     "id": bench_id,
                     "entrypoint": entrypoint_name,
                     "artifact": str(artifact_path),
                 }

                 if entrypoint_name == "pinocchio":
                     print(f"--- Executing Pinocchio benchmark for: {artifact_path} ---")
                     program_id = "Pinocchio1111111111111111111111111111111111"
                     instruction_hex = "00"
                     
                     exec_command = [
                         "cargo", "run",
                         "--bin", "eisodos-bench-executor",
                         "--manifest-path", str(EISODOS_ROOT / "benchmark" / "Cargo.toml"), 
                         "--", 
                         str(artifact_path), program_id, instruction_hex,
                     ]
                     print(f"Executing: {' '.join(exec_command)}")
                     try:
                         exec_result = subprocess.run(
                             exec_command, check=True, capture_output=True, text=True, encoding='utf-8'
                         )
                         print("--- Benchmark Executor Output ---")
                         print(exec_result.stdout)
                         if exec_result.stderr:
                            print("--- Benchmark Executor Stderr ---")
                            print(exec_result.stderr)
                         print("--- End Executor Output ---")

                         # Parse metrics from executor stdout
                         in_metrics_block = False
                         for line in exec_result.stdout.splitlines():
                             if line.strip() == "--- Benchmark Metrics ---":
                                 in_metrics_block = True
                                 continue
                             if line.strip() == "--- End Metrics ---":
                                 in_metrics_block = False
                                 # Assuming one block per run for now, store and break
                                 all_benchmark_results.append(current_run_metrics.copy()) # Add copy for this run
                                 current_run_metrics = { # Reset for next potential block (if any)
                                     "id": bench_id, "entrypoint": entrypoint_name, "artifact": str(artifact_path)
                                 }
                                 continue # Or break if only one metric block expected
                             
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
                                     
                     except subprocess.CalledProcessError as e:
                         print(f"Error executing benchmark for {artifact_path}:", file=sys.stderr)
                         print("Stdout:", e.stdout, file=sys.stderr)
                         print("Stderr:", e.stderr, file=sys.stderr)
                     except Exception as e:
                         print(f"An unexpected error occurred during benchmark execution: {e}", file=sys.stderr)
            else:
                 print(f"Build failed for {temp_project_dir}")

    # --- Generate Markdown Report --- 
    if all_benchmark_results:
        md_path = WORKSPACE_ROOT / "benchmark_results.md" # Place in main workspace root
        print(f"\nGenerating Markdown report: {md_path}")
        with open(md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Eisodos Benchmark Results\n\n")
            # Define headers - adapt based on actual keys collected
            headers = ["ID", "Entrypoint", "BenchmarkName", "MedianComputeUnits", "TotalComputeUnits", "InstructionsExecuted", "Artifact"]
            md_file.write("| " + " | ".join(headers) + " |\n")
            md_file.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            for result in all_benchmark_results:
                row = [str(result.get(h, "N/A")) for h in headers]
                md_file.write("| " + " | ".join(row) + " |\n")
        print(f"Report generated: {md_path}")
    else:
        print("\nNo benchmark results to report.")

    print("\n=== Summary ===")
    if built_artifacts:
        print("Successfully built artifacts:")
        for path in built_artifacts:
            print(f" - {path}")
        print("Note: Execution of these artifacts depends on the entrypoint environment (e.g., native, SVM).")
    else:
        print("No artifacts were built successfully.")


if __name__ == "__main__":
    main() 