use super::DecrementStrategy;
use super::{
    generate_account, generate_create_account, generate_pinocchio_slot_hashes_ix,
    generate_sdk_slot_hashes_ix, generate_transfer, instruction_data, setup, ProgramInstruction,
    generate_mock_slot_hashes_data
};
use mollusk_svm_bencher::MolluskComputeUnitBencher;
use solana_account::Account;
use solana_instruction::Instruction;
use solana_pubkey::Pubkey;
use solana_program::clock::Slot;
use std::collections::HashMap;

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
        benchmark_data.push((
            format!("{}: Account ({})", name, num_accounts),
            instruction,
            accounts,
        ));
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

    // Define base instruction types and base names for SlotHashes
    // We will expand these with specific target indices
    let base_slot_hash_benchmarks = [
        // Use UNCHECKED instructions for Pinocchio
        (
            "eisodos_pinocchio",
            ProgramInstruction::SlotHashesGetEntryUnchecked, // Placeholder, won't be used directly
            "GetEntry",
            None // Indicates no target slot needed
        ),
        (
            "eisodos_pinocchio",
            ProgramInstruction::SlotHashesGetHashInterpolatedUnchecked, // Placeholder
            "GetHashInterpolated",
            None // For simplicity, keep GetHash searching for slot 0 for now
        ),
        (
            "eisodos_pinocchio",
            ProgramInstruction::SlotHashesPositionInterpolatedUnchecked { target_slot: 0 }, // Placeholder
            "PositionInterpolated",
            Some([0, 50, 100, 150, 255, 300, 350, 400, 450, 511]) // Expanded target indices
        ),
        (
            "eisodos_pinocchio",
            ProgramInstruction::SlotHashesPositionNaiveUnchecked { target_slot: 0 }, // Placeholder
            "PositionNaive",
            Some([0, 50, 100, 150, 255, 300, 350, 400, 450, 511]) // Expanded target indices
        ),
        // Use CHECKED instructions for SDK / Nostd - Add similar structure if needed
        // ... (SDK/Nostd entries unchanged for now) ...
    ];

    for (strategy, strategy_name) in strategies {
        // Generate mock data once per strategy
        let mock_entries = generate_mock_slot_hashes_data(strategy);
        let actual_len = mock_entries.len();
        if actual_len == 0 { continue; } // Skip if no entries generated

        // Define target indices relative to actual length
        let target_indices_to_get = [
            0, // First
            (actual_len.saturating_sub(1) * 1 / 10),
            (actual_len.saturating_sub(1) * 2 / 10),
            (actual_len.saturating_sub(1) * 3 / 10),
            (actual_len.saturating_sub(1) * 5 / 10), // Middle-ish
            (actual_len.saturating_sub(1) * 6 / 10),
            (actual_len.saturating_sub(1) * 7 / 10),
            (actual_len.saturating_sub(1) * 8 / 10),
            (actual_len.saturating_sub(1) * 9 / 10),
            actual_len.saturating_sub(1), // Last
        ];
        // Deduplicate indices, necessary if actual_len is small
        let unique_target_indices: std::collections::HashSet<usize> = target_indices_to_get.iter().cloned().collect();

        // Get the slot values for the unique target indices
        let target_slot_values: HashMap<usize, Slot> = unique_target_indices
            .iter()
            .map(|&idx| (idx, mock_entries[idx].0))
            .collect();

        let generate_fn = if name == "eisodos_pinocchio" {
            generate_pinocchio_slot_hashes_ix
        } else {
            generate_sdk_slot_hashes_ix // This would also need modification if SDK benches target specific slots
        };

        // Filter benchmarks relevant to the current program (`name`)
        for &(prog_name_filter, base_ix_variant, base_name, target_indices_opt) in base_slot_hash_benchmarks.iter() {
            if prog_name_filter != name {
                continue;
            }

            match target_indices_opt {
                Some(_) => { // Modified: Use unique_target_indices derived from actual_len
                    // Create benchmarks for specific indices
                    for &target_index in &unique_target_indices {
                        let target_slot = target_slot_values[&target_index]; // Get slot value from map
                        let ix_variant = match base_ix_variant {
                            ProgramInstruction::SlotHashesPositionInterpolatedUnchecked { .. } => 
                                ProgramInstruction::SlotHashesPositionInterpolatedUnchecked { target_slot },
                            ProgramInstruction::SlotHashesPositionNaiveUnchecked { .. } => 
                                ProgramInstruction::SlotHashesPositionNaiveUnchecked { target_slot },
                            _ => panic!("Unexpected instruction type for indexed target")
                        };
                        // Pass actual_len to generate_fn if it needs it (it currently doesn't, uses mock_entries.len() indirectly)
                        let (instruction, accounts) = generate_fn(*program_id, ix_variant, strategy);
                        let bench_id = format!("{}: {} (Idx {}) ({})", name, base_name, target_index, strategy_name);
                        benchmark_data.push((bench_id, instruction, accounts));
                    }
                }
                None => {
                    // Create a single benchmark (like GetEntry, GetHash)
                    let ix_variant = base_ix_variant; // Use the placeholder directly
                    let (instruction, accounts) = generate_fn(*program_id, ix_variant, strategy);
                    let bench_id = format!("{}: {} ({})", name, base_name, strategy_name);
                    benchmark_data.push((bench_id, instruction, accounts));
                }
            }
        }
    }

    for (id, instruction, accounts) in &benchmark_data {
        bencher = bencher.bench((id.as_str(), instruction, accounts));
    }

    bencher.execute();
}
