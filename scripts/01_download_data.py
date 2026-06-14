"""Baixa dados intradiarios dos tickers configurados."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.data_download import run_download


if __name__ == "__main__":
    run_download()

