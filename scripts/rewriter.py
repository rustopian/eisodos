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
        if "#![no_std]" not in content:
            content = "#![no_std]\n" + content
            needs_write = True

        # 2. Ensure macro invocations exist (using fully-qualified path so no `use` needed)
        lines = content.splitlines()
        has_no_allocator = any("no_allocator!();" in line for line in lines)
        has_panic_handler = any("nostd_panic_handler!();" in line for line in lines)
        
        macros_to_insert: List[str] = []
        if not has_no_allocator:
            macros_to_insert.append("#[cfg(not(feature = \"std\"))] pinocchio::no_allocator!();")
        if not has_panic_handler:
            macros_to_insert.append("#[cfg(not(feature = \"std\"))] pinocchio::nostd_panic_handler!();")

        if macros_to_insert:
            # Determine insertion index: first non-attribute line (items start) but **after** last inner attribute
            insert_index = 0
            for idx, ln in enumerate(lines):
                if ln.lstrip().startswith('#!['):
                    insert_index = idx + 1
                else:
                    break
            # Insert macros in original order
            for m in reversed(macros_to_insert):
                lines.insert(insert_index, m)
            content = "\n".join(lines)
            needs_write = True

        if needs_write or macros_to_insert:
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
        elif identifier == "black_box":
            target_imports[identifier] = "core::hint::black_box"
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
            path_parts = full_path.split('::')
            if len(path_parts) >= 2:
                crate = '::'.join(path_parts[:-1])
                type_name = path_parts[-1]
            else:
                # Fallback for single part paths
                crate = full_path
                type_name = identifier
        else:
            # This shouldn't happen with our mappings, but just in case
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
        # Skip empty or invalid crate names
        if not crate or crate.isspace():
            continue
            
        unique_types = sorted(set(types))  # Remove duplicates and sort
        # Filter out invalid imports like Pubkey::default()
        valid_types = [t for t in unique_types if '::' not in t or ' as ' in t]
        if not valid_types:
            continue
        if len(valid_types) == 1:
            import_lines.append(f"use {crate}::{valid_types[0]};")
        else:
            types_str = ', '.join(valid_types)
            import_lines.append(f"use {crate}::{{{types_str}}};")
    
    return '\n'.join(import_lines)


def _replace_qualified_usage_patterns(content: str, entrypoint_name: str) -> str:
    """Replace qualified usage patterns like instruction::create_account and program::ID in the code."""
    import re
    
    if entrypoint_name in ("pinocchio", "pinocchio-std"):
        # For pinocchio, replace qualified usage patterns
        content = re.sub(r'\binstruction::create_account\b', 'pinocchio::sysvars::system_instruction::create_account', content)
        content = re.sub(r'\bprogram::ID\b', 'pinocchio::sysvars::SYSTEM_PROGRAM_ID', content)
        
        # Fix remaining pinocchio qualified patterns that weren't handled in import stripping
        # Split content into lines and only apply replacements to non-import lines
        lines = content.splitlines()
        modified_lines = []
        
        for line in lines:
            if line.strip().startswith('use '):
                # Don't modify import lines
                modified_lines.append(line)
            else:
                # Apply replacements to non-import lines
                line = re.sub(r'\bpinocchio::msg!', 'msg!', line)
                line = re.sub(r'\bpinocchio::log::sol_log\b', 'sol_log', line)
                line = re.sub(r'\bpinocchio::pubkey::Pubkey\b', 'Pubkey', line)
                line = re.sub(r'\bpinocchio::account_info::AccountInfo\b', 'AccountInfo', line)
                line = re.sub(r'\bpinocchio::program_error::ProgramError\b', 'ProgramError', line)
                line = re.sub(r'\bpinocchio::ProgramResult\b', 'ProgramResult', line)
                modified_lines.append(line)
        
        content = '\n'.join(modified_lines)
    
    elif entrypoint_name == "solana-program":
        # Replace instruction::create_account with full path
        content = re.sub(r'\binstruction::create_account\b', 'solana_system_interface::instruction::create_account', content)
        # Replace instruction::transfer with full path
        content = re.sub(r'\binstruction::transfer\b', 'solana_system_interface::instruction::transfer', content)
        # Replace program::ID with full path
        content = re.sub(r'\bprogram::ID\b', 'solana_system_interface::program::ID', content)
    
    elif entrypoint_name == "solana-program-mono":
        # Replace instruction::create_account with full path
        content = re.sub(r'\binstruction::create_account\b', 'solana_program::system_instruction::create_account', content)
        # Replace instruction::transfer with full path
        content = re.sub(r'\binstruction::transfer\b', 'solana_program::system_instruction::transfer', content)
        # Replace program::ID with full path
        content = re.sub(r'\bprogram::ID\b', 'solana_program::system_program::ID', content)
    
    elif entrypoint_name == "solana-nostd-entrypoint":
        # For nostd, avoid system functions that require unavailable crates
        # Replace with basic invoke pattern since we can't use system_instruction 
        content = re.sub(r'\binstruction::create_account\b', 'create_account_instruction', content)
        # Use a hardcoded system program ID since solana_program isn't available
        content = re.sub(r'\bprogram::ID\b', 'system_program_id', content)
    
    return content


