use pinocchio::{
    ProgramResult,
    pubkey::Pubkey,
    account_info::AccountInfo,
    sysvars::slot_hashes::SlotHashes,
    program_error::ProgramError,
    no_allocator,
    nostd_panic_handler
};

no_allocator!();
nostd_panic_handler!();


// Helper function for std feature to parse SlotHashes without expensive bincode
#[cfg(feature = "std")]
fn parse_slot_hashes_raw(data: &[u8]) -> Result<(usize, &[(u64, [u8; 32])]), ProgramError> {
    if data.len() < 8 {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Read the length as little-endian u64
    let len_bytes = data.get(0..8).ok_or(ProgramError::InvalidAccountData)?;
    let len = u64::from_le_bytes([
        len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3],
        len_bytes[4], len_bytes[5], len_bytes[6], len_bytes[7],
    ]) as usize;
    
    if len > 512 { // MAX_ENTRIES
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Each entry is 40 bytes (8 bytes slot + 32 bytes hash)
    let expected_data_len = 8 + (len * 40);
    if data.len() < expected_data_len {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Cast the entries section directly (zero-copy!)
    let entries_data = &data[8..8 + (len * 40)];
    let entries = unsafe {
        core::slice::from_raw_parts(
            entries_data.as_ptr() as *const (u64, [u8; 32]),
            len
        )
    };
    
    Ok((len, entries))
}

#[cfg(feature = "std")]
fn find_slot_in_entries(entries: &[(u64, [u8; 32])], target_slot: u64) -> Option<&[u8; 32]> {
    // Binary search since slots are in descending order
    entries.binary_search_by(|entry| entry.0.cmp(&target_slot).reverse())
        .ok()
        .map(|index| &entries[index].1)
}

// Helper function for broken-out crates to parse SlotHashes without expensive bincode
#[cfg(feature = "std")]
fn parse_slot_hashes_raw(data: &[u8]) -> Result<(usize, &[(u64, [u8; 32])]), ProgramError> {
    if data.len() < 8 {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Read the length as little-endian u64
    let len_bytes = data.get(0..8).ok_or(ProgramError::InvalidAccountData)?;
    let len = u64::from_le_bytes([
        len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3],
        len_bytes[4], len_bytes[5], len_bytes[6], len_bytes[7],
    ]) as usize;
    
    if len > 512 { // MAX_ENTRIES
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Each entry is 40 bytes (8 bytes slot + 32 bytes hash)
    let expected_data_len = 8 + (len * 40);
    if data.len() < expected_data_len {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Cast the entries section directly (zero-copy!)
    let entries_data = &data[8..8 + (len * 40)];
    let entries = unsafe {
        core::slice::from_raw_parts(
            entries_data.as_ptr() as *const (u64, [u8; 32]),
            len
        )
    };
    
    Ok((len, entries))
}

#[cfg(feature = "std")]
fn find_slot_in_entries(entries: &[(u64, [u8; 32])], target_slot: u64) -> Option<&[u8; 32]> {
    // Binary search since slots are in descending order
    entries.binary_search_by(|entry| entry.0.cmp(&target_slot).reverse())
        .ok()
        .map(|index| &entries[index].1)
}

// Helper function for solana-program-mono to parse SlotHashes without expensive bincode  
#[cfg(feature = "std")]
fn parse_slot_hashes_raw(data: &[u8]) -> Result<(usize, &[(u64, [u8; 32])]), ProgramError> {
    if data.len() < 8 {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Read the length as little-endian u64
    let len_bytes = data.get(0..8).ok_or(ProgramError::InvalidAccountData)?;
    let len = u64::from_le_bytes([
        len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3],
        len_bytes[4], len_bytes[5], len_bytes[6], len_bytes[7],
    ]) as usize;
    
    if len > 512 { // MAX_ENTRIES
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Each entry is 40 bytes (8 bytes slot + 32 bytes hash)
    let expected_data_len = 8 + (len * 40);
    if data.len() < expected_data_len {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Cast the entries section directly (zero-copy!)
    let entries_data = &data[8..8 + (len * 40)];
    let entries = unsafe {
        core::slice::from_raw_parts(
            entries_data.as_ptr() as *const (u64, [u8; 32]),
            len
        )
    };
    
    Ok((len, entries))
}

#[cfg(feature = "std")]
fn find_slot_in_entries(entries: &[(u64, [u8; 32])], target_slot: u64) -> Option<&[u8; 32]> {
    // Binary search since slots are in descending order
    entries.binary_search_by(|entry| entry.0.cmp(&target_slot).reverse())
        .ok()
        .map(|index| &entries[index].1)
}

// Helper function for solana-nostd-mono to parse SlotHashes without expensive bincode  
#[cfg(feature = "std")]
fn parse_slot_hashes_raw(data: &[u8]) -> Result<(usize, &[(u64, [u8; 32])]), ProgramError> {
    if data.len() < 8 {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Read the length as little-endian u64
    let len_bytes = data.get(0..8).ok_or(ProgramError::InvalidAccountData)?;
    let len = u64::from_le_bytes([
        len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3],
        len_bytes[4], len_bytes[5], len_bytes[6], len_bytes[7],
    ]) as usize;
    
    if len > 512 { // MAX_ENTRIES
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Each entry is 40 bytes (8 bytes slot + 32 bytes hash)
    let expected_data_len = 8 + (len * 40);
    if data.len() < expected_data_len {
        return Err(ProgramError::InvalidAccountData);
    }
    
    // Cast the entries section directly (zero-copy!)
    let entries_data = &data[8..8 + (len * 40)];
    let entries = unsafe {
        core::slice::from_raw_parts(
            entries_data.as_ptr() as *const (u64, [u8; 32]),
            len
        )
    };
    
    Ok((len, entries))
}

#[cfg(feature = "std")]
fn find_slot_in_entries(entries: &[(u64, [u8; 32])], target_slot: u64) -> Option<&[u8; 32]> {
    // Binary search since slots are in descending order
    entries.binary_search_by(|entry| entry.0.cmp(&target_slot).reverse())
        .ok()
        .map(|index| &entries[index].1)
}

// Define instruction module that contains the main benchmarkable function
pub mod instruction {
    // Bring crate-level items into scope based on feature flags
    use crate::{Pubkey, AccountInfo, ProgramResult, ProgramError};
    use crate::processor;

    /// Main instruction processor that dispatches to specific SlotHashes functions
    pub fn process_instruction(
        program_id: &Pubkey, 
        accounts: &[AccountInfo],
        instruction_data: &[u8],
    ) -> ProgramResult { 
        // Parse instruction data to determine which function to benchmark
        let instruction_tag = instruction_data.get(0).copied().unwrap_or(0);
        
        match instruction_tag {
            0 => processor::process_from_account_info(program_id, accounts, instruction_data),
            1 => processor::process_get_entry_early(program_id, accounts, instruction_data),
            2 => processor::process_get_entry_middle(program_id, accounts, instruction_data), 
            3 => processor::process_get_entry_late(program_id, accounts, instruction_data),
            4 => processor::process_get_entry_missing(program_id, accounts, instruction_data),
            5 => processor::process_get_entry_early_unchecked(program_id, accounts, instruction_data),
            6 => processor::process_get_entry_middle_unchecked(program_id, accounts, instruction_data),
            7 => processor::process_get_entry_late_unchecked(program_id, accounts, instruction_data),
            8 => processor::process_iterator(program_id, accounts, instruction_data),
            9 => processor::process_entries_slice(program_id, accounts, instruction_data),
            10 => processor::process_get_hash(program_id, accounts, instruction_data),
            11 => processor::process_position(program_id, accounts, instruction_data),
            _ => {
                return Err(ProgramError::InvalidInstructionData);
        }
    }
}

// Define processor module that contains the benchmarkable functions
pub mod processor {
    // Bring crate-level items into scope based on feature flags
    #[cfg(all(feature = "no_std"))]
    use crate::{Pubkey, AccountInfo, ProgramResult, ProgramError, SlotHashes};
    #[cfg(feature = "std")]
    use crate::{Pubkey, AccountInfo, ProgramResult, ProgramError, parse_slot_hashes_raw, find_slot_in_entries};
    
    /// Benchmark SlotHashes::from_account_info() construction
    pub fn process_from_account_info(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            let len = slot_hashes.len();
            if len == 0 { return Err(ProgramError::InvalidArgument); }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (len, _entries) = parse_slot_hashes_raw(&data)?;
            if len == 0 { return Err(ProgramError::InvalidArgument); }
        }
        Ok(())
    }

    /// Benchmark SlotHashes::get_entry() for EARLY position (slot 10000 - first entry)
    pub fn process_get_entry_early(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let target_slot = 10000u64;
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            if let Some(hash) = slot_hashes.get_hash(target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            let target_slot = 10000u64;
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes::get_entry() for MIDDLE position (slot 9750 - middle depth)
    pub fn process_get_entry_middle(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or_else(|| {
            return ProgramError::NotEnoughAccountKeys;
        })?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            let target_slot = 9750u64; // Middle position - moderate search depth
            if let Some(hash) = slot_hashes.get_hash(target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 9750u64;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes::get_entry() for LATE position (slot 9100 - deep search)
    pub fn process_get_entry_late(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or_else(|| {
            return ProgramError::NotEnoughAccountKeys;
        })?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            let target_slot = 9100u64; // Late position - deep search
            if let Some(hash) = slot_hashes.get_hash(target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 9100u64;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes::get_entry() for MISSING slot (full tree traversal)
    pub fn process_get_entry_missing(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            let target_slot = 8000u64; // Missing slot - full tree traversal (slowest)
            let hash_opt = slot_hashes.get_hash(target_slot);
            // Force computation - verify it's None (missing)
            if hash_opt.is_some() { return Err(ProgramError::InvalidArgument); }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 8000u64;
            let hash_opt = find_slot_in_entries(entries, target_slot);
            if hash_opt.is_some() { return Err(ProgramError::InvalidArgument); }
        }
        Ok(())
    }

    /// Benchmark SlotHashes iterator (baseline iteration benchmark)
    pub fn process_iterator(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Iterate through first 10 entries and count them to prevent optimization
            let count = slot_hashes.into_iter().take(10).count();
            if count == 0 { return Err(ProgramError::InvalidArgument); }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let count = entries.iter().take(10).count();
            if count == 0 { return Err(ProgramError::InvalidArgument); }
        }
        Ok(())
    }

    /// Benchmark SlotHashes UNCHECKED get_entry() for EARLY position (slot 10000)
    pub fn process_get_entry_early_unchecked(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Use unsafe unchecked access - first find position, then access unchecked
            let target_slot = 10000u64;
            if let Some(position) = slot_hashes.position(target_slot) {
                let entry = unsafe { slot_hashes.get_entry_unchecked(position) };
                // Force usage - verify slot matches what we searched for
                if entry.slot() != target_slot { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            // solana-program doesn't have unchecked variants, so use same safe method
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 10000u64;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes UNCHECKED get_entry() for MIDDLE position (slot 9750)
    pub fn process_get_entry_middle_unchecked(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Use unsafe unchecked access - first find position, then access unchecked
            let target_slot = 9750u64;
            if let Some(position) = slot_hashes.position(target_slot) {
                let entry = unsafe { slot_hashes.get_entry_unchecked(position) };
                // Force usage - verify slot matches what we searched for
                if entry.slot() != target_slot { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            // solana-program doesn't have unchecked variants, so use same safe method
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 9750u64;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes UNCHECKED get_entry() for LATE position (slot 9100)
    pub fn process_get_entry_late_unchecked(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Use unsafe unchecked access - first find position, then access unchecked
            let target_slot = 9100u64;
            if let Some(position) = slot_hashes.position(target_slot) {
                let entry = unsafe { slot_hashes.get_entry_unchecked(position) };
                // Force usage - verify slot matches what we searched for
                if entry.slot() != target_slot { return Err(ProgramError::InvalidArgument); }
            }
        }
        #[cfg(feature = "std")]
        {
            // solana-program doesn't have unchecked variants, so use same safe method
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            let target_slot = 9100u64;
            if let Some(hash) = find_slot_in_entries(entries, target_slot) {
                if hash.iter().all(|&b| b == 0) { return Err(ProgramError::InvalidArgument); }
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes get_hash() method (binary search)
    pub fn process_get_hash(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Get the first entry's slot and search for its hash (forces binary search)
            if let Some(first_entry) = slot_hashes.get_entry(0) {
                let target_slot = first_entry.slot();
                let _hash = slot_hashes.get_hash(target_slot).ok_or(ProgramError::InvalidArgument)?;
            } else {
                return Err(ProgramError::InvalidArgument);
            }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            // Search for a hash using binary search
            if !entries.is_empty() {
                let target_slot = entries[0].0;
                let _hash = find_slot_in_entries(entries, target_slot).ok_or(ProgramError::InvalidArgument)?;
            } else {
                return Err(ProgramError::InvalidArgument);
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes position() method (binary search)
    pub fn process_position(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            // Get the first entry's slot and search for its position (forces binary search)
            if let Some(first_entry) = slot_hashes.get_entry(0) {
                let target_slot = first_entry.slot();
                let _position = slot_hashes.position(target_slot).ok_or(ProgramError::InvalidArgument)?;
            } else {
                return Err(ProgramError::InvalidArgument);
            }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (_len, entries) = parse_slot_hashes_raw(&data)?;
            // Binary search equivalent - find position of first entry
            if !entries.is_empty() {
                let target_slot = entries[0].0;
                // Use binary search to find position
                let _position = entries.binary_search_by(|entry| entry.0.cmp(&target_slot).reverse())
                    .map_err(|_| ProgramError::InvalidArgument)?;
            } else {
                return Err(ProgramError::InvalidArgument);
            }
        }
        Ok(())
    }

    /// Benchmark SlotHashes entries() slice access
    pub fn process_entries_slice(
        _program_id: &Pubkey,
        accounts: &[AccountInfo],
        _instruction_data: &[u8],
    ) -> ProgramResult {
        let slot_hashes_account = accounts.get(0).ok_or(ProgramError::NotEnoughAccountKeys)?;

        #[cfg(all(feature = "no_std"))]
        {
            let slot_hashes = SlotHashes::from_account_info(slot_hashes_account)?;
            let entries = slot_hashes.entries();
            // Force usage by checking slice properties and accessing elements
            if entries.len() != slot_hashes.len() {
                return Err(ProgramError::InvalidArgument);
            }
            if !entries.is_empty() {
                let first_slot = entries[0].slot();
                if entries.len() > 1 {
                    let second_slot = entries[1].slot();
                    // Verify ordering (slots should be descending)
                    if first_slot <= second_slot {
                        return Err(ProgramError::InvalidArgument);
                    }
                }
            }
        }
        #[cfg(feature = "std")]
        {
            let data = slot_hashes_account.try_borrow_data().map_err(|_| ProgramError::InvalidAccountData)?;
            let (len, entries) = parse_slot_hashes_raw(&data)?;
            // Access through raw entries and verify we can get at least one element
            if len != entries.len() {
                return Err(ProgramError::InvalidArgument);
            }
            if !entries.is_empty() {
                let first_slot = entries[0].0;
                if entries.len() > 1 {
                    let second_slot = entries[1].0;
                    // Verify ordering (slots should be descending)
                    if first_slot <= second_slot {
                        return Err(ProgramError::InvalidArgument);
                    }
                }
            }
        }
        Ok(())
    }
} 