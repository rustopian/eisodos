#![cfg_attr(not(feature = "std"), no_std)]

// Conditionally include Pinocchio for no_std
#[cfg(not(feature = "std"))]
use pinocchio::{ProgramResult, no_allocator, nostd_panic_handler};

// Define handlers only if needed for SBF no_std library builds
#[cfg(all(not(feature = "std"), feature = "provide-handlers"))]
no_allocator!();
#[cfg(all(not(feature = "std"), feature = "provide-handlers"))]
nostd_panic_handler!();

// Use cfg attributes for Solana imports only when std is active
#[cfg(feature = "std")]
use solana_program::{
    entrypoint_deprecated::ProgramResult,
    account_info::AccountInfo, // Example import if needed by logic under std
    pubkey::Pubkey,            // Example import
    program_error::ProgramError,
};

// Define a module that might typically contain benchmarkable functions
pub mod benchmarking {
    use super::*;

    // Function to be benchmarked
    pub fn ping_for_benchmark() -> ProgramResult {
        Ok(())
    }
} 