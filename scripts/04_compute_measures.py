"""Calcula RV, RVol, BV, TQ, JV e teste de jumps."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.realized_measures import run_realized_measures


if __name__ == "__main__":
    run_realized_measures()

