#! /usr/bin/env python3

import argparse
import toml
import pathlib
import shutil
import subprocess
import sys
import os
import json
import time
import textwrap
import re
import orchestrator

# Import extracted helper modules (refactor)
from console_utils import (
    print_section,
    print_subsection,
    print_success,
    print_warning,
    print_error,
    print_result,
    print_build_info,
)
from builder import run_cargo_build
from rewriter import rewrite_sources_for_entrypoint
from entrypoint_config import ENTRYPOINT_DEPS
# NEW imports from helper module
from helpers import (
    discover_crates,
    parse_function_path,
    format_features,
    replace_placeholders,
    get_workspace_dependencies_block,
    get_package_name_from_manifest,
)
from executor import perform_benchmark_runs
from reporter import generate_markdown_report, print_console_summary

# --- Color Constants ---
# (moved to console_utils.py)

# --- Constants ---
EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKSPACE_ROOT = EISODOS_ROOT
TEMPLATES_DIR = EISODOS_ROOT / "scripts" / "benchmark_templates"
TARGET_DIR = EISODOS_ROOT / "target" / "bench_gen"
BENCHED_CRATE_COPY_DIR_NAME = "benched_crate_src" # Dir name for the copied source

# Placeholder line to find and replace in the template Cargo.toml
PINOCCHIO_PLACEHOLDER_LINE = "pinocchio = { workspace = true }"

# --- Rewrite Matrix for Import Path Translation ---
# (moved to entrypoint_config.py / rewriter.py)

# Define dependencies that must be ensured inside the *benched crate* Cargo.toml for each entrypoint
# (moved to entrypoint_config.py)

# --- Helper Functions ---

def format_toml_dict(data):
    """ Formats a dictionary into TOML syntax (basic implementation). """
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            items_str = ", ".join([f'{k} = "{v}"' for k, v in value.items()])
            lines.append(f'{key} = {{ {items_str} }}')
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        # Add other types if needed (bool, int, etc.)
        else:
             lines.append(f'{key} = {value}') # Basic fallback 
    return "\n".join(lines)

def ensure_pinocchio_handlers(crate_root: pathlib.Path):
    """Ensure crate is #![no_std] and has pinocchio no_allocator/nostd_panic_handler wiring."""
    # body removed (now in rewriter.py)
    pass

def ensure_nostd_entrypoint_alias(crate_root: pathlib.Path):
    """Alias helper moved to rewriter.py"""
    pass

def ensure_manifest_deps_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    """Manifest patch helper moved to rewriter.py"""
    pass

# --- Main Logic ---

def main():
    orchestrator.run()


if __name__ == "__main__":
    main() 