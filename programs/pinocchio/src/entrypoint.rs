use {
    crate::{
        instruction::Instruction,
        processor::{
            process_account, process_create_account, process_log, process_ping, process_transfer,
            process_slot_hashes_get_entry, process_slot_hashes_get_hash_interpolated,
            process_slot_hashes_position_interpolated, process_slot_hashes_get_hash_midpoint,
            process_slot_hashes_position_midpoint,
            process_slot_hashes_get_entry_unchecked,
            process_slot_hashes_get_hash_interpolated_unchecked,
            process_slot_hashes_position_interpolated_unchecked,
            process_slot_hashes_get_hash_midpoint_unchecked,
            process_slot_hashes_position_midpoint_unchecked,
        },
    },
    pinocchio::{
        account_info::AccountInfo, no_allocator, nostd_panic_handler, program_entrypoint,
        pubkey::Pubkey, ProgramResult,
    },
};

program_entrypoint!(process_instruction);
no_allocator!();
nostd_panic_handler!();

#[inline(always)]
pub fn process_instruction(
    _program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let instruction = Instruction::unpack(instruction_data)?;

    match instruction {
        Instruction::Ping => process_ping(),
        Instruction::Log => process_log(),
        Instruction::Account { expected } => process_account(accounts, expected),
        Instruction::CreateAccount => process_create_account(accounts),
        Instruction::Transfer => process_transfer(accounts),
        Instruction::SlotHashesGetEntry => process_slot_hashes_get_entry(accounts),
        Instruction::SlotHashesGetHashInterpolated => process_slot_hashes_get_hash_interpolated(accounts),
        Instruction::SlotHashesPositionInterpolated => process_slot_hashes_position_interpolated(accounts),
        Instruction::SlotHashesGetHashMidpoint => process_slot_hashes_get_hash_midpoint(accounts),
        Instruction::SlotHashesPositionMidpoint => process_slot_hashes_position_midpoint(accounts),
        Instruction::SlotHashesGetEntryUnchecked => unsafe { process_slot_hashes_get_entry_unchecked(accounts) },
        Instruction::SlotHashesGetHashInterpolatedUnchecked => unsafe { process_slot_hashes_get_hash_interpolated_unchecked(accounts) },
        Instruction::SlotHashesPositionInterpolatedUnchecked => unsafe { process_slot_hashes_position_interpolated_unchecked(accounts) },
        Instruction::SlotHashesGetHashMidpointUnchecked => unsafe { process_slot_hashes_get_hash_midpoint_unchecked(accounts) },
        Instruction::SlotHashesPositionMidpointUnchecked => unsafe { process_slot_hashes_position_midpoint_unchecked(accounts) },
    }
}
