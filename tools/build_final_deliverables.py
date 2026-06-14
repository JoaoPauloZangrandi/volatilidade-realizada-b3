"""Gera os dois arquivos autocontidos usados como entrega final."""

from __future__ import annotations

import ast
import base64
import io
import textwrap
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "vol_realizada_b3"
CODE_PATH = ROOT / "Código Final.py"
HTML_PATH = ROOT / "Relatório Final.html"


MODULE_ORDER = [
    "utils.py",
    "data_download.py",
    "data_cleaning.py",
    "sample_selection.py",
    "jumps.py",
    "realized_measures.py",
    "garch_models.py",
    "event_analysis.py",
    "tables.py",
    "plots.py",
    "slides_builder.py",
    "report_writer.py",
    "final_html.py",
]


def _snapshot_payload() -> str:
    """Compacta a configuracao, dados brutos e eventos para o script unico."""
    buffer = io.BytesIO()
    paths = [
        ROOT / "config" / "config.yaml",
        ROOT / "data" / "manual" / "events_earnings.csv",
        ROOT / "data" / "manual" / "README.md",
        *sorted((ROOT / "data" / "raw").glob("*.csv")),
    ]
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "\n".join(textwrap.wrap(encoded, width=120))


def _definitions(path: Path) -> str:
    """Extrai funcoes e classes sem imports relativos ou estado modular."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    chunks: list[str] = []
    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            chunks.append("\n".join(lines[node.lineno - 1 : node.end_lineno]))
    return "\n\n\n".join(chunks)


def _header(payload: str) -> str:
    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CÓDIGO FINAL — VOLATILIDADE REALIZADA COM DADOS INTRADIÁRIOS DA B3
=================================================================

Arquivo único e autocontido para avaliação e execução no Google Colab.

Conteúdo:
1. Snapshot comprimido dos dados intradiários reais usados na entrega.
2. Download opcional de uma nova janela via yfinance.
3. Limpeza, sincronização e retornos sem cruzar pregões.
4. Seleção objetiva da amostra.
5. RV, RVol, BV, TQ, JV e teste de jumps.
6. GARCH(1,1), eventos de earnings, tabelas e gráficos.
7. Relatório Markdown, Relatório Final HTML e PowerPoint.
8. Testes internos e ZIP de todos os resultados.

Google Colab:
    from google.colab import files
    files.upload()
    %run "Código Final.py"

Terminal:
    python "Código Final.py"
    python "Código Final.py" --refresh-data

Por padrão o script usa o snapshot incorporado, garantindo reprodutibilidade.
Com --refresh-data, tenta baixar uma nova janela de 60 dias/5 minutos.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import io
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time as time_module
import zipfile
from collections.abc import Callable, Iterable
from datetime import datetime, time
from math import ceil, gamma, pi, sqrt
from pathlib import Path
from typing import Any


REQUIRED_PACKAGES = {{
    "pandas": "pandas>=2.2,<3.0",
    "numpy": "numpy>=1.26,<3.0",
    "scipy": "scipy>=1.12,<2.0",
    "statsmodels": "statsmodels>=0.14,<1.0",
    "arch": "arch>=7.0,<9.0",
    "yfinance": "yfinance>=0.2.54,<1.0",
    "matplotlib": "matplotlib>=3.8,<4.0",
    "pptx": "python-pptx>=1.0,<2.0",
    "yaml": "PyYAML>=6.0,<7.0",
    "openpyxl": "openpyxl>=3.1,<4.0",
    "PIL": "Pillow>=9",
}}


def ensure_dependencies() -> None:
    missing = [
        package
        for module, package in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print("Instalando dependências ausentes:", ", ".join(missing))
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        )


ensure_dependencies()

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from scipy.stats import norm


PROJECT_ROOT = Path(
    os.environ.get(
        "VOL_B3_OUTPUT_DIR",
        str(Path.cwd() / "volatilidade_realizada_b3_entrega"),
    )
).resolve()

CONFIG: dict[str, Any] = {{
    "project": {{
        "title": "Volatilidade Realizada com Dados Intradiarios: Evidencias para Acoes da B3",
        "student_name": "Joao Paulo Zangrandi",
        "institution": "FGV EESP",
        "obsidian_path": "",
    }},
    "tickers": {{
        "core_liquid": [
            "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA",
            "B3SA3.SA", "WEGE3.SA", "ABEV3.SA", "TOTS3.SA",
        ],
        "high_vol_growth_candidates": [
            "LWSA3.SA", "MGLU3.SA", "BHIA3.SA", "CASH3.SA",
            "CVCB3.SA", "AZUL4.SA", "VIIA3.SA",
        ],
    }},
    "data": {{
        "source": "embedded_yfinance_snapshot",
        "period": "60d",
        "interval": "5m",
        "timezone": "America/Sao_Paulo",
        "market_open": "10:00",
        "market_close": "17:55",
        "resample_interval": "5min",
    }},
    "sample_selection": {{
        "min_valid_days": 30,
        "min_avg_candle_coverage": 0.70,
        "min_intraday_returns_per_day": 40,
        "max_stale_price_share": 0.50,
        "min_positive_volume_share": 0.10,
        "require_positive_prices": True,
    }},
    "volatility": {{
        "annualization_days": 252,
        "jump_test_alpha": 0.99,
        "min_intraday_obs_per_day": 40,
    }},
    "garch": {{
        "p": 1, "q": 1, "distribution": "normal",
        "min_daily_observations": 30,
    }},
    "event_analysis": {{
        "enabled": True, "event_window_days": [-1, 0, 1],
    }},
    "outputs": {{
        "save_figures": True, "save_tables": True,
        "build_report": True, "build_slides": True,
    }},
}}

STANDARD_COLUMNS = [
    "datetime", "ticker", "open", "high", "low", "close", "volume"
]
PRICE_COLUMNS = ["open", "high", "low", "close"]
EVENT_COLUMNS = [
    "ticker", "event_date", "event_type", "event_description",
    "rvol_t_minus_1", "rvol_t", "rvol_t_plus_1",
    "jump_day_t_minus_1", "jump_day_t", "jump_day_t_plus_1",
    "normal_mean_rvol", "event_window_mean_rvol", "event_vs_normal_ratio",
    "normal_jump_frequency", "event_window_jump_frequency", "status",
]
COLORS = {{
    "blue": "#1F4E78", "light_blue": "#4C78A8", "red": "#C43C39",
    "orange": "#F28E2B", "green": "#2E7D32", "gray": "#6B7280",
}}
NAVY = RGBColor(24, 54, 93)
BLUE = RGBColor(55, 105, 150)
RED = RGBColor(180, 55, 55)
DARK = RGBColor(40, 44, 52)
LIGHT = RGBColor(245, 247, 250)
GRAY = RGBColor(105, 112, 122)

EMBEDDED_SNAPSHOT_B64 = """{payload}"""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Retorna uma cópia da configuração interna do arquivo único."""
    del path
    import copy
    return copy.deepcopy(CONFIG)


