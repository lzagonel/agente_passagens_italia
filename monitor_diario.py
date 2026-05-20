from __future__ import annotations

import argparse
import os
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from agente_passagens_italia import PedidoViagem, cidade_conhecida, escolher_modal, montar_links, rota_interna_italia, validar_data


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PADRAO = BASE_DIR / "dados" / "rotas_monitoramento.json"
RESULTADOS_DIR = BASE_DIR / "resultados"
PRECO_RE = re.compile(r"(?:EUR|BRL|R\$|USD|\$|\u20ac)\s*((?:[0-9]{1,3}(?:[.,][0-9]{3})+|[0-9]+)(?:[.,][0-9]{1,2})?)", re.IGNORECASE)


def carregar_config(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def validar_data_se_preenchida(valor: str, campo: str) -> str:
    return validar_data(valor, campo) if valor else ""


def descrever_janela(rota: dict, prefixo: str) -> str:
    data_fixa = rota.get(f"data_{prefixo}", "")
    if data_fixa:
        return validar_data(data_fixa, f"data_{prefixo}")

    inicio = validar_data_se_preenchida(rota.get(f"data_{prefixo}_inicio", ""), f"data_{prefixo}_inicio")
    fim = validar_data_se_preenchida(rota.get(f"data_{prefixo}_fim", ""), f"data_{prefixo}_fim")

    if inicio and fim:
        return f"{inicio} a {fim}"
    if inicio:
        return f"a partir de {inicio}"
    if fim:
        return f"ate {fim}"
    return "flexivel"


def data_para_busca(rota: dict, prefixo: str) -> str:
    data_fixa = rota.get(f"data_{prefixo}", "")
    if data_fixa:
        return validar_data(data_fixa, f"data_{prefixo}")

    inicio = validar_data_se_preenchida(rota.get(f"data_{prefixo}_inicio", ""), f"data_{prefixo}_inicio")
    fim = validar_data_se_preenchida(rota.get(f"data_{prefixo}_fim", ""), f"data_{prefixo}_fim")
    return inicio or fim or ""


def datas_da_rota(rota: dict, prefixo: str) -> list[str]:
    data_fixa = rota.get(f"data_{prefixo}", "")
    if data_fixa:
        return [validar_data(data_fixa, f"data_{prefixo}")]

    inicio = validar_data_se_preenchida(rota.get(f"data_{prefixo}_inicio", ""), f"data_{prefixo}_inicio")
    fim = validar_data_se_preenchida(rota.get(f"data_{prefixo}_fim", ""), f"data_{prefixo}_fim")
    if not inicio and not fim:
        return []

    inicio_dt = datetime.strptime(inicio or fim, "%Y-%m-%d")
    fim_dt = datetime.strptime(fim or inicio, "%Y-%m-%d")
    if fim_dt < inicio_dt:
        raise ValueError(f"data_{prefixo}_fim deve ser maior ou igual a data_{prefixo}_inicio.")

    datas = []
    atual = inicio_dt
    while atual <= fim_dt:
        datas.append(atual.strftime("%Y-%m-%d"))
        atual += timedelta(days=1)
    return datas


def montar_pedido(config: dict, rota: dict) -> PedidoViagem:
    return PedidoViagem(
        origem=rota["origem"],
        destino=rota["destino"],
        data_ida=data_para_busca(rota, "ida"),
        data_volta=data_para_busca(rota, "volta"),
        viajantes=int(rota.get("viajantes", config.get("viajantes", 1))),
        preferencia=rota.get("preferencia", config.get("preferencia", "menor preco")),
        bagagem=rota.get("bagagem", config.get("bagagem", "bagagem leve")),
        janela_horario=rota.get("janela_horario", config.get("janela_horario", "qualquer horario")),
    )


def normalizar_preco(valor: str) -> float:
    return float(valor.replace(".", "").replace(",", "."))


def normalizar_preco_generico(valor: object) -> float | None:
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        return None

    match = PRECO_RE.search(valor)
    numero = match.group(1) if match else re.sub(r"[^0-9,.]", "", valor)
    if not numero:
        return None
    try:
        return normalizar_preco(numero)
    except ValueError:
        return None


def buscar_precos_em_url(url: str, timeout: int = 20) -> list[float]:
    requisicao = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgentePassagensItalia/1.0)",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,it;q=0.7",
        },
    )
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        html = resposta.read(2_000_000).decode("utf-8", errors="ignore")
    return sorted({normalizar_preco(match) for match in PRECO_RE.findall(html)})


