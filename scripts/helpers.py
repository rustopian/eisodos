from __future__ import annotations

import pathlib
import toml
from typing import List

from console_utils import print_error, print_warning

# Resolve the project root based on this file's location (scripts/)
EISODOS_ROOT = pathlib.Path(__file__).parent.parent.resolve()
WORKSPACE_ROOT = EISODOS_ROOT

__all__ = [
    "discover_crates",
    "parse_function_path",
    "format_features",
    "replace_placeholders",
    "get_workspace_dependencies_block",
    "get_package_name_from_manifest",
]


# ---------------------------------------------------------------------------
# String / path helpers
# ---------------------------------------------------------------------------

def discover_crates(path: pathlib.Path) -> List[pathlib.Path]:
    """Return a list of crate directories that contain an *eisodos_benchmarks.toml* file.

    If *path* itself points to such a crate, a single-element list is returned.
    If *path* is a directory, its immediate children are scanned for crates.
    """
    path = path.resolve()

    if (path / "eisodos_benchmarks.toml").is_file():
        return [path]

    if path.is_dir():
        crates: List[pathlib.Path] = [
            subdir
            for subdir in path.iterdir()
            if subdir.is_dir() and (subdir / "eisodos_benchmarks.toml").is_file()
        ]
        return sorted(crates)

    return []


def parse_function_path(full_path: str):
    """Split a Rust-style path like ``crate::mod::func`` into (crate, module, func)."""
    try:
        parts = full_path.split("::")
        if len(parts) < 2:
            raise ValueError("Function path must include crate name and function name.")
        crate_name = parts[0]
        func_name = parts[-1]
        module_path = "::".join(parts[1:-1]) if len(parts) > 2 else ""
        return crate_name, module_path, func_name
    except Exception as exc:
        print_error(f"parsing function path '{full_path}': {exc}")
        return None, None, None


# ---------------------------------------------------------------------------
# Templating helpers
# ---------------------------------------------------------------------------

def format_features(features_list):
    if not features_list:
        return ""
    return ", ".join([f'"{feat}"' for feat in features_list])


def replace_placeholders(content: str, replacements: dict[str, str]):
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, str(value))
    return content


# ---------------------------------------------------------------------------
# Workspace-level helpers
# ---------------------------------------------------------------------------

def _format_toml_dict(data: dict) -> str:
    """Formats a flat dict into minimal inline TOML."""
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            items_str = ", ".join([f'{k} = "{v}"' for k, v in value.items()])
            lines.append(f"{key} = {{ {items_str} }}")
        elif isinstance(value, str):
            lines.append(f"{key} = \"{value}\"")
        else:
            lines.append(f"{key} = {value}")
    return "\n".join(lines)


def get_workspace_dependencies_block(dep_names):
    """Extract dependency definitions from the *workspace* Cargo.toml.*"""
    root_cargo_path = WORKSPACE_ROOT / "Cargo.toml"
    try:
        manifest = toml.loads(root_cargo_path.read_text("utf-8"))
        workspace_deps = manifest.get("workspace", {}).get("dependencies", {})

        deps_to_include = {}
        for name in dep_names:
            if name in workspace_deps:
                deps_to_include[name] = workspace_deps[name]
            else:
                print_warning(
                    f"Dependency '{name}' requested but not found in [workspace.dependencies] in {root_cargo_path}"
                )

        if not deps_to_include:
            return "[workspace.dependencies]"

        return "[workspace.dependencies]\n" + _format_toml_dict(deps_to_include)
    except FileNotFoundError:
        print_error(f"Workspace root Cargo.toml not found at {root_cargo_path}")
        return None
    except Exception as exc:
        print_error(f"reading or parsing workspace root Cargo.toml {root_cargo_path}: {exc}")
        return None


def get_package_name_from_manifest(crate_dir: pathlib.Path):
    manifest_path = crate_dir / "Cargo.toml"
    try:
        manifest = toml.loads(manifest_path.read_text("utf-8"))
        package_name = manifest.get("package", {}).get("name")
        if not package_name:
            print_error(f"Could not find [package].name in {manifest_path}")
            return None
        return package_name
    except FileNotFoundError:
        print_error(f"Manifest file not found at {manifest_path}")
        return None
    except Exception as exc:
        print_error(f"reading or parsing manifest {manifest_path}: {exc}")
        return None 