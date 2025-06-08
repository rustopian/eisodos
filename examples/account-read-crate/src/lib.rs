//! Benchmark crate for testing account reading operations.

#![cfg_attr(not(any(feature = "std", feature = "solana-program-mono", feature = "solana-nostd-entrypoint")), no_std)]

pub mod processor;

// === no_std specific setup ===
#[cfg(feature = "no_std")]
use pinocchio::{
    no_allocator,
    nostd_panic_handler
};

// Handlers MUST be present for no_std SBF builds
#[cfg(feature = "no_std")]
no_allocator!();
#[cfg(feature = "no_std")]
nostd_panic_handler!();
// ============================ 