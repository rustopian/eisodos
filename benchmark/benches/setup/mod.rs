pub mod runner;

// Bring crates into scope
use solana_program;

use mollusk_svm::{program::keyed_account_for_system_program, Mollusk};
use solana_account::Account;
use solana_instruction::{AccountMeta, Instruction};
use solana_pubkey::Pubkey;
use std::vec;
// Use Sysvar ID from solana_program
use solana_program::sysvar::ID as SYSVAR_PROGRAM_ID;
// Imports needed for SlotHashes construction
// Use correct paths for 1.18
use solana_program::clock::Slot;
use solana_program::hash::Hash;
// SlotHash is a type alias (Slot, Hash)
use solana_program::slot_hashes::SlotHash;

// Enum to control slot decrement behavior in mock data generation
#[derive(Clone, Copy, Debug)]
enum DecrementStrategy {
    Strictly1,
    Average1_05, // Avg decrement: (19*1 + 1*2)/20 = 1.05
    Average2,    // Avg decrement: (1 + 3)/2 = 2
}

pub const BASE_LAMPORTS: u64 = 2_000_000_000u64;
const NUM_BENCH_SLOT_HASH_ENTRIES: usize = 512;
const BENCH_SLOT_HASH_START_SLOT: u64 = 900;

// Simple deterministic PRNG for varied decrements
// Using a basic Lehmer / MINSTD generator approach
fn simple_prng(seed: u64) -> u64 {
    // Parameters (chosen somewhat arbitrarily, ensure non-zero output often)
    const A: u64 = 16807; // Multiplier
    const M: u64 = 2147483647; // Modulus (2^31 - 1)
    // Ensure seed is non-zero for this specific PRNG
    let initial_state = if seed == 0 { 1 } else { seed };
    (A.wrapping_mul(initial_state)) % M
}

/// Create a new Mollusk instance for the given program ID and name.
pub fn setup(program_id: &Pubkey, name: &'static str) -> Mollusk {
    std::env::set_var("SBF_OUT_DIR", "../target/deploy");
    solana_logger::setup_with("");

    Mollusk::new(program_id, name)
}

/// Instructions on the program to be executed.
#[derive(Clone, Copy, Debug)]
pub enum ProgramInstruction {
    Ping,
    Log,
    Account { expected: u64 },
    CreateAccount,
    Transfer,
    SlotHashesGetEntry,          
    SlotHashesGetHashInterpolated, 
    SlotHashesPositionInterpolated,
    SlotHashesGetHashMidpoint,     
    SlotHashesPositionMidpoint,    
}

/// Returns the instruction data for the given instruction.
pub fn instruction_data(instruction: ProgramInstruction) -> Vec<u8> {
    match instruction {
        ProgramInstruction::Ping => vec![0],
        ProgramInstruction::Log => vec![1],
        ProgramInstruction::Account { expected } => {
            let mut data = Vec::with_capacity(9);
            data.push(2);
            data.extend_from_slice(&expected.to_le_bytes());
            data
        }
        ProgramInstruction::CreateAccount => vec![3],
        ProgramInstruction::Transfer => vec![4],
        ProgramInstruction::SlotHashesGetEntry => vec![5],
        ProgramInstruction::SlotHashesGetHashInterpolated => vec![6],
        ProgramInstruction::SlotHashesPositionInterpolated => vec![7],
        ProgramInstruction::SlotHashesGetHashMidpoint => vec![8],
        ProgramInstruction::SlotHashesPositionMidpoint => vec![9],
    }
}

/// Generate a set of unique public keys.
pub fn generate_pubkeys(count: usize) -> Vec<Pubkey> {
    let mut keys = Vec::with_capacity(count);
    for _ in 0..count {
        keys.push(Pubkey::new_unique());
    }
    keys
}

