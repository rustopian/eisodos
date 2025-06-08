#![cfg_attr(not(any(feature = "std", feature = "solana-program", feature = "solana-program-mono", feature = "solana-nostd-mono")), no_std)]

// === no_std specific setup (pinocchio only) ===
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-mono")))]
use pinocchio::{
    ProgramResult, // Use Pinocchio's ProgramResult
    pubkey::Pubkey, // Import Pinocchio's Pubkey
    account_info::AccountInfo, // Import Pinocchio's AccountInfo
    no_allocator,
    nostd_panic_handler
};

// Handlers MUST be present for no_std SBF builds
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-mono")))]
no_allocator!();
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-mono")))]
nostd_panic_handler!();
// ============================

// === std specific setup (broken-out crates) ===
#[cfg(all(any(feature = "std", feature = "solana-program"), not(feature = "solana-nostd-mono")))]
use {
    solana_account_info::AccountInfo,
    solana_entrypoint::ProgramResult,
    solana_pubkey::Pubkey,
};
// =========================

// === solana-program-mono specific setup ===
#[cfg(all(feature = "solana-program-mono", not(feature = "solana-nostd-mono")))]
use solana_program::{
    account_info::AccountInfo,
    entrypoint::ProgramResult,
    pubkey::Pubkey,
};
// =========================

// === solana-nostd-mono specific setup ===
#[cfg(feature = "solana-nostd-mono")]
use {
    solana_nostd_entrypoint::NoStdAccountInfo as AccountInfo,
    solana_program_error::ProgramResult,
    solana_pubkey::Pubkey,
};
// =========================

// Define a module that contains the benchmarkable function
pub mod instruction {
    // Bring crate-level items into scope based on feature flags
    #[cfg(all(feature = "no_std", not(feature = "solana-nostd-mono")))]
    use crate::{Pubkey, AccountInfo, ProgramResult};
    #[cfg(all(any(feature = "std", feature = "solana-program"), not(feature = "solana-nostd-mono")))]
    use crate::{Pubkey, AccountInfo, ProgramResult};
    #[cfg(all(feature = "solana-program-mono", not(feature = "solana-nostd-mono")))]
    use crate::{Pubkey, AccountInfo, ProgramResult};
    #[cfg(feature = "solana-nostd-mono")]
    use crate::{Pubkey, AccountInfo, ProgramResult};

    // Function to be benchmarked
    // Signature now correctly uses types based on feature flags
    pub fn process_instruction(
        _program_id: &Pubkey, 
        _accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult { 
        // Simple ping: just return Ok
        Ok(())
    }
} 