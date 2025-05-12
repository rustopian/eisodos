use std::{path::PathBuf, process::exit, str::FromStr};
use mollusk_svm_bencher::MolluskComputeUnitBencher;
use mollusk_svm::Mollusk;
use solana_sdk::{
    instruction::Instruction,
    pubkey::Pubkey,
};

struct Args {
    so_path: PathBuf,
    program_id: Pubkey,
    instruction_data: Vec<u8>,
}

fn parse_args() -> Result<Args, String> {
    let mut args = std::env::args().skip(1); 

    let so_path_str = args.next().ok_or_else(|| "Missing <so_path> argument".to_string())?;
    let program_id_str = args.next().ok_or_else(|| "Missing <program_id> argument".to_string())?;
    let instruction_hex_str = args.next().ok_or_else(|| "Missing <instruction_hex> argument".to_string())?;

    let so_path = PathBuf::from(so_path_str.clone());
    if !so_path.is_file() {
        return Err(format!("SO file not found: {}", so_path_str));
    }

    let program_id = Pubkey::from_str(&program_id_str)
        .map_err(|e| format!("Invalid program_id: {}. Error: {}", program_id_str, e))?;
    
    let instruction_data = match hex::decode(&instruction_hex_str) {
        Ok(data) => data,
        Err(e) => return Err(format!("Invalid hex for instruction_data: '{}'. Error: {}", instruction_hex_str, e)),
    };

    Ok(Args {
        so_path,
        program_id,
        instruction_data,
    })
}

fn main() {
    let args = match parse_args() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("Argument parsing error: {}", e);
            eprintln!("Usage: eisodos-bench-executor <so_path> <program_id> <instruction_hex>");
            exit(1);
        }
    };

    println!(
        "Executor: SO: {:?}, ProgramID: {}, Instruction (hex): {}",
        args.so_path, args.program_id, hex::encode(&args.instruction_data)
    );
    
    if let Some(parent_dir) = args.so_path.parent() {
        if let Some(parent_dir_str) = parent_dir.to_str() {
            std::env::set_var("SBF_OUT_DIR", parent_dir_str);
            println!("Executor: Set SBF_OUT_DIR to: {}", parent_dir_str);
        } else {
            eprintln!("Executor Error: Could not convert .so parent directory to string.");
            exit(1);
        }
    } else {
        eprintln!("Executor Error: Could not get parent directory of .so file.");
        exit(1);
    }
    
    let program_crate_name = args.so_path.file_stem().unwrap_or_default().to_str().unwrap_or_default();
    if program_crate_name.is_empty() {
        eprintln!("Executor Error: Could not determine program crate name from .so file stem.");
        exit(1);
    }
    println!("Executor: Using program crate name for Mollusk: {}", program_crate_name);

    // Initialize logger (optional, but good for seeing Mollusk/SVM logs)
    // solana_logger::setup_with(""); // Removed - Let MolluskComputeUnitBencher handle its own output

    let mollusk = Mollusk::new(&args.program_id, program_crate_name);
    let mut bencher = MolluskComputeUnitBencher::new(mollusk)
        .must_pass(true); 

    let instruction = Instruction {
        program_id: args.program_id,
        accounts: vec![], 
        data: args.instruction_data,
    };

    // Create a longer-lived binding for the empty accounts vector
    let empty_accounts_for_bench = Vec::new(); 
    bencher = bencher.bench(("benchmark_run", &instruction, &empty_accounts_for_bench));

    println!("Executor: Executing benchmark via MolluskComputeUnitBencher...");
    bencher.execute(); // This method prints the results to stdout.

    // The Python script will capture and display/parse the stdout from bencher.execute().
    println!("Executor: Benchmark execution completed (results printed to stdout).");
} 