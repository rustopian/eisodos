use {
    crate::cpi::{create_account_unchecked, transfer_unchecked},
    solana_nostd_entrypoint::NoStdAccountInfo,
    solana_program::{entrypoint::ProgramResult, msg, program_error::ProgramError},
    solana_program::sysvar::{slot_hashes as solana_slot_hashes},
    // borsh::de::BorshDeserialize, // Removed as unused (code using it is commented out)
};

#[inline(always)]
pub fn process_ping() -> ProgramResult {
    Ok(())
}

#[inline(always)]
pub fn process_log() -> ProgramResult {
    msg!("Instruction: Log");
    Ok(())
}

#[inline(always)]
pub fn process_account(accounts: &[NoStdAccountInfo], expected: u64) -> ProgramResult {
    if accounts.len() == expected as usize {
        Ok(())
    } else {
        Err(ProgramError::InvalidArgument)
    }
}

#[inline(always)]
pub fn process_create_account(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let [from, to, _remaining @ ..] = accounts else {
        return Err(ProgramError::InvalidArgument);
    };

    unsafe { create_account_unchecked(from, to, 500_000_000, 10, &crate::ID) }
}

#[inline(always)]
pub fn process_transfer(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let [from, to, _remaining @ ..] = accounts else {
        return Err(ProgramError::InvalidArgument);
    };

    unsafe { transfer_unchecked(from, to, 1_000_000_000) }
}

// Solana SDK SlotHashes Sysvar Processors

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let _slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let _slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let _slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_midpoint(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    process_slot_hashes_get_hash_interpolated(accounts)
}

#[inline(always)]
pub fn process_slot_hashes_position_midpoint(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    process_slot_hashes_position_interpolated(accounts)
}
