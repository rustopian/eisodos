from __future__ import annotations

import pathlib
import re
import toml
from console_utils import print_success, print_warning
from entrypoint_config import NORMALIZE_TO_BREAKOUT, DENORMALIZE_FROM_BREAKOUT, BENCHED_CRATE_DEPS, IDENTIFIER_MAPPINGS
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
        
        # Only add alias to NoStdAccountInfo that doesn't already have an alias
        # Pattern: NoStdAccountInfo (but not NoStdAccountInfo as something)
        if "NoStdAccountInfo as AccountInfo" not in content:
            # Use a more precise regex that doesn't match already aliased imports
            content = re.sub(
                r'\bNoStdAccountInfo(?!\s+as\s+\w+)',  # NoStdAccountInfo not followed by " as word"
                'NoStdAccountInfo as AccountInfo',
                content
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


def _extract_all_imported_identifiers(content: str) -> set:
    """Extract all imported identifiers from use statements."""
    import re
    
    identifiers = set()
    
    # Find all use statements
    use_pattern = r'use\s+[^;]+;'
    use_statements = re.findall(use_pattern, content, re.MULTILINE | re.DOTALL)
    
    for stmt in use_statements:
        # Remove 'use' and ';', clean up whitespace
        cleaned = re.sub(r'use\s+|;', '', stmt).strip()
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        # Check if this is a top-level grouped import: use { ... }
        if cleaned.startswith('{') and cleaned.endswith('}'):
            # This is a top-level grouped import like: use { item1, item2::subitem, item3::{a, b} }
            inner_content = cleaned[1:-1]  # Remove outer braces
            
            # Split by comma, but be careful about nested braces
            items = []
            current_item = ""
            brace_depth = 0
            
            for char in inner_content + ',':  # Add comma to ensure last item is processed
                if char == '{':
                    brace_depth += 1
                    current_item += char
                elif char == '}':
                    brace_depth -= 1
                    current_item += char
                elif char == ',' and brace_depth == 0:
                    if current_item.strip():
                        items.append(current_item.strip())
                    current_item = ""
                else:
                    current_item += char
            
            # Process each item in the top-level group
            for item in items:
                item = item.strip()
                if not item:
                    continue
                    
                # Check if this item has its own grouped imports: item::{a, b}
                if '{' in item and '}' in item:
                    # This is like: solana_account_info::{AccountInfo, next_account_info}
                    base = item.split('{')[0].strip()
                    grouped_part = item[item.find('{')+1:item.find('}')]
                    for subitem in grouped_part.split(','):
                        subitem = subitem.strip()
                        if ' as ' in subitem:
                            alias = subitem.split(' as ')[1].strip()
                            identifiers.add(alias)
                        else:
                            identifiers.add(subitem)
                else:
                    # This is a simple import like: solana_cpi::invoke or Pubkey
                    if '::' in item:
                        final_part = item.split('::')[-1]
                        if ' as ' in final_part:
                            alias = final_part.split(' as ')[1].strip()
                            identifiers.add(alias)
                        else:
                            identifiers.add(final_part.strip())
                    else:
                        identifiers.add(item.strip())
        
        else:
            # Handle regular imports (not top-level grouped)
            # Handle grouped imports: extract from {...}
            grouped_match = re.search(r'\{([^}]*)\}', cleaned)
            if grouped_match:
                grouped_content = grouped_match.group(1)
                # Split by comma and extract identifiers
                for item in grouped_content.split(','):
                    item = item.strip()
                    if not item or item.startswith('//'):
                        continue
                    # Handle aliases like "Account as CpiAccount"
                    if ' as ' in item:
                        # Take the alias name (what it's called in the code)
                        alias = item.split(' as ')[1].strip()
                        identifiers.add(alias)
                    else:
                        # Extract the final identifier
                        if '::' in item:
                            identifiers.add(item.split('::')[-1].strip())
                        else:
                            identifiers.add(item.strip())
            else:
                # Handle individual imports like "use solana_program::pubkey::Pubkey;"
                if '::' in cleaned:
                    final_part = cleaned.split('::')[-1]
                    if ' as ' in final_part:
                        alias = final_part.split(' as ')[1].strip()
                        identifiers.add(alias)
                    else:
                        identifiers.add(final_part.strip())
                else:
                    # Handle simple imports like "use some_crate;"
                    identifiers.add(cleaned)
    
    return identifiers


def _get_rewrite_mapping_for_entrypoint(entrypoint_name: str) -> dict:
    """Retrieve identifier→import-path mapping for the selected entrypoint.

    The heavy mapping data now lives in `entrypoint_config.IDENTIFIER_MAPPINGS` so
    we only keep a very thin wrapper here, reducing the overall file size while
    maintaining the original public helper name.
    """
    
    return IDENTIFIER_MAPPINGS.get(entrypoint_name, {})


def _generate_target_imports(found_identifiers: set, entrypoint_name: str) -> str:
    """Generate clean import statements for the target entrypoint."""
    
    rewrite_mapping = _get_rewrite_mapping_for_entrypoint(entrypoint_name)
    
    # Find which identifiers need to be imported for this target
    target_imports = {}
    unknown_identifiers = []
    
    for identifier in found_identifiers:
        if identifier in rewrite_mapping:
            target_path = rewrite_mapping[identifier]
            target_imports[identifier] = target_path
        else:
            # Only warn about identifiers that look like Solana types
            if any(solana_hint in identifier.lower() for solana_hint in 
                   ['program', 'account', 'pubkey', 'invoke', 'instruction', 'error', 'result']):
                unknown_identifiers.append(identifier)
    
    if unknown_identifiers:
        print_warning(f"Unknown Solana identifiers for {entrypoint_name}: {', '.join(unknown_identifiers)}")
    
    if not target_imports:
        return ""
    
    # Group imports by crate
    crate_imports = {}
    for identifier, full_path in target_imports.items():
        if '::' in full_path:
            crate = '::'.join(full_path.split('::')[:-1])
            type_name = full_path.split('::')[-1]
        else:
            crate = full_path
            type_name = identifier
            
        if crate not in crate_imports:
            crate_imports[crate] = []
        
        # Special handling for solana-nostd-entrypoint double alias issue
        if entrypoint_name == "solana-nostd-entrypoint" and crate == "solana_nostd_entrypoint" and type_name == "NoStdAccountInfo":
            if identifier == "AccountInfo":
                # Just import as AccountInfo (the alias will be added by _ensure_nostd_entrypoint_alias)
                crate_imports[crate].append("NoStdAccountInfo")
            elif identifier == "CpiAccount":
                # Import as CpiAccount directly
                crate_imports[crate].append("NoStdAccountInfo as CpiAccount")
            else:
                crate_imports[crate].append(type_name)
        else:
            # Handle aliases (like AccountInfo as CpiAccount)
            if identifier != type_name and identifier == "CpiAccount":
                crate_imports[crate].append(f"{type_name} as {identifier}")
            else:
                crate_imports[crate].append(type_name)
    
    # Generate import statements
    import_lines = []
    for crate, types in sorted(crate_imports.items()):
        unique_types = sorted(set(types))  # Remove duplicates and sort
        if len(unique_types) == 1:
            import_lines.append(f"use {crate}::{unique_types[0]};")
        else:
            types_str = ', '.join(unique_types)
            import_lines.append(f"use {crate}::{{{types_str}}};")
    
    return '\n'.join(import_lines)


def _replace_qualified_usage_patterns(content: str, entrypoint_name: str) -> str:
    """Replace qualified usage patterns like instruction::create_account and program::ID in the code."""
    import re
    
    if entrypoint_name == "pinocchio":
        # For pinocchio, replace with pinocchio-specific patterns
        content = re.sub(r'\binstruction::create_account\b', 'pinocchio::sysvars::system_instruction::create_account', content)
        content = re.sub(r'\bprogram::ID\b', 'pinocchio::sysvars::SYSTEM_PROGRAM_ID', content)
    
    elif entrypoint_name == "solana-program":
        # Replace instruction::create_account with full path
        content = re.sub(r'\binstruction::create_account\b', 'solana_system_interface::instruction::create_account', content)
        # Replace program::ID with full path
        content = re.sub(r'\bprogram::ID\b', 'solana_system_interface::program::ID', content)
    
    elif entrypoint_name == "solana-program-mono":
        # Replace instruction::create_account with full path
        content = re.sub(r'\binstruction::create_account\b', 'solana_program::system_instruction::create_account', content)
        # Replace program::ID with full path
        content = re.sub(r'\bprogram::ID\b', 'solana_program::system_program::ID', content)
    
    elif entrypoint_name == "solana-nostd-entrypoint":
        # For nostd, avoid system functions that require unavailable crates
        # Replace with basic invoke pattern since we can't use system_instruction 
        content = re.sub(r'\binstruction::create_account\b', 'create_account_instruction', content)
        # Use a hardcoded system program ID since solana_program isn't available
        content = re.sub(r'\bprogram::ID\b', 'system_program_id', content)
    
    return content


def _replace_imports_with_target_imports(content: str, entrypoint_name: str) -> str:
    """Replace Solana imports with clean target-specific imports and fix module names expected by the runner."""
    import re

    # -------------------------------------------------------------
    # 1. Selectively remove code based on feature gates
    # -------------------------------------------------------------
    lines = content.splitlines()
    kept_lines = []
    
    is_std_target = entrypoint_name in ("solana-program", "solana-program-mono")

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("#[cfg"):
            is_no_std_cfg = 'feature = "no_std"' in stripped
            
            # Determine if this is the block to discard
            if (is_std_target and is_no_std_cfg) or \
               (not is_std_target and not is_no_std_cfg and "feature = " in stripped):
                # Find the end of the module block and skip it
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("pub mod"):
                    j += 1
                
                if j < len(lines):
                    brace_level = 0
                    k = j
                    found_start_brace = False
                    while k < len(lines):
                        if '{' in lines[k]:
                            brace_level += lines[k].count('{')
                            found_start_brace = True
                        if '}' in lines[k]:
                            brace_level -= lines[k].count('}')
                        if found_start_brace and brace_level == 0:
                            i = k + 1
                            break
                        k += 1
                    else: # If no closing brace, just skip the cfg and mod line
                        i = j + 1
                else: # if no mod after cfg, just skip the cfg line
                    i += 1
                continue
        
        kept_lines.append(line)
        i += 1
        
    modified_content = "\n".join(kept_lines)
    # Remove any remaining cfg attributes (including nested parentheses)
    modified_content = re.sub(r'#\[\s*cfg[^\]]*\]\s*\n?', '', modified_content, flags=re.MULTILINE)


    # -------------------------------------------------------------
    # 2.  Extract identifiers from the cleaned content
    # -------------------------------------------------------------
    found_identifiers = _extract_all_imported_identifiers(modified_content)
    # Add identifiers that might be used without a `use` statement in the original code
    if "msg!" in modified_content:
        found_identifiers.add("msg")
    if "sol_log" in modified_content:
        found_identifiers.add("sol_log")
    for keyword in ["Pubkey", "AccountInfo", "ProgramResult", "ProgramError", "Instruction", "AccountMeta", "next_account_info"]:
        if re.search(r'\b' + keyword + r'\b', modified_content):
            found_identifiers.add(keyword)


    # -------------------------------------------------------------
    # 3. Strip old imports
    # -------------------------------------------------------------
    lines = modified_content.splitlines()
    clean_lines: list[str] = []

    # State for simple one-line import filtering
    skip_block_until: int | None = None

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ---------------------------------------------------------
        # 3a. Remove single-line imports that start with pinocchio/solana_
        # ---------------------------------------------------------
        if stripped.startswith("use pinocchio") or stripped.startswith("use solana_"):
            # Multi-line grouped import handled below – this path covers the plain form
            #   use solana_account_info::AccountInfo;
            i += 1
            continue

        # ---------------------------------------------------------
        # 3b. Remove a *grouped* import beginning with `use {` that lists
        #     pinocchio/* or solana_* items. We scan forward until the closing `};`.
        # ---------------------------------------------------------
        if stripped.startswith("use {"):
            # Peek forward to find closing `};` and decide whether to drop.
            j = i + 1
            group_has_solana = False
            while j < len(lines):
                inner = lines[j].strip()
                if "};" in inner:
                    break
                if "solana_" in inner or "pinocchio" in inner:
                    group_has_solana = True
                j += 1

            if group_has_solana:
                # Skip i … j (inclusive)
                i = j + 1
                continue

        clean_lines.append(line)
        i += 1

    modified_content = "\n".join(clean_lines)


    # -------------------------------------------------------------
    # 4. Generate and insert new imports
    # -------------------------------------------------------------
    target_imports = _generate_target_imports(found_identifiers, entrypoint_name)
    if not target_imports:
        return modified_content

    top_level_import_block = target_imports

    # For pinocchio, ensure no_std setup is present before adding imports
    if entrypoint_name == "pinocchio":
        if "#![no_std]" not in modified_content:
            modified_content = "#![no_std]\n" + modified_content
        if "use pinocchio::{no_allocator, nostd_panic_handler};" not in modified_content and "no_allocator" not in top_level_import_block:
             modified_content = modified_content.replace(
                "#![no_std]",
                "#![no_std]\nuse pinocchio::{no_allocator, nostd_panic_handler};"
            )

    # Insert imports at the top
    lines = modified_content.splitlines()
    insert_index = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('#!['):
            insert_index = i + 1
        elif line.strip() and not line.strip().startswith("//"):
            break
    lines.insert(insert_index, "\n" + top_level_import_block)
    modified_content = "\n".join(lines)


    # -------------------------------------------------------------
    # 5. Final fixups
    # -------------------------------------------------------------
    if entrypoint_name == "pinocchio":
        lines = modified_content.split('\n')
        insert_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('use ') or line.strip().startswith('#!['):
                insert_index = i + 1
            elif line.strip() and not line.strip().startswith('//'):
                break
        
        # Re-locate insertion point *after* the full import section so we
        # never end up inside a `use { … }` group.
        def _end_of_imports(ls: list[str]) -> int:
            inside_grp = False
            last_idx = 0
            for idx, ln in enumerate(ls):
                s = ln.strip()
                if s.startswith("use "):
                    last_idx = idx
                    if s.endswith("{") or s == "use {":
                        inside_grp = True
                elif inside_grp:
                    last_idx = idx
                    if s.endswith("};") or s == "};":
                        inside_grp = False
                elif s == "":
                    continue
                else:
                    # first non-import line outside group
                    break
            return last_idx + 1

        insert_index = _end_of_imports(lines)

        if "no_allocator!();" not in modified_content:
            lines.insert(insert_index, "no_allocator!();")
            insert_index += 1
        if "nostd_panic_handler!();" not in modified_content:
            lines.insert(insert_index, "nostd_panic_handler!();")
        modified_content = '\n'.join(lines)
    
    modified_content = _replace_qualified_usage_patterns(modified_content, entrypoint_name)
    
    if entrypoint_name != "pinocchio":
        modified_content = re.sub(r"\bno_allocator\s*,?\s*", "", modified_content)
        modified_content = re.sub(r"\bnostd_panic_handler\s*,?\s*", "", modified_content)
        modified_content = re.sub(r",\s*}\s*;", " };", modified_content)
        modified_content = re.sub(r"^.*no_allocator!\(\).*\n?", "", modified_content, flags=re.MULTILINE)
        modified_content = re.sub(r"^.*nostd_panic_handler!\(\).*\n?", "", modified_content, flags=re.MULTILINE)
        modified_content = re.sub(r'^\s*use crate::\{[^}]*\};\s*\n', '', modified_content, flags=re.MULTILINE)
        modified_content = re.sub(r'^\s*const PINOCCHIO_SYSTEM_PROGRAM_ID.*\n', '', modified_content, flags=re.MULTILINE)

    modified_content = _collapse_double_prefixes(modified_content)
    modified_content = _ensure_use_super_in_modules(modified_content)
    modified_content = _deduplicate_use_lines(modified_content)
    
    return modified_content


def _transform_grouped_solana_program_imports(content: str) -> str:
    """DEPRECATED: Use _replace_solana_imports_with_clean_imports instead."""
    return content


def _apply_import_rewrite_patterns(content: str, patterns: dict) -> str:
    """Apply a set of regex patterns to rewrite imports in content."""
    modified_content = content
    for pattern, replacement in patterns.items():
        modified_content = re.sub(pattern, replacement, modified_content)
    return modified_content


def _should_skip_normalization_for_mono(content: str) -> bool:
    """Check if we should skip normalization for solana-program-mono target.
    
    Skip if the source already uses correct solana_program grouped imports
    to avoid breaking them.
    """
    return ("use solana_program::{" in content and 
            any(pattern in content for pattern in ["pubkey::", "account_info::", "entrypoint::"]))


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
# Generic post-processing helpers (entrypoint-agnostic)
# ---------------------------------------------------------------------------


def _deduplicate_use_lines(content: str) -> str:
    """Remove duplicate `use XXX;` lines that cause E0252 re-imports."""
    seen: set[str] = set()
    out_lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("use ") and stripped.endswith(";"):
            if stripped in seen:
                continue
            seen.add(stripped)
        out_lines.append(line)
    return "\n".join(out_lines)


def _ensure_use_super_in_modules(content: str) -> str:
    """Insert `use super::*;` at the start of every module block if absent.

    This allows inner modules to see top-level imports/consts without knowing
    their names. We detect a line that opens a `pub mod … {` (any visibility)
    and inject one indent level deeper.
    """
    lines = content.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        stripped = line.lstrip()
        if stripped.startswith("pub mod ") and stripped.rstrip().endswith("{"):
            # determine indent (spaces/tabs before 'pub')
            indent = line[: len(line) - len(stripped)] + "    "
            # look ahead for first non-blank line inside module
            j = i + 1
            has_super = False
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and "use super::*;" in lines[j]:
                has_super = True
            if not has_super:
                out.append(f"{indent}use super::*;")
        i += 1
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rewrite_sources_for_entrypoint(entrypoint_name: str, crate_root: pathlib.Path):
    """Rewrite imported paths in the copied benched crate by detecting all Solana types
    and mapping them to the appropriate target entrypoint format.
    """
    print_success(f"Rewriting source imports for entrypoint: {entrypoint_name}")
    files_modified = 0

    for rust_file in crate_root.rglob("*.rs"):
        try:
            original_content = rust_file.read_text("utf-8")
            modified_content = original_content
            
            # Step 1: Normalize to breakout format (unless we should skip)
            should_skip_normalization = (entrypoint_name == "solana-program-mono" and 
                                       _should_skip_normalization_for_mono(original_content))
            
            if should_skip_normalization:
                print_success(f"  Skipping normalization for {rust_file.relative_to(crate_root)} (already uses solana_program)")
                
                # Even when skipping normalization, we may need to fix imports inside feature-gated modules
                # Apply patterns only within module blocks for mono target
                lines = modified_content.split('\n')
                in_std_module = False
                brace_count = 0
                
                for i, line in enumerate(lines):
                    if '#[cfg(all(feature = "std"))]' in line:
                        in_std_module = True
                    elif in_std_module and 'pub mod ' in line and ' {' in line:
                        brace_count = 1  # Found any module inside std cfg block
                    elif in_std_module and brace_count > 0:
                        # Count braces to know when we exit the module
                        brace_count += line.count('{') - line.count('}')
                        
                        # Apply transformations within this module
                        if 'solana_account_info::' in line:
                            lines[i] = line.replace('solana_account_info::', 'solana_program::account_info::')
                        if 'solana_program_error::' in line:
                            # Special handling for ProgramResult vs ProgramError
                            if 'ProgramResult' in line and 'ProgramError' in line:
                                # Handle the case where both are on the same line: {ProgramResult, ProgramError}
                                lines[i] = line.replace('solana_program_error::{ProgramResult, ProgramError}', 'solana_program::entrypoint::ProgramResult, solana_program::program_error::ProgramError')
                            elif 'ProgramResult' in line:
                                lines[i] = line.replace('solana_program_error::ProgramResult', 'solana_program::entrypoint::ProgramResult')
                            else:
                                lines[i] = line.replace('solana_program_error::', 'solana_program::program_error::')
                        if 'solana_cpi::invoke' in line:
                            lines[i] = line.replace('solana_cpi::invoke', 'solana_program::program::invoke')
                        if 'solana_pubkey::' in line:
                            lines[i] = line.replace('solana_pubkey::', 'solana_program::pubkey::')
                        if 'solana_system_interface::{instruction, program}' in line:
                            lines[i] = line.replace('solana_system_interface::{instruction, program}', 'solana_program::system_instruction, solana_program::system_program')
                        if 'instruction::' in line and '::' not in line[:line.find('instruction::')]:
                            lines[i] = line.replace('instruction::', 'solana_program::system_instruction::')
                        if 'program::ID' in line and '::' not in line[:line.find('program::ID')]:
                            lines[i] = line.replace('program::ID', 'solana_program::system_program::ID')
                        
                        if brace_count == 0:
                            in_std_module = False
                
                modified_content = '\n'.join(lines)

                # Strip any cfg attributes that may still gate the kept module
                modified_content = re.sub(r'#\[\s*cfg[^\]]*\]\s*\n?', '', modified_content, flags=re.MULTILINE)
            else:
                # Replace all Solana imports with clean, target-specific imports
                modified_content = _replace_imports_with_target_imports(modified_content, entrypoint_name)
            
            # No need for Step 2 denormalization - the new function handles everything

            # Cleanup for non-pinocchio entrypoints: remove pinocchio-specific helpers
            if entrypoint_name != "pinocchio":
                # Remove pinocchio helper identifiers from use lists
                modified_content = re.sub(r"\bno_allocator\s*,?\s*", "", modified_content)
                modified_content = re.sub(r"\bnostd_panic_handler\s*,?\s*", "", modified_content)
                # Clean up duplicate commas/braces after removal
                modified_content = re.sub(r",\s*}\s*;", " };", modified_content)
                # Remove the macro invocations entirely
                modified_content = re.sub(r"^.*no_allocator!\(\).*\n?", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^.*nostd_panic_handler!\(\).*\n?", "", modified_content, flags=re.MULTILINE)
                
                # Remove broken use crate:: imports 
                modified_content = re.sub(r'^\s*use crate::\{[^}]*\};\s*\n', '', modified_content, flags=re.MULTILINE)
                
                # Remove pinocchio-specific constants
                modified_content = re.sub(r'^\s*const PINOCCHIO_SYSTEM_PROGRAM_ID.*\n', '', modified_content, flags=re.MULTILINE)
                
                # Remove broken no_std modules for non-pinocchio entrypoints 
                modified_content = re.sub(
                    r'#\[cfg\(all\(feature = "no_std"\)\)\]\s*pub mod \w+\s*\{.*',
                    '',
                    modified_content,
                    flags=re.MULTILINE | re.DOTALL
                )

                # For solana-nostd-entrypoint, change std feature gate to no_std
                if entrypoint_name == "solana-nostd-entrypoint":
                    modified_content = re.sub(
                        r'#\[cfg\(all\(feature = "std"\)\)\]',
                        '#[cfg(feature = "no_std")]',
                        modified_content
                    )

            # Collapse any duplicated prefixes that may have been produced
            modified_content = _collapse_double_prefixes(modified_content)

            # Generic cleanup: ensure inner modules see top-level items and drop duplicate `use` lines
            modified_content = _ensure_use_super_in_modules(modified_content)
            modified_content = _deduplicate_use_lines(modified_content)

            # ------------------------------------------------------------------
            # Entry-specific post-pass to ensure logging macros are available
            # without relying on prior `use` lines in source.
            # ------------------------------------------------------------------

            if entrypoint_name in ("solana-program", "solana-program-mono"):
                if "msg!(" in modified_content:
                    expected_import = (
                        "use solana_msg::msg;" if entrypoint_name == "solana-program" else "use solana_program::msg;"
                    )
                    if expected_import not in modified_content:
                        # insert after the last file-level attribute (#![ .. ])
                        lines = modified_content.splitlines()
                        idx = 0
                        while idx < len(lines) and lines[idx].lstrip().startswith("#!["):
                            idx += 1
                        lines.insert(idx, expected_import)
                        modified_content = "\n".join(lines)
                
            elif entrypoint_name == "pinocchio":
                if "sol_log(" in modified_content and "use pinocchio::log::sol_log;" not in modified_content:
                    lines = modified_content.splitlines()
                    idx = 0
                    while idx < len(lines) and lines[idx].startswith("#!["):
                        idx += 1
                    lines.insert(idx, "use pinocchio::log::sol_log;")
                    modified_content = "\n".join(lines)

                # Remove duplicate inclusion of allocator/panic macros if we inserted a shorter `use` earlier
                modified_content = _deduplicate_use_lines(modified_content)

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

    # Post-processing tweaks
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