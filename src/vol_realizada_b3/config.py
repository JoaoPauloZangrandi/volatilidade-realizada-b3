"""Leitura da configuracao e caminhos do projeto."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Carrega o YAML de configuracao."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Configuracao invalida em {config_path}")
    return config


def ticker_groups(config: dict[str, Any]) -> dict[str, str]:
    """Retorna o grupo de cada ticker configurado."""
    groups: dict[str, str] = {}
    for ticker in config["tickers"]["core_liquid"]:
        groups[ticker] = "core_liquid"
    for ticker in config["tickers"]["high_vol_growth_candidates"]:
        groups[ticker] = "high_vol_growth_candidate"
    return groups


def configured_tickers(config: dict[str, Any]) -> list[str]:
    """Retorna todos os tickers, preservando a ordem do YAML."""
    return [
        *config["tickers"]["core_liquid"],
        *config["tickers"]["high_vol_growth_candidates"],
    ]


def ensure_project_directories(root: Path = PROJECT_ROOT) -> None:
    """Cria os diretorios usados pela pipeline."""
    relative_paths = [
        "data/raw",
        "data/interim",
        "data/processed",
        "data/manual",
        "outputs/figures",
        "outputs/tables",
        "outputs/slides",
        "outputs/report",
        "outputs/logs",
        "report",
        "slides",
        "obsidian_notes",
    ]
    for relative_path in relative_paths:
        (root / relative_path).mkdir(parents=True, exist_ok=True)

