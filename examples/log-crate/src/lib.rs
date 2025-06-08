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

#[cfg(feature = "solana-nostd-entrypoint")]
pub mod nostd_entrypoint_benches {
    use solana_nostd_entrypoint::NoStdAccountInfo as AccountInfo;
    use solana_program_error::ProgramResult;
    use solana_pubkey::Pubkey;

    pub fn run_log_bench(_program_id: &Pubkey, _accounts: &[AccountInfo], _instruction_data: &[u8]) -> ProgramResult {
        // Use a simple log function that should work in nostd environment
        // Since there's no built-in logging in nostd, we'll use a dummy operation
        // or add a basic logging function if available
        #[cfg(target_os = "solana")]
        unsafe {
            let message = b"Hello from Solana NoStd log benchmark!";
            solana_syscalls::sol_log(message.as_ptr(), message.len() as u64);
        }
        
        // For non-Solana targets (tests, etc.) just use black_box to prevent optimization
        #[cfg(not(target_os = "solana"))]
        core::hint::black_box("Hello from Solana NoStd log benchmark!");
        
        Ok(())
    }
} 