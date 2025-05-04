use {
    crate::cpi::{create_account_unchecked, transfer_unchecked},
    solana_nostd_entrypoint::NoStdAccountInfo,
    solana_program::{entrypoint::ProgramResult, program_error::ProgramError},
    solana_program::sysvar::{slot_hashes as solana_slot_hashes},
    // borsh::de::BorshDeserialize, // Removed as unused (code using it is commented out)
};
use bytemuck::{Zeroable, Pod, cast_slice, from_bytes};
use core::mem::size_of;

#[inline(always)]
pub fn process_ping() -> ProgramResult {
    Ok(())
}

#[inline(always)]
pub fn process_log() -> ProgramResult {
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

// --- Bytemuck based SlotHashes access ---

// Define the structure matching the account data layout
#[repr(C)]
#[derive(Clone, Copy, Zeroable, Pod, Debug)]
struct SlotHashEntry {
    slot: u64,
    hash: [u8; 32],
}

const SLOT_HASH_ENTRY_SIZE: usize = size_of::<SlotHashEntry>(); // Should be 8 + 32 = 40
const LEN_PREFIX_SIZE: usize = size_of::<u64>(); // Using u64 based on Pinocchio's definition and benchmark data

// Solana SDK SlotHashes Sysvar Processors (Using bytemuck)

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    if data.len() < LEN_PREFIX_SIZE {
        return Err(ProgramError::AccountDataTooSmall);
    }

    let num_entries: u64 = *from_bytes(&data[0..LEN_PREFIX_SIZE]);
    let num_entries_usize = num_entries as usize;

    let entries_data_start = LEN_PREFIX_SIZE;
    let entries_data_end = entries_data_start.checked_add(
        num_entries_usize.checked_mul(SLOT_HASH_ENTRY_SIZE).ok_or(ProgramError::ArithmeticOverflow)?
    ).ok_or(ProgramError::ArithmeticOverflow)?;

    if data.len() < entries_data_end {
        return Err(ProgramError::AccountDataTooSmall); // Or InvalidAccountData
    }

    let entries: &[SlotHashEntry] = cast_slice(&data[entries_data_start..entries_data_end]);

    // Minimal operation: check if empty (equivalent to previous check)
    let _ = entries.is_empty();

    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    if data.len() < LEN_PREFIX_SIZE { return Err(ProgramError::AccountDataTooSmall); }

    let num_entries: u64 = *from_bytes(&data[0..LEN_PREFIX_SIZE]);
    let num_entries_usize = num_entries as usize;

    let entries_data_start = LEN_PREFIX_SIZE;
    let entries_data_end = entries_data_start.checked_add(
        num_entries_usize.checked_mul(SLOT_HASH_ENTRY_SIZE).ok_or(ProgramError::ArithmeticOverflow)?
    ).ok_or(ProgramError::ArithmeticOverflow)?;

    if data.len() < entries_data_end { return Err(ProgramError::AccountDataTooSmall); }

    let entries: &[SlotHashEntry] = cast_slice(&data[entries_data_start..entries_data_end]);

    // Minimal operation: find entry for slot 0 (or nearest if implementing search)
    // For now, just access first entry if possible, similar to SDK get(&0)
    let _ = entries.first().map(|e| e.hash);

    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).filter(|acc| acc.key() == &solana_slot_hashes::ID).ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    if data.len() < LEN_PREFIX_SIZE { return Err(ProgramError::AccountDataTooSmall); }

    let num_entries: u64 = *from_bytes(&data[0..LEN_PREFIX_SIZE]);
    let num_entries_usize = num_entries as usize;

    let entries_data_start = LEN_PREFIX_SIZE;
    let entries_data_end = entries_data_start.checked_add(
        num_entries_usize.checked_mul(SLOT_HASH_ENTRY_SIZE).ok_or(ProgramError::ArithmeticOverflow)?
    ).ok_or(ProgramError::ArithmeticOverflow)?;

    if data.len() < entries_data_end { return Err(ProgramError::AccountDataTooSmall); }

    let entries: &[SlotHashEntry] = cast_slice(&data[entries_data_start..entries_data_end]);

    // Minimal operation: find position of slot 0 (or nearest if implementing search)
    // For now, just check if first entry exists, similar to SDK position(&0)
    let _ = entries.first().map(|_| 0usize);

    Ok(())
}

// --- Midpoint versions remain identical for now, as no search is implemented ---
#[inline(always)]
pub fn process_slot_hashes_get_hash_midpoint(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    process_slot_hashes_get_hash_interpolated(accounts)
}

#[inline(always)]
pub fn process_slot_hashes_position_midpoint(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    process_slot_hashes_position_interpolated(accounts)
}
