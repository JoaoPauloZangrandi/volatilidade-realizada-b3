# Eventos de resultados

Preencha `events_earnings.csv` somente com eventos verificados, mantendo as colunas:

```text
ticker,date,event_type,event_description
PETR4.SA,2026-05-12,earnings,Divulgacao de resultados trimestrais
```

- Use datas no formato `YYYY-MM-DD`.
- Use o ticker com sufixo `.SA`.
- Nao inclua linhas comentadas no CSV.
- O pipeline funciona normalmente quando o arquivo contem apenas o cabecalho.
- Para cada evento preenchido, a analise compara os pregoes `t-1`, `t` e `t+1`.

## Eventos usados na entrega final

Na entrega gerada em 14 de junho de 2026, o arquivo foi preenchido com o
historico de earnings retornado por `yfinance.Ticker(...).get_earnings_dates()`
para datas dentro da janela intradiaria de 17 de marco a 12 de junho de 2026.

Essa fonte e terceirizada e pode revisar datas ou valores. Os eventos sao usados
como analise descritiva, sem interpretacao causal. Para uma versao definitiva
baseada em fonte primaria, recomenda-se conferir cada data no site de Relacoes
com Investidores da companhia.
