#![no_std]
#![no_main]

use solana_nostd_entrypoint::{
    entrypoint_nostd, basic_panic_impl, noalloc_allocator, NoStdAccountInfo,
};
use solana_entrypoint::ProgramResult;
use solana_pubkey::Pubkey;

// Import the function to be benchmarked
use %%RUST_IMPORT_CRATE_NAME%%::%%BENCHMARK_FUNCTION_MODULE%%::%%BENCHMARK_FUNCTION_NAME%% as benchmark_function_to_call;

// Solana NoStd Entrypoint setup
entrypoint_nostd!(process_instruction, 64);
noalloc_allocator!();
basic_panic_impl!();

// The entrypoint function required by solana-nostd-entrypoint
#[inline(always)]
pub fn process_instruction(
    _program_id: &Pubkey,
    _accounts: &[NoStdAccountInfo],
    _instruction_data: &[u8],
) -> ProgramResult {
    // TODO: Add logic here to load/deserialize input_data if specified in the config
    // For ping, no input data is needed.

    // Note: We need to convert NoStdAccountInfo to the format expected by the benchmark function
    // This is a simplified conversion - in practice you might need more sophisticated handling
    // depending on the benchmark function's expectations
    
    // For now, assume the benchmark function can work with the raw data
    // If the benchmarked function expects standard AccountInfo, we may need conversion logic
    
    // Call the benchmarked function (using the alias)
    // Note: This assumes the benchmark function signature is compatible
    // benchmark_function_to_call(_program_id, _accounts, _instruction_data)?;
    
    // For compatibility, we'll create a simple ping-like operation
    // The actual benchmark logic should be implemented based on the specific function being tested
    
    Ok(())
    // We might want to serialize/log output here if needed in the future
} 