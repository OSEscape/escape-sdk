"""Dijkstra implementation for CSR graph format via Rust native extension."""

from __future__ import annotations

from escape.pathfinding._native import dijkstra_csr as _dijkstra_csr
from escape.pathfinding._native import dijkstra_csr_multi_target as _dijkstra_csr_multi_target
