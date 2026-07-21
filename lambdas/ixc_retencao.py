"""
Lambda: ixc-os-retencao
------------------------
Simula o processamento de um evento de "Ordem de Serviço criada" vindo do
IXC Provider (via webhook -> API Gateway -> esta Lambda).

Regra de negócio:
- Se o cliente teve 2+ OS (contando a atual) nos últimos 90 dias,
  o gatilho é acionado e uma mensagem estruturada é gerada para a
  equipe de retenção, já com sugestão de ação e prioridade.

Payload de entrada esperado (body do POST):
{
  "cliente_id": "12345",
  "cliente_nome": "João Silva",
  "os_id": "98765",
  "tipo_os": "Sem conexão",
  "data_abertura": "2026-07-19T10:00:00",
  "historico_os": [
    {"os_id": "98700", "tipo_os": "Sem conexão", "data_abertura": "2026-06-10T09:00:00"},
    {"os_id": "98550", "tipo_os": "Lentidão", "data_abertura": "2026-04-02T14:00:00"}
  ]
}
"""

import json
from datetime import datetime, timedelta


def _parse_dt(value):
    return datetime.fromisoformat(value)


def handler(event, context):
    body = json.loads(event.get("body") or "{}")

    cliente_id = body.get("cliente_id")
    cliente_nome = body.get("cliente_nome", "desconhecido")
    os_atual_id = body.get("os_id")
    tipo_os_atual = body.get("tipo_os", "não informado")
    data_abertura = _parse_dt(body["data_abertura"])
    historico = body.get("historico_os", [])

    limite = data_abertura - timedelta(days=90)
    os_recentes = [
        os for os in historico
        if _parse_dt(os["data_abertura"]) >= limite
    ]

    total_90_dias = len(os_recentes) + 1  # incluindo a OS que acabou de abrir

    resultado = {
        "cliente_id": cliente_id,
        "cliente_nome": cliente_nome,
        "os_atual": os_atual_id,
        "total_os_90_dias": total_90_dias,
        "gatilho_acionado": total_90_dias >= 2,
    }

    if total_90_dias >= 2:
        if total_90_dias >= 3:
            prioridade = "ALTA"
            acao_sugerida = "Visita técnica prioritária + oferta de retenção (desconto ou upgrade de plano)"
        else:
            prioridade = "MEDIA"
            acao_sugerida = "Contato proativo do time de retenção para investigar causa raiz antes da 3ª OS"

        mensagem_retencao = {
            "destino": "equipe-retencao",
            "prioridade": prioridade,
            "cliente_id": cliente_id,
            "cliente_nome": cliente_nome,
            "total_os_90_dias": total_90_dias,
            "os_relacionadas": os_recentes + [{
                "os_id": os_atual_id,
                "tipo_os": tipo_os_atual,
                "data_abertura": body["data_abertura"],
            }],
            "acao_sugerida": acao_sugerida,
            "gerado_em": datetime.utcnow().isoformat(),
        }
        resultado["mensagem_gerada"] = mensagem_retencao

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(resultado, ensure_ascii=False),
    }
