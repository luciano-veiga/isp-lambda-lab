"""
simulate_ixc.py
-----------------
Simulador de eventos do IXC Provider, exclusivo para o lab. Gera
aberturas de OS para clientes fictícios (data/clientes.json) e
dispara o webhook para a Lambda `ixc-os-retencao` publicada no
MiniStack. Não se conecta a nenhum sistema real.

Uso:
  export API_URL="http://localhost:4566/restapis/<api_id>/lab/_user_request_"
  export API_TOKEN="<token gerado pelo setup_ministack.sh>"

  # Um evento aleatório
  python3 simulate_ixc.py

  # Forçar cenário de repetição (3ª OS em 90 dias) num cliente específico
  python3 simulate_ixc.py --cliente-id 12345 --forcar-repeticao

  # Disparar eventos continuamente, um a cada N segundos
  python3 simulate_ixc.py --loop --intervalo 15
"""

import os
import json
import random
import argparse
import time
from datetime import datetime, timedelta
import requests

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "clientes.json")
TIPOS_OS = ["Sem conexão", "Lentidão", "Instabilidade", "Troca de equipamento", "Dúvida de fatura"]

API_URL = os.environ.get("API_URL", "http://localhost:4566/restapis/REPLACE_ME/lab/_user_request_")
API_TOKEN = os.environ.get("API_TOKEN", "REPLACE_ME")
HEADERS = {"Content-Type": "application/json", "x-api-key": API_TOKEN}


def carregar_clientes():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_clientes(clientes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=2)


def gerar_evento(cliente, forcar_repeticao=False):
    agora = datetime.utcnow()

    if forcar_repeticao:
        # garante duas OS anteriores dentro dos últimos 90 dias, para
        # forçar o gatilho de prioridade ALTA (3ª OS)
        cliente["historico_os"] = [
            {
                "os_id": f"OS{random.randint(90000, 99999)}",
                "tipo_os": random.choice(TIPOS_OS),
                "data_abertura": (agora - timedelta(days=random.randint(5, 40))).isoformat(),
            },
            {
                "os_id": f"OS{random.randint(90000, 99999)}",
                "tipo_os": random.choice(TIPOS_OS),
                "data_abertura": (agora - timedelta(days=random.randint(41, 85))).isoformat(),
            },
        ]

    nova_os_id = f"OS{random.randint(90000, 99999)}"
    payload = {
        "cliente_id": cliente["cliente_id"],
        "cliente_nome": cliente["nome"],
        "os_id": nova_os_id,
        "tipo_os": random.choice(TIPOS_OS),
        "data_abertura": agora.isoformat(),
        # cópia da lista: sem isso, o append logo abaixo mutaria o
        # mesmo objeto referenciado aqui, duplicando a OS atual no payload
        "historico_os": list(cliente.get("historico_os", [])),
    }

    # persiste a nova OS no histórico do cliente fictício, para que o
    # próximo evento já "lembre" dela
    cliente.setdefault("historico_os", []).append({
        "os_id": nova_os_id,
        "tipo_os": payload["tipo_os"],
        "data_abertura": payload["data_abertura"],
    })

    return payload


def enviar(payload):
    resp = requests.post(f"{API_URL}/ixc-webhook", headers=HEADERS, json=payload)
    print(f"[IXC] cliente={payload['cliente_nome']} os={payload['os_id']} -> {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)


def main():
    parser = argparse.ArgumentParser(description="Simulador de eventos do IXC (apenas lab)")
    parser.add_argument("--cliente-id", help="ID do cliente específico (senão escolhe aleatório)")
    parser.add_argument("--forcar-repeticao", action="store_true", help="Força histórico de 2 OS recentes")
    parser.add_argument("--loop", action="store_true", help="Dispara eventos continuamente")
    parser.add_argument("--intervalo", type=int, default=15, help="Segundos entre eventos no modo --loop")
    args = parser.parse_args()

    clientes = carregar_clientes()

    def ciclo():
        if args.cliente_id:
            cliente = next((c for c in clientes if c["cliente_id"] == args.cliente_id), None)
        else:
            cliente = random.choice(clientes)

        if cliente is None:
            print("Cliente não encontrado em data/clientes.json")
            return

        payload = gerar_evento(cliente, forcar_repeticao=args.forcar_repeticao)
        enviar(payload)
        salvar_clientes(clientes)

    if args.loop:
        print(f"Disparando eventos IXC a cada {args.intervalo}s (Ctrl+C para parar)...")
        while True:
            ciclo()
            time.sleep(args.intervalo)
    else:
        ciclo()


if __name__ == "__main__":
    main()