/// Helper function to generate more realistic SlotHashes data
fn generate_mock_slot_hashes_data(strategy: DecrementStrategy) -> Vec<(u64, [u8; 32])> {
    let mut entries = Vec::with_capacity(NUM_BENCH_SLOT_HASH_ENTRIES);
    let mut current_slot = BENCH_SLOT_HASH_START_SLOT;

    for i in 0..NUM_BENCH_SLOT_HASH_ENTRIES {
        // Generate a predictable, unique hash based on index
        let hash_byte = (i % 256) as u8;
        let hash = [hash_byte; 32];
        entries.push((current_slot, hash));

        // Determine next slot based on strategy
        let random_val = simple_prng(i as u64);
        let decrement = match strategy {
            DecrementStrategy::Strictly1 => 1,
            DecrementStrategy::Average1_05 => {
                // Use PRNG to decide when to decrement by 2 (approx 1/20 chance)
                if random_val % 20 == 0 { 2 } else { 1 }
            }
            DecrementStrategy::Average2 => {
                // Use PRNG to choose between 1 and 3 (approx 50/50 chance)
                if random_val % 2 == 0 { 1 } else { 3 }
            }
        };
        current_slot = current_slot.saturating_sub(decrement);
    }
    entries
}

/// Generates the instruction data and accounts for the
/// `ProgramInstruction::Account` instruction.
fn generate_account(program_id: Pubkey, expected: u64) -> (Instruction, Vec<(Pubkey, Account)>) {
    let mut keys = generate_pubkeys(expected as usize);

    let mut accounts = Vec::with_capacity(keys.len());
    let mut account_metas = Vec::with_capacity(keys.len());

    for _ in 0..keys.len() {
        let key = keys.pop().unwrap();
        accounts.push((
            key,
            Account::new(BASE_LAMPORTS, 0, &solana_system_interface::program::ID),
        ));
        account_metas.push(AccountMeta::new_readonly(key, false));
    }

    (
        Instruction {
            program_id,
            accounts: account_metas,
            data: instruction_data(crate::ProgramInstruction::Account { expected }),
        },
        accounts,
    )
}

/// Generates the instruction data and accounts for the
/// `ProgramInstruction::CreateAccount` instruction.
fn generate_create_account(program_id: Pubkey) -> (Instruction, Vec<(Pubkey, Account)>) {
    let keys = generate_pubkeys(2);
    let [key1, key2] = keys.as_slice() else {
        panic!()
    };

    let (system_program_id, system_program_account) = keyed_account_for_system_program();

    let accounts = vec![
        (
            *key1,
            Account::new(BASE_LAMPORTS, 0, &solana_system_interface::program::ID),
        ),
        // account being created, starts with 0 lamports and no data
        (
            *key2,
            Account::new(0, 0, &solana_system_interface::program::ID),
        ),
        (system_program_id, system_program_account),
    ];

    let account_metas = vec![
        AccountMeta::new(*key1, true),
        AccountMeta::new(*key2, true),
        AccountMeta::new_readonly(system_program_id, false),
    ];

    (
        Instruction {
            program_id,
            accounts: account_metas,
            data: instruction_data(crate::ProgramInstruction::CreateAccount),
        },
        accounts,
    )
}

/// Generates the instruction data and accounts for the
/// `ProgramInstruction::Transfer` instruction.
fn generate_transfer(program_id: Pubkey) -> (Instruction, Vec<(Pubkey, Account)>) {
    let keys = generate_pubkeys(2);
    let [key1, key2] = keys.as_slice() else {
        panic!()
    };

    let (system_program_id, system_program_account) = keyed_account_for_system_program();

    let accounts = vec![
        (
            *key1,
            Account::new(BASE_LAMPORTS, 0, &solana_system_interface::program::ID),
        ),
        // account receiving the transfer, so it starts with 0 lamports
        (
            *key2,
            Account::new(0, 0, &solana_system_interface::program::ID),
        ),
        (system_program_id, system_program_account),
    ];

    let account_metas = vec![
        AccountMeta::new(*key1, true),
        AccountMeta::new(*key2, true),
        AccountMeta::new_readonly(system_program_id, false),
    ];

    (
        Instruction {
            program_id,
            accounts: account_metas,
            data: instruction_data(crate::ProgramInstruction::Transfer),
        },
        accounts,
    )
}

