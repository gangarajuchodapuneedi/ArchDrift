"""Architecture configuration loader and validator.

This module loads and validates architecture configuration files:
- module_map.json: Maps file paths to modules
- allowed_rules.json: Defines allowed dependencies between modules
- exceptions.json: Defines temporary exceptions to rules
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class ModuleSpec:
    """Specification for a module with its file path roots."""

    id: str
    roots: list[str]


@dataclass
class AllowedEdge:
    """Allowed dependency edge between modules."""

    from_module: str
    to_module: str


@dataclass
class ExceptionEdge:
    """Exception to dependency rules."""

    from_module: str
    to_module: str
    reason: str
    owner: str
    expires_on: Optional[date] = None


@dataclass
class ArchitectureConfig:
    """Complete architecture configuration."""

    version: str
    unmapped_module_id: str
    modules: list[ModuleSpec]
    deny_by_default: bool
    allowed_edges: list[AllowedEdge]
    exceptions: list[ExceptionEdge]


def _get_default_config_dir() -> Path:
    """Get the default architecture config directory."""
    backend_dir = Path(__file__).resolve().parents[1]
    return backend_dir / "architecture"


def _load_json_file(file_path: Path, file_name: str) -> dict:
    """Load and parse a JSON file.

    Args:
        file_path: Path to the JSON file.
        file_name: Name of the file (for error messages).

    Returns:
        Parsed JSON dictionary.

    Raises:
        ValueError: If file is missing or contains invalid JSON.
    """
    if not file_path.exists():
        raise ValueError(
            f"Missing configuration file '{file_name}' at expected path: {file_path}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in '{file_name}': {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e


def _validate_module_map(data: dict, file_name: str) -> tuple[str, str, list[ModuleSpec]]:
    """Validate and parse module_map.json structure.

    Args:
        data: Parsed JSON dictionary.
        file_name: Name of the file (for error messages).

    Returns:
        Tuple of (version, unmapped_module_id, modules).

    Raises:
        ValueError: If structure is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError(f"'{file_name}': root must be an object, got {type(data).__name__}")

    # Validate version
    if "version" not in data:
        raise ValueError(f"'{file_name}': missing required key 'version'")
    if not isinstance(data["version"], str):
        raise ValueError(
            f"'{file_name}': 'version' must be a string, got {type(data['version']).__name__}"
        )
    version = data["version"]

    # Validate unmapped_module_id
    if "unmapped_module_id" not in data:
        raise ValueError(f"'{file_name}': missing required key 'unmapped_module_id'")
    if not isinstance(data["unmapped_module_id"], str):
        raise ValueError(
            f"'{file_name}': 'unmapped_module_id' must be a string, got {type(data['unmapped_module_id']).__name__}"
        )
    unmapped_module_id = data["unmapped_module_id"]
    if not unmapped_module_id:
        raise ValueError(f"'{file_name}': 'unmapped_module_id' must be non-empty")

    # Validate modules
    if "modules" not in data:
        raise ValueError(f"'{file_name}': missing required key 'modules'")
    if not isinstance(data["modules"], list):
        raise ValueError(
            f"'{file_name}': 'modules' must be a list, got {type(data['modules']).__name__}"
        )

    # Parse modules
    modules: list[ModuleSpec] = []
    module_ids: set[str] = set()
    for i, module_data in enumerate(data["modules"]):
        if not isinstance(module_data, dict):
            raise ValueError(
                f"'{file_name}': 'modules'[{i}] must be an object, got {type(module_data).__name__}"
            )

        if "id" not in module_data:
            raise ValueError(f"'{file_name}': 'modules'[{i}] missing required key 'id'")
        if not isinstance(module_data["id"], str):
            raise ValueError(
                f"'{file_name}': 'modules'[{i}]['id'] must be a string, got {type(module_data['id']).__name__}"
            )
        module_id = module_data["id"]
        if not module_id:
            raise ValueError(f"'{file_name}': 'modules'[{i}]['id'] must be non-empty")

        if module_id in module_ids:
            raise ValueError(
                f"'{file_name}': duplicate module id '{module_id}' in 'modules' list"
            )
        module_ids.add(module_id)

        if "roots" not in module_data:
            raise ValueError(f"'{file_name}': 'modules'[{i}] missing required key 'roots'")
        if not isinstance(module_data["roots"], list):
            raise ValueError(
                f"'{file_name}': 'modules'[{i}]['roots'] must be a list, got {type(module_data['roots']).__name__}"
            )

        roots: list[str] = []
        for j, root in enumerate(module_data["roots"]):
            if not isinstance(root, str):
                raise ValueError(
                    f"'{file_name}': 'modules'[{i}]['roots'][{j}] must be a string, got {type(root).__name__}"
                )
            if not root:
                raise ValueError(f"'{file_name}': 'modules'[{i}]['roots'][{j}] must be non-empty")
            roots.append(root)

        modules.append(ModuleSpec(id=module_id, roots=roots))

    return version, unmapped_module_id, modules


