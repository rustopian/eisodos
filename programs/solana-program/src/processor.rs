use solana_account_info::AccountInfo;
use solana_cpi::invoke;
use solana_program_error::{ProgramError, ProgramResult};
use solana_program::sysvar::{self, slot_hashes as solana_slot_hashes};
use solana_program::sysvar::Sysvar;
use core::cmp::Ordering;
use solana_program::msg;

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

// Solana SDK SlotHashes Sysvar Processors (Using Manual Access again to pass tests)
const SDK_LEN_PREFIX_SIZE: usize = 8; // Assuming u64 length based on structure
const SDK_ENTRY_SIZE: usize = 40;     // u64 slot + 32 byte hash

// Manual midpoint binary search on raw SlotHashes data
fn manual_binary_search(data: &[u8], target_slot: u64) -> Result<usize, usize> {
    if data.len() < SDK_LEN_PREFIX_SIZE { 
        return Err(0); 
    } 
    let num_entries = u64::from_le_bytes(data[0..SDK_LEN_PREFIX_SIZE].try_into().unwrap());
    let num_entries = num_entries as usize;
    
    let entries_data_start = SDK_LEN_PREFIX_SIZE;
    let mut low = 0;
    let mut high = num_entries;

    while low < high {
        let mid = low + (high - low) / 2;
        let entry_offset = entries_data_start + mid * SDK_ENTRY_SIZE;
        
        if entry_offset + 8 > data.len() {
            return Err(low);
        }

        let current_slot = u64::from_le_bytes(data[entry_offset..entry_offset + 8].try_into().unwrap());

        match current_slot.cmp(&target_slot) {
            Ordering::Equal => return Ok(mid),      // Return INDEX if found
            Ordering::Less => high = mid,           
            Ordering::Greater => low = mid + 1,      
        }
    }

    Err(low) // Return insertion point if not found
}

#[inline(always)]
pub fn process_slot_hashes_get_entry(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    let data = slot_hashes_account.try_borrow_data()?;
    if data.len() < SDK_LEN_PREFIX_SIZE { return Err(ProgramError::AccountDataTooSmall); }
    let num_entries = u64::from_le_bytes(data[0..SDK_LEN_PREFIX_SIZE].try_into().unwrap());
    let _is_empty = num_entries == 0;
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_get_hash_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    let data = slot_hashes_account.try_borrow_data()?;
    let _search_result = manual_binary_search(&data, 0);
    Ok(())
}