def _strip_imports_and_generate_clean_imports(content: str, entrypoint_name: str) -> str:
    """Remove all `use …;` statements (except `use crate::processor;`) **without**
    touching surrounding braces/new-lines, then regenerate a cleaned import block
    that targets the requested entrypoint.
    
    The previous implementation used a single DOTALL regex that occasionally
    deleted the `}` following a multi-line grouped import, breaking brace
    balance.  We now work line-by-line so only the import lines themselves (and
    any #[cfg] attributes directly above them) are removed.
    """

    import re

    lines = content.splitlines()
    kept_lines: list[str] = []
    removed_use_lines: list[str] = []

    i = 0
    while i < len(lines):
        attr_buffer: list[str] = []

        # Collect preceding attributes (#[cfg …]) so we can drop them together
        while i < len(lines) and lines[i].lstrip().startswith('#['):
            attr_buffer.append(lines[i])
            i += 1

        if i >= len(lines):
            kept_lines.extend(attr_buffer)
            break

        line = lines[i]
        stripped = line.lstrip()

        if stripped.startswith('use '):
            # Keep the special crate::processor import, drop everything else
            if stripped.startswith('use crate::processor'):
                kept_lines.extend(attr_buffer)
                kept_lines.append(line)
                i += 1
            else:
                # Drop attr_buffer + the entire use-block up to and including the semicolon
                current_use_lines: list[str] = attr_buffer + [line]
                while ';' not in lines[i]:
                    i += 1
                    current_use_lines.append(lines[i])
                removed_use_lines.extend(current_use_lines)
                i += 1  # move past the semicolon line
        else:
            # Not an import – keep what we buffered and this line
            kept_lines.extend(attr_buffer)
            kept_lines.append(line)
            i += 1

    content_without_imports = '\n'.join(kept_lines)

    # --------------------------------------------------------------------------------
    # Identifier extraction / new-import generation (mostly unchanged)
    # --------------------------------------------------------------------------------

    had_original_imports = len(removed_use_lines) > 0

    found_identifiers = _extract_all_imported_identifiers('\n'.join(removed_use_lines))

    # Add identifiers that might be used without explicit imports
    if "msg!" in content_without_imports:
        found_identifiers.add("msg")
    if "sol_log" in content_without_imports:
        found_identifiers.add("sol_log")

    for keyword in [
        "Pubkey",
        "AccountInfo",
        "ProgramResult",
        "ProgramError",
        "Instruction",
        "AccountMeta",
        "next_account_info",
        "invoke",
        "invoke_signed",
    ]:
        if re.search(rf"\b{keyword}\b", content_without_imports):
            found_identifiers.add(keyword)

    if entrypoint_name in ("pinocchio", "pinocchio-std"):
        content_without_imports = re.sub(r"\bpinocchio::msg!", "msg!", content_without_imports)
        content_without_imports = re.sub(r"\bpinocchio::log::sol_log", "sol_log", content_without_imports)
        content_without_imports = re.sub(r"\bpinocchio::pubkey::Pubkey", "Pubkey", content_without_imports)
        content_without_imports = re.sub(r"\bpinocchio::account_info::AccountInfo", "AccountInfo", content_without_imports)
        content_without_imports = re.sub(r"\bpinocchio::program_error::ProgramError", "ProgramError", content_without_imports)
        content_without_imports = re.sub(r"\bpinocchio::ProgramResult", "ProgramResult", content_without_imports)

        found_identifiers.update(["Pubkey", "AccountInfo", "ProgramResult", "ProgramError"])
        found_identifiers.discard("no_allocator")
        found_identifiers.discard("nostd_panic_handler")

    new_imports = ""
    if had_original_imports and found_identifiers:
        new_imports = _generate_target_imports(found_identifiers, entrypoint_name)

    # insert import block after initial #![…] attrs
    final_lines = content_without_imports.splitlines()
    insert_idx = 0
    for idx, ln in enumerate(final_lines):
        if ln.strip().startswith('#!['):
            insert_idx = idx + 1
        elif ln.strip() and not ln.strip().startswith('//'):
            break

    if new_imports:
        final_lines.insert(insert_idx, "")
        final_lines.insert(insert_idx + 1, new_imports)
        final_lines.insert(insert_idx + 2, "")

    if 'pub mod instruction' in content_without_imports:
        patched = re.sub(
            r'(pub\s+mod\s+instruction\s*{\s*)(?![^}]*use\s+crate::processor;)',
            r'\1use crate::processor;\n',
            '\n'.join(final_lines),
            count=1,
            flags=re.DOTALL,
        )
        return patched

    # Remove any use line that imports these macros – they are not needed and
    # break compilation because the macros are not re-exported as items.
    modified_content = re.sub(r"^\s*use\s+[^;]*\bno_allocator\b[^;]*;\s*\n?", "", content_without_imports, flags=re.MULTILINE)
    modified_content = re.sub(r"^\s*use\s+[^;]*\bnostd_panic_handler\b[^;]*;\s*\n?", "", content_without_imports, flags=re.MULTILINE)

    return '\n'.join(final_lines)


