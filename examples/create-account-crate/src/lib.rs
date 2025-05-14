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
    instruction::{AccountMeta, Instruction, Account as CpiAccount},
    cpi::invoke_signed_unchecked, 
    program_error::ProgramError,
};

#[cfg(feature = "no_std")]
no_allocator!();
#[cfg(feature = "no_std")]
nostd_panic_handler!();

#[cfg(feature = "no_std")]
const PINOCCHIO_SYSTEM_PROGRAM_ID: Pubkey = [0u8; 32];

// Define a simple instruction structure for this crate
// byte 0: instruction_tag (0 for CreateAccount)
// byte 1-8: lamports (u64)
// byte 9-16: space (u64)
const CREATE_ACCOUNT_INSTRUCTION_TAG: u8 = 0;
const LAMPORTS_OFFSET: usize = 1;
const SPACE_OFFSET: usize = 9;
const REQUIRED_INSTRUCTION_DATA_LEN: usize = 17;

#[cfg(feature = "std")]
pub mod solana_benches {
    use solana_program::{
        account_info::{next_account_info, AccountInfo},
        entrypoint::ProgramResult,
        program::invoke,
        pubkey::Pubkey,
        system_instruction,
        system_program,
    };
    use super::{CREATE_ACCOUNT_INSTRUCTION_TAG, LAMPORTS_OFFSET, SPACE_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_create_account_bench(
        program_id: &Pubkey,
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != CREATE_ACCOUNT_INSTRUCTION_TAG {
            return Err(solana_program::program_error::ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(solana_program::program_error::ProgramError::InvalidInstructionData);
        }

        let lamports = u64::from_le_bytes(instruction_data[LAMPORTS_OFFSET..SPACE_OFFSET].try_into().unwrap());
        let space = u64::from_le_bytes(instruction_data[SPACE_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let account_iter = &mut accounts.iter();
        let funder_account = next_account_info(account_iter)?;
        let new_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;
        
        if system_program_account.key != &system_program::ID {
            // Optional: Add a specific error if system program ID is not as expected
            // return Err(ProgramError::IncorrectProgramId);
        }

        invoke(
            &system_instruction::create_account(
                funder_account.key,
                new_account.key,
                lamports,
                space,
                program_id,
            ),
            &[
                funder_account.clone(),
                new_account.clone(),
                system_program_account.clone(),
            ],
        )
    }
}

#[cfg(feature = "no_std")]
pub mod pinocchio_benches {
    use crate::{ProgramResult, Pubkey, AccountInfo, Instruction, AccountMeta, CpiAccount, invoke_signed_unchecked, ProgramError, PINOCCHIO_SYSTEM_PROGRAM_ID};
    use crate::{CREATE_ACCOUNT_INSTRUCTION_TAG, LAMPORTS_OFFSET, SPACE_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

    pub fn run_create_account_bench(
        program_id: &Pubkey, 
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult {
        if instruction_data.is_empty() || instruction_data[0] != CREATE_ACCOUNT_INSTRUCTION_TAG {
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
        }

        let lamports = u64::from_le_bytes(instruction_data[LAMPORTS_OFFSET..SPACE_OFFSET].try_into().unwrap());
        let space = u64::from_le_bytes(instruction_data[SPACE_OFFSET..REQUIRED_INSTRUCTION_DATA_LEN].try_into().unwrap());

        let funder_account_info = &accounts[0]; 
        let new_account_info = &accounts[1];   

        let mut system_instruction_data = [0u8; 52];
        system_instruction_data[0..4].copy_from_slice(&0u32.to_le_bytes()); // CreateAccount discriminator for System Program
        system_instruction_data[4..12].copy_from_slice(&lamports.to_le_bytes());
        system_instruction_data[12..20].copy_from_slice(&space.to_le_bytes());
        system_instruction_data[20..52].copy_from_slice(program_id.as_ref());

        let account_metas = [
            AccountMeta::writable_signer(funder_account_info.key()),
            AccountMeta::writable_signer(new_account_info.key()),
        ];

        let ix = Instruction {
            program_id: &PINOCCHIO_SYSTEM_PROGRAM_ID,
            accounts: &account_metas,
            data: &system_instruction_data,
        };
        
        // Convert AccountInfo to pinocchio::instruction::Account (CpiAccount) for invoke_signed_unchecked
        let funder_cpi_account = CpiAccount::from(funder_account_info);
        let new_cpi_account = CpiAccount::from(new_account_info);
        let accounts_for_invoke: [CpiAccount; 2] = [funder_cpi_account, new_cpi_account];

        unsafe {
            invoke_signed_unchecked(&ix, &accounts_for_invoke, &[]); 
        }
        Ok(())
    }
} 