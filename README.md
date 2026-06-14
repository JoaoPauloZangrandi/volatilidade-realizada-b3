# Volatilidade Realizada B3

Projeto do trabalho final da FGV EESP sobre volatilidade realizada, bipower variation, jumps e GARCH em acoes da B3 com dados intradiarios de 5 minutos.

## Entregaveis finais para avaliacao

Os dois arquivos abaixo sao autocontidos e foram preparados para serem avaliados
sem acesso ao restante do repositorio:

- [`Relatorio Final.html`](Relatório%20Final.html): relatorio completo com 23
  figuras embutidas, explicacao especifica apos cada grafico, 12 tabelas,
  metodologia, interpretacao, auditoria da rubrica, earnings,
  referencias e um ZIP interno contendo bases e tabelas.
- [`Codigo Final.py`](Código%20Final.py): pipeline unica para Google Colab, com
  snapshot comprimido das bases reais, todos os modulos analiticos, geracao dos
  outputs e testes internos.

## Status

Pipeline completa executada em 14 de junho de 2026 na branch `feature/trabalho-volatilidade-realizada-b3`. A reproducao integral usa:

```powershell
python scripts/run_all.py
```

## Fonte e limitacao principal

Na ausencia de uma base intradiaria local, o projeto usa `yfinance` com `period="60d"` e `interval="5m"`. O Yahoo Finance limita o historico intradiario disponivel. Portanto, os resultados representam uma janela recente, nao uma amostra historica longa, e o GARCH deve ser interpretado com cautela.

O `yfinance` e um cliente independente para APIs publicas do Yahoo Finance, destinado a pesquisa e uso educacional. Consulte os termos da fonte antes de redistribuir os dados.

## Amostras candidatas

- Core/liquida: PETR4, VALE3, ITUB4, BBDC4, B3SA3, WEGE3, ABEV3 e TOTS3.
- Growth/high-vol/small caps: LWSA3, MGLU3, BHIA3, CASH3, CVCB3, AZUL4 e VIIA3.

A amostra final e definida por criterios objetivos de cobertura, quantidade de dias validos, retornos por dia, precos positivos, volume e proporcao de precos parados.

## Resultados da execucao

Foram incluidos 11 ativos:

- Core/liquida: PETR4, VALE3, ITUB4, BBDC4, B3SA3, WEGE3, ABEV3 e TOTS3.
- Growth/high-vol: LWSA3, MGLU3 e CASH3.

Foram excluidos:

- BHIA3 e CVCB3: proporcao de precos parados acima do limite de 50%.
- AZUL4 e VIIA3: download vazio/possivel ticker descontinuado no Yahoo Finance.

Principais resultados observados:

- CASH3 apresentou a maior RVol anualizada media: 54,4%.
- O grupo core apresentou RVol anualizada media de 25,7%; o complementar, 49,4%.
- A frequencia media de jump days foi 11,0% no core e 27,2% no complementar.
- CASH3 e LWSA3 tiveram as maiores frequencias individuais de jumps, 36,7% e 35,0%.
- Os 11 modelos GARCH foram estimados, mas a amostra de 59 retornos diarios exige cautela.
- Foram analisados 12 eventos de earnings dentro da janela. A RVol media em
  t-1/t/t+1 ficou 16,7% acima dos dias normais; jump days foram 25,0% nas
  janelas contra 16,8% fora delas. A evidencia e descritiva, nao causal.

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

Outputs principais:

- `outputs/tables/data_coverage_by_ticker.csv`: qualidade, inclusao e exclusao.
- `outputs/tables/realized_measures_summary.csv`: RV, RVol, BV e JV.
- `outputs/tables/jump_summary.csv`: frequencia e intensidade dos jumps.
- `outputs/tables/garch_summary.csv`: parametros, persistencia e ajuste.
- `outputs/tables/asset_ranking_risk.csv`: ranking consolidado.
- `outputs/report/relatorio.md`: mini-paper final.
- `outputs/slides/trabalho_volatilidade_realizada_b3.pptx`: apresentacao final.

Para exportar os slides em PDF no Windows, abra o `.pptx` no PowerPoint e use `Arquivo > Exportar > Criar PDF/XPS`.

## Eventos

O arquivo `data/manual/events_earnings.csv` contem 12 datas obtidas via historico
de earnings do `yfinance` e documenta a fonte. Ele pode ser revisado ou
substituido por datas oficiais de RI. Sem eventos, a pipeline gera uma tabela
vazia com esquema valido e nao inventa datas.

## Checklist de entregaveis

- [x] Dados intradiarios baixados e organizados.
- [x] Limpeza, sincronizacao e retornos sem cruzar dias.
- [x] RV, RVol, BV, JV e teste de jumps.
- [x] GARCH(1,1) com retornos diarios.
- [x] Selecao automatica da amostra.
- [x] Analise de 12 eventos, com pipeline robusta a arquivo vazio.
- [x] Tabelas e graficos.
- [x] Relatorio em Markdown.
- [x] Slides em PowerPoint.
- [x] Notas no Obsidian.
- [x] Dez testes e pipeline completo.

## Checklist da Rubrica

1. **Tratamento e organizacao dos dados — 1,5:** limpeza, sessao efetiva, sincronizacao, retornos sem cruzar dias e auditoria de cobertura.
2. **Medidas de volatilidade — 2,0:** RV, RVol e BV implementadas, exportadas e testadas.
3. **Jumps — 1,5:** JV, tripower quarticity, estatistica BNS, tabela, graficos e interpretacao.
4. **Analise comparativa — 1,5:** ativos, periodos, grupos, correlacoes e eventos.
5. **Qualidade do codigo — 1,0:** pacote modular, YAML, logs, testes, pipeline unica e Codigo Final autocontido.
6. **Qualidade da analise — 2,0:** teoria, leitura apos cada grafico, limitacoes e implicacoes para risco.
7. **Apresentacao — 0,5:** PowerPoint, HTML autocontido, mini-paper e graficos em alta resolucao.

## Referencias de software

- Documentacao oficial do `arch`: https://bashtage.github.io/arch/
- Documentacao oficial do `yfinance`: https://ranaroussi.github.io/yfinance/
