#![cfg_attr(not(feature = "std"), no_std)]

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
    instruction::{Instruction, AccountMeta, Account as CpiAccount},
    cpi::invoke_signed_unchecked,
    program_error::ProgramError,
};

#[cfg(feature = "no_std")]
no_allocator!();
#[cfg(feature = "no_std")]
nostd_panic_handler!();

#[cfg(feature = "no_std")]
const PINOCCHIO_SYSTEM_PROGRAM_ID: Pubkey = [0u8; 32];
// ============================

// Define a simple instruction structure for this crate
// byte 0: instruction_tag (0 for Transfer)
// byte 1-8: amount (u64)
const TRANSFER_INSTRUCTION_TAG: u8 = 0;
const AMOUNT_OFFSET: usize = 1;
const REQUIRED_INSTRUCTION_DATA_LEN: usize = 9;

#[cfg(feature = "std")]
pub mod solana_benches {
    use {
        solana_account_info::{AccountInfo, next_account_info},
        solana_entrypoint::ProgramResult,
        solana_invoke,
        solana_msg,
        solana_program_error::ProgramError,
        solana_pubkey::Pubkey,
        solana_system_program::system_instruction,
    };
    use super::{TRANSFER_INSTRUCTION_TAG, AMOUNT_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_transfer_bench(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != TRANSFER_INSTRUCTION_TAG {
            return Err(solana_program::program_error::ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(solana_program::program_error::ProgramError::InvalidInstructionData);
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

#[cfg(feature = "no_std")]
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