use pinocchio::program_error::ProgramError;

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
    SlotHashesGetHashMidpoint,     // Tag 8
    SlotHashesPositionMidpoint,    // Tag 9
    SlotHashesGetEntryUnchecked,           // Tag 10
    SlotHashesGetHashInterpolatedUnchecked,// Tag 11
    SlotHashesPositionInterpolatedUnchecked,// Tag 12
    SlotHashesGetHashMidpointUnchecked,     // Tag 13
    SlotHashesPositionMidpointUnchecked,    // Tag 14
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
            // 8 - SlotHashesGetHashMidpoint
            Some((&8, [])) => Ok(Instruction::SlotHashesGetHashMidpoint),
            // 9 - SlotHashesPositionMidpoint
            Some((&9, [])) => Ok(Instruction::SlotHashesPositionMidpoint),
            // 10 - SlotHashesGetEntryUnchecked
            Some((&10, [])) => Ok(Instruction::SlotHashesGetEntryUnchecked),
            // 11 - SlotHashesGetHashInterpolatedUnchecked
            Some((&11, [])) => Ok(Instruction::SlotHashesGetHashInterpolatedUnchecked),
            // 12 - SlotHashesPositionInterpolatedUnchecked
            Some((&12, [])) => Ok(Instruction::SlotHashesPositionInterpolatedUnchecked),
            // 13 - SlotHashesGetHashMidpointUnchecked
            Some((&13, [])) => Ok(Instruction::SlotHashesGetHashMidpointUnchecked),
            // 14 - SlotHashesPositionMidpointUnchecked
            Some((&14, [])) => Ok(Instruction::SlotHashesPositionMidpointUnchecked),
            _ => Err(ProgramError::InvalidInstructionData),
        }
    }
}
