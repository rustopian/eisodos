from __future__ import annotations

import pathlib
import re
import toml
from console_utils import print_success, print_warning
from entrypoint_config import REWRITE_TABLE, BENCHED_CRATE_DEPS
from typing import List

__all__ = [
    "rewrite_sources_for_entrypoint",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_pinocchio_handlers(crate_root: pathlib.Path):
    """Make sure the copied benched crate is *no_std* and wired up for Pinocchio."""
    lib_rs = crate_root / "src" / "lib.rs"
    if not lib_rs.is_file():
        return

    try:
        content = lib_rs.read_text("utf-8")
        needs_write = False

        # 1. Guarantee #![no_std]
        if "#![no_std]" not in content and "#![cfg_attr(" not in content:
            content = "#![no_std]\n" + content
            needs_write = True

        # 2. Ensure use + macro calls
        if "use pinocchio::{no_allocator, nostd_panic_handler}" not in content:
            content = content.replace(
                "use {",
                "use pinocchio::{no_allocator, nostd_panic_handler};\nuse {",
                1,
            )
            needs_write = True

        # 3. Ensure macro invocations *after* the first use group
        if "no_allocator!();" not in content or "nostd_panic_handler!();" not in content:
            content_lines = [
                l
                for l in content.splitlines()
                if not l.strip().startswith(("no_allocator!()", "nostd_panic_handler!()"))
            ]
            content = "\n".join(content_lines)
            insert_pos = content.find("};")
            insert_pos = insert_pos + 3 if insert_pos != -1 else content.find("\n")
            macros = []
            if "no_allocator!();" not in content:
                macros.append("no_allocator!();")
            if "nostd_panic_handler!();" not in content:
                macros.append("nostd_panic_handler!();")
            content = (
                content[:insert_pos] + "\n" + "\n".join(macros) + "\n" + content[insert_pos:]
            )
            needs_write = True

        if needs_write:
            lib_rs.write_text(content, encoding="utf-8")
            print_success("Updated src/lib.rs for pinocchio handlers and no_std")
    except Exception as exc:
        print_warning(f"Failed to patch {lib_rs}: {exc}")


def _ensure_nostd_entrypoint_alias(crate_root: pathlib.Path):
    lib_rs = crate_root / "src" / "lib.rs"
    if not lib_rs.is_file():
        return
    try:
        content = lib_rs.read_text("utf-8")
        if "NoStdAccountInfo as AccountInfo" not in content:
            content = content.replace(
                "NoStdAccountInfo", "NoStdAccountInfo as AccountInfo"
            )
            lib_rs.write_text(content, encoding="utf-8")
            print_success("Added alias `as AccountInfo` for NoStdAccountInfo")
    except Exception as exc:
        print_warning(f"Failed to patch alias in {lib_rs}: {exc}")


def _ensure_manifest_deps_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    deps_to_add = BENCHED_CRATE_DEPS.get(entrypoint_name)
    if not deps_to_add:
        return

    manifest_path = crate_root / "Cargo.toml"
    if not manifest_path.is_file():
        return

    try:
        manifest_data = toml.load(manifest_path)
    except Exception as exc:
        print_warning(f"Failed to parse manifest {manifest_path}: {exc}")
        return

    deps_table = manifest_data.setdefault("dependencies", {})
    changed = False

    ALL_KNOWN_SDK_DEPS = [
        "pinocchio",
        "solana-program",
        "solana-account-info",
        "solana-entrypoint",
        "solana-program-error",
        "solana-pubkey",
        "solana-msg",
        "solana-nostd-entrypoint",
    ]

    for key in list(deps_table.keys()):
        if key in ALL_KNOWN_SDK_DEPS:
            deps_table.pop(key)
            changed = True

    for dep_name, dep_info in deps_to_add.items():
        if dep_name not in deps_table:
            deps_table[dep_name] = dep_info
            changed = True

    if changed:
        try:
            manifest_path.write_text(toml.dumps(manifest_data), encoding="utf-8")
            print_success(
                f"Patched dependencies in benched crate manifest for {entrypoint_name}"
            )
        except Exception as exc:
            print_warning(f"Failed to update manifest {manifest_path}: {exc}")


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_DOUBLE_PREFIX_RE = re.compile(
    r"\b(\w+)::(solana_(?:pubkey|account_info))::"
)


def _collapse_double_prefixes(content: str) -> str:
    """Turn `foo::solana_pubkey::` -> `solana_pubkey::`."""
    return _DOUBLE_PREFIX_RE.sub(r"\2::", content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rewrite_sources_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    """Rewrite imported paths in the copied benched crate so that they target
    the chosen *entrypoint* implementation (pinocchio, solana-program, ...).
    """
    patterns = REWRITE_TABLE.get(entrypoint_name, {})
    if not patterns:
        print_warning(
            f"No rewrite patterns defined for entrypoint '{entrypoint_name}'. Skipping source rewrite."
        )
        return

    print_success(f"Rewriting source imports for entrypoint: {entrypoint_name}")
    files_modified = 0

    for rust_file in crate_root.rglob("*.rs"):
        try:
            original_content = rust_file.read_text("utf-8")
            modified_content = original_content
            for pattern, replacement in patterns.items():
                modified_content = re.sub(pattern, replacement, modified_content)

            # Extra cleanup for non-pinocchio entrypoints ------------------
            if entrypoint_name != "pinocchio":
                # 1. Drop helper identifiers from use lists
                modified_content = re.sub(r"\bno_allocator\s*,?\s*", "", modified_content)
                modified_content = re.sub(r"\bnostd_panic_handler\s*,?\s*", "", modified_content)

                # clean up duplicate commas/ braces after removal
                modified_content = re.sub(r",\s*}\s*;", " };", modified_content)

                # 2. Remove the macro invocations entirely
                modified_content = re.sub(r"^.*no_allocator!\(\).*\n?", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^.*nostd_panic_handler!\(\).*\n?", "", modified_content, flags=re.MULTILINE)

                # 3. Fix nested path mappings for Pubkey / AccountInfo
                modified_content = re.sub(r"solana_entrypoint::pubkey::", "solana_pubkey::", modified_content)
                modified_content = re.sub(r"solana_entrypoint::account_info::", "solana_account_info::", modified_content)
                modified_content = re.sub(
                    r"solana_entrypoint::solana_(pubkey|account_info)::",
                    r"solana_\1::",
                    modified_content,
                )

                modified_content = re.sub(r"solana_program::entrypoint::pubkey::", "solana_program::pubkey::", modified_content)
                modified_content = re.sub(r"solana_program::entrypoint::account_info::", "solana_program::account_info::", modified_content)
                modified_content = re.sub(
                    r"solana_program::entrypoint::solana_program::(pubkey|account_info)::",
                    r"solana_program::\1::",
                    modified_content,
                )

                # Replace inside grouped imports like `{ pubkey::Pubkey, account_info::AccountInfo }`
                if entrypoint_name == "solana-program":
                    # Map bare path segments to breakout crates
                    modified_content = re.sub(r"\bpubkey::", "solana_pubkey::", modified_content)
                    modified_content = re.sub(r"\baccount_info::", "solana_account_info::", modified_content)

                    # Drop the leading `solana_entrypoint::` prefix in grouped uses, turning
                    # `use solana_entrypoint::{ ... }` into `use { ... }`.
                    modified_content = re.sub(r"\buse\s+solana_entrypoint::\s*{", "use {", modified_content)

                    # Convert any leftover ProgramResult references → solana_entrypoint::ProgramResult
                    modified_content = re.sub(
                        r"\bsolana_entrypoint::ProgramResult\b|\bProgramResult\b",
                        "solana_entrypoint::ProgramResult",
                        modified_content,
                    )

                elif entrypoint_name == "solana-program-mono":
                    # For the monolithic SDK, convert bare paths directly to solana_program::* but
                    # only when they are *not* already properly prefixed to avoid duplications.
                    modified_content = re.sub(
                        r"(?<!solana_program::)\bpubkey::",
                        "solana_program::pubkey::",
                        modified_content,
                    )
                    modified_content = re.sub(
                        r"(?<!solana_program::)\baccount_info::",
                        "solana_program::account_info::",
                        modified_content,
                    )

                    # Drop grouped import root: `use solana_program::entrypoint::{ ... }` => `use { ... }`
                    modified_content = re.sub(
                        r"\buse\s+solana_program::entrypoint::\s*{",
                        "use {",
                        modified_content,
                    )

                    # Adjust ProgramResult to the correct path within the monolithic crate
                    modified_content = re.sub(
                        r"\bsolana_program::entrypoint(::deprecated)?::ProgramResult\b|\bProgramResult\b",
                        "solana_program::entrypoint_deprecated::ProgramResult",
                        modified_content,
                    )

                elif entrypoint_name == "solana-nostd-entrypoint":
                    # NoStd-entrypoint uses breakout crates directly as well
                    modified_content = re.sub(r"\bpubkey::", "solana_pubkey::", modified_content)
                    modified_content = re.sub(r"\baccount_info::", "solana_account_info::", modified_content)

                    # Replace full paths to AccountInfo with NoStdAccountInfo
                    modified_content = re.sub(
                        r"solana_account_info::AccountInfo",
                        "solana_nostd_entrypoint::NoStdAccountInfo",
                        modified_content,
                    )

                    # 3b. For nostd entrypoint ensure ProgramResult is referenced correctly
                    modified_content = re.sub(
                        r"\bProgramResult\b",
                        "solana_program_error::ProgramResult",
                        modified_content,
                    )

                # 4. Remove lingering pinocchio prefix for nostd target
                if entrypoint_name == "solana-nostd-entrypoint":
                    modified_content = re.sub(r"\bpinocchio::", "", modified_content)

                # 5. Collapse any duplicated prefixes produced by previous steps
                modified_content = _collapse_double_prefixes(modified_content)

                # 6. Strip entrypoint feature-gate cfg attributes for non-pinocchio builds so that
                #    the bench modules are always compiled.
                if entrypoint_name != "pinocchio":
                    modified_content = re.sub(
                        r"(?m)^\s*#\s*\[cfg\(any\([^)]*solana-[^)]*\)\)\]\s*\n",
                        "",
                        modified_content,
                    )

                # 6b. Rewrite any `use crate::{ ... ProgramResult}` import blocks to entrypoint-specific paths
                def _replace_crate_use(match: re.Match) -> str:
                    pre = match.group(1)
                    if entrypoint_name == "solana-program":
                        return f"{pre}use {{solana_pubkey::Pubkey, solana_account_info::AccountInfo, solana_entrypoint::ProgramResult}};"
                    elif entrypoint_name == "solana-program-mono":
                        return f"{pre}use {{solana_program::pubkey::Pubkey, solana_program::account_info::AccountInfo, solana_program::entrypoint_deprecated::ProgramResult}};"
                    elif entrypoint_name == "solana-nostd-entrypoint":
                        return f"{pre}use {{solana_pubkey::Pubkey, solana_nostd_entrypoint::NoStdAccountInfo as AccountInfo, solana_program_error::ProgramResult, solana_msg::sol_log}};"
                    else:  # pinocchio
                        return f"{pre}use {{pinocchio::pubkey::Pubkey, pinocchio::account_info::AccountInfo, pinocchio::ProgramResult}};"

                modified_content = re.sub(
                    r"(^\s*)use\s+crate::\{[^}]*ProgramResult[^}]*};",
                    _replace_crate_use,
                    modified_content,
                    flags=re.MULTILINE,
                )

                # 6c. Collapse duplicate solana_program_error path
                modified_content = re.sub(
                    r"solana_program_error::solana_program_error::ProgramResult",
                    "solana_program_error::ProgramResult",
                    modified_content,
                )

                # 7. Add appropriate imports and fix logging calls within benchmark modules
                if entrypoint_name == "solana-program":
                    # Add imports to solana_benches module if it exists
                    if "pub mod solana_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod solana_benches\s*\{)",
                            r"\1\n    use {solana_msg::msg, solana_pubkey::Pubkey, solana_account_info::AccountInfo, solana_entrypoint::ProgramResult};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Add imports to pinocchio_benches module if it exists
                    if "pub mod pinocchio_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod pinocchio_benches\s*\{)",
                            r"\1\n    use {solana_msg::msg, solana_pubkey::Pubkey, solana_account_info::AccountInfo, solana_entrypoint::ProgramResult};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Replace sol_log with msg! in pinocchio_benches for this target
                    modified_content = re.sub(
                        r'sol_log\("([^"]*)"\);',
                        r'msg!("\1");',
                        modified_content,
                    )

                elif entrypoint_name == "solana-program-mono":
                    # Add imports to solana_benches module if it exists
                    if "pub mod solana_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod solana_benches\s*\{)",
                            r"\1\n    use {solana_program::msg, solana_program::pubkey::Pubkey, solana_program::account_info::AccountInfo, solana_program::entrypoint_deprecated::ProgramResult};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Add imports to pinocchio_benches module if it exists
                    if "pub mod pinocchio_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod pinocchio_benches\s*\{)",
                            r"\1\n    use {solana_program::msg, solana_program::pubkey::Pubkey, solana_program::account_info::AccountInfo, solana_program::entrypoint_deprecated::ProgramResult};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Replace sol_log with msg! in pinocchio_benches for this target
                    modified_content = re.sub(
                        r'sol_log\("([^"]*)"(?:\)|; )',
                        r'msg!("\1");',
                        modified_content,
                    )

                elif entrypoint_name == "solana-nostd-entrypoint":
                    # Add imports to solana_benches module if it exists
                    if "pub mod solana_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod solana_benches\s*\{)",
                            r"\1\n    use {solana_pubkey::Pubkey, solana_nostd_entrypoint::NoStdAccountInfo as AccountInfo, solana_program_error::ProgramResult, solana_msg::sol_log};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Add imports to pinocchio_benches module if it exists
                    if "pub mod pinocchio_benches" in modified_content:
                        modified_content = re.sub(
                            r"(pub mod pinocchio_benches\s*\{)",
                            r"\1\n    use {solana_pubkey::Pubkey, solana_nostd_entrypoint::NoStdAccountInfo as AccountInfo, solana_program_error::ProgramResult, solana_msg::sol_log};",
                            modified_content,
                            flags=re.MULTILINE,
                        )
                    # Convert msg! to sol_log for nostd target
                    modified_content = re.sub(
                        r'msg!\("([^"]*)"\);',
                        r'sol_log("\1");',
                        modified_content,
                    )

            # ---------------- Pinocchio specific imports & logging ----------------
            if entrypoint_name == "pinocchio":
                # Bring required symbols into both bench modules if they exist
                if "pub mod pinocchio_benches" in modified_content:
                    modified_content = re.sub(
                        r"(pub mod pinocchio_benches\s*\{)",
                        r"\1\n    use {pinocchio::log::sol_log, pinocchio::pubkey::Pubkey, pinocchio::account_info::AccountInfo, pinocchio::ProgramResult};",
                        modified_content,
                        flags=re.MULTILINE,
                    )
                if "pub mod solana_benches" in modified_content:
                    modified_content = re.sub(
                        r"(pub mod solana_benches\s*\{)",
                        r"\1\n    use {pinocchio::log::sol_log, pinocchio::pubkey::Pubkey, pinocchio::account_info::AccountInfo, pinocchio::ProgramResult};",
                        modified_content,
                        flags=re.MULTILINE,
                    )
                modified_content = re.sub(
                    r'msg!\("([^"]*)"\);',
                    r'sol_log("\1");',
                    modified_content,
                )

            # ---------------- nostd cfg cleanup ----------------
            if entrypoint_name == "solana-nostd-entrypoint":
                # Remove #[cfg(feature="no_std")] lines so pinocchio_benches is compiled
                modified_content = re.sub(
                    r"(?m)^\s*#\s*\[cfg\(feature\s*=\s*\"no_std\"\)\]\s*\n",
                    "",
                    modified_content,
                )

            # 9. Ensure benchmark module aliases exist for mono & nostd targets (only if source modules exist)
            if entrypoint_name == "solana-program-mono" and "solana_program_mono_benches" not in modified_content:
                if "pub mod solana_benches" in modified_content:
                    modified_content += "\n\npub use solana_benches as solana_program_mono_benches;\n"

            if entrypoint_name == "solana-nostd-entrypoint" and "nostd_entrypoint_benches" not in modified_content:
                if "pub mod pinocchio_benches" in modified_content:
                    modified_content += "\n\npub use pinocchio_benches as nostd_entrypoint_benches;\n"
                elif "pub mod solana_benches" in modified_content:
                    modified_content += "\n\npub use solana_benches as nostd_entrypoint_benches;\n"

            if modified_content != original_content:
                rust_file.write_text(modified_content, "utf-8")
                files_modified += 1
                print_success(f"  Modified: {rust_file.relative_to(crate_root)}")
        except Exception as exc:
            print_warning(f"Failed to rewrite {rust_file}: {exc}")

    if files_modified == 0:
        print_warning(
            f"No source files needed import rewriting for '{entrypoint_name}' entrypoint."
        )

    # Post-processing tweaks ----------------------------------------------------------
    if entrypoint_name == "pinocchio":
        _ensure_pinocchio_handlers(crate_root)
        # Inject a dummy no_std feature so cfg(feature="no_std") sections compile
        manifest_path = crate_root / "Cargo.toml"
        try:
            manifest_data = toml.load(manifest_path)
            feats = manifest_data.setdefault("features", {})
            if "no_std" not in feats:
                feats["no_std"] = []
                manifest_path.write_text(toml.dumps(manifest_data), "utf-8")
        except Exception:
            pass
    elif entrypoint_name == "solana-nostd-entrypoint":
        _ensure_nostd_entrypoint_alias(crate_root)

    _ensure_manifest_deps_for_entrypoint(entrypoint_name, crate_root) 