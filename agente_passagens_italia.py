from __future__ import annotations

import argparse
import json
import unicodedata
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus


CIDADES = {
    "curitiba": {"nome": "Curitiba", "estacao": "Curitiba", "iata": "CWB", "pais": "BR"},
    "roma": {"nome": "Roma", "estacao": "Roma Termini", "iata": "FCO", "pais": "IT"},
    "florenca": {"nome": "Florenca", "estacao": "Firenze Santa Maria Novella", "iata": "FLR", "pais": "IT"},
    "veneza": {"nome": "Veneza", "estacao": "Venezia Santa Lucia", "iata": "VCE", "pais": "IT"},
    "milao": {"nome": "Milao", "estacao": "Milano Centrale", "iata": "MXP", "pais": "IT"},
    "napoles": {"nome": "Napoles", "estacao": "Napoli Centrale", "iata": "NAP", "pais": "IT"},
    "bolonha": {"nome": "Bolonha", "estacao": "Bologna Centrale", "iata": "BLQ", "pais": "IT"},
    "pisa": {"nome": "Pisa", "estacao": "Pisa Centrale", "iata": "PSA", "pais": "IT"},
    "turim": {"nome": "Turim", "estacao": "Torino Porta Nuova", "iata": "TRN", "pais": "IT"},
    "verona": {"nome": "Verona", "estacao": "Verona Porta Nuova", "iata": "VRN", "pais": "IT"},
}

TRECHOS_TREM_FORTES = {
    ("roma", "florenca"),
    ("florenca", "veneza"),
    ("roma", "napoles"),
    ("milao", "veneza"),
    ("milao", "florenca"),
    ("bolonha", "florenca"),
    ("verona", "veneza"),
}


@dataclass
class PedidoViagem:
    origem: str
    destino: str
    data_ida: str
    data_volta: str
    viajantes: int
    preferencia: str
    bagagem: str
    janela_horario: str


def normalizar_cidade(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor.strip().lower())
    return "".join(caractere for caractere in texto if not unicodedata.combining(caractere))


