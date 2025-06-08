#![cfg_attr(not(any(feature = "std", feature = "solana-program-mono", feature = "solana-nostd-entrypoint")), no_std)]

// === no_std specific setup (pinocchio only) ===
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
extern crate alloc;

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
use pinocchio::{
    ProgramResult,
    no_allocator,
    nostd_panic_handler,
    pubkey::Pubkey,
    account_info::AccountInfo,
    instruction::{Instruction, AccountMeta, Account as CpiAccount},
    cpi::invoke_signed_unchecked,
    program_error::ProgramError,
};

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
no_allocator!();
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
nostd_panic_handler!();

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
const PINOCCHIO_SYSTEM_PROGRAM_ID: Pubkey = [0u8; 32];
// ============================

// === std specific setup (broken-out crates) ===
#[cfg(all(feature = "std", not(feature = "solana-nostd-entrypoint")))]
use {
    solana_account_info::{AccountInfo, next_account_info},
    solana_entrypoint::ProgramResult,
    solana_cpi::invoke,
    solana_program_error::ProgramError,
    solana_pubkey::Pubkey,
    solana_system_interface::instruction,
};
// =========================

// === solana-nostd-entrypoint specific setup ===
#[cfg(feature = "solana-nostd-entrypoint")]
use {
    solana_nostd_entrypoint_dep::NoStdAccountInfo as AccountInfo,
    solana_program_error::{ProgramResult, ProgramError},
    solana_nostd_entrypoint_dep::solana_program::pubkey::Pubkey,
    solana_syscalls,
};
// =========================

// === solana-program-mono specific setup ===
#[cfg(feature = "solana-program-mono")]
use solana_program::{
    account_info::{AccountInfo, next_account_info},
    entrypoint::ProgramResult,
    program::invoke,
    program_error::ProgramError,
    pubkey::Pubkey,
    system_instruction,
};
// =========================

// Define a simple instruction structure for this crate
// byte 0: instruction_tag (0 for Transfer)
// byte 1-8: amount (u64)
const TRANSFER_INSTRUCTION_TAG: u8 = 0;
const AMOUNT_OFFSET: usize = 1;
const REQUIRED_INSTRUCTION_DATA_LEN: usize = 9;