/// Generates the instruction data and accounts for the SlotHashes instructions (SDK version).
fn generate_sdk_slot_hashes_ix(
    program_id: Pubkey, 
    ix_type: ProgramInstruction, 
    strategy: DecrementStrategy
) -> (Instruction, Vec<(Pubkey, Account)>) {
    // Use the well-known ID directly to avoid sdk dependency
    let sysvar_id = solana_pubkey::Pubkey::new_from_array([
        6, 167, 213, 23, 25, 47, 10, 175, 198, 242, 101, 227, 251, 119, 204, 122, 
        218, 130, 197, 41, 208, 190, 59, 19, 110, 45, 0, 85, 32, 0, 0, 0
    ]);

    // Generate realistic mock SlotHashes data
    let mock_entries_raw = generate_mock_slot_hashes_data(strategy);

    // Manually serialize mock data according to layout: u64 len + [(u64 slot, [u8; 32] hash)]
    // (Using u64 len for consistency, as prefix didn't cause the UnsupportedSysvar error)
    let num_entries = mock_entries_raw.len() as u64;
    let mut data = Vec::with_capacity(8 + mock_entries_raw.len() * (8 + 32)); // Use 8 for u64 len
    data.extend_from_slice(&(num_entries as u64).to_le_bytes());
    for (slot, hash) in &mock_entries_raw {
        data.extend_from_slice(&slot.to_le_bytes());
        data.extend_from_slice(hash);
    }

    // Create the sysvar account owned by the Sysvar Program ID
    let mut sysvar_account = Account::new(1, data.len(), &SYSVAR_PROGRAM_ID);
    sysvar_account.data = data;
    sysvar_account.executable = false; // Sysvars aren't executable

    let accounts = vec![(sysvar_id, sysvar_account)];

    let account_metas = vec![AccountMeta::new_readonly(sysvar_id, false)];

    (
        Instruction {
            program_id,
            accounts: account_metas,
            data: instruction_data(ix_type),
        },
        accounts,
    )
}

/// Generates the instruction data and accounts for the SlotHashes instructions (Pinocchio version).
fn generate_pinocchio_slot_hashes_ix(
    program_id: Pubkey, 
    ix_type: ProgramInstruction, 
    strategy: DecrementStrategy
) -> (Instruction, Vec<(Pubkey, Account)>) {
    // Use the well-known ID directly to avoid sdk dependency
    let sysvar_id = solana_pubkey::Pubkey::new_from_array([
        6, 167, 213, 23, 25, 47, 10, 175, 198, 242, 101, 227, 251, 119, 204, 122, 
        218, 130, 197, 41, 208, 190, 59, 19, 110, 45, 0, 85, 32, 0, 0, 0
    ]);

    // Generate realistic mock SlotHashes data
    let mock_entries = generate_mock_slot_hashes_data(strategy);

    let num_entries = mock_entries.len() as u64;
    let mut data = Vec::with_capacity(8 + mock_entries.len() * (8 + 32)); // Use 8 for u64 len
    data.extend_from_slice(&(num_entries as u64).to_le_bytes());
    for (slot, hash) in &mock_entries {
        data.extend_from_slice(&slot.to_le_bytes());
        data.extend_from_slice(hash);
    }

    // Create the sysvar account (owned by SYSVAR_PROGRAM_ID)
    let mut sysvar_account = Account::new(1, data.len(), &SYSVAR_PROGRAM_ID);
    sysvar_account.data = data;
    sysvar_account.executable = false;

    let accounts = vec![(sysvar_id, sysvar_account)];

    let account_metas = vec![AccountMeta::new_readonly(sysvar_id, false)];

    (
        Instruction {
            program_id,
            accounts: account_metas,
            data: instruction_data(ix_type),
        },
        accounts,
    )
}
