"""Path to module ID mapper.

This module provides functions to map file paths to module IDs based on
architecture configuration module roots.
"""

from pathlib import Path

from utils.architecture_config import ArchitectureConfig


def normalize_repo_path(p: str | Path) -> str:
    """Normalize a repository path to a consistent format.

    Converts backslashes to forward slashes, strips leading "./" and "/",
    and collapses duplicate slashes.

    Args:
        p: Path string or Path object to normalize.

    Returns:
        Normalized path string with forward slashes.
    """
    # Convert Path to string if needed
    path_str = str(p)

    # Convert backslashes to forward slashes
    path_str = path_str.replace("\\", "/")

    # Strip leading "./" if present
    if path_str.startswith("./"):
        path_str = path_str[2:]

    # Strip leading "/" if present
    if path_str.startswith("/"):
        path_str = path_str[1:]

    # Collapse duplicate slashes
    while "//" in path_str:
        path_str = path_str.replace("//", "/")

    return path_str


def map_path_to_module_id(file_path: str | Path, module_map: ArchitectureConfig) -> str:
    """Map a file path to a module ID based on module roots.

    Matches the path against module roots, using the longest matching root
    (most specific match). If no match is found, returns the unmapped_module_id.

    Args:
        file_path: File path to map (string or Path).
        module_map: ArchitectureConfig containing modules and unmapped_module_id.

    Returns:
        Module ID string. Returns unmapped_module_id if no match found.

    Raises:
        ValueError: If a root is empty or invalid type.
    """
    # Normalize the input path
    normalized_path = normalize_repo_path(file_path)

    # If modules list is empty, return unmapped immediately
    if not module_map.modules:
        return module_map.unmapped_module_id

    # Track best match (longest root)
    best_match_module_id = None
    best_root_length = -1

    # Iterate through all modules and their roots
    for module in module_map.modules:
        for root in module.roots:
            # Validate root
            if not isinstance(root, str):
                raise ValueError(
                    f"Invalid root type in module '{module.id}': expected str, got {type(root).__name__}"
                )
            if not root:
                raise ValueError(f"Empty root string in module '{module.id}'")

            # Normalize root
            normalized_root = normalize_repo_path(root)

            # Check for match: exact match or prefix match
            if normalized_path == normalized_root:
                # Exact match
                root_length = len(normalized_root)
                if root_length > best_root_length:
                    best_match_module_id = module.id
                    best_root_length = root_length
            elif normalized_path.startswith(normalized_root + "/"):
                # Prefix match (path starts with root + "/")
                root_length = len(normalized_root)
                if root_length > best_root_length:
                    best_match_module_id = module.id
                    best_root_length = root_length

    # Return best match or unmapped
    return best_match_module_id if best_match_module_id is not None else module_map.unmapped_module_id

