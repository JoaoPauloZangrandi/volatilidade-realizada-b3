"""Estima modelos GARCH(1,1)."""

from _common import ROOT  # noqa: F401

from vol_realizada_b3.garch_models import run_garch_models


if __name__ == "__main__":
    run_garch_models()

