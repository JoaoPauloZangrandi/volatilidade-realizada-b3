"""Geracao do mini-paper e das notas do Obsidian a partir dos resultados."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config
from .utils import write_text_targets


def _pct(value: float, digits: int = 1) -> str:
    return "n/d" if not np.isfinite(value) else f"{100 * value:.{digits}f}%"


def _list_tickers(values: pd.Series) -> str:
    items = [str(item) for item in values.dropna()]
    return ", ".join(items) if items else "nenhum"


def _economic_comparison(groups: pd.DataFrame) -> str:
    core = groups.loc[groups["grupo"].eq("core_liquid")]
    complement = groups.loc[
        groups["grupo"].eq("high_vol_growth_candidate")
    ]
    if core.empty:
        return "Nenhum ativo core passou aos filtros, impedindo a comparacao."
    if complement.empty:
        return (
            "Nenhum candidato growth/high-vol passou aos filtros objetivos. "
            "Isso e um resultado de qualidade de dados, e nao evidencia de baixo risco."
        )
    core_row = core.iloc[0]
    complement_row = complement.iloc[0]
    rvol_ratio = (
        complement_row["mean_rvol_annualized"]
        / core_row["mean_rvol_annualized"]
        if core_row["mean_rvol_annualized"] > 0
        else np.nan
    )
    direction = "maior" if rvol_ratio > 1 else "menor"
    return (
        f"O grupo complementar apresentou volatilidade realizada media {direction}: "
        f"{_pct(complement_row['mean_rvol_annualized'])}, contra "
        f"{_pct(core_row['mean_rvol_annualized'])} no core "
        f"(razao {rvol_ratio:.2f}). A frequencia de jumps foi "
        f"{_pct(complement_row['jump_frequency'])} no complementar e "
        f"{_pct(core_row['jump_frequency'])} no core."
    )


def build_report(config: dict[str, Any]) -> str:
    """Monta o relatorio usando somente tabelas observadas."""
    tables = PROJECT_ROOT / "outputs" / "tables"
    coverage = pd.read_csv(tables / "data_coverage_by_ticker.csv")
    realized = pd.read_csv(tables / "realized_measures_summary.csv")
    jumps = pd.read_csv(tables / "jump_summary.csv")
    garch = pd.read_csv(tables / "garch_summary.csv")
    ranking = pd.read_csv(tables / "asset_ranking_risk.csv")
    groups = pd.read_csv(tables / "group_comparison.csv")
    events = pd.read_csv(tables / "event_window_summary.csv")

    included = coverage.loc[coverage["status"].eq("included")]
    excluded = coverage.loc[coverage["status"].eq("excluded")]
    top_rvol = realized.sort_values("mean_rvol_annualized", ascending=False).iloc[0]
    top_jump = jumps.sort_values("jump_day_percentage", ascending=False).iloc[0]
    successful_garch = garch.loc[garch["fit_status"].eq("ok")]
    persistence_text = (
        f"A persistencia mediana alpha + beta foi "
        f"{successful_garch['alpha_plus_beta'].median():.3f}."
        if not successful_garch.empty
        else "Nenhum ajuste GARCH convergiu com status plenamente satisfatorio."
    )
    event_valid = events.loc[events.get("status", pd.Series(dtype=str)).eq("ok")]
    event_text = (
        f"Foram avaliados {len(event_valid)} eventos manuais."
        if not event_valid.empty
        else (
            "O arquivo manual nao continha eventos utilizaveis. "
            "A pipeline foi executada sem atribuir datas de resultados nao verificadas."
        )
    )

    excluded_lines = "\n".join(
        f"- {row.ticker}: {row.razao_exclusao}"
        for row in excluded.itertuples()
    ) or "- Nenhum ticker foi excluido."
    garch_lines = "\n".join(
        f"- {row.ticker}: alpha+beta={row.alpha_plus_beta:.3f}, "
        f"correlacao GARCH-RVol={row.correlation_garch_realized:.3f}, "
        f"status={row.fit_status}."
        for row in garch.itertuples()
        if np.isfinite(row.alpha_plus_beta)
    ) or "- Ajustes indisponiveis ou insuficientes."

    return f"""# {config['project']['title']}