def ticker_groups(config: dict[str, Any]) -> dict[str, str]:
    groups: dict[str, str] = {{}}
    for ticker in config["tickers"]["core_liquid"]:
        groups[ticker] = "core_liquid"
    for ticker in config["tickers"]["high_vol_growth_candidates"]:
        groups[ticker] = "high_vol_growth_candidate"
    return groups


def configured_tickers(config: dict[str, Any]) -> list[str]:
    return [
        *config["tickers"]["core_liquid"],
        *config["tickers"]["high_vol_growth_candidates"],
    ]


def ensure_project_directories(root: Path = PROJECT_ROOT) -> None:
    for relative_path in [
        "config", "data/raw", "data/interim", "data/processed", "data/manual",
        "outputs/figures", "outputs/tables", "outputs/slides",
        "outputs/report", "outputs/logs", "report", "slides", "obsidian_notes",
    ]:
        (root / relative_path).mkdir(parents=True, exist_ok=True)


def materialize_embedded_snapshot() -> None:
    """Extrai somente os arquivos incorporados, com validação de caminho."""
    ensure_project_directories()
    raw = base64.b64decode(EMBEDDED_SNAPSHOT_B64)
    root = PROJECT_ROOT.resolve()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        for member in archive.infolist():
            destination = (root / member.filename).resolve()
            if root not in destination.parents and destination != root:
                raise ValueError(f"Caminho inválido no snapshot: {{member.filename}}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

'''


def _footer() -> str:
    return r'''

LOGGER = setup_logging("codigo_final")


def run_internal_tests() -> None:
    """Testes essenciais sem depender de pytest."""
    test_returns = np.array([0.01, -0.02, 0.03])
    assert np.isclose(realized_variance(test_returns), np.sum(test_returns**2))
    assert np.isclose(
        realized_volatility(test_returns),
        np.sqrt(np.sum(test_returns**2)),
    )
    assert np.isfinite(bipower_variation([0.01, -0.02, 0.015, -0.005]))
    assert bipower_variation([0.01, -0.02, 0.015, -0.005]) > 0
    assert jump_variation(0.01, 0.02) == 0
    assert jump_variation(0.03, 0.02) > 0

    frame = pd.DataFrame(
        [
            {"datetime": "2026-05-04 10:00", "ticker": "TEST3.SA", "open": 10,
             "high": 10, "low": 10, "close": 10, "volume": 100},
            {"datetime": "2026-05-04 10:05", "ticker": "TEST3.SA", "open": 10.1,
             "high": 10.1, "low": 10.1, "close": 10.1, "volume": 100},
            {"datetime": "2026-05-05 10:00", "ticker": "TEST3.SA", "open": 11,
             "high": 11, "low": 11, "close": 11, "volume": 100},
            {"datetime": "2026-05-05 10:05", "ticker": "TEST3.SA", "open": 11.1,
             "high": 11.1, "low": 11.1, "close": 11.1, "volume": 100},
        ]
    )
    synchronized, _ = synchronize_intraday(
        frame, market_open="10:00", market_close="10:05"
    )
    first_returns = synchronized.groupby("date")["log_return"].nth(0)
    assert first_returns.isna().all()

    negative = frame.iloc[[0]].copy()
    negative.loc[:, "close"] = -1
    assert clean_price_frame(negative).empty

    empty_events = pd.DataFrame(
        columns=["ticker", "date", "event_type", "event_description"]
    )
    assert analyze_event_windows(empty_events, pd.DataFrame()).empty
    print("Testes internos: 8 verificações concluídas com sucesso.")


def create_results_archive() -> Path:
    """Compacta a pasta produzida para download no Colab."""
    output = PROJECT_ROOT.parent / "entrega_volatilidade_realizada_b3.zip"
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7
    ) as archive:
        for path in sorted(PROJECT_ROOT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(PROJECT_ROOT.parent))
    return output


