# Automacao diaria do agente de passagens da Italia

Leia `dados/rotas_monitoramento.json` neste projeto. Para cada rota ativa:

1. Consulte opcoes atuais de trem, onibus e voo quando fizer sentido.
2. Priorize fontes como Trenitalia, Italo, Omio, Rome2Rio e Google Flights.
3. Compare melhor preco, melhor horario, tempo total, conexoes/trocas e politica de bagagem.
4. Compare com `preco_alvo`, quando existir.
5. Entregue apenas um relatorio curto em portugues.

Formato do relatorio:

- Data da consulta.
- Resumo executivo com a melhor acao: comprar, esperar ou acompanhar.
- Uma tabela curta por rota com menor preco encontrado, fonte, horario, duracao e link.
- Alertas objetivos, como preco abaixo do alvo, aumento relevante, risco de pouca disponibilidade ou horario ruim.
- Nada de abrir navegador para o usuario e nada de mensagens intermediarias.
