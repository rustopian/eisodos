use crate::cpi::{create_account_unchecked, transfer_unchecked};
use pinocchio::{account_info::AccountInfo, msg, program_error::ProgramError, ProgramResult};
use pinocchio::sysvars::slot_hashes::SlotHashes;

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
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.get_entry(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.get_hash(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    let _ = slot_hashes.position(0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    // Call the specific midpoint method. Ignore result.
    let _ = slot_hashes.get_hash_midpoint(0); 
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_midpoint(accounts: &[AccountInfo]) -> ProgramResult {
    // Assume accounts[0] is the SlotHashes sysvar
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    
    let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
    // Call the specific midpoint method. Ignore result.
    let _ = slot_hashes.position_midpoint(0);
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std; // Bring std into scope for tests
    use pinocchio::sysvars::slot_hashes::SlotHashes;
    use solana_program::hash::Hash;
    use std::vec::Vec; // Correct import for tests

    // Helper moved inside tests module
    fn create_mock_slot_hashes_data(entries: &[(u64, [u8; 32])]) -> Vec<u8> {
        const LEN_PREFIX_SIZE: usize = 8; // Use literal value
        const ENTRY_SIZE: usize = 40;     // Use literal value
        const SLOT_SIZE: usize = 8;       // Use literal value
        let num_entries = entries.len() as u64;
        let data_len = LEN_PREFIX_SIZE + entries.len() * ENTRY_SIZE;
        let mut data = std::vec![0u8; data_len]; // Use std::vec! macro
        data[0..LEN_PREFIX_SIZE].copy_from_slice(&num_entries.to_le_bytes());
        let mut offset = LEN_PREFIX_SIZE;
        for (slot, hash) in entries {
            data[offset..offset + SLOT_SIZE].copy_from_slice(&slot.to_le_bytes());
            data[offset + SLOT_SIZE..offset + ENTRY_SIZE].copy_from_slice(hash);
            offset += ENTRY_SIZE;
        }
        data
    }
    
    #[test]
    fn test_pinocchio_slot_hashes_logic() {
        // Test the SlotHashes methods directly using mock data,
        // bypassing the processor functions and AccountInfo mocking.
        let mock_entries_data = [
            (100, [1u8; 32]), (98, [2u8; 32]), (95, [3u8; 32]),
            (90, [4u8; 32]), (85, [5u8; 32]), (80, [6u8; 32]),
        ];
        let hash_for_98 = [2u8; 32]; // Pinocchio Hash is [u8; 32]
        let data = create_mock_slot_hashes_data(&mock_entries_data);
        let entry_count = mock_entries_data.len();

        // Create SlotHashes instance directly from data slice
        // Safety: We constructed the data correctly according to Pinocchio's layout
        let slot_hashes = unsafe { SlotHashes::new_unchecked(data.as_slice(), entry_count) };

        assert_eq!(slot_hashes.len(), entry_count);

        // Test GetEntry
        let entry = slot_hashes.get_entry(1).unwrap(); // Get 2nd entry (slot 98)
        assert_eq!(entry.slot, 98);
        assert_eq!(entry.hash, hash_for_98);
        assert!(slot_hashes.get_entry(entry_count).is_none()); // Out of bounds
        
        // Test GetHash (Interpolated)
        assert_eq!(slot_hashes.get_hash(98), Some(&hash_for_98));
        assert_eq!(slot_hashes.get_hash(99), None);

        // Test Position (Interpolated)
        assert_eq!(slot_hashes.position(95), Some(2));
        assert_eq!(slot_hashes.position(91), None);

        // Test GetHash (Midpoint)
        assert_eq!(slot_hashes.get_hash_midpoint(98), Some(&hash_for_98));
        assert_eq!(slot_hashes.get_hash_midpoint(99), None);
        
        // Test Position (Midpoint)
        assert_eq!(slot_hashes.position_midpoint(95), Some(2));
        assert_eq!(slot_hashes.position_midpoint(91), None);
    }
}