def extrair_precos_json(valor: object) -> list[float]:
    precos = []
    if isinstance(valor, dict):
        for chave, conteudo in valor.items():
            if chave in {"price", "total_price"}:
                preco = normalizar_preco_generico(conteudo)
                if preco is not None:
                    precos.append(preco)
            precos.extend(extrair_precos_json(conteudo))
    elif isinstance(valor, list):
        for item in valor:
            precos.extend(extrair_precos_json(item))
    return precos


def extrair_opcoes_serpapi(dados: dict, data_ida: str, data_volta: str, max_escalas: int | None) -> list[dict]:
    opcoes = []
    for grupo in ("best_flights", "other_flights"):
        for voo in dados.get(grupo, []) or []:
            preco = normalizar_preco_generico(voo.get("price") or voo.get("total_price"))
            trechos = voo.get("flights") or []
            escalas = max(len(trechos) - 1, 0)

            if preco is None:
                continue
            if max_escalas is not None and escalas > max_escalas:
                continue

            companhias = []
            for trecho in trechos:
                companhia = trecho.get("airline")
                if companhia and companhia not in companhias:
                    companhias.append(companhia)

            opcoes.append(
                {
                    "preco": preco,
                    "data_ida": data_ida,
                    "data_volta": data_volta,
                    "escalas": escalas,
                    "companhias": ", ".join(companhias) if companhias else "nao informado",
                    "duracao_min": voo.get("total_duration"),
                }
            )

    return sorted(opcoes, key=lambda opcao: opcao["preco"])


def consultar_serpapi_voos(pedido: PedidoViagem, rota: dict, moeda: str, api_key: str) -> list[dict]:
    origem = cidade_conhecida(pedido.origem)
    destino = cidade_conhecida(pedido.destino)
    if not origem or not destino or rota_interna_italia(origem, destino):
        return []

    idas = datas_da_rota(rota, "ida")
    voltas = datas_da_rota(rota, "volta") or [""]
    max_consultas = int(rota.get("max_consultas_serpapi", 12))
    max_escalas = rota.get("max_escalas")
    max_escalas = int(max_escalas) if max_escalas is not None else None
    resultados = []

    for data_ida in idas:
        for data_volta in voltas:
            if len(resultados) >= max_consultas:
                return resultados

            parametros = {
                "engine": "google_flights",
                "departure_id": origem["iata"],
                "arrival_id": destino["iata"],
                "outbound_date": data_ida,
                "currency": moeda,
                "hl": "pt",
                "gl": "br",
                "num_adults": str(pedido.viajantes),
                "api_key": api_key,
            }
            if data_volta:
                parametros["return_date"] = data_volta
                parametros["type"] = "1"
            else:
                parametros["type"] = "2"

            url = "https://serpapi.com/search.json?" + urlencode(parametros)
            item = {
                "fonte": "SerpApi Google Flights",
                "url": url.replace(api_key, "***"),
                "precos": [],
                "erro": "",
                "data_ida": data_ida,
                "data_volta": data_volta,
            }

            try:
                with urllib.request.urlopen(url, timeout=40) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
                if "error" in dados:
                    item["erro"] = str(dados["error"])
                item["opcoes"] = extrair_opcoes_serpapi(dados, data_ida, data_volta, max_escalas)
                item["precos"] = [opcao["preco"] for opcao in item["opcoes"]]
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                item["erro"] = str(exc)

            resultados.append(item)

    return resultados


