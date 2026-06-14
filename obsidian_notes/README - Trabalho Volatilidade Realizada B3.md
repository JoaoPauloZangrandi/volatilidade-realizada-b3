# Trabalho - Volatilidade Realizada B3

## Objetivo

Estimar volatilidade realizada, separar variacao continua e jumps, comparar ativos liquidos com growth/high-vol e discutir gestao de risco.

## Repositorio

`https://github.com/JoaoPauloZangrandi/volatilidade-realizada-b3`

## Amostra executada

Incluidos: PETR4.SA, VALE3.SA, ITUB4.SA, BBDC4.SA, B3SA3.SA, WEGE3.SA, ABEV3.SA, TOTS3.SA, LWSA3.SA, MGLU3.SA, CASH3.SA.

Excluidos:

- BHIA3.SA: precos parados 51.9% acima do maximo
- CVCB3.SA: precos parados 51.1% acima do maximo
- AZUL4.SA: download vazio
- VIIA3.SA: download vazio

## Execucao

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/run_all.py
```

## Entregaveis

- Relatorio: `outputs/report/relatorio.md`.
- Slides: `outputs/slides/trabalho_volatilidade_realizada_b3.pptx`.
- Tabelas: `outputs/tables/`.
- Figuras: `outputs/figures/`.

## Limitacao central

O historico intradiario do Yahoo Finance e curto. GARCH e jumps devem ser interpretados junto com cobertura e liquidez.
