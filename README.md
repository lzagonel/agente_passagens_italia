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
- Monta links de busca para Trenitalia, Italo, Google Flights, Omio e Rome2Rio.
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

Para receber email, configure estes Secrets no repositorio:

- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

O monitor tenta extrair precos automaticamente das paginas, mas isso e de melhor esforco:
sites de passagens podem bloquear bots ou renderizar precos apenas no navegador.

## Proximos passos bons

- Integrar scraping/automacao com navegador, se voce quiser comparar precos em tempo real.
- Salvar resultados em uma planilha.
- Adicionar alertas de preco por rota e data.
- Criar uma interface web simples.