def consultar_fontes(pedido: PedidoViagem, rota: dict, moeda: str, consultar_web: bool, serpapi_key: str) -> list[dict]:
    resultados = []
    if serpapi_key:
        resultados.extend(consultar_serpapi_voos(pedido, rota, moeda, serpapi_key))

    fontes_com_html_confiavel = set(rota.get("fontes_html_confiaveis", []))
    for nome, url in montar_links(pedido).items():
        item = {"fonte": nome, "url": url, "precos": [], "erro": ""}

        if consultar_web and nome in fontes_com_html_confiavel:
            try:
                item["precos"] = buscar_precos_em_url(url)[:5]
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                item["erro"] = str(exc)

        resultados.append(item)
    return resultados


def link_google_flights_iata(origem_iata: str, destino_iata: str, data_ida: str, data_volta: str) -> str:
    consulta = f"{origem_iata} to {destino_iata} {data_ida}"
    if data_volta:
        consulta += f" return {data_volta}"
    return "https://www.google.com/travel/flights?q=" + urlencode({"": consulta})[1:]


def adicionar_links_melhores_opcoes(pedido: PedidoViagem, opcoes: list[dict]) -> list[dict]:
    origem = cidade_conhecida(pedido.origem)
    destino = cidade_conhecida(pedido.destino)
    if not origem or not destino:
        return opcoes

    for opcao in opcoes:
        opcao["link"] = link_google_flights_iata(
            origem["iata"],
            destino["iata"],
            opcao["data_ida"],
            opcao["data_volta"],
        )
    return opcoes


def montar_dados_monitoramento(config: dict, consultar_web: bool) -> dict:
    rotas = [rota for rota in config.get("rotas", []) if rota.get("ativa", True)]
    dados = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "moeda": config.get("moeda", "EUR"),
        "rotas": [],
        "alertas": [],
    }
    serpapi_key = os.getenv("SERPAPI_API_KEY", "")

    for rota in rotas:
        pedido = montar_pedido(config, rota)
        modal, motivos = escolher_modal(pedido)
        fontes = consultar_fontes(pedido, rota, dados["moeda"], consultar_web, serpapi_key)
        precos = [preco for fonte in fontes for preco in fonte["precos"]]
        opcoes = [opcao for fonte in fontes for opcao in fonte.get("opcoes", [])]
        opcoes_ordenadas = adicionar_links_melhores_opcoes(pedido, sorted(opcoes, key=lambda opcao: opcao["preco"]))
        menor_preco = min(precos) if precos else None
        preco_alvo = rota.get("preco_alvo")
        alerta = bool(menor_preco is not None and preco_alvo is not None and menor_preco <= float(preco_alvo))

        item = {
            "nome": rota.get("nome", f"{pedido.origem} -> {pedido.destino}"),
            "origem": pedido.origem,
            "destino": pedido.destino,
            "data_ida": pedido.data_ida,
            "janela_ida": descrever_janela(rota, "ida"),
            "data_volta": pedido.data_volta,
            "janela_volta": descrever_janela(rota, "volta"),
            "viajantes": pedido.viajantes,
            "preferencia": pedido.preferencia,
            "preco_alvo": preco_alvo,
            "recomendacao_base": modal,
            "motivos": motivos,
            "fontes": fontes,
            "melhores_opcoes": opcoes_ordenadas[: int(rota.get("max_opcoes_relatorio", 3))],
            "menor_preco": menor_preco,
            "alerta_preco": alerta,
        }
        dados["rotas"].append(item)

        if alerta:
            dados["alertas"].append(
                {
                    "rota": item["nome"],
                    "menor_preco": menor_preco,
                    "preco_alvo": preco_alvo,
                    "moeda": dados["moeda"],
                }
            )

    return dados


