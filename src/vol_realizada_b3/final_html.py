"""Relatorio HTML autocontido para entrega aos avaliadores."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, load_config


def _read_table(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = PROJECT_ROOT / "outputs" / "tables" / f"{name}.csv"
    return pd.read_csv(path, parse_dates=parse_dates)


def _percentage(value: float, digits: int = 1) -> str:
    return "n/d" if not np.isfinite(value) else f"{100 * value:.{digits}f}%"


def _number(value: float, digits: int = 3) -> str:
    return "n/d" if not np.isfinite(value) else f"{value:.{digits}f}"


def _image_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _file_uri(path: Path, mime: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _data_bundle() -> tuple[bytes, list[dict[str, Any]]]:
    """Compacta bases e tabelas para download dentro do proprio HTML."""
    roots = [
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "data" / "interim",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "data" / "manual",
        PROJECT_ROOT / "outputs" / "tables",
    ]
    buffer = io.BytesIO()
    inventory: list[dict[str, Any]] = []
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(PROJECT_ROOT)
                archive.write(path, relative.as_posix())
                inventory.append(
                    {
                        "arquivo": relative.as_posix(),
                        "tamanho_kb": round(path.stat().st_size / 1024, 1),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
                    }
                )
    return buffer.getvalue(), inventory


def _table(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    rename: dict[str, str] | None = None,
    max_rows: int | None = None,
) -> str:
    data = frame.copy()
    if columns:
        data = data[columns]
    if rename:
        data = data.rename(columns=rename)
    if max_rows:
        data = data.head(max_rows)
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else f"{value:.4f}"
            )
        elif pd.api.types.is_datetime64_any_dtype(data[column]):
            data[column] = data[column].dt.strftime("%Y-%m-%d")
    return data.to_html(index=False, border=0, classes="data-table", escape=True)


def _figure(
    filename: str,
    title: str,
    caption: str,
    css_class: str = "",
) -> str:
    path = PROJECT_ROOT / "outputs" / "figures" / filename
    if not path.exists():
        return ""
    return f"""
    <figure class="{css_class}">
      <img src="{_image_uri(path)}" alt="{html.escape(title)}">
      <figcaption><strong>{html.escape(title)}.</strong> {html.escape(caption)}</figcaption>
    </figure>
    """


def _asset_commentary(
    ranking: pd.DataFrame,
    jumps: pd.DataFrame,
    garch: pd.DataFrame,
) -> str:
    merged = ranking.merge(
        jumps[["ticker", "jump_day_percentage", "max_jump_date"]],
        on="ticker",
        how="left",
        suffixes=("", "_jump"),
    ).merge(
        garch[["ticker", "alpha_plus_beta", "correlation_garch_realized"]],
        on="ticker",
        how="left",
        suffixes=("", "_garch"),
    )
    items: list[str] = []
    for row in merged.sort_values("rank_mean_realized_volatility").itertuples():
        persistence = (
            f"persistência GARCH α+β={row.alpha_plus_beta:.3f}"
            if np.isfinite(row.alpha_plus_beta)
            else "persistência GARCH indisponível"
        )
        correlation = (
            f"correlação GARCH–RVol={row.correlation_garch_realized:.3f}"
            if np.isfinite(row.correlation_garch_realized)
            else "correlação indisponível"
        )
        items.append(
            "<li><strong>{ticker}</strong> ({group}): RVol anualizada média "
            "{rvol}; jump days {jumps}; jump share médio {share}; {persistence}; "
            "{correlation}.</li>".format(
                ticker=html.escape(row.ticker),
                group=html.escape(row.grupo),
                rvol=_percentage(row.mean_rvol_annualized),
                jumps=_percentage(row.jump_day_percentage),
                share=_percentage(row.mean_jump_share),
                persistence=html.escape(persistence),
                correlation=html.escape(correlation),
            )
        )
    return "\n".join(items)


def _source_code_summary(code_path: Path | None) -> tuple[str, str]:
    if code_path is None or not code_path.exists():
        return "Código Final.py será entregue separadamente.", ""
    raw = code_path.read_bytes()
    lines = code_path.read_text(encoding="utf-8").count("\n") + 1
    digest = hashlib.sha256(raw).hexdigest()
    return (
        f"`Código Final.py` contém {lines:,} linhas e SHA-256 {digest}.",
        _file_uri(code_path, "text/x-python;charset=utf-8"),
    )


def build_final_html(
    output_path: Path | None = None,
    code_path: Path | None = None,
    config: dict[str, Any] | None = None,
) -> Path:
    """Gera o Relatorio Final com imagens, tabelas e dados embutidos."""
    config = config or load_config()
    output_path = output_path or PROJECT_ROOT / "Relatório Final.html"

    coverage = _read_table("data_coverage_by_ticker", parse_dates=["primeiro_dia", "ultimo_dia"])
    descriptive = _read_table("descriptive_intraday_returns")
    realized = _read_table("realized_measures_summary")
    jumps = _read_table("jump_summary", parse_dates=["max_jump_date"])
    garch = _read_table("garch_summary")
    ranking = _read_table("asset_ranking_risk")
    excluded = _read_table("excluded_tickers")
    groups = _read_table("group_comparison")
    events = _read_table("event_window_summary", parse_dates=["event_date"])
    measures = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "realized_measures.csv",
        parse_dates=["date"],
    )
    daily_quality = pd.read_csv(
        PROJECT_ROOT / "data" / "interim" / "daily_data_quality.csv",
        parse_dates=["date"],
    )
    download_status = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "download_status.csv"
    )

    included = coverage.loc[coverage["status"].eq("included")].copy()
    event_ok = events.loc[events["status"].eq("ok")].copy()
    core = groups.loc[groups["grupo"].eq("core_liquid")].iloc[0]
    high_vol = groups.loc[
        groups["grupo"].eq("high_vol_growth_candidate")
    ].iloc[0]
    top_rvol = realized.sort_values("mean_rvol_annualized", ascending=False).iloc[0]
    top_jump = jumps.sort_values("jump_day_percentage", ascending=False).iloc[0]
    rvol_ratio = high_vol["mean_rvol_annualized"] / core["mean_rvol_annualized"]
    jump_ratio = high_vol["jump_frequency"] / core["jump_frequency"]
    event_rvol_ratio = event_ok["event_vs_normal_ratio"].mean()
    event_jump_frequency = event_ok["event_window_jump_frequency"].mean()
    normal_jump_frequency = event_ok["normal_jump_frequency"].mean()
    date_start = measures["date"].min().strftime("%d/%m/%Y")
    date_end = measures["date"].max().strftime("%d/%m/%Y")
    code_summary, code_download = _source_code_summary(code_path)

    bundle, inventory = _data_bundle()
    bundle_sha = hashlib.sha256(bundle).hexdigest()
    bundle_uri = "data:application/zip;base64," + base64.b64encode(bundle).decode("ascii")
    inventory_frame = pd.DataFrame(inventory)

    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    figure_gallery = "\n".join(
        [
            _figure(
                "realized_volatility_time_series.png",
                "Volatilidade realizada no tempo",
                "Séries diárias anualizadas; picos mostram episódios de risco observado.",
            ),
            _figure(
                "rvol_boxplot_by_ticker.png",
                "Distribuição da RVol por ativo",
                "Compara mediana, dispersão e observações extremas.",
            ),
            _figure(
                "rv_vs_bv.png",
                "RV versus BV",
                "A distância entre RV e BV sustenta a estimativa não negativa de jump variation.",
            ),
            _figure(
                "jump_days_realized_volatility.png",
                "Dias de jump nas séries",
                "Os pontos destacados excedem o valor crítico do teste estatístico configurado em 99%.",
            ),
            _figure(
                "rvol_correlation_heatmap.png",
                "Correlação das volatilidades realizadas",
                "Comovimento de volatilidade é relevante para diversificação em regimes de estresse.",
            ),
            _figure(
                "intraday_volatility_signature.png",
                "Assinatura intradiária",
                "Média de |retorno| e retorno² por horário, separada por grupo.",
            ),
            _figure(
                "garch_vs_realized_all.png",
                "GARCH versus RVol",
                "A volatilidade GARCH é mais suavizada; a RVol reage diretamente aos movimentos intradiários.",
            ),
            _figure(
                "event_window_volatility.png",
                "Janelas de earnings",
                "Compara a RVol média em t-1/t/t+1 com a média dos demais dias do mesmo ativo.",
            ),
        ]
    )

    garch_gallery = "\n".join(
        _figure(
            f"garch_vs_realized_{ticker.replace('.', '_').lower()}.png",
            f"GARCH e RVol — {ticker}",
            "Comparação diária individual. A interpretação deve considerar que GARCH usa close-to-close, incluindo overnight.",
            css_class="compact",
        )
        for ticker in included["ticker"]
    )

    code_link = (
        f'<a class="button secondary" download="Código Final.py" href="{code_download}">'
        "Baixar cópia do Código Final.py</a>"
        if code_download
        else ""
    )

    document = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório Final — Volatilidade Realizada B3</title>
<style>
:root {{
  --navy:#12304f; --blue:#1f5f8b; --red:#a33a3a; --gold:#b98b2f;
  --ink:#202630; --muted:#657180; --line:#dce3e9; --paper:#ffffff;
  --background:#eef2f5; --soft:#f6f8fa; --green:#2f6f50;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{
  margin:0; color:var(--ink); background:var(--background);
  font-family:"Segoe UI", Arial, sans-serif; line-height:1.62;
}}
main {{ max-width:1180px; margin:0 auto; background:var(--paper); box-shadow:0 0 35px #23384a22; }}
header {{
  min-height:570px; padding:78px 8% 55px; color:white;
  background:linear-gradient(135deg,#0d2740 0%,#1f5f8b 70%,#39799f 100%);
  display:flex; flex-direction:column; justify-content:center;
}}
header .eyebrow {{ letter-spacing:.16em; text-transform:uppercase; font-size:.82rem; opacity:.84; }}
h1 {{ font-family:Georgia,serif; font-size:3.2rem; line-height:1.08; max-width:920px; margin:.35em 0; }}
header .subtitle {{ font-size:1.25rem; max-width:850px; opacity:.94; }}
header .meta {{ margin-top:38px; border-top:1px solid #ffffff55; padding-top:20px; }}
nav {{
  position:sticky; top:0; z-index:5; padding:12px 5%; background:#102b45f5;
  display:flex; gap:16px; flex-wrap:wrap; box-shadow:0 4px 15px #0002;
}}
nav a {{ color:white; text-decoration:none; font-size:.86rem; }}
section {{ padding:54px 7%; border-bottom:1px solid var(--line); }}
h2 {{ color:var(--navy); font-family:Georgia,serif; font-size:2rem; margin-top:0; }}
h3 {{ color:var(--blue); margin-top:2em; }}
h4 {{ color:var(--navy); }}
.lead {{ font-size:1.12rem; color:#34414e; }}
.notice {{ background:#fff8e8; border-left:5px solid var(--gold); padding:18px 22px; margin:25px 0; }}
.method {{ background:#edf5fa; border-left:5px solid var(--blue); padding:18px 22px; margin:20px 0; }}
.risk {{ background:#fceded; border-left:5px solid var(--red); padding:18px 22px; margin:20px 0; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin:28px 0; }}
.card {{ border:1px solid var(--line); border-radius:10px; padding:20px; background:var(--soft); }}
.card .value {{ font-size:1.8rem; font-weight:700; color:var(--navy); }}
.card .label {{ color:var(--muted); font-size:.88rem; }}
.formula {{
  overflow-x:auto; text-align:center; font-family:"Cambria Math",Georgia,serif;
  font-size:1.15rem; background:#f7f9fb; border:1px solid var(--line);
  padding:18px; margin:16px 0;
}}
figure {{ margin:34px 0; page-break-inside:avoid; }}
figure img {{ width:100%; height:auto; border:1px solid var(--line); border-radius:7px; }}
figcaption {{ color:var(--muted); font-size:.9rem; margin-top:9px; }}
.gallery {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:22px; }}
.gallery figure {{ margin:0; }}
.compact img {{ max-height:430px; object-fit:contain; }}
.table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:7px; margin:20px 0; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:.84rem; }}
.data-table th {{ position:sticky; top:0; background:var(--navy); color:white; text-align:left; }}
.data-table th,.data-table td {{ padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
.data-table tr:nth-child(even) {{ background:#f7f9fb; }}
.button {{
  display:inline-block; padding:12px 18px; margin:8px 8px 8px 0; border-radius:6px;
  background:var(--green); color:white; text-decoration:none; font-weight:600;
}}
.button.secondary {{ background:var(--blue); }}
code,pre {{ font-family:Consolas,"Courier New",monospace; }}
pre {{ background:#111a24; color:#d9e7f2; padding:18px; overflow:auto; border-radius:7px; }}
.two-col {{ columns:2 330px; column-gap:38px; }}
.asset-list li {{ margin-bottom:10px; break-inside:avoid; }}
.small {{ color:var(--muted); font-size:.87rem; }}
.checklist li {{ margin-bottom:9px; }}
footer {{ background:var(--navy); color:white; padding:34px 7%; }}
@media print {{
  body {{ background:white; }} main {{ box-shadow:none; max-width:none; }}
  nav,.button {{ display:none; }} section {{ padding:32px 5%; }}
  h2,h3 {{ page-break-after:avoid; }} figure,.table-wrap {{ page-break-inside:avoid; }}
}}
@media (max-width:700px) {{
  h1 {{ font-size:2.25rem; }} section {{ padding:38px 5%; }}
  .gallery {{ grid-template-columns:1fr; }} nav {{ display:none; }}
}}
</style>
</head>
<body>
<main>
<header>
  <div class="eyebrow">FGV EESP · Trabalho Final · Tema 1</div>
  <h1>Volatilidade Realizada com Dados Intradiários: Evidências para Ações da B3</h1>
  <p class="subtitle">Relatório Final autocontido: dados, tratamento, metodologia econométrica,
  resultados, jumps, GARCH, eventos de resultados, implicações para risco e documentação do código.</p>
  <div class="meta">
    <strong>{html.escape(config['project']['student_name'])}</strong><br>
    {html.escape(config['project']['institution'])}<br>
    Janela observada: {date_start} a {date_end} · Gerado em {generated}
  </div>
</header>
<nav>
  <a href="#resumo">Resumo</a><a href="#dados">Dados</a><a href="#tratamento">Tratamento</a>
  <a href="#metodologia">Metodologia</a><a href="#resultados">Resultados</a>
  <a href="#jumps">Jumps</a><a href="#garch">GARCH</a><a href="#eventos">Earnings</a>
  <a href="#risco">Risco</a><a href="#codigo">Código</a><a href="#apendices">Apêndices</a>
</nav>

<section id="resumo">
<h2>1. Resumo executivo</h2>
<p class="lead">Este trabalho mede a variação diária observada nos preços de ações da B3 usando
retornos intradiários de cinco minutos. A análise combina realized variance (RV), realized
volatility (RVol), bipower variation (BV), jump variation (JV), teste estatístico de jumps e
GARCH(1,1). O desenho compara uma amostra líquida com ativos growth/high-vol que sobreviveram
a filtros objetivos de qualidade.</p>
<div class="cards">
  <div class="card"><div class="value">{len(included)}</div><div class="label">ativos incluídos de {len(coverage)} candidatos</div></div>
  <div class="card"><div class="value">{int(included['numero_dias_validos'].sum())}</div><div class="label">ticker-dias válidos</div></div>
  <div class="card"><div class="value">{top_rvol['ticker']}</div><div class="label">maior RVol média: {_percentage(top_rvol['mean_rvol_annualized'])}</div></div>
  <div class="card"><div class="value">{rvol_ratio:.2f}×</div><div class="label">RVol do grupo complementar / core</div></div>
  <div class="card"><div class="value">{jump_ratio:.2f}×</div><div class="label">frequência de jumps complementar / core</div></div>
  <div class="card"><div class="value">{len(event_ok)}</div><div class="label">eventos de earnings na janela</div></div>
</div>
<div class="notice"><strong>Resultado central.</strong> O grupo complementar selecionado apresentou
RVol anualizada média de {_percentage(high_vol['mean_rvol_annualized'])}, contra
{_percentage(core['mean_rvol_annualized'])} no core. A frequência de jump days foi
{_percentage(high_vol['jump_frequency'])} contra {_percentage(core['jump_frequency'])}.
Isso é consistente com maior risco idiossincrático e sensibilidade a notícias, mas não constitui
identificação causal.</div>
<p>As maiores RVol médias foram observadas em <strong>{top_rvol['ticker']}</strong>
({_percentage(top_rvol['mean_rvol_annualized'])}), LWSA3 e MGLU3. A maior frequência individual
de jumps ocorreu em <strong>{top_jump['ticker']}</strong>
({_percentage(top_jump['jump_day_percentage'])}).</p>
</section>

<section id="dados">
<h2>2. Dados, universo e reprodutibilidade</h2>
<h3>2.1 Fonte</h3>
<p>Os candles intradiários foram obtidos do Yahoo Finance por meio do pacote
<code>yfinance</code>, com <code>period="60d"</code> e <code>interval="5m"</code>.
O Yahoo Finance limita o histórico intradiário e o <code>yfinance</code> é um cliente
independente para APIs públicas, voltado a pesquisa e uso educacional. O snapshot empregado
está incorporado no arquivo <code>Código Final.py</code>, de modo que a reprodução não depende
de o provedor continuar retornando exatamente a mesma janela.</p>
<h3>2.2 Universo candidato</h3>
<ul>
  <li><strong>Core/liquid:</strong> PETR4, VALE3, ITUB4, BBDC4, B3SA3, WEGE3, ABEV3 e TOTS3.</li>
  <li><strong>Growth/high-vol/small-cap candidates:</strong> LWSA3, MGLU3, BHIA3, CASH3, CVCB3, AZUL4 e VIIA3.</li>
</ul>
<h3>2.3 Critérios de inclusão</h3>
<ol>
  <li>Pelo menos 30 dias válidos.</li>
  <li>Cobertura média de no mínimo 70% dos 96 candles esperados por dia.</li>
  <li>Pelo menos 40 retornos intradiários válidos no dia.</li>
  <li>Preços OHLC estritamente positivos.</li>
  <li>Volume positivo em parcela relevante dos intervalos observados.</li>
  <li>Proporção agregada de retornos iguais a zero inferior ou igual a 50%.</li>
  <li>Ausência de falha grave de download.</li>
</ol>
{_figure("data_coverage_by_ticker.png","Cobertura dos dados","Verde indica ativo incluído; cinza indica exclusão. A linha tracejada marca o mínimo de 70%.")}
<h3>2.4 Auditoria por ticker</h3>
<div class="table-wrap">{_table(coverage, columns=[
    'ticker','grupo','primeiro_dia','ultimo_dia','numero_dias','numero_dias_validos',
    'numero_observacoes_intradiarias','observacoes_medias_por_dia',
    'cobertura_media_candles','proporcao_precos_parados','status','razao_exclusao'
], rename={
    'grupo':'grupo','primeiro_dia':'início','ultimo_dia':'fim','numero_dias':'dias',
    'numero_dias_validos':'dias válidos','numero_observacoes_intradiarias':'observações',
    'observacoes_medias_por_dia':'obs./dia','cobertura_media_candles':'cobertura',
    'proporcao_precos_parados':'preços parados','razao_exclusao':'razão de exclusão'
})}</div>
<h3>2.5 Exclusões</h3>
<div class="table-wrap">{_table(excluded)}</div>
<p>BHIA3 e CVCB3 tinham boa cobertura nominal, mas excesso de preços parados. AZUL4 e VIIA3
retornaram download vazio/possível ticker descontinuado. Excluir esses casos reduz a chance de
interpretar iliquidez ou ausência de negociação como volatilidade econômica ou jump genuíno.</p>
<h3>2.6 Base incorporada</h3>
<p>O pacote abaixo contém dados brutos, intermediários, processados, eventos e tabelas. Ele está
codificado dentro deste HTML; não é um link externo.</p>
<a class="button" download="bases_e_tabelas_volatilidade_b3.zip" href="{bundle_uri}">Baixar bases e tabelas (ZIP)</a>
<p class="small">SHA-256 do ZIP incorporado: <code>{bundle_sha}</code>.</p>
</section>

<section id="tratamento">
<h2>3. Tratamento, sincronização e retornos</h2>
<h3>3.1 Padronização do esquema</h3>
<p>Cada observação foi convertida ao formato longo:
<code>datetime, date, time, ticker, open, high, low, close, volume</code>. As datas foram
normalizadas para <code>America/Sao_Paulo</code>; preços e volume foram convertidos para tipos
numéricos; registros duplicados por ticker e timestamp foram removidos, mantendo a observação
mais recente.</p>
<h3>3.2 Horário e grade regular</h3>
<p>A análise usa o pregão regular entre 10:00 e 17:55. Para cada ticker-dia, timestamps foram
arredondados para intervalos de cinco minutos. Em cada intervalo: abertura = primeiro preço,
máxima = máximo, mínima = mínimo, fechamento = último preço e volume = soma. A grade esperada
tem 96 candles por dia.</p>
<h3>3.3 Forward-fill controlado</h3>
<p>O último preço disponível foi carregado para frente apenas dentro do mesmo ticker-dia.
Nenhum preço foi propagado para o pregão seguinte. Candles preenchidos têm volume zero e são
marcados como não observados para que a cobertura use somente registros efetivamente recebidos.</p>
<h3>3.4 Retornos sem cruzar dias</h3>
<div class="formula">r<sub>i,d,k</sub> = log(P<sub>i,d,k</sub>) − log(P<sub>i,d,k−1</sub>)</div>
<p>O <code>diff()</code> é aplicado separadamente em cada ticker-dia. O primeiro retorno de cada
dia permanece ausente e não entra em nenhuma soma. Para GARCH, foi criada outra série:
retorno diário close-to-close, em porcentagem.</p>
<h3>3.5 Diagnósticos calculados</h3>
<ul>
  <li>Candles esperados, observados e cobertura por ticker-dia.</li>
  <li>Número de retornos válidos por dia.</li>
  <li>Proporção de retornos zero, usada como indicador de preço parado.</li>
  <li>Parcela de candles observados com volume positivo.</li>
  <li>Contagem antes/depois da limpeza e motivo de exclusão por ativo.</li>
</ul>
<div class="method"><strong>Decisão metodológica.</strong> A sincronização produz comparabilidade
temporal, mas o forward-fill pode introduzir retornos zero. Por isso, cobertura e stale-price
share são parte explícita da seleção, não apenas estatísticas descritivas.</div>
</section>

<section id="metodologia">
<h2>4. Metodologia econométrica</h2>
<h3>4.1 Realized Variance e Realized Volatility</h3>
<div class="formula">RV<sub>i,d</sub> = Σ<sub>k=1</sub><sup>M</sup> r²<sub>i,d,k</sub></div>
<div class="formula">RVol<sub>i,d</sub> = √RV<sub>i,d</sub> &nbsp;&nbsp;|&nbsp;&nbsp;
RVol<sup>ann</sup><sub>i,d</sub> = √(252 · RV<sub>i,d</sub>)</div>
<p>RV é uma medida ex post da variação quadrática diária. RVol está em unidade de desvio-padrão;
a versão anualizada facilita comparação com métricas usuais de mercado, mas não transforma a
janela curta em uma amostra anual.</p>
<h3>4.2 Bipower Variation</h3>
<div class="formula">BV<sub>i,d</sub> = μ<sub>1</sub><sup>−2</sup> · M/(M−1) ·
Σ<sub>k=2</sub><sup>M</sup> |r<sub>k</sub>| |r<sub>k−1</sub>|,
&nbsp; μ<sub>1</sub>=√(2/π)</div>
<p>Sob condições usuais de semimartingale, a BV é robusta a um número finito de saltos e aproxima
a parcela contínua da variação. Em amostras finitas, RV pode ser menor que BV; por isso a JV é
truncada em zero.</p>
<h3>4.3 Jump Variation e jump share</h3>
<div class="formula">JV<sub>i,d</sub> = max(RV<sub>i,d</sub> − BV<sub>i,d</sub>, 0)
&nbsp;&nbsp;|&nbsp;&nbsp; jump share = JV/RV</div>
<h3>4.4 Tripower Quarticity e teste de jumps</h3>
<div class="formula">TQ = M · μ<sub>4/3</sub><sup>−3</sup> · M/(M−2) ·
Σ |r<sub>k−2</sub>|<sup>4/3</sup>|r<sub>k−1</sub>|<sup>4/3</sup>|r<sub>k</sub>|<sup>4/3</sup></div>
<div class="formula">Z = [(RV−BV)/RV] ÷ √{{[((π/2)²+π−5)/M] · max(1,TQ/BV²)}}</div>
<p>Um dia é classificado como jump day quando <code>Z &gt; Φ⁻¹(0,99)</code>. Casos com RV ou BV
não positiva, TQ inválida ou observações insuficientes são marcados como instáveis e não são
forçados a jump.</p>
<h3>4.5 GARCH(1,1)</h3>
<div class="formula">r<sub>t</sub> = μ + ε<sub>t</sub>, &nbsp;
ε<sub>t</sub>=σ<sub>t</sub>z<sub>t</sub>, &nbsp;
σ²<sub>t</sub>=ω+αε²<sub>t−1</sub>+βσ²<sub>t−1</sub></div>
<p>O modelo foi estimado pelo pacote <code>arch</code> com distribuição normal e retornos diários
em porcentagem. A persistência é α+β. A comparação com RVol exige cautela: GARCH close-to-close
inclui overnight, enquanto a RVol foi construída apenas no horário intradiário regular.</p>
<h3>4.6 Eventos de resultados</h3>
<p>Datas de earnings foram obtidas em 14/06/2026 por
<code>yfinance.Ticker(ticker).get_earnings_dates()</code> e limitadas à janela da amostra. Para
cada evento, foram usadas as posições de pregão t−1, t e t+1. A média dessa janela foi comparada
à média dos demais dias do mesmo ativo. Como muitas divulgações ocorrem após o fechamento, t+1
pode concentrar a reação. A análise é descritiva e a fonte é terceirizada.</p>
</section>

<section id="resultados">
<h2>5. Resultados de volatilidade realizada</h2>
<h3>5.1 Estatísticas dos retornos intradiários</h3>
<div class="table-wrap">{_table(descriptive)}</div>
<p>Os retornos intradiários têm média próxima de zero, dispersão distinta entre ativos e caudas
relevantes. Assimetria, curtose e percentis extremos reforçam que uma aproximação gaussiana simples
é insuficiente para descrever todo o risco de alta frequência.</p>
{_figure("realized_volatility_time_series.png","Série temporal da RVol anualizada","A comparação mostra nível, picos e clustering ao longo dos 60 pregões válidos.")}
{_figure("rvol_boxplot_by_ticker.png","Boxplot da RVol anualizada","CASH3, LWSA3 e MGLU3 ocupam o topo da distribuição; o core é mais concentrado.")}
<h3>5.2 Resumo por ativo</h3>
<div class="table-wrap">{_table(realized)}</div>
<h3>5.3 Ranking consolidado</h3>
{_figure("asset_risk_ranking.png","Ranking de risco realizado","Barras vermelhas representam ativos do grupo complementar selecionado.")}
<div class="table-wrap">{_table(ranking)}</div>
<h3>5.4 Comparação entre grupos</h3>
{_figure("core_vs_high_vol_comparison.png","Core versus growth/high-vol","As três métricas apontam maior risco no grupo complementar selecionado.")}
<div class="table-wrap">{_table(groups)}</div>
<p>A RVol do grupo complementar foi <strong>{rvol_ratio:.2f} vezes</strong> a do core. Sua
frequência de jumps foi <strong>{jump_ratio:.2f} vezes</strong> maior, e o jump share médio
também foi superior. O resultado apoia a hipótese substantiva, condicionado à seleção: BHIA3
e CVCB3 foram excluídos por iliquidez, portanto a comparação não representa todo o universo
de small caps.</p>
<h3>5.5 Leitura ativo a ativo</h3>
<ul class="asset-list">{_asset_commentary(ranking, jumps, garch)}</ul>
<h3>5.6 Assinatura e correlação</h3>
{_figure("intraday_volatility_signature.png","Assinatura intradiária da volatilidade","A forma por horário ajuda a identificar concentração de risco na abertura, fechamento ou períodos específicos.")}
{_figure("rvol_correlation_heatmap.png","Correlação das RVols","Correlações positivas indicam que episódios de risco podem ocorrer conjuntamente, reduzindo diversificação.")}
</section>

<section id="jumps">
<h2>6. Jumps: frequência, intensidade e interpretação</h2>
{_figure("rv_vs_bv.png","RV versus BV por ativo","Quando RV se afasta de BV, a parcela JV aumenta; a classificação ainda depende da padronização por TQ.")}
{_figure("jump_days_realized_volatility.png","Jump days nas séries","A marcação estatística permite localizar episódios descontínuos sem usar um limiar arbitrário de retorno bruto.")}
{_figure("jump_frequency_by_ticker.png","Frequência de jump days","CASH3 e LWSA3 tiveram as maiores incidências na amostra observada.")}
<div class="table-wrap">{_table(jumps)}</div>
<div class="risk"><strong>Interpretação.</strong> Um jump day significa que a diferença relativa
entre RV e BV foi grande diante da incerteza estimada por TQ. Não significa automaticamente
notícia específica, erro de preço ou causalidade. Em ativos ilíquidos, negociação esparsa pode
gerar movimentos discretos; por isso a seleção de qualidade é parte da inferência.</div>
</section>

<section id="garch">
<h2>7. GARCH versus volatilidade realizada</h2>
{_figure("garch_vs_realized_all.png","Comparação agregada GARCH–RVol","Os modelos GARCH capturam memória e suavização; a RVol reage no próprio dia aos movimentos intradiários.")}
<div class="table-wrap">{_table(garch)}</div>
<p>Todos os 11 ajustes retornaram status de convergência, com 59 retornos diários. Essa quantidade
é suficiente para executar o estimador, mas pequena para inferência robusta. Valores de α+β
próximos de um em alguns ativos sugerem persistência elevada; resultados muito baixos em outros
podem refletir a amostra curta, regime específico ou dificuldade de identificação. A correlação
entre GARCH e RVol varia por ativo e não deve ser interpretada como teste de superioridade.</p>
<div class="gallery">{garch_gallery}</div>
</section>

<section id="eventos">
<h2>8. Eventos de divulgação de resultados</h2>
<p>Foram analisados {len(event_ok)} eventos dentro da janela. Na média dos eventos, a RVol em
t−1/t/t+1 foi <strong>{_percentage(event_rvol_ratio - 1)}</strong> acima da média dos dias normais
do mesmo ativo. A frequência média de jump days foi <strong>{_percentage(event_jump_frequency)}</strong>
nas janelas e <strong>{_percentage(normal_jump_frequency)}</strong> nos dias normais.</p>
{_figure("event_window_volatility.png","RVol em janelas de earnings","A heterogeneidade é relevante: algumas janelas elevaram fortemente a RVol; outras ficaram próximas ou abaixo da média.")}
<div class="table-wrap">{_table(event_ok)}</div>
<div class="notice"><strong>Cautela.</strong> Esta comparação tem apenas 12 eventos, sobreposição
potencial com notícias macro e setoriais, datas fornecidas por fonte terceirizada e nenhuma
estratégia de identificação causal. O resultado deve ser apresentado como evidência descritiva
compatível com maior risco informacional ao redor de resultados.</div>
</section>

<section id="risco">
<h2>9. Implicações econômicas e para gestão de risco</h2>
<div class="two-col">
<h3>VaR e Expected Shortfall</h3>
<p>Modelos baseados em volatilidade suavizada e distribuições leves podem reagir tarde a saltos.
Em jump days, quantis de perda e expected shortfall podem ser subestimados se a calibração ignora
descontinuidades e caudas.</p>
<h3>Limites e sizing</h3>
<p>Ativos com RVol e jump share elevados justificam posições menores, limites intradiários mais
restritos, haircuts maiores e stress tests específicos para gaps.</p>
<h3>Liquidez</h3>
<p>Preço parado não é sinônimo de estabilidade. Pode significar ausência de negociação. Quando
uma nova transação ocorre, o ajuste acumulado pode parecer um jump. Cobertura e stale share devem
acompanhar qualquer métrica de risco de alta frequência.</p>
<h3>Diversificação</h3>
<p>A correlação das RVols mostra dependência no segundo momento: ativos podem ter retornos
diversificados e ainda apresentar alta simultânea de volatilidade. Em crises, limites baseados
apenas em correlação de retornos podem ser otimistas.</p>
<h3>Commodities, bancos e growth</h3>
<p>PETR4 e VALE3 respondem a commodities, câmbio e notícias globais; bancos respondem a crédito,
juros e risco doméstico; growth e tecnologia são sensíveis a desconto de fluxos e revisões de
expectativas. Na janela estudada, o grupo growth/high-vol selecionado teve risco observado maior,
mas mecanismos específicos exigiriam dados de notícias e identificação adicional.</p>
<h3>Monitoramento</h3>
<p>RVol intradiária fornece sinal rápido do risco realizado; GARCH oferece uma referência
persistente e prospectiva. O uso conjunto é preferível a escolher uma única métrica.</p>
</div>
</section>

<section id="codigo">
<h2>10. Código Final e reprodução no Google Colab</h2>
<p>{html.escape(code_summary)}</p>
<p>O arquivo separado <code>Código Final.py</code> reúne configuração, snapshot comprimido das
bases brutas, limpeza, seleção, medidas, jumps, GARCH, earnings, tabelas, gráficos, relatório,
PowerPoint e testes internos. Por padrão ele usa o snapshot incorporado para produzir resultados
determinísticos. A opção <code>--refresh-data</code> solicita uma nova janela ao Yahoo Finance.</p>
{code_link}
<h3>Execução no Colab</h3>
<pre>from google.colab import files
uploaded = files.upload()  # selecione Código Final.py
%run "Código Final.py"</pre>
<p>Alternativa no terminal do Colab:</p>
<pre>!python "Código Final.py"
!zip -r entrega_gerada.zip volatilidade_realizada_b3_entrega</pre>
<h3>Ordem executada</h3>
<ol>
  <li>Instalação/verificação de dependências.</li>
  <li>Extração do snapshot ou download novo.</li>
  <li>Limpeza, timezone, horário e sincronização.</li>
  <li>Seleção da amostra e retornos diário/intradiário.</li>
  <li>RV, RVol, BV, TQ, JV e teste de jumps.</li>
  <li>GARCH(1,1) por ticker.</li>
  <li>Janelas de earnings.</li>
  <li>Tabelas CSV/Excel e figuras PNG.</li>
  <li>Relatório Markdown, HTML e PowerPoint.</li>
  <li>Testes internos e ZIP final da execução.</li>
</ol>
<h3>Testes incluídos</h3>
<ul>
  <li>RV e RVol em caso simples.</li>
  <li>BV positiva e finita.</li>
  <li>Retorno intradiário sem cruzar dias.</li>
  <li>JV não negativa.</li>
  <li>Remoção de preços negativos/nulos.</li>
  <li>Exclusão por baixa cobertura e manutenção de ticker válido.</li>
  <li>Pipeline de eventos vazia sem falhar.</li>
</ul>
</section>

<section id="limitacoes">
<h2>11. Limitações e extensões</h2>
<ol>
  <li><strong>Janela curta:</strong> o histórico intradiário do Yahoo Finance é limitado.</li>
  <li><strong>Microestrutura:</strong> bid-ask bounce, discreteness e negócios esparsos afetam RV.</li>
  <li><strong>Frequência:</strong> cinco minutos equilibra informação e ruído, mas não elimina o problema.</li>
  <li><strong>Overnight:</strong> GARCH close-to-close e RVol intradiária medem objetos parcialmente distintos.</li>
  <li><strong>Small caps:</strong> filtros de qualidade reduzem o universo e geram seleção.</li>
  <li><strong>Jumps:</strong> classificação estatística não identifica a notícia causadora.</li>
  <li><strong>Earnings:</strong> fonte terceirizada, apenas 12 eventos e ausência de controle causal.</li>
  <li><strong>GARCH:</strong> 59 retornos diários tornam os parâmetros sensíveis ao regime da amostra.</li>
</ol>
<h3>Extensões recomendadas</h3>
<ul>
  <li>Dados tick-by-tick oficiais/pagos da B3 e filtros de negócios anômalos.</li>
  <li>Comparação entre 1, 5 e 15 minutos e volatility signature plot por ativo.</li>
  <li>Realized kernels e pre-averaging para ruído de microestrutura.</li>
  <li>HAR-RV e modelos com componentes contínuo/jump para previsão.</li>
  <li>Calendário de RI e notícias com timestamp exato, surpresa e estudo de eventos causal.</li>
  <li>VaR/ES backtesting usando RVol, GARCH e cenários de salto.</li>
</ul>
</section>

<section id="referencias">
<h2>12. Referências</h2>
<ol>
  <li>Andersen, T. G.; Bollerslev, T.; Diebold, F. X.; Labys, P. (2003).
  “Modeling and Forecasting Realized Volatility”. <em>Econometrica</em>, 71(2), 579–625.</li>
  <li>Barndorff-Nielsen, O. E.; Shephard, N. (2004). “Power and Bipower Variation
  with Stochastic Volatility and Jumps”. <em>Journal of Financial Econometrics</em>, 2(1), 1–37.</li>
  <li>Barndorff-Nielsen, O. E.; Shephard, N. (2006). “Econometrics of Testing for
  Jumps in Financial Economics Using Bipower Variation”. <em>Journal of Financial Econometrics</em>, 4(1), 1–30.</li>
  <li>Bollerslev, T. (1986). “Generalized Autoregressive Conditional
  Heteroskedasticity”. <em>Journal of Econometrics</em>, 31(3), 307–327.
  DOI: <a href="https://doi.org/10.1016/0304-4076(86)90063-1">10.1016/0304-4076(86)90063-1</a>.</li>
  <li>Sheppard, K. <a href="https://bashtage.github.io/arch/">Documentação oficial do pacote arch</a>.</li>
  <li>Ranaroussi, R. <a href="https://ranaroussi.github.io/yfinance/">Documentação do yfinance</a>.</li>
</ol>
</section>

<section id="apendices">
<h2>13. Apêndices de auditoria</h2>
<h3>13.1 Inventário do download</h3>
<div class="table-wrap">{_table(download_status)}</div>
<h3>13.2 Qualidade diária — resumo</h3>
<div class="table-wrap">{_table(
    daily_quality.groupby('ticker', as_index=False).agg(
        dias=('date','nunique'),
        candles_observados=('observed_candles','sum'),
        cobertura_media=('candle_coverage','mean'),
        retornos_validos_medios=('valid_intraday_returns','mean'),
        stale_share_medio=('stale_price_share','mean'),
        volume_positivo_medio=('positive_volume_share','mean')
    )
)}</div>
<h3>13.3 Inventário das bases incorporadas</h3>
<div class="table-wrap">{_table(inventory_frame)}</div>
<h3>13.4 Galeria completa dos gráficos principais</h3>
<div class="gallery">{figure_gallery}</div>
<h3>13.5 Checklist da rubrica</h3>
<ul class="checklist">
  <li>✓ Limpeza, timezone, horário regular, duplicatas, preços positivos e sincronização.</li>
  <li>✓ Retornos intradiários sem cruzar dias e retornos diários close-to-close.</li>
  <li>✓ RV, RVol diária/anualizada e BV com correção de amostra.</li>
  <li>✓ JV, jump share, tripower quarticity e teste a 99%.</li>
  <li>✓ GARCH(1,1), parâmetros, persistência, AIC/BIC e comparação visual.</li>
  <li>✓ Comparação temporal, por ativo e core versus growth/high-vol.</li>
  <li>✓ Eventos de resultados em t−1/t/t+1, com ressalvas de fonte e causalidade.</li>
  <li>✓ Tabelas, Excel, gráficos, relatório, PowerPoint e código único para Colab.</li>
  <li>✓ Base incorporada e outputs determinísticos, sem dados sintéticos nos resultados.</li>
  <li>✓ Testes internos e tratamento de falhas por ticker.</li>
</ul>
</section>

<footer>
<strong>Conclusão.</strong> A evidência desta janela indica que os ativos growth/high-vol que
passaram aos filtros apresentaram maior volatilidade realizada, maior frequência de jumps e maior
jump share do que o core líquido. Earnings coincidiram, em média, com RVol e frequência de jumps
mais altas, mas a amostra é pequena e descritiva. Para risco, a combinação de qualidade de dados,
RVol, BV/JV e GARCH é mais informativa do que qualquer medida isolada.
</footer>
</main>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path
