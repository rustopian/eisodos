use crate::{
    instruction::Instruction,
    processor::{
        process_account, process_create_account, process_log, process_ping, process_transfer,
        process_slot_hashes_get_entry, process_slot_hashes_get_hash_interpolated,
        process_slot_hashes_position_interpolated, process_slot_hashes_get_hash_midpoint,
        process_slot_hashes_position_midpoint,
    },
};
use solana_account_info::AccountInfo;
use solana_program_error::ProgramResult;
use solana_pubkey::Pubkey;

solana_program_entrypoint::entrypoint!(process_instruction);

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
    }
}
