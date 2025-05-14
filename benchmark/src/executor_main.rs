use clap::Parser;
use mollusk_svm::{program::keyed_account_for_system_program, Mollusk};
use mollusk_svm_bencher::MolluskComputeUnitBencher;
use solana_sdk::{
    account::Account,
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    system_program,
};
use std::{collections::HashMap, path::PathBuf, str::FromStr};

#[derive(Parser, Debug)]
#[clap(author, version, about, long_about = None)]
struct Args {
    #[clap()]
    program_path: String,
    #[clap()]
    program_id: String,

    // Format for each string:
    // "role_name:key_placeholder:is_signer:is_writable:lamports:data_len:
    // owner_id_or_self_or_system" For clap v4, Vec<String> automatically means multiple
    // occurrences.
    #[clap(long = "account-spec")]
    account_specs: Vec<String>,

    #[clap(long, default_value = "")]
    instruction_data: String,
}

struct ParsedAccountSpec {
    role_name: String,       // For logging or mapping if needed
    key_placeholder: String, // For logging or mapping
    actual_pubkey: Pubkey,
    is_signer: bool,
    is_writable: bool,
    lamports: u64,
    data_len: usize,
    owner: Pubkey,
}

// Helper to parse the account_spec string
fn parse_account_spec(
    spec_str: &str,
    program_id: &Pubkey,
    key_map: &mut HashMap<String, Pubkey>,
    key_counter: &mut usize,
) -> Result<ParsedAccountSpec, String> {
    let parts: Vec<&str> = spec_str.split(':').collect();
    if parts.len() != 7 {
        return Err(format!(
            "Invalid account spec format. Expected 7 parts, got {}: {}",
            parts.len(),
            spec_str
        ));
    }

    let role_name = parts[0].to_string();
    let key_placeholder = parts[1].to_string();
    let is_signer = bool::from_str(parts[2])
        .map_err(|e| format!("Invalid is_signer bool: {} ({})", parts[2], e))?;
    let is_writable = bool::from_str(parts[3])
        .map_err(|e| format!("Invalid is_writable bool: {} ({})", parts[3], e))?;
    let lamports = u64::from_str(parts[4])
        .map_err(|e| format!("Invalid lamports u64: {} ({})", parts[4], e))?;
    let data_len = usize::from_str(parts[5])
        .map_err(|e| format!("Invalid data_len usize: {} ({})", parts[5], e))?;

    let owner_str = parts[6];
    let owner_pk = if owner_str.eq_ignore_ascii_case("self") {
        *program_id
    } else if owner_str.eq_ignore_ascii_case("system") {
        system_program::id()
    } else {
        Pubkey::from_str(owner_str)
            .map_err(|e| format!("Invalid owner pubkey: {owner_str} ({e})"))?
    };

    // For system_program role, its actual_pubkey will be overridden later by
    // keyed_account_for_system_program For others, generate/retrieve pubkey for
    // the placeholder.
    let generated_pubkey = *key_map.entry(key_placeholder.clone()).or_insert_with(|| {
        let mut base_bytes = program_id.to_bytes();
        base_bytes[0] = base_bytes[0]
            .wrapping_add(*key_counter as u8)
            .wrapping_add(1);
        base_bytes[1] = base_bytes[1].wrapping_add((*key_counter >> 8) as u8);
        *key_counter += 1;
        Pubkey::new_from_array(base_bytes)
    });

    Ok(ParsedAccountSpec {
        role_name,
        key_placeholder,
        actual_pubkey: generated_pubkey, // Placeholder, might be overridden for system_program
        is_signer,
        is_writable,
        lamports,
        data_len,
        owner: owner_pk,
    })
}

