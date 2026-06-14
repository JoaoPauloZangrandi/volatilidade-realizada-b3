"""Gera tabelas, workbook e graficos finais."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.plots import run_plots
from vol_realizada_b3.tables import run_tables


if __name__ == "__main__":
    run_tables()
    run_plots()

