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
    instruction::{AccountMeta, Instruction, Account as CpiAccount},
    cpi::invoke_signed_unchecked, 
    program_error::ProgramError,
};

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
no_allocator!();
#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
nostd_panic_handler!();

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
const PINOCCHIO_SYSTEM_PROGRAM_ID: Pubkey = [0u8; 32];

// === std specific setup (broken-out crates) ===
#[cfg(all(feature = "std", not(feature = "solana-nostd-entrypoint")))]
use {
    solana_account_info::{AccountInfo, next_account_info},
    solana_program_error::{ProgramResult, ProgramError},
    solana_cpi::invoke,
    solana_pubkey::Pubkey,
    solana_system_interface::{instruction, program},
};
// =========================

// === solana-nostd-entrypoint specific setup ===
#[cfg(feature = "solana-nostd-entrypoint")]
use {
    solana_nostd_entrypoint_dep::NoStdAccountInfo as AccountInfo,
    solana_program_error::{ProgramResult, ProgramError},
    solana_nostd_entrypoint_dep::solana_program::pubkey::Pubkey,
};
// =========================

// Define a simple instruction structure for this crate
// byte 0: instruction_tag (0 for CreateAccount)
// byte 1-8: lamports (u64)
// byte 9-16: space (u64)
const CREATE_ACCOUNT_INSTRUCTION_TAG: u8 = 0;
const LAMPORTS_OFFSET: usize = 1;
const SPACE_OFFSET: usize = 9;
const REQUIRED_INSTRUCTION_DATA_LEN: usize = 17;

#[cfg(all(feature = "solana-program", not(feature = "solana-nostd-entrypoint")))]
pub mod solana_benches {
    use {
        solana_account_info::{AccountInfo, next_account_info},
        solana_program_error::{ProgramResult, ProgramError},
        solana_cpi::invoke,
        solana_pubkey::Pubkey,
        solana_system_interface::{instruction, program},
    };
    use super::{CREATE_ACCOUNT_INSTRUCTION_TAG, LAMPORTS_OFFSET, SPACE_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

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

        let account_iter = &mut accounts.iter();
        let funder_account = next_account_info(account_iter)?;
        let new_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;
        
        if system_program_account.key != &program::ID {
            // Optional: Add a specific error if system program ID is not as expected
            // return Err(ProgramError::IncorrectProgramId);
        }

        invoke(
            &instruction::create_account(
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

#[cfg(all(feature = "std", not(feature = "solana-nostd-entrypoint")))]
pub mod std_benches {
    use crate::{AccountInfo, ProgramResult, ProgramError, Pubkey, invoke, instruction, program, next_account_info};
    use super::{CREATE_ACCOUNT_INSTRUCTION_TAG, LAMPORTS_OFFSET, SPACE_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};

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

        let account_iter = &mut accounts.iter();
        let funder_account = next_account_info(account_iter)?;
        let new_account = next_account_info(account_iter)?;
        let system_program_account = next_account_info(account_iter)?;
        
        if system_program_account.key != &program::ID {
            // Optional: Add a specific error if system program ID is not as expected
            // return Err(ProgramError::IncorrectProgramId);
        }

        invoke(
            &instruction::create_account(
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

#[cfg(feature = "solana-nostd-entrypoint")]
pub mod nostd_entrypoint_benches {
    use crate::{AccountInfo, ProgramResult, ProgramError, Pubkey};
    use super::{CREATE_ACCOUNT_INSTRUCTION_TAG, LAMPORTS_OFFSET, SPACE_OFFSET, REQUIRED_INSTRUCTION_DATA_LEN};
    use solana_nostd_entrypoint_dep::{InstructionC, AccountInfoC, NoStdAccountInfo};
    use core::mem::MaybeUninit;

    const SYSTEM_PROGRAM_ID: [u8; 32] = [0u8; 32];

    /// Helper function to invoke a program (following the pattern from the original test program)
    unsafe fn invoke_unchecked<const ACCOUNTS: usize>(
        instruction: &InstructionC,
        accounts: &[&NoStdAccountInfo; ACCOUNTS],
    ) -> ProgramResult {
        if (instruction.accounts_len as usize) < ACCOUNTS {
            return Err(ProgramError::NotEnoughAccountKeys);
        }

        const UNINIT: MaybeUninit<AccountInfoC> = MaybeUninit::<AccountInfoC>::uninit();
        let mut infos = [UNINIT; ACCOUNTS];
        infos
            .iter_mut()
            .zip(accounts.iter())
            .for_each(|(info, account)| {
                info.write(account.to_info_c());
            });

        let seeds: &[&[&[u8]]] = &[];

        // Invoke system program
        #[cfg(target_os = "solana")]
        unsafe {
            extern "C" {
                fn sol_invoke_signed_c(
                    instruction_addr: *const u8,
                    account_infos_addr: *const u8,
                    account_infos_len: u64,
                    seed_addr: *const u8,
                    seed_len: u64,
                ) -> u64;
            }
            sol_invoke_signed_c(
                instruction as *const InstructionC as *const u8,
                infos.as_ptr() as *const u8,
                infos.len() as u64,
                seeds.as_ptr() as *const u8,
                seeds.len() as u64,
            );
        }

        // For non-Solana targets (tests, etc.)
        #[cfg(not(target_os = "solana"))]
        core::hint::black_box(&(&instruction, &accounts, &seeds));

        Ok(())
    }

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

        let funder_account = &accounts[0];
        let new_account = &accounts[1];

        // Prepare system program create_account instruction data
        // CreateAccount has discriminant 0_u32 (little endian), followed by lamports, space, and owner
        let mut system_instruction_data = [0u8; 52];
        // create account instruction has a '0' discriminator (already set by initialization)
        system_instruction_data[4..12].copy_from_slice(&lamports.to_le_bytes());
        system_instruction_data[12..20].copy_from_slice(&space.to_le_bytes());
        system_instruction_data[20..52].copy_from_slice(program_id.as_ref());

        let instruction_accounts = [funder_account.to_meta_c_signer(), new_account.to_meta_c_signer()];

        let system_program_id = unsafe { 
            core::mem::transmute::<&[u8; 32], &solana_nostd_entrypoint_dep::solana_program::pubkey::Pubkey>(&SYSTEM_PROGRAM_ID)
        };

        let instruction = InstructionC {
            program_id: system_program_id,
            accounts: instruction_accounts.as_ptr(),
            accounts_len: instruction_accounts.len() as u64,
            data: system_instruction_data.as_ptr(),
            data_len: system_instruction_data.len() as u64,
        };

        unsafe {
            invoke_unchecked(&instruction, &[funder_account, new_account])
        }
    }
}

#[cfg(all(feature = "solana-program-mono", not(feature = "solana-nostd-entrypoint")))]
pub mod solana_program_mono_benches {
    use solana_program::{
        account_info::{AccountInfo, next_account_info},
        entrypoint::ProgramResult,
        program::invoke,
        program_error::ProgramError,
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
            return Err(ProgramError::InvalidInstructionData);
        }
        if instruction_data.len() < REQUIRED_INSTRUCTION_DATA_LEN {
            return Err(ProgramError::InvalidInstructionData);
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

#[cfg(all(feature = "no_std", not(feature = "solana-nostd-entrypoint")))]
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