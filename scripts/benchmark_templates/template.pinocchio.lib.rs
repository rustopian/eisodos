#![no_std]
#![no_main]

use pinocchio::{
    program_entrypoint,
    ProgramResult,
    no_allocator,
    nostd_panic_handler,
    account_info::AccountInfo, // Corrected import path
    pubkey::Pubkey             // Corrected import path
};

// Import the function to be benchmarked
// Use %%RUST_IMPORT_CRATE_NAME%% which comes from the function path string
use %%RUST_IMPORT_CRATE_NAME%%::%%BENCHMARK_FUNCTION_MODULE%%::%%BENCHMARK_FUNCTION_NAME%%;

// Pinocchio entrypoint setup
program_entrypoint!(process_instruction);
no_allocator!();        // Ensures no heap allocations are used
nostd_panic_handler!(); // Provides a panic handler for no_std

// The entrypoint function required by Pinocchio
#[inline(always)]
pub fn process_instruction(
    _program_id: &Pubkey,
    _accounts: &[AccountInfo],
    _instruction_data: &[u8],
) -> ProgramResult {
    // TODO: Add logic here to load/deserialize input_data if specified in the config
    // For ping, no input data is needed.

    // Call the benchmarked function
    %%BENCHMARK_FUNCTION_NAME%%()

    // We might want to serialize/log output here if needed in the future
}

// REMOVED Manual Panic Handler as nostd_panic_handler!() provides it.
// #[panic_handler]
// fn panic(_info: &core::panic::PanicInfo) -> ! {
//     loop {}
// } 