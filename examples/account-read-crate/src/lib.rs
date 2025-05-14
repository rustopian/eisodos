//! Benchmark crate for testing account reading operations.

#![cfg_attr(feature = "no_std", no_std)] // Enable no_std when feature is active

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