#[cfg(feature = "solana-program")]
pub mod solana_benches {
    use {
        solana_account_info::{AccountInfo, next_account_info},
        solana_entrypoint::ProgramResult,
        solana_cpi::invoke,
        solana_program_error::ProgramError,
        solana_pubkey::Pubkey,
        solana_system_interface::instruction,
    };
    use super::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_transfer_bench(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let amount = u64::from_le_bytes(instruction_data[AMOUNT_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let account_iter = &mut accounts.iter();
        let source_account = next_account_info(account_iter)?;
        let destination_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;

        invoke(
            &instruction::transfer(
                source_account.key,
                destination_account.key,
                amount,
            ),
            &[
                source_account.clone(),
                destination_account.clone(),
                system_program_account.clone(),
            ],
        )
    }
}

#[cfg(all(feature = "std", not(feature = "solana-nostd-entrypoint")))]
pub mod std_benches {
    use crate::{AccountInfo, ProgramResult, ProgramError, Pubkey, invoke, instruction, next_account_info};
    use super::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_transfer_bench(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let amount = u64::from_le_bytes(instruction_data[AMOUNT_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let account_iter = &mut accounts.iter();
        let source_account = next_account_info(account_iter)?;
        let destination_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;

        invoke(
            &instruction::transfer(
                source_account.key,
                destination_account.key,
                amount,
            ),
            &[
                source_account.clone(),
                destination_account.clone(),
                system_program_account.clone(),
            ],
        )
    }
}

#[cfg(feature = "solana-nostd-entrypoint")]
pub mod nostd_entrypoint_benches {
    use crate::{AccountInfo, ProgramResult, ProgramError, Pubkey};
    use super::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};
    use solana_nostd_entrypoint_dep::InstructionC;

    const SYSTEM_PROGRAM_ID: [u8; 32] = [0u8; 32];

    pub fn run_transfer_bench(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let amount = u64::from_le_bytes(instruction_data[AMOUNT_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let source_account = &accounts[0];
        let destination_account = &accounts[1];

        // Prepare system program transfer instruction data
        // Transfer has discriminant 2_u32 (little endian), followed by u64 lamport amount
        let mut system_instruction_data = [0u8; 12];
        system_instruction_data[0..4].copy_from_slice(&2u32.to_le_bytes()); // Transfer discriminator
        system_instruction_data[4..12].copy_from_slice(&amount.to_le_bytes());

        // Prepare instruction accounts using NoStdAccountInfo methods
        let instruction_accounts = [source_account.to_meta_c(), destination_account.to_meta_c()];

        // Build instruction expected by sol_invoke_signed_c
        let instruction = InstructionC {
            program_id: &Pubkey::from(SYSTEM_PROGRAM_ID),
            accounts: instruction_accounts.as_ptr(),
            accounts_len: instruction_accounts.len() as u64,
            data: system_instruction_data.as_ptr(),
            data_len: system_instruction_data.len() as u64,
        };

        // Get account infos
        let infos = [source_account.to_info_c(), destination_account.to_info_c()];

        // Invoke system program
        #[cfg(target_os = "solana")]
        unsafe {
            solana_syscalls::sol_invoke_signed_c(
                &instruction as *const InstructionC as *const u8,
                infos.as_ptr() as *const u8,
                infos.len() as u64,
                core::ptr::null(),
                0,
            );
        }

        // For non-Solana targets (tests, etc.)
        #[cfg(not(target_os = "solana"))]
        core::hint::black_box(&(&instruction, &infos));

        Ok(())
    }
}

#[cfg(feature = "solana-program-mono")]
pub mod solana_program_mono_benches {
    use solana_program::{
        account_info::{AccountInfo, next_account_info},
        entrypoint::ProgramResult,
        program::invoke,
        program_error::ProgramError,
        pubkey::Pubkey,
        system_instruction,
    };
    use super::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_transfer_bench(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let amount = u64::from_le_bytes(instruction_data[AMOUNT_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let account_iter = &mut accounts.iter();
        let source_account = next_account_info(account_iter)?;
        let destination_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;

        invoke(
            &system_instruction::transfer(
                source_account.key,
                destination_account.key,
                amount,
            ),
            &[
                source_account.clone(),
                destination_account.clone(),
                system_program_account.clone(),
            ],
        )
    }
}

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
pub mod pinocchio_benches {
    use crate::{ProgramResult, Pubkey, AccountInfo, Instruction, AccountMeta, CpiAccount, invoke_signed_unchecked, ProgramError, PINOCCHIO_SYSTEM_PROGRAM_ID};
    use crate::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_transfer_bench(
        _program_id: &Pubkey, 
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let amount = u64::from_le_bytes(instruction_data[AMOUNT_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let source_account_info = &accounts[0];
        let destination_account_info = &accounts[1];

        let mut system_instruction_data = [0u8; 12]; 
        system_instruction_data[0..4].copy_from_slice(&2u32.to_le_bytes()); // System Program Transfer discriminator is 2
        system_instruction_data[4..12].copy_from_slice(&amount.to_le_bytes());

        let account_metas = [
            AccountMeta::writable_signer(source_account_info.key()),
            AccountMeta::writable(destination_account_info.key()),
        ];

        let ix = Instruction {
            program_id: &PINOCCHIO_SYSTEM_PROGRAM_ID,
            accounts: &account_metas,
            data: &system_instruction_data,
        };

        let source_cpi_account = CpiAccount::from(source_account_info);
        let destination_cpi_account = CpiAccount::from(destination_account_info);
        let accounts_for_invoke: [CpiAccount; 2] = [source_cpi_account, destination_cpi_account];

        unsafe {
            invoke_signed_unchecked(&ix, &accounts_for_invoke, &[]);
        }
        Ok(())
    }
} 