fn main() {
    let args = Args::parse();

    println!(
        "Executor: SO: \"{}\", ProgramID: {}, AccountSpecs: {:?}, InstrData(hex): {}",
        args.program_path, args.program_id, args.account_specs, args.instruction_data
    );

    let so_path_obj = PathBuf::from(&args.program_path);
    if let Some(parent_dir) = so_path_obj.parent() {
        // target/deploy
        if let Some(target_dir) = parent_dir.parent() {
            // target
            if let Some(program_dir) = target_dir.parent() {
                // bench_gen/some_bench_run_dir
                let sbf_out_dir = program_dir.join("target").join("deploy");
                std::env::set_var("SBF_OUT_DIR", sbf_out_dir.to_str().unwrap_or("."));
                println!("Executor: Set SBF_OUT_DIR to: {}", sbf_out_dir.display());
            }
        }
    }

    let program_id_pubkey = Pubkey::from_str(&args.program_id).expect("Invalid program ID");
    let instruction_data_bytes_original =
        hex::decode(&args.instruction_data).expect("Failed to decode instruction data from hex");

    let program_crate_name = so_path_obj
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown_program")
        .to_string();
    println!("Executor: Using program crate name for Mollusk: {program_crate_name}");

    let mollusk_instance = Mollusk::new(&program_id_pubkey, &program_crate_name);

    let mut accounts_for_bench: Vec<(Pubkey, Account)> = Vec::new();
    let mut account_metas_for_instruction: Vec<AccountMeta> = Vec::new();

    let mut key_map: HashMap<String, Pubkey> = HashMap::new();
    let mut role_name_to_actual_pubkey_map: HashMap<String, Pubkey> = HashMap::new();
    let mut key_counter: usize = 0; // For generating unique-ish keys

    if !args.account_specs.is_empty() {
        // Primary logic: Use account_specs if provided
        for spec_str in &args.account_specs {
            match parse_account_spec(spec_str, &program_id_pubkey, &mut key_map, &mut key_counter) {
                Ok(mut spec) => {
                    let account_to_add: Account;
                    let final_pubkey: Pubkey = spec.actual_pubkey;
                    let is_executable: bool;

                    if spec.role_name == "system_program" {
                        let (sys_prog_pk, sys_prog_acct) = keyed_account_for_system_program();
                        account_to_add = sys_prog_acct;
                        spec.is_signer = false;
                        spec.is_writable = false;
                        is_executable = account_to_add.executable;
                        role_name_to_actual_pubkey_map.insert(spec.role_name.clone(), sys_prog_pk);
                        println!(
                            "Executor: Using keyed_account_for_system_program() for role '{}'. \
                             Key: {}",
                            spec.role_name, sys_prog_pk
                        );
                        account_metas_for_instruction.push(AccountMeta {
                            pubkey: sys_prog_pk,
                            is_signer: spec.is_signer,
                            is_writable: spec.is_writable,
                        });
                        accounts_for_bench.push((sys_prog_pk, account_to_add));
                    } else {
                        // Only the *system program account itself* should be executable.
                        // Normal user accounts that are merely *owned* by the system program must
                        // **not** be executable, otherwise the runtime
                        // rejects instructions like `transfer` or `create_account`.
                        is_executable = final_pubkey == system_program::id();
                        account_to_add = Account {
                            lamports: spec.lamports,
                            data: vec![0u8; spec.data_len],
                            owner: spec.owner,
                            executable: is_executable,
                            rent_epoch: 0,
                        };
                        account_metas_for_instruction.push(AccountMeta {
                            pubkey: final_pubkey,
                            is_signer: spec.is_signer,
                            is_writable: spec.is_writable,
                        });
                        accounts_for_bench.push((final_pubkey, account_to_add));
                        role_name_to_actual_pubkey_map.insert(spec.role_name.clone(), final_pubkey);
                    }

                    println!(
                        "Executor: Setting up account '{}({})': {}, signer: {}, writable: {}, \
                         lamports: {}, data_len: {}, owner: {}, executable: {}",
                        spec.role_name,
                        spec.key_placeholder,
                        if spec.role_name == "system_program" {
                            accounts_for_bench.last().unwrap().0
                        } else {
                            final_pubkey
                        },
                        spec.is_signer,
                        spec.is_writable,
                        if spec.role_name == "system_program" {
                            accounts_for_bench.last().unwrap().1.lamports
                        } else {
                            spec.lamports
                        },
                        if spec.role_name == "system_program" {
                            accounts_for_bench.last().unwrap().1.data.len()
                        } else {
                            spec.data_len
                        },
                        if spec.role_name == "system_program" {
                            accounts_for_bench.last().unwrap().1.owner
                        } else {
                            spec.owner
                        },
                        if spec.role_name == "system_program" {
                            accounts_for_bench.last().unwrap().1.executable
                        } else {
                            is_executable
                        }
                    );
                }
                Err(e) => {
                    eprintln!("Error parsing account spec \"{spec_str}\": {e}. Skipping.");
                }
            }
        }
    } else {
        // Fallback logic: If no account_specs, try to infer from instruction_data (for
        // account-read style benchmarks)
        if !instruction_data_bytes_original.is_empty() {
            let num_accounts_from_instr = instruction_data_bytes_original[0] as usize;
            if num_accounts_from_instr > 0 {
                println!(
                    "Executor: No account-specs. Setting up {} accounts based on first byte of \
                     instruction_data (0x{:02x}).",
                    num_accounts_from_instr, instruction_data_bytes_original[0]
                );
                for i in 0..num_accounts_from_instr {
                    let mut pk_bytes = program_id_pubkey.to_bytes();
                    // Simple offset to generate somewhat unique keys for these default accounts
                    pk_bytes[0] = pk_bytes[0].wrapping_add(100u8).wrapping_add(i as u8);
                    let account_pubkey = Pubkey::new_from_array(pk_bytes);

                    let account = Account {
                        lamports: 1_000_000_000,  // Default lamports
                        data: vec![0u8; 1024],    // Default data size
                        owner: program_id_pubkey, // Default owner (self)
                        executable: false,
                        rent_epoch: 0,
                    };
                    accounts_for_bench.push((account_pubkey, account));
                    account_metas_for_instruction.push(AccountMeta {
                        pubkey: account_pubkey,
                        is_signer: false,  // Default for these generic accounts
                        is_writable: true, // Default for these generic accounts
                    });
                }
            } else {
                println!(
                    "Executor: No account-specs, and instruction_data[0] is 0. Proceeding with \
                     zero accounts for instruction."
                );
            }
        } else {
            // This case handles truly no accounts needed (e.g. a bare ping with no instr
            // data either)
            println!(
                "Executor: No account-specs and no instruction data. Proceeding with zero \
                 accounts."
            );
        }
    }

    let instruction = Instruction {
        program_id: program_id_pubkey,
        accounts: account_metas_for_instruction,
        data: instruction_data_bytes_original.clone(),
    };

    let benchmark_id = format!(
        "{}{}",
        program_crate_name,
        if !args.account_specs.is_empty() {
            "_custom_accounts".to_string()
        } else if !instruction_data_bytes_original.is_empty()
            && instruction_data_bytes_original[0] > 0
        {
            format!("_default_accounts_{}", instruction_data_bytes_original[0])
        } else {
            "".to_string()
        }
    );

    println!("Executor: Executing benchmark: {benchmark_id}");

    // --------------------
    // Optional functional-correctness checks using Mollusk's `Check` API.
    // We currently add checks for the two CPI benchmarks that ship with
    // Eisodos examples:
    //  * CreateAccount – 17-byte instruction data, tag == 0
    //  * Transfer      –  9-byte instruction data,  tag == 0
    // --------------------

    use mollusk_svm::result::Check;

    let mut additional_checks: Vec<Check> = vec![Check::success()];

    // Helper to fetch pubkeys for well-known roles.
    let get_role_pk = |role: &str| -> Option<&Pubkey> { role_name_to_actual_pubkey_map.get(role) };

    if !instruction_data_bytes_original.is_empty() && instruction_data_bytes_original[0] == 0 {
        match instruction_data_bytes_original.len() {
            17 => {
                // CreateAccount
                let lamports =
                    u64::from_le_bytes(instruction_data_bytes_original[1..9].try_into().unwrap());
                let space =
                    u64::from_le_bytes(instruction_data_bytes_original[9..17].try_into().unwrap())
                        as usize;

                if let Some(new_acct_pk_ref) = get_role_pk("new_account") {
                    println!(
                        "Executor: Validating CreateAccount: new_account_pk '{new_acct_pk_ref}', \
                         expected_lamports={lamports}, expected_space={space}, \
                         expected_owner='{program_id_pubkey}'"
                    );
                    additional_checks.push(
                        Check::account(new_acct_pk_ref)
                            .lamports(lamports)
                            .owner(&program_id_pubkey) // program_id_pubkey lives long enough
                            .space(space)
                            .build(),
                    );
                }

                if let Some(funder_pk_ref) = get_role_pk("funder") {
                    let funder_initial = 10000000000u64;
                    additional_checks.push(
                        Check::account(funder_pk_ref)
                            .lamports(funder_initial.saturating_sub(lamports))
                            .build(),
                    );
                }
            }
            9 => {
                // Transfer
                let amount =
                    u64::from_le_bytes(instruction_data_bytes_original[1..9].try_into().unwrap());

                if let Some(source_pk_ref) = get_role_pk("source") {
                    let source_initial = 20000000000u64;
                    additional_checks.push(
                        Check::account(source_pk_ref)
                            .lamports(source_initial.saturating_sub(amount))
                            .build(),
                    );
                }

                if let Some(dest_pk_ref) = get_role_pk("destination") {
                    additional_checks.push(Check::account(dest_pk_ref).lamports(amount).build());
                }
            }
            _ => {}
        }

        // Run the validation pass (will panic on mismatch).
        if additional_checks.len() > 1 {
            mollusk_instance.process_and_validate_instruction(
                &instruction,
                &accounts_for_bench,
                &additional_checks,
            );
        }
    }

    // Now create bencher using the (now validated with) mollusk_instance
    let mut bencher = MolluskComputeUnitBencher::new(mollusk_instance) // mollusk_instance is moved here
        .must_pass(true);

    // Configure the bencher with the benchmark details
    bencher = bencher.bench((&benchmark_id, &instruction, &accounts_for_bench));

    bencher.execute();
    println!("Executor: Benchmark execution completed.");

    // The Python script will capture and display/parse the stdout from
    // bencher.execute(). Specifically, it looks for "--- Benchmark Metrics
    // ---" blocks. MolluskComputeUnitBencher is expected to print metrics
    // in that format.
}
