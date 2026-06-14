# Trabalho - Volatilidade Realizada B3

## Objetivo

Estimar volatilidade realizada e jumps em acoes da B3, comparar uma amostra liquida com candidatas growth/high-vol/small caps e discutir implicacoes para gestao de risco.

## Repositorio

`https://github.com/JoaoPauloZangrandi/volatilidade-realizada-b3`

## Execucao

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/run_all.py
```

## Fonte

Dados intradiarios de 5 minutos obtidos via `yfinance`, com janela maxima recente imposta pelo Yahoo Finance.

## Entregaveis

- Dados organizados em `data/`.
- Tabelas e figuras em `outputs/`.
- Relatorio em `report/relatorio.md`.
- Slides em `outputs/slides/`.

