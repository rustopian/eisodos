use clap::Parser;
use mollusk_svm_bencher::api::{BencherContext, BencherParameters, SVMExecutionResults};
use solana_sdk::{
    account::AccountSharedData,
    instruction::AccountMeta,
    pubkey::Pubkey,
};
use std::fs;
use std::str::FromStr;

#[derive(Parser, Debug)]
#[clap(author, version, about, long_about = None)]
struct Args {
    #[clap()] // Positional argument for program_path
    program_path: String,
    #[clap()] // Positional argument for program_id
    program_id: String,

    #[clap(long, default_value_t = 0, help = "Number of accounts to create and pass to the program")]
    num_accounts: u8,

    #[clap(long, default_value_t = 1024, help = "Initial data size for each created account (bytes)")]
    initial_account_data_size: usize,

    // Changed from positional to long arg to match --num-accounts style
    #[clap(long, default_value = "", help = "Hex-encoded instruction data")]
    instruction_data: String,
}

fn main() {
    let args = Args::parse();

    println!(
        "Executor: SO: \"{}\", ProgramID: {}, Instruction (hex): {}",
        args.program_path,
        args.program_id,
        args.instruction_data
    );

    // Set SBF_OUT_DIR for the bencher, assuming it might be needed by underlying tools
    // The actual path might need to be more dynamic or configurable if benchmarks are run in parallel
    // For now, using the parent of the SO file's deploy directory.
    let so_path = std::path::Path::new(&args.program_path);
    if let Some(parent_dir) = so_path.parent() { // target/deploy
        if let Some(target_dir) = parent_dir.parent() { // target
             if let Some(program_dir) = target_dir.parent() { // bench_gen/some_bench_run_dir
                let sbf_out_dir = program_dir.join("target").join("deploy");
                std::env::set_var("SBF_OUT_DIR", sbf_out_dir.to_str().unwrap_or("."));
                println!("Executor: Set SBF_OUT_DIR to: {}", sbf_out_dir.display());
            }
        }
    }

    let program_id_pubkey = Pubkey::from_str(&args.program_id).expect("Invalid program ID");
    let elf_bytes = fs::read(&args.program_path).expect("Failed to read SBF program file");
    let instruction_data_bytes = hex::decode(&args.instruction_data).expect("Failed to decode instruction data from hex");

    let mut accounts_for_svm: Vec<AccountSharedData> = Vec::new();
    let mut account_metas_for_tx: Vec<AccountMeta> = Vec::new();

    if args.num_accounts > 0 {
        println!(
            "Executor: Setting up {} accounts, each with {} bytes of data.",
            args.num_accounts,
            args.initial_account_data_size
        );
        for i in 0..args.num_accounts {
            // Create deterministic-enough pubkeys for benchmarking context
            // This is simple; a more robust approach might derive from program_id + index
            let mut pk_bytes = program_id_pubkey.to_bytes();
            pk_bytes[0] = pk_bytes[0].wrapping_add(i + 1); // Ensure some variation
            let account_pubkey = Pubkey::new_from_array(pk_bytes);

            let mut account = AccountSharedData::new(
                1_000_000_000, // Lamports (rent-exempt for typical sizes)
                args.initial_account_data_size,
                &program_id_pubkey, // Owner is the benchmarked program
            );
            // Initialize account data with a simple pattern (e.g., sequence of bytes)
            let mut data_vec = vec![0u8; args.initial_account_data_size];
            if !data_vec.is_empty() {
                for (idx, byte) in data_vec.iter_mut().enumerate() {
                    *byte = (idx % 256) as u8;
                }
                // Use direct field assignment for account data
                account.data = data_vec;
            }
            
            accounts_for_svm.push(account.clone());
            
            account_metas_for_tx.push(AccountMeta {
                pubkey: account_pubkey,
                is_signer: false, // Benchmarked programs usually don't require signers
                is_writable: true,  // Assume writable for benchmarks that modify accounts
            });
        }
    }

    // Determine the program name for Mollusk, typically from the SO file name
    let crate_name_for_mollusk = so_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown_program")
        .to_string();
    println!("Executor: Using program crate name for Mollusk: {}", crate_name_for_mollusk);

    let bencher_params = BencherParameters {
        target_cu: Some(1_000_000), // Default target CU, can be adjusted
        ..Default::default()
    };

    println!("Executor: Executing benchmark via MolluskComputeUnitBencher...");

    // Note: The way accounts are passed to mollusk_svm_bencher might need adjustments.
    // It expects `loaded_accounts: &[(&Pubkey, &RefCell<AccountSharedData>)]`
    // We need to adapt our `accounts_for_svm` and `account_metas_for_tx` to this.
    // This is a simplified conceptual representation.
    // The actual setup for TransactionContext and passing accounts to `run_program_with_unified_context`
    // will be more involved.

    // Placeholder for actual account setup for Mollusk. 
    // This part is complex and depends on how Mollusk wants its TransactionContext and accounts.
    // The following is a conceptual sketch and WILL LIKELY NOT COMPILE as is without
    // further refinement based on mollusk-svm-bencher's exact API for account setup.

    // Create the RefCell wrappers and pubkey references needed by mollusk
    use std::cell::RefCell;
    let mut accounts_ref_cells: Vec<RefCell<AccountSharedData>> = accounts_for_svm
        .into_iter()
        .map(RefCell::new)
        .collect();

    let mut loaded_accounts_for_mollusk: Vec<(&Pubkey, &RefCell<AccountSharedData>)> = Vec::new();
    for i in 0..args.num_accounts as usize {
        loaded_accounts_for_mollusk.push((
            &account_metas_for_tx[i].pubkey, 
            &accounts_ref_cells[i]
        ));
    }
    
    let bencher_context = BencherContext {
        program_id: program_id_pubkey,
        elf_bytes: &elf_bytes, // Pass as slice
        instruction_data: &instruction_data_bytes, // Pass as slice
        accounts: &loaded_accounts_for_mollusk, // Pass as slice of tuples
        // account_metas needs to be correctly set for the TransactionContext if mollusk doesn't derive it.
        // This might involve creating a Solana Transaction and extracting its message.
    };

    match mollusk_svm_bencher::api::run_program_with_unified_context(&bencher_context, Some(&bencher_params), true) {
        Ok(execution_results) => {
            println!("Executor: Benchmark execution completed (results printed to stdout).");
            // The metrics printing logic from the script is now largely here.
            println!("--- Benchmark Metrics ---");
            // Use the crate name derived earlier for consistent naming
            println!("BenchmarkName: {}{}", crate_name_for_mollusk, 
                if args.num_accounts > 0 { format!("_accounts_{}", args.num_accounts) } else { "".to_string() });
            println!("MedianComputeUnits: {}", execution_results.median_cu);
            println!("TotalComputeUnits: {}", execution_results.total_cu);
            println!("InstructionsExecuted: {}", execution_results.executed_units); // Assuming this maps to instructions
            // Add other relevant metrics from execution_results if available
            println!("--- End Metrics ---");
        }
        Err(e) => {
            eprintln!("Executor: Benchmark execution failed: {:?}", e);
            std::process::exit(1);
        }
    }
} 