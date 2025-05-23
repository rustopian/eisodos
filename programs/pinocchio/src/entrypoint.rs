use {
    crate::{
        instruction::Instruction,
        processor::{
            process_account, process_create_account, process_log, process_ping,
            process_slot_hashes_get_entry, process_slot_hashes_get_entry_unchecked,
            process_slot_hashes_get_hash_interpolated,
            process_slot_hashes_get_hash_interpolated_unchecked,
            process_slot_hashes_position_interpolated,
            process_slot_hashes_position_interpolated_unchecked,
            process_slot_hashes_position_naive_unchecked,
            process_transfer,
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
        Instruction::SlotHashesGetHashInterpolated => {
            process_slot_hashes_get_hash_interpolated(accounts)
        }
        Instruction::SlotHashesPositionInterpolated => {
            process_slot_hashes_position_interpolated(accounts)
        }
        Instruction::SlotHashesGetEntryUnchecked => unsafe {
            process_slot_hashes_get_entry_unchecked(accounts)
        },
        Instruction::SlotHashesGetHashInterpolatedUnchecked => unsafe {
            process_slot_hashes_get_hash_interpolated_unchecked(accounts)
        },
        Instruction::SlotHashesPositionInterpolatedUnchecked { target_slot } => unsafe {
            process_slot_hashes_position_interpolated_unchecked(accounts, target_slot)
        },
        Instruction::SlotHashesPositionNaiveUnchecked { target_slot } => unsafe {
            process_slot_hashes_position_naive_unchecked(accounts, target_slot)
        },
    }
}