def validar_data(valor: str, campo: str) -> str:
    if not valor:
        return ""
    try:
        datetime.strptime(valor, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{campo} deve estar no formato AAAA-MM-DD.") from exc
    return valor


def carregar_exemplo(caminho: Path) -> PedidoViagem:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return PedidoViagem(
        origem=dados["origem"],
        destino=dados["destino"],
        data_ida=validar_data(dados["data_ida"], "data_ida"),
        data_volta=validar_data(dados.get("data_volta", ""), "data_volta"),
        viajantes=int(dados.get("viajantes", 1)),
        preferencia=dados.get("preferencia", "equilibrio entre preco e tempo"),
        bagagem=dados.get("bagagem", "bagagem leve"),
        janela_horario=dados.get("janela_horario", "qualquer horario"),
    )


def perguntar() -> PedidoViagem:
    origem = input("Origem: ").strip()
    destino = input("Destino: ").strip()
    data_ida = validar_data(input("Data de ida (AAAA-MM-DD): ").strip(), "data_ida")
    data_volta = validar_data(input("Data de volta, se houver (AAAA-MM-DD): ").strip(), "data_volta")
    viajantes = int(input("Numero de viajantes: ").strip() or "1")
    preferencia = input("Preferencia (menor preco, menor tempo total, conforto): ").strip()
    bagagem = input("Bagagem: ").strip()
    janela_horario = input("Janela de horario desejada: ").strip()

    return PedidoViagem(
        origem=origem,
        destino=destino,
        data_ida=data_ida,
        data_volta=data_volta,
        viajantes=viajantes,
        preferencia=preferencia or "equilibrio entre preco e tempo",
        bagagem=bagagem or "bagagem leve",
        janela_horario=janela_horario or "qualquer horario",
    )


def cidade_conhecida(cidade: str) -> dict[str, str] | None:
    return CIDADES.get(normalizar_cidade(cidade))


def rota_interna_italia(origem: dict[str, str] | None, destino: dict[str, str] | None) -> bool:
    return bool(origem and destino and origem.get("pais") == "IT" and destino.get("pais") == "IT")


def escolher_modal(pedido: PedidoViagem) -> tuple[str, list[str]]:
    origem = normalizar_cidade(pedido.origem)
    destino = normalizar_cidade(pedido.destino)
    par = (origem, destino)
    par_inverso = (destino, origem)
    origem_ok = cidade_conhecida(pedido.origem)
    destino_ok = cidade_conhecida(pedido.destino)
    motivos = []

    if not rota_interna_italia(origem_ok, destino_ok):
        motivos.append("rota internacional; voo deve ser a fonte principal")
        motivos.append("comparar conexoes, bagagem e chegada em FCO")
        return "voo internacional", motivos

    if par in TRECHOS_TREM_FORTES or par_inverso in TRECHOS_TREM_FORTES:
        motivos.append("trecho italiano bem servido por trem rapido")
        motivos.append("evita deslocamento e antecedencia de aeroporto")
        return "trem", motivos

    motivos.append("rota interna na Italia; comparar trem antes de voo costuma valer a pena")
    return "comparar trem e onibus", motivos


def montar_links(pedido: PedidoViagem) -> dict[str, str]:
    origem = cidade_conhecida(pedido.origem) or {"nome": pedido.origem, "estacao": pedido.origem, "iata": pedido.origem, "pais": ""}
    destino = cidade_conhecida(pedido.destino) or {"nome": pedido.destino, "estacao": pedido.destino, "iata": pedido.destino, "pais": ""}
    origem_busca = quote_plus(origem["nome"])
    destino_busca = quote_plus(destino["nome"])
    data = quote_plus(pedido.data_ida)
    consulta_voo = f"{origem['iata']} to {destino['iata']} {pedido.data_ida}"
    kayak_trecho = f"{origem['iata']}-{destino['iata']}/{pedido.data_ida}"

    if pedido.data_volta:
        consulta_voo += f" return {pedido.data_volta}"
        kayak_trecho += f"/{pedido.data_volta}"

    google_flights = "https://www.google.com/travel/flights?q=" + quote_plus(consulta_voo)

    if not rota_interna_italia(origem, destino):
        return {
            "Google Flights": google_flights,
            "Kayak": "https://www.kayak.com.br/flights/" + quote_plus(kayak_trecho),
            "Rome2Rio": f"https://www.rome2rio.com/map/{origem_busca}/{destino_busca}",
        }

    return {
        "Trenitalia": "https://www.trenitalia.com/",
        "Italo": "https://www.italotreno.it/en",
        "Omio": f"https://www.omio.com/search-frontend/results/{origem_busca}/{destino_busca}/{data}",
        "Rome2Rio": f"https://www.rome2rio.com/map/{origem_busca}/{destino_busca}",
        "Google Flights": google_flights,
    }


def gerar_relatorio(pedido: PedidoViagem) -> str:
    modal, motivos = escolher_modal(pedido)
    links = montar_links(pedido)
    volta = pedido.data_volta if pedido.data_volta else "sem volta definida"

    linhas = [
        "AGENTE DE PASSAGENS DA ITALIA",
        "",
        f"Rota: {pedido.origem} -> {pedido.destino}",
        f"Ida: {pedido.data_ida} | Volta: {volta}",
        f"Viajantes: {pedido.viajantes}",
        f"Preferencia: {pedido.preferencia}",
        f"Bagagem: {pedido.bagagem}",
        f"Horario desejado: {pedido.janela_horario}",
        "",
        f"Recomendacao inicial: {modal.upper()}",
        "Motivos:",
    ]

    linhas.extend(f"- {motivo}" for motivo in motivos)
    linhas.extend(
        [
            "",
            "Checklist de compra:",
            "- comparar preco final com taxas e bagagem",
            "- verificar troca/cancelamento antes de pagar",
            "- checar chegada ao centro versus aeroporto distante",
            "- confirmar plataforma/estacao correta no dia anterior",
            "- salvar bilhetes offline no celular",
            "",
            "Links de busca:",
        ]
    )
    linhas.extend(f"- {nome}: {url}" for nome, url in links.items())
    return "\n".join(linhas)


def abrir_pesquisas(pedido: PedidoViagem) -> None:
    links = montar_links(pedido)

    print("\nAbrindo pesquisas no navegador...")
    for nome, url in links.items():
        print(f"- {nome}: {url}")
        webbrowser.open(url, new=2)


def confirmar_abertura() -> bool:
    resposta = input("\nAbrir as pesquisas no navegador? [S/n]: ").strip().lower()
    return resposta in {"", "s", "sim", "y", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de passagens para viagem na Italia.")
    parser.add_argument("--exemplo", type=Path, help="Caminho para um JSON de exemplo.")
    parser.add_argument("--abrir", action="store_true", help="Abre automaticamente os sites de busca.")
    parser.add_argument("--nao-abrir", action="store_true", help="Nao pergunta e nao abre os sites de busca.")
    args = parser.parse_args()

    pedido = carregar_exemplo(args.exemplo) if args.exemplo else perguntar()
    print(gerar_relatorio(pedido))

    if args.abrir:
        abrir_pesquisas(pedido)
    elif not args.nao_abrir and confirmar_abertura():
        abrir_pesquisas(pedido)


if __name__ == "__main__":
    main()
