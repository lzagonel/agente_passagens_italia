# Agente de Passagens da Italia

Agente CLI em Python para organizar buscas de passagens durante uma viagem pela Italia.
Ele coleta os dados da viagem, sugere o modal mais adequado, monta links de busca e gera
uma recomendacao resumida.

## Como rodar

```powershell
cd "C:\Users\leooz\Downloads\agente_passagens_italia"
.\executar_agente.bat
```

Ao final, ele pergunta se deve abrir as pesquisas no navegador. Para abrir direto:

```powershell
C:\Users\leooz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\agente_passagens_italia.py --abrir
```

Tambem da para testar com um exemplo pronto:

```powershell
C:\Users\leooz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\agente_passagens_italia.py --exemplo dados\exemplos_viagens.json --abrir
```

## O que ele faz agora

- Coleta origem, destino, datas, numero de viajantes e preferencias.
- Prioriza trem para trechos internos classicos da Italia.
- Sugere voo quando a distancia estimada tende a favorecer aeroportos.
- Monta links de busca para Google Flights, Kayak, Rome2Rio, Trenitalia, Italo e Omio conforme a rota.
- Gera uma checklist para comparar preco total, bagagem, troca, assentos e horarios.
- Gera relatorios diarios a partir de `dados/rotas_monitoramento.json`.

## Monitoramento diario

Edite as rotas em:

```powershell
notepad .\dados\rotas_monitoramento.json
```

Para gerar apenas o relatorio, sem abrir pesquisas:

```powershell
.\executar_relatorio_diario.bat
```

Ou diretamente:

```powershell
C:\Users\leooz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\monitor_diario.py --salvar
```

## Monitoramento no GitHub

O workflow em `.github/workflows/monitor-passagens.yml` roda 3 vezes ao dia:

- 08:00 no horario de Sao Paulo
- 14:00 no horario de Sao Paulo
- 20:00 no horario de Sao Paulo

Ele gera um resumo no GitHub Actions, salva um artefato com o relatorio e cria uma issue
quando encontrar preco menor ou igual ao `preco_alvo` da rota.

## Extracao real de precos

Google Flights e Kayak normalmente renderizam precos via JavaScript e podem bloquear scraping simples.
Para obter precos estruturados, configure uma chave da SerpApi:

1. Crie uma conta em `https://serpapi.com/`.
2. Copie sua API key.
3. No GitHub, va em `Settings > Secrets and variables > Actions > New repository secret`.
4. Crie o secret `SERPAPI_API_KEY` com o valor da chave.
5. Rode o workflow novamente em `Actions > Monitor de passagens Italia > Run workflow`.

Com `SERPAPI_API_KEY`, o monitor consulta Google Flights via API e compara o menor preco encontrado
com `preco_alvo`.

Para controlar o custo/uso da API em janelas flexiveis, cada rota pode ter:

```json
"max_consultas_serpapi": 12
```

A janela atual Curitiba/Roma tem 6 dias possiveis de ida e 6 de volta, ou seja, 36 combinacoes.
Com `max_consultas_serpapi: 12`, o monitor consulta as 12 primeiras combinacoes por execucao.

## Email opcional

Para receber email, configure estes Secrets no repositorio:

- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

## Proximos passos bons

- Salvar historico de precos em uma planilha.
- Ajustar estrategia de busca para consultar todas as combinacoes da janela.
- Adicionar alertas por rota e data.
- Criar uma interface web simples.
