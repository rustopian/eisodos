#![cfg_attr(feature = "no_std", no_std)]

// === no_std specific setup ===
#[cfg(feature = "no_std")]
extern crate alloc;

#[cfg(feature = "no_std")]
use pinocchio::{
    ProgramResult,
    no_allocator,
    nostd_panic_handler,
    pubkey::Pubkey,
    account_info::AccountInfo,
};

// Handlers MUST be present for no_std SBF builds if the SDK doesn't provide them globally
#[cfg(feature = "no_std")]
no_allocator!();
#[cfg(feature = "no_std")]
nostd_panic_handler!();
// ============================

#[cfg(feature = "solana-program")]
pub mod solana_benches {
    use solana_entrypoint::ProgramResult;
    use solana_pubkey::Pubkey;
    use solana_account_info::AccountInfo;
    use solana_msg::msg;

    pub fn run_log_bench(_program_id: &Pubkey, _accounts: &[AccountInfo], _instruction_data: &[u8]) -> ProgramResult {
        // Use msg! macro for logging in BPF programs
        msg!("Hello from Solana BPF log benchmark!");
        Ok(())
    }
}

#[cfg(feature = "solana-program-mono")]
pub mod solana_program_mono_benches {
    use solana_program::{
        entrypoint::ProgramResult,
        pubkey::Pubkey,
        account_info::AccountInfo,
        msg,
    };

    pub fn run_log_bench(_program_id: &Pubkey, _accounts: &[AccountInfo], _instruction_data: &[u8]) -> ProgramResult {
        // Use msg! macro for logging in BPF programs
        msg!("Hello from Solana BPF log benchmark!");
        Ok(())
    }
}

#[cfg(feature = "no_std")]
pub mod pinocchio_benches {
    use crate::{ProgramResult, Pubkey, AccountInfo};
    use pinocchio::log::sol_log; 

    pub fn run_log_bench(
        _program_id: &Pubkey, 
        _accounts: &[AccountInfo],
        _instruction_data: &[u8]
    ) -> ProgramResult {
        sol_log("Hello from Pinocchio log benchmark!");
        Ok(())
    }
} 