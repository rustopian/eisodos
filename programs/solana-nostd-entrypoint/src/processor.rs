use bytemuck::{cast_slice, from_bytes, Pod, Zeroable};
use core::cmp::Ordering;
use core::mem::size_of;
use {
    crate::cpi::{create_account_unchecked, transfer_unchecked},
    solana_nostd_entrypoint::NoStdAccountInfo,
    solana_program::sysvar::slot_hashes as solana_slot_hashes,
    // borsh::de::BorshDeserialize, // Removed as unused (code using it is commented out)
    solana_program::{entrypoint::ProgramResult, program_error::ProgramError},
};

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
const LEN_PREFIX_SIZE: usize = size_of::<u64>();

// Enum to specify which operation the pure function should perform
#[derive(PartialEq, Eq, Debug)]
enum SlotHashOp {
    IsEmpty,          // Returns Ok(()) or Err
    GetHash(u64),     // Search operations return Ok(Option<index>) or Err
    GetPosition(u64), // Search operations return Ok(Option<index>) or Err
}

// Core logic, testable with &[u8]
fn process_slot_hashes_bytes(
    data: &[u8],
    operation: SlotHashOp,
) -> Result<Option<usize>, ProgramError> {
    if data.len() < LEN_PREFIX_SIZE {
        return Err(ProgramError::AccountDataTooSmall);
    }

    let num_entries: u64 = *from_bytes(&data[0..LEN_PREFIX_SIZE]);
    let num_entries_usize = num_entries as usize;

    let entries_data_start = LEN_PREFIX_SIZE;
    let entries_data_end = entries_data_start
        .checked_add(
            num_entries_usize
                .checked_mul(SLOT_HASH_ENTRY_SIZE)
                .ok_or(ProgramError::ArithmeticOverflow)?,
        )
        .ok_or(ProgramError::ArithmeticOverflow)?;

    if data.len() < entries_data_end {
        return Err(ProgramError::AccountDataTooSmall);
    }

    let entries: &[SlotHashEntry] = cast_slice(&data[entries_data_start..entries_data_end]);

    match operation {
        SlotHashOp::IsEmpty => {
            // Perform the is_empty equivalent check
            let _ = entries.is_empty();
            Ok(None)
        }
        SlotHashOp::GetHash(target_slot) | SlotHashOp::GetPosition(target_slot) => {
            // Perform standard binary search (midpoint)
            let search_result =
                entries.binary_search_by(|entry| entry.slot.cmp(&target_slot).reverse());
            Ok(search_result.ok())
        }
    }
}

// Solana SDK SlotHashes Sysvar Processors (Using bytemuck)

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts
        .get(0)
        .filter(|acc| acc.key() == &solana_slot_hashes::ID)
        .ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    process_slot_hashes_bytes(&data, SlotHashOp::IsEmpty).map(|_| ())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts
        .get(0)
        .filter(|acc| acc.key() == &solana_slot_hashes::ID)
        .ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    process_slot_hashes_bytes(&data, SlotHashOp::GetHash(0)).map(|_| ())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[NoStdAccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts
        .get(0)
        .filter(|acc| acc.key() == &solana_slot_hashes::ID)
        .ok_or(ProgramError::InvalidArgument)?;

    let data = slot_hashes_account.try_borrow_data()?;

    process_slot_hashes_bytes(&data, SlotHashOp::GetPosition(0)).map(|_| ())
}

// --- Unit Tests for Pure Logic ---
#[cfg(test)]
mod tests {
    use super::*;
    use solana_program::hash::Hash;
    use std::vec; // For convenience, though not strictly needed

    // Helper to create mock SlotHashes data (u64 len prefix)
    fn create_mock_slot_hashes_data(entries: &[(u64, [u8; 32])]) -> Vec<u8> {
        let num_entries = entries.len() as u64;
        let data_len = LEN_PREFIX_SIZE + entries.len() * SLOT_HASH_ENTRY_SIZE;
        let mut data = vec![0u8; data_len];
        data[0..LEN_PREFIX_SIZE].copy_from_slice(&num_entries.to_le_bytes());
        let mut offset = LEN_PREFIX_SIZE;
        for (slot, hash) in entries {
            let entry = SlotHashEntry {
                slot: *slot,
                hash: *hash,
            }; // Create entry with longer lifetime
            let entry_bytes = bytemuck::bytes_of(&entry); // Borrow the longer-lived entry
            data[offset..offset + SLOT_HASH_ENTRY_SIZE].copy_from_slice(entry_bytes);
            offset += SLOT_HASH_ENTRY_SIZE;
        }
        data
    }

    #[test]
    fn test_process_slot_hashes_bytes_logic() {
        let mock_entries = [
            (100, [1u8; 32]),
            (98, [2u8; 32]),
            (95, [3u8; 32]),
            (90, [4u8; 32]), // Add more entries
            (85, [5u8; 32]),
        ];
        let data = create_mock_slot_hashes_data(&mock_entries);

        // Test IsEmpty
        assert_eq!(
            process_slot_hashes_bytes(&data, SlotHashOp::IsEmpty),
            Ok(None)
        ); // IsEmpty returns Ok(None)
        let empty_data = create_mock_slot_hashes_data(&[]);
        assert_eq!(
            process_slot_hashes_bytes(&empty_data, SlotHashOp::IsEmpty),
            Ok(None)
        ); // IsEmpty returns Ok(None)

        // Test Searches (midpoint)
        assert_eq!(
            process_slot_hashes_bytes(&data, SlotHashOp::GetHash(98)),
            Ok(Some(1))
        ); // Found at index 1
        assert_eq!(
            process_slot_hashes_bytes(&data, SlotHashOp::GetPosition(90)),
            Ok(Some(3))
        ); // Found at index 3
           // Test not found (should still return Ok as search completes)
        assert_eq!(
            process_slot_hashes_bytes(&data, SlotHashOp::GetHash(99)),
            Ok(None)
        ); // Not found
        assert_eq!(
            process_slot_hashes_bytes(&data, SlotHashOp::GetPosition(80)),
            Ok(None)
        ); // Not found (last element is 85)

        // Test edge cases for errors
        assert!(matches!(
            process_slot_hashes_bytes(&data[0..5], SlotHashOp::IsEmpty),
            Err(ProgramError::AccountDataTooSmall)
        )); // Too short for len
        let short_data = create_mock_slot_hashes_data(&[(100, [1u8; 32])]);
        assert!(matches!(
            process_slot_hashes_bytes(&short_data[0..45], SlotHashOp::IsEmpty),
            Err(ProgramError::AccountDataTooSmall)
        )); // Len says 1, but data too short
    }
}
