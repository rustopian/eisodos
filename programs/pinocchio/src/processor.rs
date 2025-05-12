use crate::cpi::{create_account_unchecked, transfer_unchecked};
use pinocchio::pubkey::log as log_pubkey;
use pinocchio::pubkey::Pubkey;
use pinocchio::sysvars::slot_hashes::{
    get_entry_from_slice_unchecked, get_hash_from_slice_unchecked,
    position_from_slice_binary_search_unchecked, SlotHashes, MAX_ENTRIES as MAX_SLOT_HASH_ENTRIES,
    NUM_ENTRIES_SIZE, SLOT_SIZE, ENTRY_SIZE
};
use pinocchio::sysvars::clock::Slot;
use pinocchio::{account_info::AccountInfo, msg, program_error::ProgramError, ProgramResult};

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
pub unsafe fn process_slot_hashes_get_entry_unchecked(accounts: &[AccountInfo]) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked();
    let _entry = get_entry_from_slice_unchecked(data, 0);
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_get_hash_interpolated_unchecked(
    accounts: &[AccountInfo],
) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked();
    let target_slot = 0;
    let hash_opt = get_hash_from_slice_unchecked(data, target_slot, MAX_SLOT_HASH_ENTRIES);
    if hash_opt.is_some() {
        msg!("GH found");
    } else {
        msg!("GH not found");
    }
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_position_interpolated_unchecked(
    accounts: &[AccountInfo],
    target_slot: Slot
) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked();
    let pos_opt = position_from_slice_binary_search_unchecked(data, target_slot, MAX_SLOT_HASH_ENTRIES);
    if pos_opt.is_some() {
        msg!("IP found");
    } else {
        msg!("IP not found");
    }
    Ok(())
}

#[inline(always)]
pub unsafe fn process_slot_hashes_position_naive_unchecked(
    accounts: &[AccountInfo],
    target_slot: Slot
) -> ProgramResult {
    let account = &accounts[0];
    let data = account.borrow_data_unchecked();
    let num_entries_val = MAX_SLOT_HASH_ENTRIES;

    // --- Naive Binary Search Logic (directly implemented) ---
    let result_idx: Option<usize> = {
        if num_entries_val == 0 {
            None
        } else {
            let mut low = 0;
            let mut high = num_entries_val;
            let mut found_idx: Option<usize> = None;
            while low < high {
                let mid_idx = low + (high - low) / 2;
                // Bounds check simulation: mid_idx is always < high <= num_entries_val
                let entry_offset = NUM_ENTRIES_SIZE + mid_idx * ENTRY_SIZE;
                // Unchecked access relies on benchmark providing correctly sized data (>= offset + ENTRY_SIZE)
                let entry_bytes = data.get_unchecked(entry_offset..(entry_offset + ENTRY_SIZE));
                let mid_slot = u64::from_le_bytes(
                    entry_bytes
                        .get_unchecked(0..SLOT_SIZE)
                        .try_into()
                        .unwrap_unchecked(),
                );
                match mid_slot.cmp(&target_slot) {
                    core::cmp::Ordering::Equal => {
                        found_idx = Some(mid_idx);
                        break;
                    }
                    // Remember: SlotHashes are stored in descending order
                    core::cmp::Ordering::Less => high = mid_idx, // mid_slot < target_slot, so target is in lower indices (left half)
                    core::cmp::Ordering::Greater => low = mid_idx + 1, // mid_slot > target_slot, so target is in higher indices (right half)
                }
            }
            found_idx
        }
    };
    if result_idx.is_some() {
        msg!("NP found");
    } else {
        msg!("NP not found");
    }

    Ok(())
}

