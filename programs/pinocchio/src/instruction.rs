use pinocchio::program_error::ProgramError;
use pinocchio::sysvars::clock::Slot;

#[derive(Clone, Debug)]
#[rustfmt::skip]
pub enum Instruction {
    Ping,
    Log,
    Account {
        expected: u64,
    },
    CreateAccount,
    Transfer,
    SlotHashesGetEntry,          // Tag 5
    SlotHashesGetHashInterpolated, // Tag 6
    SlotHashesPositionInterpolated,// Tag 7
    SlotHashesGetEntryUnchecked,           // Tag 8
    SlotHashesGetHashInterpolatedUnchecked,// Tag 9
    SlotHashesPositionInterpolatedUnchecked { target_slot: Slot }, // Tag 10
    SlotHashesPositionNaiveUnchecked { target_slot: Slot },   // Tag 11
}

impl Instruction {
    /// Unpacks a byte buffer into a [Instruction](enum.Instruction.html).
    #[inline(always)]
    pub fn unpack(input: &[u8]) -> Result<Self, ProgramError> {
        match input.split_first() {
            // 0 - Ping
            Some((&0, [])) => Ok(Instruction::Ping),
            // 1 - Log
            Some((&1, [])) => Ok(Instruction::Log),
            // 2 - Account
            Some((&2, remaining)) if remaining.len() == 8 => Ok(Instruction::Account {
                expected: u64::from_le_bytes(remaining[0..8].try_into().unwrap()),
            }),
            // 3 - CreateAccount
            Some((&3, [])) => Ok(Instruction::CreateAccount),
            // 4 - Transfer
            Some((&4, [])) => Ok(Instruction::Transfer),
            // 5 - SlotHashesGetEntry
            Some((&5, [])) => Ok(Instruction::SlotHashesGetEntry),
            // 6 - SlotHashesGetHashInterpolated
            Some((&6, [])) => Ok(Instruction::SlotHashesGetHashInterpolated),
            // 7 - SlotHashesPositionInterpolated
            Some((&7, [])) => Ok(Instruction::SlotHashesPositionInterpolated),
            // 8 - SlotHashesGetEntryUnchecked
            Some((&8, [])) => Ok(Instruction::SlotHashesGetEntryUnchecked),
            // 9 - SlotHashesGetHashInterpolatedUnchecked
            Some((&9, [])) => Ok(Instruction::SlotHashesGetHashInterpolatedUnchecked),
            // 10 - SlotHashesPositionInterpolatedUnchecked { target_slot: Slot }
            Some((&10, remaining)) if remaining.len() == 8 => {
                let target_slot = u64::from_le_bytes(remaining[0..8].try_into().unwrap());
                Ok(Instruction::SlotHashesPositionInterpolatedUnchecked { target_slot })
            },
            // 11 - SlotHashesPositionNaiveUnchecked { target_slot: Slot }
            Some((&11, remaining)) if remaining.len() == 8 => {
                let target_slot = u64::from_le_bytes(remaining[0..8].try_into().unwrap());
                Ok(Instruction::SlotHashesPositionNaiveUnchecked { target_slot })
            },
            _ => Err(ProgramError::InvalidInstructionData),
        }
    }
}
