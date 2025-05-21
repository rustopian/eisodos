#![cfg_attr(not(feature = "std"), no_std)]

// === no_std specific setup ===
#[cfg(not(feature = "std"))]
extern crate alloc;

#[cfg(not(feature = "std"))]
use pinocchio::{
    ProgramResult,
    no_allocator,
    nostd_panic_handler,
    pubkey::Pubkey,
    account_info::AccountInfo,
};
#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};

// Handlers MUST be present for no_std SBF builds if the SDK doesn't provide them globally
#[cfg(not(feature = "std"))]
no_allocator!();
#[cfg(not(feature = "std"))]
nostd_panic_handler!();
// ============================

#[cfg(feature = "std")]
pub mod solana_benches {
    use solana_entrypoint::ProgramResult;
    use solana_pubkey::Pubkey;
    use solana_account_info::AccountInfo;
    use solana_program::log::sol_log; // see if this crate has been pulled out

    pub fn run_log_bench(_program_id: &Pubkey, _accounts: &[AccountInfo], _instruction_data: &[u8]) -> ProgramResult {
        sol_log("Hello from Solana log benchmark!");
        for i in 0..10 {
            sol_log(&format!("Log message {} from solana bench", i));
        }
        Ok(())
    }
}

#[cfg(not(feature = "std"))]
pub mod pinocchio_benches {
    use crate::ProgramResult;
    use crate::{Pubkey, AccountInfo}; // Ensure these are available if signature requires them
    use pinocchio::log::sol_log; 

    pub fn run_log_bench(
        _program_id: &Pubkey, 
        _accounts: &[AccountInfo],
        _instruction_data: &[u8]
    ) -> ProgramResult {
        sol_log("Hello from Pinocchio log benchmark!");
        sol_log("Loop starting...");
        for i in 0..10 {
            // Log only static string literals to test if String allocation/formatting is the issue
            match i {
                0 => sol_log("P_Log 0"),
                1 => sol_log("P_Log 1"),
                2 => sol_log("P_Log 2"),
                3 => sol_log("P_Log 3"),
                4 => sol_log("P_Log 4"),
                5 => sol_log("P_Log 5"),
                6 => sol_log("P_Log 6"),
                7 => sol_log("P_Log 7"),
                8 => sol_log("P_Log 8"),
                9 => sol_log("P_Log 9"),
                _ => sol_log("P_Log ?"),
            }
        }
        sol_log("Loop finished.");
        Ok(())
    }
} 