def _replace_imports_with_target_imports(content: str, entrypoint_name: str) -> str:
    """DEPRECATED: Use _strip_imports_and_generate_clean_imports instead."""
    return _strip_imports_and_generate_clean_imports(content, entrypoint_name)


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

def _strip_duplicate_bench_modules(src: str) -> str:
    """Remove duplicate *_benches modules that can appear after cfg stripping."""
    import re
    pattern = re.compile(r"pub mod (\w+_benches)\s*{", re.MULTILINE)
    matches = list(pattern.finditer(src))
    if not matches:
        return src

    to_remove: list[tuple[int, int]] = []
    seen: set[str] = set()
    for m in matches:
        name = m.group(1)
        if name in seen:
            # Check if the duplicate has a cfg attribute directly above it; if so, keep both copies.
            # We look back a few lines to see if there's a cfg attribute.
            line_start = src.rfind('\n', 0, m.start()) + 1
            prev_segment = src[max(0, line_start - 120): line_start]  # up to ~4 lines back
            if re.search(r"#\s*\[\s*cfg", prev_segment):
                # Distinct feature-gated copy; keep it.
                continue

            # Otherwise treat as redundant and remove
            brace_lvl = 1
            idx = m.end()
            while idx < len(src):
                if src[idx] == '{':
                    brace_lvl += 1
                elif src[idx] == '}':
                    brace_lvl -= 1
                    if brace_lvl == 0:
                        idx += 1  # include closing brace
                        break
                idx += 1
            to_remove.append((m.start(), idx))
        else:
            seen.add(name)
    # remove from back to front so indices stay valid
    for start, end in sorted(to_remove, key=lambda t: -t[0]):
        src = src[:start] + src[end:]
    return src


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
# Bracing helpers
# ---------------------------------------------------------------------------

