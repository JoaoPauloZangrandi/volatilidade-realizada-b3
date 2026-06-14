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

