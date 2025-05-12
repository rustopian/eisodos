#![no_std]

// Using the pinocchio SDK available in the workspace
// Corrected import path based on compiler error
use pinocchio::ProgramResult;

// Define a module that might typically contain benchmarkable functions
pub mod benchmarking {
    use super::*;

    // This is the function we want to benchmark.
    // It's a simple wrapper around the core logic.
    pub fn ping_for_benchmark() -> ProgramResult {
        // In a real scenario, this might do complex no_std work.
        // For now, it just returns Ok.
        Ok(())
    }
} 