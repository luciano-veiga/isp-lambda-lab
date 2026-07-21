"""
simulate_prtg.py
-------------------
Simulador de alarmes do PRTG, exclusivo para o lab. Gera eventos de
sensor Down/Up para os clientes comerciais fictícios (data/clientes.json)
e dispara o webhook para a Lambda `prtg-alerta-comercial` publicada no
MiniStack. Não se conecta a nenhum PRTG real.

Uso:
  export API_URL="http://localhost:4566/restapis/<api_id>/lab/_user_request_"
  export API_TOKEN="<token gerado pelo setup_ministack.sh>"

  # Alarme aleatório
  python3 simulate_prtg.py

  # Forçar um cliente e status específicos
  python3 simulate_prtg.py --cliente-id 55521 --status Down

  # Forçar o horário do alarme, para testar a escala do NOC (0-23h)
  python3 simulate_prtg.py --cliente-id 55622 --status Down --hora 3

  # Disparar alarmes continuamente
  python3 simulate_prtg.py --loop --intervalo 20
"""

import os
import json
import random
import argparse
import time
from datetime import datetime
import requests

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "clientes.json")
API_URL = os.environ.get("API_URL", "http://localhost:4566/restapis/REPLACE_ME/lab/_user_request_")
API_TOKEN = os.environ.get("API_TOKEN", "REPLACE_ME")
HEADERS = {"Content-Type": "application/json", "x-api-key": API_TOKEN}


def carregar_comerciais():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        clientes = json.load(f)
    return [c for c in clientes if c.get("tipo") == "comercial"]


def gerar_alarme(cliente, status=None, hora=None):
    agora = datetime.utcnow()
    if hora is not None:
        agora = agora.replace(hour=hora)

    sensor = random.choice(cliente.get("sensores_prtg", [f"Link Principal - {cliente['nome']}"]))

    payload = {
        "sensor": sensor,
        "cliente_id": cliente["cliente_id"],
        "cliente_tipo": cliente["tipo"],
        "status": status or random.choice(["Down", "Down", "Up"]),  # mais chance de Down p/ testar o gatilho
        "device": f"Router-{cliente['cliente_id']}",
        "timestamp": agora.isoformat(),
        "responsavel_ti_email": cliente.get("responsavel_ti_email"),
    }
    return payload


def enviar(payload):
    resp = requests.post(f"{API_URL}/prtg-webhook", headers=HEADERS, json=payload)
    print(f"[PRTG] sensor={payload['sensor']} status={payload['status']} hora={payload['timestamp']} -> {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)


def main():
    parser = argparse.ArgumentParser(description="Simulador de alarmes do PRTG (apenas lab)")
    parser.add_argument("--cliente-id", help="ID do cliente comercial específico")
    parser.add_argument("--status", choices=["Down", "Up"], help="Força o status do alarme")
    parser.add_argument("--hora", type=int, help="Força a hora (0-23) para testar a escala do NOC")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--intervalo", type=int, default=20)
    args = parser.parse_args()

    comerciais = carregar_comerciais()
    if not comerciais:
        print("Nenhum cliente comercial em data/clientes.json")
        return

    def ciclo():
        if args.cliente_id:
            cliente = next((c for c in comerciais if c["cliente_id"] == args.cliente_id), None)
        else:
            cliente = random.choice(comerciais)

        if cliente is None:
            print("Cliente comercial não encontrado em data/clientes.json")
            return

        payload = gerar_alarme(cliente, status=args.status, hora=args.hora)
        enviar(payload)

    if args.loop:
        print(f"Disparando alarmes PRTG a cada {args.intervalo}s (Ctrl+C para parar)...")
        while True:
            ciclo()
            time.sleep(args.intervalo)
    else:
        ciclo()


if __name__ == "__main__":
    main()
