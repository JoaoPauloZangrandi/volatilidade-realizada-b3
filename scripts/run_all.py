"""Executa a pipeline completa de ponta a ponta."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from _common import ROOT  # noqa: F401

from vol_realizada_b3.config import ensure_project_directories, load_config
from vol_realizada_b3.data_cleaning import run_cleaning
from vol_realizada_b3.data_download import run_download
from vol_realizada_b3.event_analysis import run_event_analysis
from vol_realizada_b3.garch_models import run_garch_models
from vol_realizada_b3.plots import run_plots
from vol_realizada_b3.realized_measures import run_realized_measures
from vol_realizada_b3.report_writer import run_report_writer
from vol_realizada_b3.sample_selection import run_sample_selection
from vol_realizada_b3.slides_builder import run_slides_builder
from vol_realizada_b3.tables import run_tables
from vol_realizada_b3.utils import setup_logging


LOGGER = setup_logging("pipeline")


def _stage(name: str, function: Callable[..., Any], config: dict[str, Any]) -> Any:
    start = time.perf_counter()
    LOGGER.info("INICIO | %s", name)
    result = function(config)
    LOGGER.info("FIM | %s | %.1fs", name, time.perf_counter() - start)
    return result


def main() -> None:
    """Executa todas as etapas na ordem metodologica."""
    ensure_project_directories()
    config = load_config()
    _stage("01 download", run_download, config)
    _stage("02 limpeza e sincronizacao", run_cleaning, config)
    coverage, selected = _stage(
        "03 selecao da amostra",
        run_sample_selection,
        config,
    )
    if selected.empty:
        excluded = coverage[["ticker", "razao_exclusao"]].to_dict("records")
        raise RuntimeError(
            f"Nenhum ticker passou aos criterios de qualidade: {excluded}"
        )
    _stage("04 medidas realizadas e jumps", run_realized_measures, config)
    _stage("05 GARCH", run_garch_models, config)
    _stage("06 eventos", run_event_analysis, config)
    _stage("07 tabelas", run_tables, config)
    _stage("07 figuras", run_plots, config)
    _stage("08 relatorio e notas", run_report_writer, config)
    _stage("09 slides", run_slides_builder, config)
    LOGGER.info("PIPELINE CONCLUIDA | %s", ROOT)


if __name__ == "__main__":
    main()