def _validate_allowed_rules(data: dict, file_name: str) -> tuple[str, bool, list[AllowedEdge]]:
    """Validate and parse allowed_rules.json structure.

    Args:
        data: Parsed JSON dictionary.
        file_name: Name of the file (for error messages).

    Returns:
        Tuple of (version, deny_by_default, allowed_edges).

    Raises:
        ValueError: If structure is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError(f"'{file_name}': root must be an object, got {type(data).__name__}")

    # Validate version
    if "version" not in data:
        raise ValueError(f"'{file_name}': missing required key 'version'")
    if not isinstance(data["version"], str):
        raise ValueError(
            f"'{file_name}': 'version' must be a string, got {type(data['version']).__name__}"
        )
    version = data["version"]

    # Validate deny_by_default
    if "deny_by_default" not in data:
        raise ValueError(f"'{file_name}': missing required key 'deny_by_default'")
    if not isinstance(data["deny_by_default"], bool):
        raise ValueError(
            f"'{file_name}': 'deny_by_default' must be a boolean, got {type(data['deny_by_default']).__name__}"
        )
    deny_by_default = data["deny_by_default"]

    # Validate allowed_edges
    if "allowed_edges" not in data:
        raise ValueError(f"'{file_name}': missing required key 'allowed_edges'")
    if not isinstance(data["allowed_edges"], list):
        raise ValueError(
            f"'{file_name}': 'allowed_edges' must be a list, got {type(data['allowed_edges']).__name__}"
        )

    # Parse allowed_edges
    allowed_edges: list[AllowedEdge] = []
    for i, edge_data in enumerate(data["allowed_edges"]):
        if not isinstance(edge_data, dict):
            raise ValueError(
                f"'{file_name}': 'allowed_edges'[{i}] must be an object, got {type(edge_data).__name__}"
            )

        if "from" not in edge_data:
            raise ValueError(f"'{file_name}': 'allowed_edges'[{i}] missing required key 'from'")
        if not isinstance(edge_data["from"], str):
            raise ValueError(
                f"'{file_name}': 'allowed_edges'[{i}]['from'] must be a string, got {type(edge_data['from']).__name__}"
            )
        from_module = edge_data["from"]
        if not from_module:
            raise ValueError(f"'{file_name}': 'allowed_edges'[{i}]['from'] must be non-empty")

        if "to" not in edge_data:
            raise ValueError(f"'{file_name}': 'allowed_edges'[{i}] missing required key 'to'")
        if not isinstance(edge_data["to"], str):
            raise ValueError(
                f"'{file_name}': 'allowed_edges'[{i}]['to'] must be a string, got {type(edge_data['to']).__name__}"
            )
        to_module = edge_data["to"]
        if not to_module:
            raise ValueError(f"'{file_name}': 'allowed_edges'[{i}]['to'] must be non-empty")

        allowed_edges.append(AllowedEdge(from_module=from_module, to_module=to_module))

    return version, deny_by_default, allowed_edges


def _validate_exceptions(data: dict, file_name: str) -> tuple[str, list[ExceptionEdge]]:
    """Validate and parse exceptions.json structure.

    Args:
        data: Parsed JSON dictionary.
        file_name: Name of the file (for error messages).

    Returns:
        Tuple of (version, exceptions).

    Raises:
        ValueError: If structure is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError(f"'{file_name}': root must be an object, got {type(data).__name__}")

    # Validate version
    if "version" not in data:
        raise ValueError(f"'{file_name}': missing required key 'version'")
    if not isinstance(data["version"], str):
        raise ValueError(
            f"'{file_name}': 'version' must be a string, got {type(data['version']).__name__}"
        )
    version = data["version"]

    # Validate exceptions
    if "exceptions" not in data:
        raise ValueError(f"'{file_name}': missing required key 'exceptions'")
    if not isinstance(data["exceptions"], list):
        raise ValueError(
            f"'{file_name}': 'exceptions' must be a list, got {type(data['exceptions']).__name__}"
        )

    # Parse exceptions
    exceptions: list[ExceptionEdge] = []
    for i, exc_data in enumerate(data["exceptions"]):
        if not isinstance(exc_data, dict):
            raise ValueError(
                f"'{file_name}': 'exceptions'[{i}] must be an object, got {type(exc_data).__name__}"
            )

        if "from" not in exc_data:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}] missing required key 'from'")
        if not isinstance(exc_data["from"], str):
            raise ValueError(
                f"'{file_name}': 'exceptions'[{i}]['from'] must be a string, got {type(exc_data['from']).__name__}"
            )
        from_module = exc_data["from"]
        if not from_module:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}]['from'] must be non-empty")

        if "to" not in exc_data:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}] missing required key 'to'")
        if not isinstance(exc_data["to"], str):
            raise ValueError(
                f"'{file_name}': 'exceptions'[{i}]['to'] must be a string, got {type(exc_data['to']).__name__}"
            )
        to_module = exc_data["to"]
        if not to_module:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}]['to'] must be non-empty")

        if "reason" not in exc_data:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}] missing required key 'reason'")
        if not isinstance(exc_data["reason"], str):
            raise ValueError(
                f"'{file_name}': 'exceptions'[{i}]['reason'] must be a string, got {type(exc_data['reason']).__name__}"
            )
        reason = exc_data["reason"]
        if not reason:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}]['reason'] must be non-empty")

        if "owner" not in exc_data:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}] missing required key 'owner'")
        if not isinstance(exc_data["owner"], str):
            raise ValueError(
                f"'{file_name}': 'exceptions'[{i}]['owner'] must be a string, got {type(exc_data['owner']).__name__}"
            )
        owner = exc_data["owner"]
        if not owner:
            raise ValueError(f"'{file_name}': 'exceptions'[{i}]['owner'] must be non-empty")

        # Validate expires_on (optional)
        expires_on: Optional[date] = None
        if "expires_on" in exc_data:
            if exc_data["expires_on"] is None:
                expires_on = None
            elif not isinstance(exc_data["expires_on"], str):
                raise ValueError(
                    f"'{file_name}': 'exceptions'[{i}]['expires_on'] must be a string or null, got {type(exc_data['expires_on']).__name__}"
                )
            else:
                try:
                    expires_on = date.fromisoformat(exc_data["expires_on"])
                except ValueError as e:
                    raise ValueError(
                        f"'{file_name}': 'exceptions'[{i}]['expires_on'] must be a valid ISO date (YYYY-MM-DD), got '{exc_data['expires_on']}': {e}"
                    ) from e

        exceptions.append(
            ExceptionEdge(
                from_module=from_module,
                to_module=to_module,
                reason=reason,
                owner=owner,
                expires_on=expires_on,
            )
        )

    return version, exceptions


