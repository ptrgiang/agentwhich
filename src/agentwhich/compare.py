from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model import ResolutionResult, is_active


@dataclass(slots=True)
class Comparison:
    results: list[ResolutionResult]
    by_agent_only: dict[str, list[Path]]
    shared_paths: list[Path]
    duplicate_hashes: dict[str, list[tuple[str, Path]]]

    @property
    def divergent(self) -> bool:
        active_sets = [{layer.path for layer in result.layers if is_active(layer)} for result in self.results]
        return any(items != active_sets[0] for items in active_sets[1:]) if active_sets else False


def compare_results(results: list[ResolutionResult]) -> Comparison:
    active: dict[str, set[Path]] = {
        result.agent: {layer.path for layer in result.layers if is_active(layer)} for result in results
    }
    all_paths = set().union(*active.values()) if active else set()
    shared = sorted(path for path in all_paths if all(path in paths for paths in active.values()))
    by_agent_only = {
        agent: sorted(path for path in paths if sum(path in other for other in active.values()) == 1)
        for agent, paths in active.items()
    }

    hashes: dict[str, list[tuple[str, Path]]] = {}
    for result in results:
        for item in result.layers:
            if item.sha256 and is_active(item):
                hashes.setdefault(item.sha256, []).append((result.agent, item.path))
    duplicate_hashes = {digest: items for digest, items in hashes.items() if len({agent for agent, _ in items}) > 1}
    return Comparison(
        results=results,
        by_agent_only=by_agent_only,
        shared_paths=shared,
        duplicate_hashes=duplicate_hashes,
    )
