# Metodologia - Volatilidade Realizada

## Retornos

Retornos logaritmicos sao calculados por ticker e por dia, sem retorno entre o fechamento de um dia e a abertura do seguinte.

## Sincronizacao

- O teto configurado da sessao e 17:55.
- A fonte sustentou regularmente candles ate 16:50.
- O pipeline exige suporte em pelo menos 80% dos ticker-dias e usa 16:50 como fechamento efetivo.
- A grade final tem 83 candles de cinco minutos.
- O forward-fill ocorre apenas dentro do dia e nao prolonga artificialmente o preco ate 17:55.

## Medidas

- RV: soma dos retornos intradiarios ao quadrado.
- RVol: raiz quadrada da RV.
- BV: variacao bipotente, estimador da variacao continua.
- JV: `max(RV - BV, 0)`.
- Jump test: estatistica baseada em BV e tripower quarticity.
- GARCH(1,1): volatilidade condicional estimada com retornos diarios close-to-close.

## Cuidado interpretativo

A RVol intradiaria nao inclui diretamente o retorno overnight, enquanto o GARCH close-to-close inclui. A comparacao e informativa, mas nao mede exatamente o mesmo objeto.

O Relatorio Final inclui uma leitura numerica, economica, de risco e de cautela
apos cada um dos 23 graficos, alem de uma auditoria formal dos 10 pontos da
rubrica do Tema 1.
