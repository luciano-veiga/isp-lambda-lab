"""
client_app.py
--------------
Simula a "aplicação" (IXC / PRTG) chamando a API já publicada no
MiniStack, autenticando via token (API Key), disparando os dois
eventos de exemplo do lab.

Uso:
    export API_URL="http://localhost:4566/restapis/<api_id>/lab/_user_request_"
    export API_TOKEN="<valor impresso pelo setup_ministack.sh>"
    python3 client_app.py

Dependência: pip install requests
"""

import os
import json
import requests

API_URL = os.environ.get("API_URL", "http://localhost:4566/restapis/REPLACE_ME/lab/_user_request_")
API_TOKEN = os.environ.get("API_TOKEN", "REPLACE_ME")

HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_TOKEN,
}


def evento_ixc_repetido():
    """3ª OS do mesmo cliente em menos de 90 dias -> deve acionar prioridade ALTA."""
    payload = {
        "cliente_id": "12345",
        "cliente_nome": "João Silva",
        "os_id": "98765",
        "tipo_os": "Sem conexão",
        "data_abertura": "2026-07-19T10:00:00",
        "historico_os": [
            {"os_id": "98700", "tipo_os": "Sem conexão", "data_abertura": "2026-06-10T09:00:00"},
            {"os_id": "98550", "tipo_os": "Lentidão", "data_abertura": "2026-05-02T14:00:00"},
        ],
    }
    resp = requests.post(f"{API_URL}/ixc-webhook", headers=HEADERS, json=payload)
    print("=== Evento IXC (OS repetida) ===")
    print(resp.status_code, json.dumps(resp.json(), indent=2, ensure_ascii=False))


def evento_prtg_alarme():
    """Cliente comercial com link Down durante o turno da tarde."""
    payload = {
        "sensor": "Link Principal - Cliente XYZ Corp",
        "cliente_id": "55521",
        "cliente_tipo": "comercial",
        "status": "Down",
        "device": "Router-XYZ-01",
        "timestamp": "2026-07-19T15:32:00",
        "responsavel_ti_email": "ti@clientexyz.com.br",
    }
    resp = requests.post(f"{API_URL}/prtg-webhook", headers=HEADERS, json=payload)
    print("\n=== Evento PRTG (alarme comercial) ===")
    print(resp.status_code, json.dumps(resp.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    evento_ixc_repetido()
    evento_prtg_alarme()