**Aluno:** {config['project']['student_name']}

**Instituicao:** {config['project']['institution']}

**Data de geracao:** {datetime.now():%Y-%m-%d}

## 1. Introducao

Este trabalho estima medidas de volatilidade realizada para acoes da B3 com dados intradiarios de cinco minutos. O objetivo e separar variacao continua e saltos, comparar ativos liquidos com candidatas growth/high-vol/small caps e discutir as consequencias para gestao de risco. A literatura de Andersen, Bollerslev, Diebold e Labys motiva o uso da soma dos retornos intradiarios ao quadrado como medida ex post da variabilidade diaria.

## 2. Dados

Os dados foram obtidos via `yfinance`, com `period="60d"` e `interval="5m"`. A amostra observada incluiu {_list_tickers(included['ticker'])}. O Yahoo Finance limita o historico intradiario recente; portanto, os resultados descrevem uma janela curta e nao devem ser extrapolados mecanicamente para outros regimes.

![Cobertura](../outputs/figures/data_coverage_by_ticker.png)

## 3. Estrategia de amostra

A amostra principal liquida garante qualidade de dados e comparabilidade. A amostra complementar de acoes growth/small caps testa se ativos mais sensiveis a noticias, resultados e risco idiossincratico apresentam maior volatilidade realizada e maior frequencia/intensidade de jumps.

Foram exigidos pelo menos 30 dias validos, cobertura media minima de 70%, no minimo 40 retornos intradiarios por dia valido, precos positivos, volume positivo em parte relevante dos intervalos e proporcao de precos parados inferior a 50%.

### Tickers excluidos

{excluded_lines}

## 4. Tratamento e construcao dos retornos

Os registros foram ordenados, desduplicados, convertidos para `America/Sao_Paulo` e restritos a 10:00-17:55. Cada ticker-dia foi sincronizado em grade regular de cinco minutos. O ultimo preco de cada intervalo foi usado; o forward-fill ocorreu apenas dentro do mesmo dia. O primeiro retorno de cada dia foi removido, evitando retornos entre o fechamento anterior e a abertura seguinte.

## 5. Metodologia

Para retornos intradiarios logaritmicos `r_k`, a realized variance e `RV = sum(r_k^2)` e a volatilidade realizada diaria e `sqrt(RV)`. A versao anualizada e `sqrt(252 RV)`.

A bipower variation usa produtos de retornos absolutos adjacentes e aproxima a variacao continua sob condicoes usuais. A jump variation e `JV = max(RV - BV, 0)`. O teste de jump combina RV, BV e tripower quarticity, classificando um dia quando a estatistica excede o quantil normal de 99%.

O GARCH(1,1) foi estimado com retornos diarios close-to-close em porcentagem. Essa serie inclui o componente overnight, ao contrario da RVol intradiaria; a comparacao e informativa, mas os objetos nao sao identicos.

## 6. Resultados de volatilidade realizada

O maior nivel medio de volatilidade realizada anualizada foi observado em **{top_rvol['ticker']}**, com {_pct(top_rvol['mean_rvol_annualized'])}. O ranking completo esta em `outputs/tables/asset_ranking_risk.csv`.

![Serie de RVol](../outputs/figures/realized_volatility_time_series.png)

![Boxplot](../outputs/figures/rvol_boxplot_by_ticker.png)

As series mostram variacao temporal e episodios de clustering. A matriz de correlacao permite avaliar se aumentos de risco ocorrem de forma comum ou idiossincratica, aspecto central para diversificacao.

![Correlacao](../outputs/figures/rvol_correlation_heatmap.png)

## 7. Jumps

