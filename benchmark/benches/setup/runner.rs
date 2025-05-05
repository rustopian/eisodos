use super::{
    generate_account, generate_create_account, generate_transfer, instruction_data, setup,
    generate_sdk_slot_hashes_ix, generate_pinocchio_slot_hashes_ix, ProgramInstruction,
};
use mollusk_svm_bencher::MolluskComputeUnitBencher;
use solana_account::Account;
use solana_instruction::Instruction;
use solana_pubkey::Pubkey;
use super::DecrementStrategy;

pub fn run(program_id: &Pubkey, name: &'static str) {
    let mollusk = setup(program_id, name);
    let mut bencher = MolluskComputeUnitBencher::new(mollusk)
        .must_pass(true)
        .out_dir("../target/benches");

    let mut benchmark_data: Vec<(String, Instruction, Vec<(Pubkey, Account)>)> = Vec::new();

    // Ping
    let instruction = Instruction {
        program_id: *program_id,
        accounts: vec![],
        data: instruction_data(ProgramInstruction::Ping),
    };
    benchmark_data.push((format!("{}: Ping", name), instruction, Vec::new()));

    // Log
    let instruction = Instruction {
        program_id: *program_id,
        accounts: vec![],
        data: instruction_data(ProgramInstruction::Log),
    };
    benchmark_data.push((format!("{}: Log", name), instruction, Vec::new()));

    // Account Benchmarks
    for &num_accounts in &[1u64, 3, 5, 10, 20, 32, 64] {
        let (instruction, accounts) = generate_account(*program_id, num_accounts);
        benchmark_data.push((format!("{}: Account ({})", name, num_accounts), instruction, accounts));
    }

    // CreateAccount
    let (instruction, accounts) = generate_create_account(*program_id);
    benchmark_data.push((format!("{}: CreateAccount", name), instruction, accounts));

    // Transfer
    let (instruction, accounts) = generate_transfer(*program_id);
    benchmark_data.push((format!("{}: Transfer", name), instruction, accounts));

    // --- Generate data for SlotHashes benchmarks with different strategies ---
    let strategies = [
        (DecrementStrategy::Strictly1, "Strictly1"),
        (DecrementStrategy::Average1_05, "Avg1.05"),
        (DecrementStrategy::Average2, "Avg2"),
    ];

    // Define instruction types and base names for SlotHashes
    let slot_hash_benchmarks = [
        // Use UNCHECKED instructions for Pinocchio
        ("eisodos_pinocchio", ProgramInstruction::SlotHashesGetEntryUnchecked, "GetEntry"),
        ("eisodos_pinocchio", ProgramInstruction::SlotHashesGetHashInterpolatedUnchecked, "GetHashInterpolated"),
        ("eisodos_pinocchio", ProgramInstruction::SlotHashesPositionInterpolatedUnchecked, "PositionInterpolated"),
        ("eisodos_pinocchio", ProgramInstruction::SlotHashesGetHashMidpointUnchecked, "GetHashMidpoint"),
        ("eisodos_pinocchio", ProgramInstruction::SlotHashesPositionMidpointUnchecked, "PositionMidpoint"),
        // Use CHECKED instructions for SDK / Nostd (which use generate_sdk_slot_hashes_ix)
        ("eisodos_solana_program", ProgramInstruction::SlotHashesGetEntryChecked, "GetEntry"),
        ("eisodos_solana_program", ProgramInstruction::SlotHashesGetHashChecked, "GetHash"), // Using generic name
        ("eisodos_solana_program", ProgramInstruction::SlotHashesPositionChecked, "Position"),
        ("eisodos_solana_nostd_entrypoint", ProgramInstruction::SlotHashesGetEntryChecked, "GetEntry"),
        ("eisodos_solana_nostd_entrypoint", ProgramInstruction::SlotHashesGetHashChecked, "GetHash"),
        ("eisodos_solana_nostd_entrypoint", ProgramInstruction::SlotHashesPositionChecked, "Position"),
    ];

    for (strategy, strategy_name) in strategies {
        // Select the correct generation function based on the current program being run
        let generate_fn: fn(Pubkey, ProgramInstruction, DecrementStrategy) -> (Instruction, Vec<(Pubkey, Account)>) = 
            if name == "eisodos_pinocchio" {
                generate_pinocchio_slot_hashes_ix
            } else {
                generate_sdk_slot_hashes_ix
            };

        // Filter benchmarks relevant to the current program (`name`)
        for &(prog_name_filter, ix_type, base_name) in slot_hash_benchmarks.iter() {
            if prog_name_filter != name { continue; }

            // Generate data for the specific instruction and strategy
            let (instruction, accounts) = generate_fn(*program_id, ix_type, strategy);
            let bench_id = format!("{}: {} ({})", name, base_name, strategy_name);
            benchmark_data.push((bench_id, instruction, accounts));
        }
    }

    for (id, instruction, accounts) in &benchmark_data {
        bencher = bencher.bench((id.as_str(), instruction, accounts));
    }

    bencher.execute();
}
