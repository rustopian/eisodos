import argparse
import toml
import pathlib
import shutil
import subprocess
import sys
import os
import json
import time

# --- Constants ---
EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKSPACE_ROOT = EISODOS_ROOT
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
    """Runs cargo-build-sbf and returns artifact path and program ID."""
    print(f"--- Building benchmark project using cargo-build-sbf in: {temp_project_dir} ---")
    package_name = None
    program_id = None # Variable to store extracted program ID
    artifact_path = None # Variable to store artifact path
    
    try:
        with open(temp_project_dir / "Cargo.toml", "r", encoding="utf-8") as f:
            manifest_content = f.read()
        manifest = toml.loads(manifest_content)
        package_name = manifest.get("package", {}).get("name")
    except Exception as e:
        print(f"Warning: Could not determine package name from temp Cargo.toml: {e}", file=sys.stderr)
    
    if not package_name:
        print(f"Error: Cannot determine package name for build artifact.", file=sys.stderr)
        return None, None # Return None for both path and ID

    canonical_filename_stem = package_name.replace('-', '_')
    expected_so_filename = f"{canonical_filename_stem}.so"
    expected_keypair_filename = f"{canonical_filename_stem}-keypair.json"
    deploy_dir = temp_project_dir / "target" / "deploy"
    expected_so_path = deploy_dir / expected_so_filename
    expected_keypair_path = deploy_dir / expected_keypair_filename

    try:
        build_command = ["cargo-build-sbf"]
        print(f"Running build command: {' '.join(build_command)} in {temp_project_dir}")
        
        result = subprocess.run(
            build_command,
            cwd=temp_project_dir,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8' 
        )
        print("Build command finished.")

        # Check for SO artifact
        print(f"Checking for expected artifact at: {expected_so_path}")
        if os.path.isfile(expected_so_path):
            print(f"  Artifact found: {expected_so_path}")
            artifact_path = expected_so_path
        else:
            print(f"  Artifact NOT found: {expected_so_path}", file=sys.stderr)
            return None, None

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
                    print(f"  Extracted Program ID via solana-keygen: {program_id}")
                else:
                    print(f"  solana-keygen command returned empty output.", file=sys.stderr)

            except subprocess.CalledProcessError as e:
                print(f"Error running solana-keygen for {expected_keypair_path}:", file=sys.stderr)
                print(f"Stderr: {e.stderr}", file=sys.stderr)
            except FileNotFoundError:
                print("Error: 'solana-keygen' command not found. Is the Solana toolchain installed and in PATH?", file=sys.stderr)
            except Exception as e:
                print(f"Error extracting Program ID via solana-keygen for {expected_keypair_path}: {e}", file=sys.stderr)
        else:
            print(f"  Keypair file NOT found: {expected_keypair_path}. Cannot determine Program ID.", file=sys.stderr)

    except subprocess.CalledProcessError as e:
        print(f"Error building benchmark project in {temp_project_dir}:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return None, None
    except FileNotFoundError:
         print("Error: 'cargo-build-sbf' command not found. Is the Solana toolchain installed and in PATH?", file=sys.stderr)
         return None, None
    except Exception as e:
         print(f"An unexpected error occurred during build: {e}", file=sys.stderr)
         return None, None

    # Return the found artifact path and program ID (which might be None if keypair failed)
    return artifact_path, program_id

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

    # Define the list of ALL workspace dependencies that *might* be needed
    # by the benchmarked crate OR the runner templates across any entrypoint.
    potentially_needed_workspace_deps = ["pinocchio", "solana-program", "solana-program-error"]
    print(f"Fetching definitions for potentially needed workspace deps: {potentially_needed_workspace_deps}")

    # Get the definitions for ALL these potential dependencies from eisodos/Cargo.toml
    complete_workspace_deps_block = get_workspace_dependencies_block(potentially_needed_workspace_deps)
    if not complete_workspace_deps_block:
        print(f"Error: Failed to get definitions for workspace dependencies: {potentially_needed_workspace_deps}", file=sys.stderr)
        sys.exit(1)
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
                cargo_template_path = TEMPLATES_DIR / "template.pinocchio.cargo.toml"
                main_template_path = TEMPLATES_DIR / "template.pinocchio.lib.rs"
            elif entrypoint_name == "solana-program":
                cargo_template_path = TEMPLATES_DIR / "template.solana_program.cargo.toml"
                main_template_path = TEMPLATES_DIR / "template.solana_program.lib.rs"
            else:
                print(f"Warning: Entrypoint '{entrypoint_name}' not yet supported. Skipping.", file=sys.stderr)
                continue

            if not cargo_template_path.is_file() or not main_template_path.is_file():
                print(f"Error: Template files not found for entrypoint '{entrypoint_name}' ({cargo_template_path}, {main_template_path}). Skipping.", file=sys.stderr)
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
            # Use entrypoint_name to build the SDK path dynamically
            relative_eisodos_sdk_path = f"{relative_to_eisodos_root}/programs/{entrypoint_name}"
            
            # Determine SDK dependency line for the runner template
            entrypoint_sdk_dep_line = ""
            if entrypoint_name == "pinocchio":
                entrypoint_sdk_dep_line = 'pinocchio = { workspace = true, default-features = false } # For runner template'
            elif entrypoint_name == "solana-program":
                entrypoint_sdk_dep_line = (
                    'solana-program = { workspace = true } # For runner template\n'
                    'solana-program-error = { workspace = true } # For direct ProgramResult import'
                )

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
            except Exception as e:
                print(f"Error processing Rust template for {temp_dir_name}: {e}", file=sys.stderr)
                continue 

            # Build the temporary project workspace
            artifact_path, program_id = run_cargo_build(temp_project_dir)

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
                         "AccountsProcessed": num_accounts_to_provide # Metric for accounts processed by program
                     }

                     print(f"--- Preparing to execute for {num_accounts_to_provide} account(s), instruction_hex: {instruction_hex} ---")
                     if entrypoint_name == "pinocchio":
                         print(f"--- Executing Pinocchio benchmark for: {artifact_path} ---")
                     elif entrypoint_name == "solana-program":
                         print(f"--- Executing Solana benchmark for: {artifact_path} ---")
                     else:
                         print(f"Warning: Unknown entrypoint {entrypoint_name} for execution.", file=sys.stderr)
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
                         for line in exec_result.stdout.splitlines():
                             if line.strip() == "--- Benchmark Metrics ---":
                                 in_metrics_block = True
                                 continue
                             if line.strip() == "--- End Metrics ---":
                                 in_metrics_block = False
                                 # Assuming one block per run for now, store and break
                                 all_benchmark_results.append(current_run_metrics.copy()) # Add copy for this run
                                 current_run_metrics = { # Reset for next potential block (if any)
                                     "id": f"{bench_id}{run_params['run_id_suffix']}",
                                     "entrypoint": entrypoint_name,
                                     "features": entrypoint_features,
                                     "artifact": str(artifact_path)
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
            elif artifact_path and artifact_path.is_file() and not program_id:
                print(f"Build successful but failed to extract Program ID for {artifact_path}. Skipping execution.", file=sys.stderr)
                # Optionally add to results with a 'failed_execution' status
            else:
                 print(f"Build failed for {temp_project_dir}")

    # --- Generate Markdown Report --- 
    if all_benchmark_results:
        md_path = WORKSPACE_ROOT / "benchmark_results.md"
        print(f"\nGenerating Markdown report: {md_path}")
        with open(md_path, "w", encoding="utf-8") as md_file:
            md_file.write("# Eisodos Benchmark Results\n\n")
            # Define headers - Added "Accounts Processed"
            headers = ["ID", "Entrypoint", "Features", "AccountsProcessed", "BenchmarkName", "MedianComputeUnits", "TotalComputeUnits", "InstructionsExecuted", "Program ID", "Artifact"]
            md_file.write("| " + " | ".join(headers) + " |\n")
            md_file.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            for result in all_benchmark_results:
                # Format features list to string for display
                result_display = result.copy()
                if "Features" in result_display and isinstance(result_display["Features"], list):
                     result_display["Features"] = ", ".join(result_display["Features"]) if result_display["Features"] else "none"
                 # Shorten Program ID for display
                if "program_id" in result_display:
                     pid = result_display["program_id"]
                     if len(pid) > 8:
                         result_display["program_id"] = f"{pid[:4]}...{pid[-4:]}"
                row = [str(result_display.get(h, "N/A")) for h in headers]
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