O ativo com maior frequencia estimada de jump days foi **{top_jump['ticker']}**, com {_pct(top_jump['jump_day_percentage'])}. A BV ajuda a separar a variacao continua da parcela associada a movimentos descontínuos. Em ativos menos liquidos, precos parados e negociacao esparsa podem distorcer essa separacao; por isso, os filtros de qualidade antecedem o teste.

![RV e BV](../outputs/figures/rv_vs_bv.png)

![Jump days](../outputs/figures/jump_frequency_by_ticker.png)

## 8. GARCH

{persistence_text} Em geral, o GARCH representa persistencia e clustering por uma dinamica suavizada. A volatilidade realizada reage diretamente aos movimentos intradiarios e pode exibir picos mais abruptos em dias com saltos.

{garch_lines}

![GARCH vs RVol](../outputs/figures/garch_vs_realized_all.png)

## 9. Comparacao entre ativos liquidos e growth/small caps

{_economic_comparison(groups)}

PETR4 e VALE3 podem responder a petroleo, minerio, cambio e noticias globais; bancos refletem condicoes financeiras e risco domestico; tecnologia, consumo e growth tendem a ter maior sensibilidade a juros e revisoes de expectativas. Essas interpretacoes sao mecanismos economicos plausiveis, nao identificacao causal.

![Comparacao dos grupos](../outputs/figures/core_vs_high_vol_comparison.png)

## 10. Eventos de resultados

{event_text}

![Eventos](../outputs/figures/event_window_volatility.png)

## 11. Implicacoes para gestao de risco

- VaR e expected shortfall baseados em distribuicoes suaves podem subestimar perdas em dias com jumps.
- RVol intradiaria oferece monitoramento mais rapido de mudancas no risco.
- Ativos com jump risk elevado justificam limites, margens e sizing mais conservadores.
- Correlacao entre volatilidades reduz o beneficio de diversificacao quando o risco sobe de forma conjunta.
- Baixa liquidez pode gerar ruido, precos parados e falsos sinais de salto.

## 12. Limitacoes

- Historico intradiario curto imposto pelo Yahoo Finance.
- Possivel ruido de microestrutura e ausencia de dados tick-by-tick.
- Sincronizacao por candles e forward-fill imperfeito.
- Resultados dependentes da frequencia de cinco minutos.
- Small caps podem ter negociacao esparsa ou ticker obsoleto.
- GARCH estimado com amostra diaria curta e incluindo retornos overnight.
- Eventos dependem de preenchimento manual e verificavel.

## 13. Conclusao

O projeto entrega uma pipeline reprodutivel que trata qualidade intradiaria antes de medir risco. Os resultados observados mostram que o ranking de risco, a frequencia de jumps e a persistencia GARCH sao dimensoes complementares. Para gestao de risco, a principal mensagem e que volatilidade continua, saltos e liquidez precisam ser avaliados conjuntamente.

Extensoes naturais incluem dados tick-by-tick da B3, comparacao entre 1, 5 e 15 minutos, HAR-RV, realized kernels, modelos com jumps explicitos e um calendario verificado de resultados e noticias.

## 14. Referencias

- Andersen, Bollerslev, Diebold e Labys (2003), realized volatility.
- Barndorff-Nielsen e Shephard (2004, 2006), bipower variation e testes de jumps.
- Bollerslev (1986), GARCH.
- Documentacao do pacote `arch`: https://bashtage.github.io/arch/
- Documentacao do `yfinance`: https://ranaroussi.github.io/yfinance/

## Checklist da Rubrica

1. **Tratamento e organizacao:** `data_download.py`, `data_cleaning.py`, `sample_selection.py`, scripts 01-03 e `data_coverage_by_ticker.csv`.
2. **Medidas:** RV, RVol e BV em `realized_measures.py`; resultados em `realized_measures.csv` e `realized_measures_summary.csv`.
3. **Jumps:** JV, tripower quarticity e teste em `jumps.py`; `jump_summary.csv` e figuras de jumps.
4. **Comparacao:** series, boxplot, ranking, correlacao e comparacao core versus growth/high-vol.
5. **Codigo:** pacote em `src/`, YAML, logs, tratamento de erros, testes e `run_all.py`.
6. **Analise:** interpretacao economica, conexao com teoria, GARCH e implicacoes para risco.
7. **Apresentacao:** relatorio Markdown, figuras em alta resolucao e PowerPoint de 18 slides.
"""


def _build_interpretation_note() -> str:
    ranking = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "asset_ranking_risk.csv"
    )
    groups = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "group_comparison.csv"
    )
    top = ranking.iloc[0]
    return f"""# Interpretacao Economica

