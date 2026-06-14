# Volatilidade Realizada B3

Projeto do trabalho final da FGV EESP sobre volatilidade realizada, bipower variation, jumps e GARCH em acoes da B3 com dados intradiarios de 5 minutos.

## Status

O repositorio esta em construcao na branch `feature/trabalho-volatilidade-realizada-b3`. O pipeline final sera executavel com:

```powershell
python scripts/run_all.py
```

## Fonte e limitacao principal

Na ausencia de uma base intradiaria local, o projeto usa `yfinance` com `period="60d"` e `interval="5m"`. O Yahoo Finance limita o historico intradiario disponivel. Portanto, os resultados representam uma janela recente, nao uma amostra historica longa, e o GARCH deve ser interpretado com cautela.

## Amostras candidatas

- Core/liquida: PETR4, VALE3, ITUB4, BBDC4, B3SA3, WEGE3, ABEV3 e TOTS3.
- Growth/high-vol/small caps: LWSA3, MGLU3, BHIA3, CASH3, CVCB3, AZUL4 e VIIA3.

A amostra final e definida por criterios objetivos de cobertura, quantidade de dias validos, retornos por dia, precos positivos, volume e proporcao de precos parados.

## Instalacao no Windows

Use Python 3.11, 3.12 ou 3.13. Neste computador, recomenda-se Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Execucao

Pipeline completo:

```powershell
python scripts/run_all.py
```

Etapas:

```powershell
python scripts/01_download_data.py
python scripts/02_clean_data.py
python scripts/03_select_sample.py
python scripts/04_compute_measures.py
python scripts/05_estimate_garch.py
python scripts/06_event_analysis.py
python scripts/07_make_figures_tables.py
python scripts/08_write_report.py
python scripts/09_build_slides.py
```

## Estrutura

- `config/`: parametros editaveis.
- `data/raw/`: downloads originais por ticker.
- `data/interim/`: dados limpos, sincronizados e diagnosticos diarios.
- `data/processed/`: amostra final, retornos e medidas.
- `data/manual/`: eventos de resultados preenchidos manualmente.
- `src/vol_realizada_b3/`: implementacao reutilizavel.
- `scripts/`: pontos de entrada da pipeline.
- `outputs/tables/`: tabelas CSV e workbook Excel.
- `outputs/figures/`: graficos PNG em alta resolucao.
- `outputs/report/`: copia final do relatorio.
- `outputs/slides/`: apresentacao PowerPoint.
- `report/`: mini-paper e referencias.
- `obsidian_notes/`: espelho das notas do Obsidian.
- `tests/`: testes unitarios.

## Reproducao e interpretacao

Os dados brutos nunca sao substituidos por dados sinteticos. Falhas de download sao registradas e o pipeline continua com os ativos validos. A tabela `data_coverage_by_ticker.csv` documenta inclusoes e exclusoes. As tabelas de medidas e jumps sustentam a comparacao economica; os graficos mostram dinamica temporal, clustering, correlacao e risco de saltos.

## Eventos

Preencha `data/manual/events_earnings.csv` conforme `data/manual/README.md`. Sem eventos, a pipeline gera uma tabela vazia com esquema valido e nao inventa datas.

## Checklist de entregaveis

- [ ] Dados intradiarios baixados e organizados.
- [ ] Limpeza, sincronizacao e retornos sem cruzar dias.
- [ ] RV, RVol, BV, JV e teste de jumps.
- [ ] GARCH(1,1) com retornos diarios.
- [ ] Selecao automatica da amostra.
- [ ] Analise opcional de eventos.
- [ ] Tabelas e graficos.
- [ ] Relatorio em Markdown.
- [ ] Slides em PowerPoint.
- [ ] Notas no Obsidian.
- [ ] Testes e pipeline completo.

## Checklist da Rubrica

1. **Tratamento e organizacao dos dados:** `data_cleaning.py`, scripts 01-03 e tabela de cobertura.
2. **Medidas de volatilidade:** `realized_measures.py`, RV, RVol e BV, com testes unitarios.
3. **Jumps:** `jumps.py`, JV, tripower quarticity, estatistica BNS, tabela e figuras.
4. **Analise comparativa:** rankings, series temporais e comparacao entre grupos.
5. **Qualidade do codigo:** pacote em `src/`, configuracao YAML, logs, testes e pipeline unica.
6. **Qualidade da analise:** relatorio conecta resultados, teoria, limitacoes e risco.
7. **Apresentacao:** PowerPoint, mini-paper e graficos em alta resolucao.