def gerar_relatorio_monitoramento(config: dict, consultar_web: bool = False) -> tuple[str, dict]:
    dados = montar_dados_monitoramento(config, consultar_web)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    moeda = dados["moeda"]
    rotas = dados["rotas"]

    linhas = [
        "RELATORIO DIARIO - PASSAGENS ITALIA",
        f"Gerado em: {agora}",
        f"Consulta web: {'sim' if consultar_web else 'nao'}",
        "",
        f"Rotas monitoradas: {len(rotas)}",
        "",
    ]

    if not rotas:
        linhas.append("Nenhuma rota ativa em dados/rotas_monitoramento.json.")
        return "\n".join(linhas), dados

    for indice, rota in enumerate(dados["rotas"], start=1):
        preco_alvo = rota.get("preco_alvo")
        alerta = f"preco alvo: {moeda} {preco_alvo}" if preco_alvo else "sem preco alvo"
        menor = f"{moeda} {rota['menor_preco']:.2f}" if rota["menor_preco"] is not None else "nao confirmado"
        acao = "COMPRAR/CONFERIR AGORA" if rota["alerta_preco"] else "acompanhar"

        linhas.extend(
            [
                f"{indice}. {rota['nome']}",
                f"   Rota: {rota['origem']} -> {rota['destino']}",
                f"   Ida: {rota['janela_ida']}",
                f"   Volta: {rota['janela_volta']}",
                f"   Viajantes: {rota['viajantes']}",
                f"   Preferencia: {rota['preferencia']}",
                f"   Monitoramento: {alerta}",
                f"   Menor preco encontrado: {menor}",
                f"   Acao: {acao}",
                f"   Recomendacao base: {rota['recomendacao_base']}",
                f"   Por que: {'; '.join(rota['motivos'])}",
                "   Fontes:",
            ]
        )

        for fonte in rota["fontes"]:
            if fonte.get("opcoes"):
                linhas.append(f"   - {fonte['fonte']}: {len(fonte['opcoes'])} opcoes dentro dos filtros")
            else:
                status = fonte["erro"] if fonte.get("erro") else "sem preco extraido automaticamente"
                linhas.append(f"   - {fonte['fonte']}: {status} | {fonte['url']}")

        if rota.get("melhores_opcoes"):
            linhas.append("   Melhores opcoes:")
            for posicao, opcao in enumerate(rota["melhores_opcoes"], start=1):
                volta = f" / volta {opcao['data_volta']}" if opcao["data_volta"] else ""
                duracao = f", duracao {opcao['duracao_min']} min" if opcao.get("duracao_min") else ""
                linhas.append(
                    f"   {posicao}. {moeda} {opcao['preco']:.2f} | ida {opcao['data_ida']}{volta} | "
                    f"{opcao['escalas']} escala(s) | {opcao['companhias']}{duracao}"
                )
                if opcao.get("link"):
                    linhas.append(f"      Link: {opcao['link']}")

        linhas.append("")

    linhas.extend(
        [
            "Observacao:",
            "A extracao automatica e de melhor esforco. Sites de passagens podem bloquear bots ou renderizar precos apenas no navegador.",
        ]
    )
    return "\n".join(linhas), dados


def salvar_relatorio(conteudo: str) -> Path:
    RESULTADOS_DIR.mkdir(exist_ok=True)
    nome = "relatorio_passagens_" + datetime.now().strftime("%Y-%m-%d") + ".txt"
    caminho = RESULTADOS_DIR / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera relatorio diario de monitoramento de passagens.")
    parser.add_argument("--config", type=Path, default=CONFIG_PADRAO)
    parser.add_argument("--salvar", action="store_true", help="Salva o relatorio em resultados/.")
    parser.add_argument("--consultar-web", action="store_true", help="Tenta extrair precos atuais das fontes.")
    parser.add_argument("--json-saida", type=Path, help="Salva dados estruturados em JSON.")
    parser.add_argument("--falhar-com-alerta", action="store_true", help="Retorna exit code 2 quando houver preco abaixo do alvo.")
    args = parser.parse_args()

    config = carregar_config(args.config)
    relatorio, dados = gerar_relatorio_monitoramento(config, consultar_web=args.consultar_web)
    print(relatorio)

    if args.salvar:
        caminho = salvar_relatorio(relatorio)
        print(f"\nRelatorio salvo em: {caminho}")

    if args.json_saida:
        args.json_saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.falhar_com_alerta and dados["alertas"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
