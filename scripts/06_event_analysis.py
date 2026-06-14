"""Analisa eventos manuais sem quebrar quando o arquivo esta vazio."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.event_analysis import run_event_analysis


if __name__ == "__main__":
    run_event_analysis()