def try_export_pptx_with_libreoffice(pptx_path: Path) -> Path | None:
    """Exporta PDF quando LibreOffice estiver disponível no ambiente."""
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        return None
    subprocess.run(
        [
            executable, "--headless", "--convert-to", "pdf",
            "--outdir", str(pptx_path.parent), str(pptx_path),
        ],
        check=False,
        timeout=180,
    )
    pdf_path = pptx_path.with_suffix(".pdf")
    return pdf_path if pdf_path.exists() else None


def run_complete_pipeline(refresh_data: bool = False) -> dict[str, Path]:
    """Executa toda a entrega no diretório configurado."""
    started = time_module.perf_counter()
    ensure_project_directories()
    materialize_embedded_snapshot()
    config = load_config()

    if refresh_data:
        print("Atualizando dados via yfinance...")
        run_download(config, force=True)
    else:
        print("Usando snapshot intradiário incorporado para reprodução determinística.")

    run_cleaning(config)
    coverage, selected = run_sample_selection(config)
    if selected.empty:
        raise RuntimeError(
            "Nenhum ticker passou aos critérios: "
            + coverage[["ticker", "razao_exclusao"]].to_json(orient="records")
        )
    run_realized_measures(config)
    run_garch_models(config)
    run_event_analysis(config)
    run_tables(config)
    run_plots(config)
    report_path = run_report_writer(config)
    slides_path = run_slides_builder(config)

    code_reference = Path(__file__).resolve() if "__file__" in globals() else None
    html_path = build_final_html(
        PROJECT_ROOT / "Relatório Final.html",
        code_path=code_reference,
        config=config,
    )
    run_internal_tests()
    pdf_path = try_export_pptx_with_libreoffice(slides_path)
    archive_path = create_results_archive()
    elapsed = time_module.perf_counter() - started

    print("\nPIPELINE CONCLUÍDA")
    print("Diretório:", PROJECT_ROOT)
    print("HTML:", html_path)
    print("Relatório Markdown:", report_path)
    print("PowerPoint:", slides_path)
    print("PDF:", pdf_path or "LibreOffice indisponível; PPTX foi gerado.")
    print("ZIP:", archive_path)
    print(f"Tempo total: {elapsed:.1f}s")
    return {
        "root": PROJECT_ROOT,
        "html": html_path,
        "report": report_path,
        "slides": slides_path,
        "archive": archive_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline autocontida de volatilidade realizada da B3."
    )
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Baixa uma nova janela em vez de apenas usar o snapshot incorporado.",
    )
    args, _ = parser.parse_known_args()
    run_complete_pipeline(refresh_data=args.refresh_data)


if __name__ == "__main__":
    main()
'''


def build_code_final() -> Path:
    payload = _snapshot_payload()
    parts = [_header(payload)]
    for module_name in MODULE_ORDER:
        module_path = PACKAGE / module_name
        parts.append(
            "\n\n# "
            + "=" * 78
            + f"\n# BLOCO INTEGRADO DE {module_name}\n# "
            + "=" * 78
            + "\n\n"
            + _definitions(module_path)
        )
    parts.append(_footer())
    CODE_PATH.write_text("\n".join(parts), encoding="utf-8")
    return CODE_PATH


def build_html_final(code_path: Path) -> Path:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from vol_realizada_b3.final_html import build_final_html

    return build_final_html(HTML_PATH, code_path=code_path)


def main() -> None:
    code_path = build_code_final()
    html_path = build_html_final(code_path)
    print(code_path)
    print(html_path)


if __name__ == "__main__":
    main()