def _cross_validate_module_ids(
    unmapped_module_id: str,
    modules: list[ModuleSpec],
    allowed_edges: list[AllowedEdge],
    exceptions: list[ExceptionEdge],
) -> None:
    """Cross-validate that module IDs in edges and exceptions reference known modules.

    Args:
        unmapped_module_id: The unmapped module ID.
        modules: List of module specifications.
        allowed_edges: List of allowed edges.
        exceptions: List of exception edges.

    Raises:
        ValueError: If any edge or exception references an unknown module ID.
    """
    if not modules:
        # Skip cross-validation if modules list is empty
        return

    known_module_ids = {module.id for module in modules}
    known_module_ids.add(unmapped_module_id)

    # Validate allowed_edges
    for i, edge in enumerate(allowed_edges):
        if edge.from_module not in known_module_ids:
            raise ValueError(
                f"'allowed_rules.json': 'allowed_edges'[{i}]['from'] references unknown module '{edge.from_module}'. "
                f"Known modules: {sorted(known_module_ids)}"
            )
        if edge.to_module not in known_module_ids:
            raise ValueError(
                f"'allowed_rules.json': 'allowed_edges'[{i}]['to'] references unknown module '{edge.to_module}'. "
                f"Known modules: {sorted(known_module_ids)}"
            )

    # Validate exceptions
    for i, exc in enumerate(exceptions):
        if exc.from_module not in known_module_ids:
            raise ValueError(
                f"'exceptions.json': 'exceptions'[{i}]['from'] references unknown module '{exc.from_module}'. "
                f"Known modules: {sorted(known_module_ids)}"
            )
        if exc.to_module not in known_module_ids:
            raise ValueError(
                f"'exceptions.json': 'exceptions'[{i}]['to'] references unknown module '{exc.to_module}'. "
                f"Known modules: {sorted(known_module_ids)}"
            )


def load_architecture_config(config_dir: Optional[Path] = None) -> ArchitectureConfig:
    """Load and validate architecture configuration files.

    Args:
        config_dir: Optional directory containing config files. If None, uses default
            backend/architecture directory.

    Returns:
        ArchitectureConfig object with all loaded and validated data.

    Raises:
        ValueError: If any file is missing, contains invalid JSON, or has invalid structure.
    """
    if config_dir is None:
        config_dir = _get_default_config_dir()

    # Load module_map.json
    module_map_path = config_dir / "module_map.json"
    module_map_data = _load_json_file(module_map_path, "module_map.json")
    version, unmapped_module_id, modules = _validate_module_map(
        module_map_data, "module_map.json"
    )

    # Load allowed_rules.json
    allowed_rules_path = config_dir / "allowed_rules.json"
    allowed_rules_data = _load_json_file(allowed_rules_path, "allowed_rules.json")
    rules_version, deny_by_default, allowed_edges = _validate_allowed_rules(
        allowed_rules_data, "allowed_rules.json"
    )

    # Load exceptions.json
    exceptions_path = config_dir / "exceptions.json"
    exceptions_data = _load_json_file(exceptions_path, "exceptions.json")
    exc_version, exceptions = _validate_exceptions(exceptions_data, "exceptions.json")

    # Cross-validate module IDs
    _cross_validate_module_ids(unmapped_module_id, modules, allowed_edges, exceptions)

    # Use version from module_map (assuming all should match, but not enforcing for MT_02)
    return ArchitectureConfig(
        version=version,
        unmapped_module_id=unmapped_module_id,
        modules=modules,
        deny_by_default=deny_by_default,
        allowed_edges=allowed_edges,
        exceptions=exceptions,
    )

