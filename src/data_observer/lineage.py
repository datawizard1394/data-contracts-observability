"""Lineage-manifest validation and graph traversal."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .io import read_json


class LineageError(ValueError):
    """Raised when the lineage manifest is malformed."""


def load_lineage(path: str | Path) -> dict[str, Any]:
    manifest = read_json(path)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise LineageError("'assets' must be a non-empty list")
    names = [asset.get("name") for asset in assets if isinstance(asset, dict)]
    if len(names) != len(assets) or any(not name for name in names):
        raise LineageError("Each lineage asset requires a non-empty name")
    if len(names) != len(set(names)):
        raise LineageError("Lineage asset names must be unique")

    known = set(names)
    for asset in assets:
        upstream = asset.get("upstream", [])
        if not isinstance(upstream, list):
            raise LineageError(f"{asset['name']}.upstream must be a list")
        unknown = set(upstream) - known
        if unknown:
            raise LineageError(
                f"{asset['name']} references unknown upstream assets: {sorted(unknown)}"
            )
    _assert_acyclic(assets)


def _assert_acyclic(assets: list[dict[str, Any]]) -> None:
    upstream = {asset["name"]: asset.get("upstream", []) for asset in assets}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise LineageError(f"Cycle detected at lineage asset: {name}")
        if name in visited:
            return
        visiting.add(name)
        for parent in upstream[name]:
            visit(parent)
        visiting.remove(name)
        visited.add(name)

    for asset_name in upstream:
        visit(asset_name)


def lineage_context(manifest: dict[str, Any], asset_name: str) -> dict[str, Any]:
    """Return direct and transitive lineage for one asset."""

    assets = {asset["name"]: asset for asset in manifest["assets"]}
    if asset_name not in assets:
        raise LineageError(f"Asset not found in manifest: {asset_name}")
    downstream_map: dict[str, list[str]] = defaultdict(list)
    for asset in assets.values():
        for parent in asset.get("upstream", []):
            downstream_map[parent].append(asset["name"])

    direct_upstream = sorted(assets[asset_name].get("upstream", []))
    direct_downstream = sorted(downstream_map.get(asset_name, []))
    return {
        "asset": assets[asset_name],
        "direct_upstream": direct_upstream,
        "direct_downstream": direct_downstream,
        "transitive_upstream": _walk(asset_name, {
            name: item.get("upstream", []) for name, item in assets.items()
        }),
        "transitive_downstream": _walk(asset_name, downstream_map),
    }


def _walk(start: str, adjacency: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    queue: deque[str] = deque(adjacency.get(start, []))
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        queue.extend(adjacency.get(current, []))
    return sorted(visited)