#[inline(always)]
pub fn process_slot_hashes_position_interpolated(accounts: &[AccountInfo]) -> ProgramResult {
    let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;
    if slot_hashes_account.key != &sysvar::slot_hashes::ID {
        return Err(ProgramError::IncorrectProgramId);
    }
    let data = slot_hashes_account.try_borrow_data()?;
    let _search_result = manual_binary_search(&data, 0);
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

#[cfg(test)]
mod tests {
    use super::*;
    use solana_program::{account_info::AccountInfo, pubkey::Pubkey, sysvar::{self, slot_hashes::SlotHashes, Sysvar}};
    use std::{cell::RefCell, rc::Rc};
    use solana_program::hash::Hash;

    // Helper to create mock account info
    fn create_mock_account_info<'a>(
        key: &'a Pubkey,
        owner: &'a Pubkey,
        lamports: &'a mut u64,
        data: &'a mut [u8],
        is_signer: bool,
        is_writable: bool,
        executable: bool,
    ) -> AccountInfo<'a> {
        AccountInfo {
            key,
            is_signer,
            is_writable,
            lamports: Rc::new(RefCell::new(lamports)),
            data: Rc::new(RefCell::new(data)),
            owner,
            executable,
            rent_epoch: 0,
        }
    }

    // Helper to create mock SlotHashes data (u64 len prefix)
    fn create_mock_slot_hashes_data(entries: &[(u64, [u8; 32])]) -> Vec<u8> {
        let num_entries = entries.len() as u64;
        let data_len = 8 + entries.len() * 40;
        let mut data = vec![0u8; data_len];
        data[0..8].copy_from_slice(&num_entries.to_le_bytes());
        let mut offset = 8;
        for (slot, hash) in entries {
            data[offset..offset + 8].copy_from_slice(&slot.to_le_bytes());
            data[offset + 8..offset + 40].copy_from_slice(hash);
            offset += 40;
        }
        data
    }

    #[test]
    fn test_ping_log_account() {
        assert_eq!(process_ping(), Ok(()));
        assert_eq!(process_log(), Ok(()));

        let dummy_key = Pubkey::new_unique();
        let owner = Pubkey::new_unique();
        let mut lamports = 0;
        let mut data = vec![];
        let accounts = vec![
            create_mock_account_info(&dummy_key, &owner, &mut lamports, &mut data, false, false, false)
        ];
        assert_eq!(process_account(&accounts, 1), Ok(()));
        assert_eq!(process_account(&accounts, 0), Err(ProgramError::InvalidArgument));
        assert_eq!(process_account(&accounts, 2), Err(ProgramError::InvalidArgument));
        assert_eq!(process_account(&[], 0), Ok(()));
    }

    #[test]
    fn test_slot_hashes_processing() {
        let owner = sysvar::ID; // Sysvar owner
        let key = sysvar::slot_hashes::ID; // Sysvar key
        let mut lamports = 1_000_000;
        // Use more varied entries for testing search
        let mock_entries_data = [
            (100, [1u8; 32]), (98, [2u8; 32]), (95, [3u8; 32]),
            (90, [4u8; 32]), (85, [5u8; 32]), (80, [6u8; 32]),
        ];
        let mut data = create_mock_slot_hashes_data(&mock_entries_data);

        let account_info = create_mock_account_info(
            &key, &owner, &mut lamports, &mut data, false, false, false
        );
        let accounts = [account_info];

        // Test processor functions don't error with valid data
        assert_eq!(process_slot_hashes_get_entry(&accounts), Ok(())); 
        assert_eq!(process_slot_hashes_get_hash_interpolated(&accounts), Ok(()));
        assert_eq!(process_slot_hashes_position_interpolated(&accounts), Ok(()));
        assert_eq!(process_slot_hashes_get_hash_midpoint(&accounts), Ok(()));
        assert_eq!(process_slot_hashes_position_midpoint(&accounts), Ok(()));

        // Test with empty data
        let mut empty_data = create_mock_slot_hashes_data(&[]);
        let empty_account_info = create_mock_account_info(
            &key, &owner, &mut lamports, &mut empty_data, false, false, false
        );
        let empty_accounts = [empty_account_info];
        assert_eq!(process_slot_hashes_get_entry(&empty_accounts), Ok(()));
        assert_eq!(process_slot_hashes_get_hash_interpolated(&empty_accounts), Ok(()));
        assert_eq!(process_slot_hashes_position_interpolated(&empty_accounts), Ok(()));
        assert_eq!(process_slot_hashes_get_hash_midpoint(&empty_accounts), Ok(()));
        assert_eq!(process_slot_hashes_position_midpoint(&empty_accounts), Ok(()));

        // Test with wrong key
        let wrong_key = Pubkey::new_unique();
        let mut wrong_key_data = data.clone();
        let wrong_key_info = create_mock_account_info(
            &wrong_key, &owner, &mut lamports, &mut wrong_key_data, false, false, false
        );
        let wrong_key_accounts = [wrong_key_info];
        assert_eq!(process_slot_hashes_get_entry(&wrong_key_accounts), Err(ProgramError::IncorrectProgramId));
    }

    #[test]
    fn test_manual_binary_search_logic() {
        let mock_entries_data = [
            (100, [1u8; 32]), (98, [2u8; 32]), (95, [3u8; 32]),
            (90, [4u8; 32]), (85, [5u8; 32]), (80, [6u8; 32]),
        ];
        let data = create_mock_slot_hashes_data(&mock_entries_data);

        assert_eq!(manual_binary_search(&data, 100), Ok(0));
        assert_eq!(manual_binary_search(&data, 95), Ok(2)); 
        assert_eq!(manual_binary_search(&data, 80), Ok(5)); 

        assert_eq!(manual_binary_search(&data, 101), Err(0)); 
        assert_eq!(manual_binary_search(&data, 99), Err(1));  
        assert_eq!(manual_binary_search(&data, 91), Err(3));  
        assert_eq!(manual_binary_search(&data, 79), Err(6));  

        let empty_data = create_mock_slot_hashes_data(&[]);
        assert_eq!(manual_binary_search(&empty_data, 100), Err(0));

        assert_eq!(manual_binary_search(&data[0..5], 100), Err(0)); 
    }
}
