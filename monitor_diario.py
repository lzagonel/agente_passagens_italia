from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from agente_passagens_italia import PedidoViagem, escolher_modal, montar_links, validar_data


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PADRAO = BASE_DIR / "dados" / "rotas_monitoramento.json"
RESULTADOS_DIR = BASE_DIR / "resultados"
PRECO_RE = re.compile(r"(?:EUR|\u20ac)\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.IGNORECASE)


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


def consultar_fontes(pedido: PedidoViagem, consultar_web: bool) -> list[dict]:
    resultados = []
    for nome, url in montar_links(pedido).items():
        item = {"fonte": nome, "url": url, "precos": [], "erro": ""}

        if consultar_web:
            try:
                item["precos"] = buscar_precos_em_url(url)[:5]
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                item["erro"] = str(exc)

        resultados.append(item)
    return resultados


def montar_dados_monitoramento(config: dict, consultar_web: bool) -> dict:
    rotas = [rota for rota in config.get("rotas", []) if rota.get("ativa", True)]
    dados = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "moeda": config.get("moeda", "EUR"),
        "rotas": [],
        "alertas": [],
    }

    for rota in rotas:
        pedido = montar_pedido(config, rota)
        modal, motivos = escolher_modal(pedido)
        fontes = consultar_fontes(pedido, consultar_web)
        precos = [preco for fonte in fontes for preco in fonte["precos"]]
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
            precos = ", ".join(f"{moeda} {preco:.2f}" for preco in fonte["precos"])
            status = precos if precos else "sem preco extraido automaticamente"
            linhas.append(f"   - {fonte['fonte']}: {status} | {fonte['url']}")

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
