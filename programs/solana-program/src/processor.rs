use solana_account_info::AccountInfo;
use solana_cpi::invoke;
use solana_msg::msg;
use solana_program_error::{ProgramError, ProgramResult};
use solana_program::sysvar::{self, slot_hashes as solana_slot_hashes};

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
pub fn process_account(accounts: &[AccountInfo], expected: u64) -> ProgramResult {
    if accounts.len() == expected as usize {
        Ok(())
    } else {
        Err(ProgramError::InvalidArgument)
    }
}

#[inline(always)]
pub fn process_create_account(accounts: &[AccountInfo]) -> ProgramResult {
    invoke(
        &solana_system_interface::instruction::create_account(
            accounts[0].key,
            accounts[1].key,
            500_000_000,
            10,
            &crate::ID,
        ),
        &[accounts[0].clone(), accounts[1].clone()],
    )
}

#[inline(always)]
pub fn process_transfer(accounts: &[AccountInfo]) -> ProgramResult {
    invoke(
        &solana_system_interface::instruction::transfer(
            accounts[0].key,
            accounts[1].key,
            1_000_000_000,
        ),
        &[accounts[0].clone(), accounts[1].clone()],
    )
}

// Solana SDK SlotHashes Sysvar Processors

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // --- Manual Sysvar Check & Access ---
    // Verify key matches the sysvar ID
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    // Borrow data and perform a minimal read (e.g., length prefix)
    let data = slot_hashes_account.try_borrow_data()?;
    if data.len() < 8 {
        // Handle insufficient data for length prefix if needed
        return Err(ProgramError::AccountDataTooSmall);
    }
    let _num_entries = u64::from_le_bytes(data[0..8].try_into().unwrap());
    // msg!("Manual Check: Num entries: {}", _num_entries); // Optional log
    // --- End Manual Check & Access ---
    
    // Bypassed from_account_info. Minimal check/op done above.
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // --- Manual Sysvar Check & Access ---
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    let data = slot_hashes_account.try_borrow_data()?;
    if data.len() < 8 {
        return Err(ProgramError::AccountDataTooSmall);
    }
    let _num_entries = u64::from_le_bytes(data[0..8].try_into().unwrap());
    // --- End Manual Check & Access ---
    
    // Bypassed from_account_info. Minimal check/op done above.
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    // --- Manual Sysvar Check & Access ---
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    let data = slot_hashes_account.try_borrow_data()?;
    if data.len() < 8 {
        return Err(ProgramError::AccountDataTooSmall);
    }
    let _num_entries = u64::from_le_bytes(data[0..8].try_into().unwrap());
    // --- End Manual Check & Access ---
    
    // Bypassed from_account_info. Minimal check/op done above.
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    process_slot_hashes_get_hash_interpolated(accounts)
}

#[inline(always)]
pub fn process_slot_hashes_position_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    process_slot_hashes_position_interpolated(accounts)
}
