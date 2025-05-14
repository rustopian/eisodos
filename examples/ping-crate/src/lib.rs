#![cfg_attr(not(feature = "std"), no_std)]

// === no_std specific setup ===
#[cfg(not(feature = "std"))]
use pinocchio::{
    ProgramResult, // Use Pinocchio's ProgramResult
    pubkey::Pubkey, // Import Pinocchio's Pubkey
    account_info::AccountInfo, // Import Pinocchio's AccountInfo
    no_allocator,
    nostd_panic_handler
};

// Handlers MUST be present for no_std SBF builds
#[cfg(feature = "no_std")]
no_allocator!();
#[cfg(feature = "no_std")]
nostd_panic_handler!();
// ============================

// === std specific setup ===
#[cfg(feature = "std")]
use solana_program::{ 
    // Note: Using entrypoint_deprecated::ProgramResult for std compatibility
    // if the templates/executor expect that specific type.
    // Adjust if necessary based on how std results are handled.
    entrypoint_deprecated::ProgramResult,
    account_info::AccountInfo, // Use Solana's AccountInfo
    pubkey::Pubkey,            // Use Solana's Pubkey
};
// =========================

// Define a module that contains the benchmarkable function
pub mod instruction {
    // Bring crate-level items into scope based on feature flags
    #[cfg(feature = "no_std")]
    use crate::{Pubkey, AccountInfo, ProgramResult};
    #[cfg(feature = "std")]
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