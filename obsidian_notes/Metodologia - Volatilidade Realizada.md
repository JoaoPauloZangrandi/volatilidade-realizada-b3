# Metodologia - Volatilidade Realizada

## Retornos

Retornos logaritmicos sao calculados por ticker e por dia, sem retorno entre o fechamento de um dia e a abertura do seguinte.

## Medidas

- RV: soma dos retornos intradiarios ao quadrado.
- RVol: raiz quadrada da RV.
- BV: variacao bipotente, estimador da variacao continua.
- JV: `max(RV - BV, 0)`.
- Jump test: estatistica baseada em BV e tripower quarticity.
- GARCH(1,1): volatilidade condicional estimada com retornos diarios close-to-close.

## Cuidado interpretativo

A RVol intradiaria nao inclui diretamente o retorno overnight, enquanto o GARCH close-to-close inclui. A comparacao e informativa, mas nao mede exatamente o mesmo objeto.

