use crate::cpi::{create_account_unchecked, transfer_unchecked};
use pinocchio::{account_info::AccountInfo, msg, program_error::ProgramError, ProgramResult};
use pinocchio::sysvars::slot_hashes::{
    SlotHashes,
    get_entry_count_unchecked,
    get_entry_from_slice_unchecked,
    position_from_slice_unchecked,
    get_hash_from_slice_unchecked,
    position_midpoint_from_slice_unchecked,
    get_hash_midpoint_from_slice_unchecked,
};
use pinocchio::pubkey::log as log_pubkey;
use pinocchio::pubkey::Pubkey;

#[inline(always)]
pub fn process_ping() -> ProgramResult {
    Ok(())
}

#[inline(always)]
pub fn process_log() -> ProgramResult {
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
    let [from, to, _remaining @ ..] = accounts else {
        return Err(ProgramError::InvalidArgument);
    };

    unsafe { create_account_unchecked(from, to, 500_000_000, 10, &crate::ID) }
}

#[inline(always)]
pub fn process_transfer(accounts: &[AccountInfo]) -> ProgramResult {
    let [from, to, _remaining @ ..] = accounts else {
        return Err(ProgramError::InvalidArgument);
    };

    unsafe { transfer_unchecked(from, to, 1_000_000_000) }
}

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.get_entry(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.get_hash(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.position(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    #[cfg(feature = "test-helpers")]
    let _ = slot_hashes.get_hash_midpoint(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    #[cfg(feature = "test-helpers")]
    let _ = slot_hashes.position_midpoint(0);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_get_entry_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked(); 
    let _entry = get_entry_from_slice_unchecked(data, 0);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_get_hash_interpolated_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked(); 
    let target_slot = 0; 
    let _hash_opt = get_hash_from_slice_unchecked(data, target_slot);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_position_interpolated_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked(); 
    let target_slot = 0; 
    let _pos_opt = position_from_slice_unchecked(data, target_slot);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_get_hash_midpoint_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked(); 
    let target_slot = 0; 
    let _hash_opt = get_hash_midpoint_from_slice_unchecked(data, target_slot);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_position_midpoint_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked(); 
    let target_slot = 0; 
    let _pos_opt = position_midpoint_from_slice_unchecked(data, target_slot);
    Ok(())
}