def _close_unclosed_top_modules(content: str) -> str:
    """Ensure each top-level `pub mod XYZ {{` declaration has a matching closing brace.

    We only track braces that appear at column 0 (i.e. no leading whitespace)
    so that braces within function bodies, impl blocks, etc. do **not** affect
    our module-level balance accounting.
    """

    out_lines: list[str] = []
    depth = 0  # number of currently open top-level modules

    mod_start_re = re.compile(r"^pub\s+mod\s+\w+\s*{\s*$")
    closing_brace_re = re.compile(r"^\s*}\s*$")

    for line in content.splitlines():
        stripped = line.lstrip()

        # If a new module starts while one is already open, close the previous
        # one first.
        if mod_start_re.match(stripped) and depth == 1:
            out_lines.append("}")
            depth -= 1

        out_lines.append(line)

        # Update depth counters *after* writing the current line so that the
        # opening brace we just saw isn't immediately cancelled out.
        if mod_start_re.match(stripped):
            depth += 1
        elif closing_brace_re.match(stripped) and depth > 0:
            depth -= 1

    # Close any unbalanced modules at EOF.
    while depth > 0:
        out_lines.append("}")
        depth -= 1

    return "\n".join(out_lines) + "\n"


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

                # After the manual fixes, drop any remaining no_std-gated module blocks – they are
                # unused when compiling for std entrypoints and can cause duplicate definitions.
                modified_content = re.sub(
                    r"#\[cfg\(all\(feature = \"no_std\"\)\)\]\s*pub mod \w+_benches\s*\{[^}]*\}\s*",
                    "",
                    modified_content,
                    flags=re.MULTILINE | re.DOTALL,
                )
                
                # Remove duplicate bench modules that may remain after cfg stripping
                modified_content = _strip_duplicate_bench_modules(modified_content)
            else:
                # Replace all Solana imports with clean, target-specific imports
                modified_content = _strip_imports_and_generate_clean_imports(modified_content, entrypoint_name)
            
            # We keep all feature-gated blocks intact and rely on Cargo feature selection.
            # (Previously we tried to strip non-active blocks which caused brace mismatches
            #  and duplicate-definition errors when the cfg conditions changed. The crates
            #  now provide proper `no_std` / `std` gating, so we no longer remove or edit
            #  these sections here.)

            # Post-processing fixes
            modified_content = _strip_duplicate_bench_modules(modified_content)
            modified_content = _ensure_use_super_in_modules(modified_content)
            # Final brace-balance pass removed – brace integrity is preserved by
            # improved import stripping logic.

            # Add benchmark module alias
            benches_alias_map = {
                "pinocchio": "pinocchio_benches",
                "pinocchio-std": "pinocchio_std_benches",
                "solana-program": "solana_benches",
                "solana-program-mono": "solana_program_mono_benches",
                "solana-nostd-entrypoint": "nostd_entrypoint_benches",
            }
            benches_alias = benches_alias_map.get(entrypoint_name, "solana_benches")
            if benches_alias not in modified_content:
                # Prefer the module that actually compiles for the current target:  
                #   • pinocchio / nostd-entrypoint → `nostd_benches`  
                #   • std entrypoints             → `std_benches` (or first seen)

                preferred_module_name = None
                if entrypoint_name in ("pinocchio", "solana-nostd-entrypoint"):
                    # Look explicitly for nostd_benches first
                    m_pref = re.search(r"pub mod (nostd_benches)\s*\{", modified_content)
                    if m_pref:
                        preferred_module_name = m_pref.group(1)

                # Fallback: first benches module in file
                if preferred_module_name is None:
                    m_generic = re.search(r"pub mod (\w+_benches)\s*\{", modified_content)
                    if m_generic:
                        preferred_module_name = m_generic.group(1)

                if preferred_module_name:
                    orig_benches = preferred_module_name
                    alias_line = f"\npub use {orig_benches} as {benches_alias};\n"
                    if alias_line.strip() not in modified_content:
                        modified_content = modified_content.rstrip() + alias_line

            # Entrypoint-specific fixes
            if entrypoint_name == "pinocchio":
                # For non-lib.rs files, remove any macro calls and imports that might have been added
                lines = modified_content.splitlines()
                filtered_lines = []
                for line in lines:
                    stripped = line.strip()
                    if (stripped == "no_allocator!();" or 
                        stripped == "nostd_panic_handler!();" or
                        stripped == "use pinocchio::{no_allocator, nostd_panic_handler};"):
                        continue
                    filtered_lines.append(line)
                modified_content = '\n'.join(filtered_lines)
                
                # Fix pinocchio-specific issues
                modified_content = modified_content.replace("PINOCCHIO_SYSTEM_PROGRAM_ID", "Pubkey::default()")
                # Fix CpiAccount conversion - use .into() instead of removing it
                modified_content = re.sub(r"CpiAccount::from\(\s*&?(\w+)\s*\)", r"\1.into()", modified_content)
                
            elif entrypoint_name == "solana-nostd-entrypoint":
                # Fix nostd-specific issues
                modified_content = re.sub(r"&?\s*PINOCCHIO_SYSTEM_PROGRAM_ID", "Pubkey::default()", modified_content)
                modified_content = modified_content.replace("invoke_signed_unchecked", "invoke_signed")
                # Normalize *foo.key() usage and handle Into<> mismatch
                modified_content = re.sub(r"\*\s*([A-Za-z_][A-Za-z0-9_]*)\.key\b", r"*\1.key()", modified_content)

                # Replace (*foo.key()).into() with Pubkey::new_from_array(foo.key().to_bytes())
                modified_content = re.sub(
                    r"\(\*\s*([A-Za-z_][A-Za-z0-9_]*)\.key\(\)\)\.into\(\)",
                    r"Pubkey::new_from_array(\1.key().to_bytes())",
                    modified_content,
                )
                # Also replace standalone *foo.key() in AccountMeta::new args
                modified_content = re.sub(
                    r"\*\s*([A-Za-z_][A-Za-z0-9_]*)\.key\(\)",
                    r"Pubkey::new_from_array(\1.key().to_bytes())",
                    modified_content,
                )

                # Update AccountMeta helpers to use the new Pubkey constructor
                modified_content = re.sub(
                    r"AccountMeta::writable_signer\(\s*([A-Za-z_][A-Za-z0-9_]*)\.key\(\)\s*\)",
                    r"AccountMeta::new(Pubkey::new_from_array(\1.key().to_bytes()), true)",
                    modified_content,
                )
                
                # Convert AccountMeta::new(foo.key(), true) to use Pubkey constructor
                modified_content = re.sub(
                    r"AccountMeta::new\(\s*([A-Za-z_][A-Za-z0-9_]*)\.key\(\)\s*,\s*true\s*\)",
                    r"AccountMeta::new(Pubkey::new_from_array(\1.key().to_bytes()), true)",
                    modified_content,
                )

                modified_content = re.sub(r"accounts:\s*&([A-Za-z_][A-Za-z0-9_]*)", r"accounts: \1.to_vec()", modified_content)
                modified_content = re.sub(r"data:\s*&([A-Za-z_][A-Za-z0-9_]*)", r"data: \1.to_vec()", modified_content)
                modified_content = re.sub(r"CpiAccount::from\(\s*([^)]+)\s*\)", r"\1.clone()", modified_content)
                modified_content = re.sub(r"let accounts_for_invoke: \[AccountInfo; 2\] = \[([A-Za-z0-9_]+), ([A-Za-z0-9_]+)\];", r"let accounts_for_invoke = accounts;", modified_content)
                modified_content = re.sub(r"unsafe \{ core::mem::transmute\(&accounts_for_invoke\[\.\.\]\) \}", r"accounts", modified_content)
                modified_content = re.sub(r"invoke_signed\(([^,]+),\s*&accounts_for_invoke,\s*&\[\]\)", r"invoke_signed(\1, accounts, &[])", modified_content)
                modified_content = re.sub(r"invoke\(([^,]+),\s*&accounts_for_invoke,\s*&\[\]\)", r"invoke(\1, accounts, &[])", modified_content)

                # Direct string replacements for any previously injected helper that still uses transmute
                modified_content = modified_content.replace(
                    "unsafe { invoke_signed(&ix, core::mem::transmute(&[funder_account_info, new_account_info]), &[]); }",
                    "unsafe { solana_nostd_entrypoint::cpi::create_account_unchecked(funder_account_info, new_account_info, lamports, space, program_id)?; }",
                )
                modified_content = modified_content.replace(
                    "unsafe { invoke(&ix, core::mem::transmute(&[funder_account_info, new_account_info]), &[]); }",
                    "unsafe { solana_nostd_entrypoint::cpi::create_account_unchecked(funder_account_info, new_account_info, lamports, space, program_id)?; }",
                )

            elif entrypoint_name in ("solana-program", "solana-program-mono", "pinocchio-std"):
                # Fix AccountMeta for solana entrypoints
                modified_content = re.sub(r"AccountMeta::writable_signer\(\s*([A-Za-z_][A-Za-z0-9_]*)\.key\(\)\s*\)", r"AccountMeta::new((*\1.key()).into(), true)", modified_content)

                # Strip Pinocchio-only allocator / panic macros that are invalid for std entrypoints
                modified_content = re.sub(r"^\s*no_allocator!\(\);\s*\n?", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^\s*nostd_panic_handler!\(\);\s*\n?", "", modified_content, flags=re.MULTILINE)
                # Also remove any lingering use statements importing those macros
                modified_content = re.sub(r"^\s*use\s+[^;]*\bno_allocator\b[^;]*;\s*\n?", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^\s*use\s+[^;]*\bnostd_panic_handler\b[^;]*;\s*\n?", "", modified_content, flags=re.MULTILINE)

                # pinocchio-std needs `alloc` crate and vec! macro when we are compiling with
                # `#![no_std]` on-chain. Inject the crate import once per file and rewrite
                # `std::vec!` / `vec::vec!` to `alloc::vec!`.
                if entrypoint_name == "pinocchio-std":
                    if "extern crate alloc" not in modified_content:
                        # insert after the last #![...] inner attribute
                        lines = modified_content.splitlines()
                        insert_at = 0
                        for idx, ln in enumerate(lines):
                            if ln.strip().startswith("#!["):
                                insert_at = idx + 1
                        lines.insert(insert_at, "extern crate alloc;")
                        modified_content = "\n".join(lines)

                    # Replace vec macro paths
                    modified_content = modified_content.replace("std::vec!", "alloc::vec!")
                    modified_content = modified_content.replace("vec::vec!", "alloc::vec!")

                    # Ensure black_box import exists if the symbol is used
                    if "black_box(" in modified_content and "use core::hint::black_box;" not in modified_content:
                        # insert after other use lines / attributes
                        lines = modified_content.splitlines()
                        insert_at = 0
                        for idx, ln in enumerate(lines):
                            if ln.strip().startswith("use ") or ln.strip().startswith("#!["):
                                insert_at = idx + 1
                        lines.insert(insert_at, "use core::hint::black_box;")
                        modified_content = "\n".join(lines)

            # Replace qualified usage patterns
            modified_content = _replace_qualified_usage_patterns(modified_content, entrypoint_name)

            # Remove NoStdAccountInfo as CpiAccount alias import
            modified_content = re.sub(r",\s*NoStdAccountInfo\s+as\s+CpiAccount", "", modified_content)

            # Fix invoke calls with transmute wrapper
            if entrypoint_name == "solana-nostd-entrypoint":
                modified_content = re.sub(
                    r"invoke_signed\(&ix,\s*&?\[funder_account_info\.clone\(\),\s*new_account_info\.clone\(\)\],\s*&\[\]\)",
                    r"unsafe { invoke_unchecked(core::mem::transmute(&ix), &[funder_account_info.clone(), new_account_info.clone()])?; }",
                    modified_content
                )
                modified_content = re.sub(
                    r"invoke\(&ix,\s*&?\[funder_account_info\.clone\(\),\s*new_account_info\.clone\(\)\],\s*&\[\]\)",
                    r"unsafe { invoke_unchecked(core::mem::transmute(&ix), &[funder_account_info.clone(), new_account_info.clone()])?; }",
                    modified_content
                )

                # Replace any transmute of accounts slice with slice_invoke_signed as well
                modified_content = re.sub(
                    r"unsafe \{\s*invoke_signed\(&ix,\s*unsafe \{ core::mem::transmute\(&accounts\[\.\.2?\]\) \},\s*&\[\]\)\s*;?\s*\}",
                    r"unsafe { invoke_unchecked(core::mem::transmute(&ix), &[funder_account_info.clone(), new_account_info.clone()])?; }",
                    modified_content,
                )
                modified_content = re.sub(
                    r"unsafe \{\s*invoke\(&ix,\s*unsafe \{ core::mem::transmute\(&accounts\[\.\.2?\]\) \},\s*&\[\]\)\s*;?\s*\}",
                    r"unsafe { invoke_unchecked(core::mem::transmute(&ix), &[funder_account_info.clone(), new_account_info.clone()])?; }",
                    modified_content,
                )

            # Remove leftover CpiAccount comment and broken array line
            if entrypoint_name == "solana-nostd-entrypoint":
                modified_content = re.sub(r"^\s*//.*CpiAccount.*\n", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^.*funder_cpi_account.*\n", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^.*new_cpi_account.*\n", "", modified_content, flags=re.MULTILINE)
                modified_content = re.sub(r"^.*\]\s*=\s*\[funder_cpi_account.*\n", "", modified_content, flags=re.MULTILINE)

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

    # Remove any remaining slice_invoke_signed import line globally
    modified_content = re.sub(r"^\s*use\s+solana_cpi::slice_invoke_signed;\s*\n", "", modified_content, flags=re.MULTILINE)

    return modified_content 