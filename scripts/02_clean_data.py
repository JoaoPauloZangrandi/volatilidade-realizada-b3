"""Limpa e sincroniza os dados intradiarios."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.data_cleaning import run_cleaning


if __name__ == "__main__":
    run_cleaning()

