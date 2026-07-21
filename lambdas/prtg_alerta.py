"""
Lambda: prtg-alerta-comercial
-------------------------------
Simula o processamento de um alarme do PRTG (via webhook -> API Gateway
-> esta Lambda) para clientes do tipo "comercial".

Regra de negócio:
- Só age se cliente_tipo == "comercial" e status == "Down".
- Identifica o operador do NOC responsável pelo horário do alarme.
- Monta o e-mail (simulado) para o responsável de TI do cliente e
  para o operador do NOC do turno.

Payload de entrada esperado (body do POST):
{
  "sensor": "Link Principal - Cliente XYZ Corp",
  "cliente_id": "55521",
  "cliente_tipo": "comercial",
  "status": "Down",
  "device": "Router-XYZ-01",
  "timestamp": "2026-07-19T14:32:00",
  "responsavel_ti_email": "ti@clientexyz.com.br"
}
"""

import json
from datetime import datetime

# Escala do NOC por horário — ajuste para a escala real da Vitória Net
ESCALA_NOC = [
    {"inicio": 0, "fim": 6, "operador": "Operador Noturno", "email": "noc.noturno@vitorianet.com.br"},
    {"inicio": 6, "fim": 14, "operador": "Operador Manhã", "email": "noc.manha@vitorianet.com.br"},
    {"inicio": 14, "fim": 22, "operador": "Operador Tarde", "email": "noc.tarde@vitorianet.com.br"},
    {"inicio": 22, "fim": 24, "operador": "Operador Noturno", "email": "noc.noturno@vitorianet.com.br"},
]


def _operador_do_turno(hora):
    for turno in ESCALA_NOC:
        if turno["inicio"] <= hora < turno["fim"]:
            return turno
    return ESCALA_NOC[0]


def handler(event, context):
    body = json.loads(event.get("body") or "{}")

    if body.get("cliente_tipo") != "comercial":
        return {
            "statusCode": 200,
            "body": json.dumps({"gatilho_acionado": False, "motivo": "cliente não é comercial"}),
        }

    if body.get("status") != "Down":
        return {
            "statusCode": 200,
            "body": json.dumps({"gatilho_acionado": False, "motivo": "status não é crítico"}),
        }

    ts = datetime.fromisoformat(body["timestamp"])
    turno = _operador_do_turno(ts.hour)

    email_simulado = {
        "para": [body.get("responsavel_ti_email"), turno["email"]],
        "assunto": f"[ALERTA] Link comercial DOWN - {body.get('sensor')}",
        "corpo": (
            f"Sensor: {body.get('sensor')}\n"
            f"Dispositivo: {body.get('device')}\n"
            f"Status: {body.get('status')}\n"
            f"Horário do alarme: {body.get('timestamp')}\n"
            f"Operador NOC responsável pelo turno: {turno['operador']}"
        ),
    }

    resultado = {
        "gatilho_acionado": True,
        "cliente_id": body.get("cliente_id"),
        "operador_noc_turno": turno["operador"],
        "email_simulado": email_simulado,
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(resultado, ensure_ascii=False),
    }
