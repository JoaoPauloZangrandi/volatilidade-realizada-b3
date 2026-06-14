"""Utilidades compartilhadas pela pipeline."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import PROJECT_ROOT


def setup_logging(name: str = "vol_realizada_b3") -> logging.Logger:
    """Configura log em arquivo e no terminal sem duplicar handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_path = PROJECT_ROOT / "outputs" / "logs" / "pipeline.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def ticker_slug(ticker: str) -> str:
    """Converte ticker em nome seguro de arquivo."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", ticker).strip("_").lower()


def save_csv(dataframe: pd.DataFrame, path: Path) -> None:
    """Salva CSV de forma padronizada."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False, encoding="utf-8")


def write_text_targets(
    relative_name: str,
    content: str,
    obsidian_path: str | Path | None = None,
) -> list[Path]:
    """Escreve uma nota no espelho local e, quando possivel, no Obsidian."""
    targets = [PROJECT_ROOT / "obsidian_notes" / relative_name]
    if obsidian_path:
        targets.append(Path(obsidian_path) / relative_name)

    written: list[Path] = []
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(target)
        except OSError:
            continue
    return written


def first_existing(paths: Iterable[Path]) -> Path | None:
    """Retorna o primeiro caminho existente."""
    return next((path for path in paths if path.exists()), None)