## Resultado principal

O maior nivel medio de volatilidade realizada anualizada foi de **{top['ticker']}**, com {_pct(top['mean_rvol_annualized'])}.

## Core versus growth/high-vol

{_economic_comparison(groups)}

## Leitura de risco

- RV mede a variacao total observada intradiariamente.
- BV aproxima a parcela continua; RV acima de BV sustenta a estimativa de JV.
- GARCH captura persistencia, mas suaviza picos que aparecem imediatamente na RVol.
- Jump risk elevado pede sizing, margens e stress tests mais conservadores.
- Resultados de ativos com baixa liquidez devem ser lidos junto com a tabela de cobertura.
"""


def _build_readme_note(config: dict[str, Any]) -> str:
    coverage = pd.read_csv(
        PROJECT_ROOT / "outputs" / "tables" / "data_coverage_by_ticker.csv"
    )
    included = coverage.loc[coverage["status"].eq("included"), "ticker"]
    excluded = coverage.loc[coverage["status"].eq("excluded")]
    excluded_lines = "\n".join(
        f"- {row.ticker}: {row.razao_exclusao}"
        for row in excluded.itertuples()
    ) or "- Nenhum ticker excluido."
    return f"""# Trabalho - Volatilidade Realizada B3

## Objetivo

Estimar volatilidade realizada, separar variacao continua e jumps, comparar ativos liquidos com growth/high-vol e discutir gestao de risco.

## Repositorio

`https://github.com/JoaoPauloZangrandi/volatilidade-realizada-b3`

## Amostra executada

Incluidos: {_list_tickers(included)}.

Excluidos:

{excluded_lines}

## Execucao

```powershell
.\\.venv\\Scripts\\Activate.ps1
python scripts/run_all.py
```

## Entregaveis

- Relatorio: `outputs/report/relatorio.md`.
- Slides: `outputs/slides/trabalho_volatilidade_realizada_b3.pptx`.
- Tabelas: `outputs/tables/`.
- Figuras: `outputs/figures/`.

## Limitacao central

O historico intradiario do Yahoo Finance e curto. GARCH e jumps devem ser interpretados junto com cobertura e liquidez.
"""


def run_report_writer(
    config: dict[str, Any] | None = None,
) -> Path:
    """Gera relatorio, copia para outputs e atualiza notas."""
    config = config or load_config()
    content = build_report(config)
    report_path = PROJECT_ROOT / "report" / "relatorio.md"
    report_path.write_text(content, encoding="utf-8")
    output_path = PROJECT_ROOT / "outputs" / "report" / "relatorio.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_content = content.replace(
        "../outputs/figures/",
        "../figures/",
    )
    output_path.write_text(output_content, encoding="utf-8")

    obsidian_path = config["project"].get("obsidian_path")
    write_text_targets(
        "Interpretação Econômica.md",
        _build_interpretation_note(),
        obsidian_path,
    )
    write_text_targets(
        "README - Trabalho Volatilidade Realizada B3.md",
        _build_readme_note(config),
        obsidian_path,
    )
    log_content = f"""# Log de Execucao

## {datetime.now():%Y-%m-%d %H:%M}

- Pipeline de dados, medidas, jumps, GARCH, tabelas e graficos executada.
- Relatorio atualizado em `report/relatorio.md`.
- Slides preparados em `outputs/slides/`.
- Resultados usados nas notas sao observados, sem dados sinteticos.
"""
    write_text_targets("Log de Execução.md", log_content, obsidian_path)
    return report_path
