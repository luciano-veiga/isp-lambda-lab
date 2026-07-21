# Lab: Automações de Provedor via Lambda no MiniStack

Simula, localmente, dois processos automatizados de um provedor de
internet — disparados por eventos do **IXC Provider** e do **PRTG** —
usando Lambdas reais rodando no **MiniStack** (emulador AWS local) e
uma "aplicação cliente" que se autentica via token (API Key) para
acionar esses eventos.

## Arquitetura do lab

```
Aplicação (IXC/PRTG) --[POST + x-api-key]--> API Gateway (MiniStack)
                                                    |
                                                    v
                                      Lambda (Python, execução real)
                                                    |
                                                    v
                                    Mensagem estruturada de saída
                              (equipe de retenção / e-mail NOC + TI)
```

- **MiniStack** roda Lambda com execução Python real e expõe API
  Gateway REST, permitindo simular o fluxo webhook -> função -> ação
  sem custo de AWS.
- O **token** (API Key + Usage Plan) representa a credencial que o
  IXC/PRTG (ou o N8N no meio do caminho) usaria para chamar a API.
- Cada Lambda representa a lógica de decisão que hoje seria manual.

## Processo 1 — OS repetida em menos de 90 dias (retenção)

**Gatilho:** IXC Provider gera uma nova Ordem de Serviço para um cliente.

**Fluxo:**
1. IXC dispara webhook (simulado pelo `client_app.py`) para
   `POST /ixc-webhook` com os dados da OS atual + histórico do cliente.
2. A Lambda `ixc-os-retencao` filtra as OS dos últimos 90 dias.
3. Se o cliente teve **2 ou mais OS** no período (incluindo a atual):
   - **2 OS** → prioridade **MÉDIA** → contato proativo do time de
     retenção para investigar a causa raiz.
   - **3 ou mais OS** → prioridade **ALTA** → visita técnica
     prioritária + oferta de retenção (desconto/upgrade).
4. A Lambda retorna a mensagem estruturada que seria entregue à
   equipe de retenção (por e-mail, WhatsApp via N8N, ou fila interna).

**Arquivo:** `lambdas/ixc_retencao.py`

## Processo 2 — Alarme PRTG em cliente comercial

**Gatilho:** PRTG detecta um sensor em status `Down` associado a um
cliente do tipo comercial.

**Fluxo:**
1. PRTG dispara webhook (simulado pelo `client_app.py`) para
   `POST /prtg-webhook`.
2. A Lambda `prtg-alerta-comercial` verifica se o cliente é comercial
   e se o status é crítico.
3. A Lambda identifica o operador do NOC responsável pelo horário do
   alarme, consultando uma escala interna (manhã/tarde/noite).
4. É montado o e-mail (simulado) com o alerta, endereçado ao
   **responsável de TI do cliente** e ao **operador do NOC do turno**.

**Arquivo:** `lambdas/prtg_alerta.py`

## Como rodar o lab

Pré-requisitos: Docker, AWS CLI v2, `zip`, Python 3 com `requests`.

```bash
chmod +x setup_ministack.sh
./setup_ministack.sh
```

O script:
1. Sobe o MiniStack (`docker run ... ministackorg/ministack`).
2. Cria a role IAM da Lambda.
3. Publica as duas funções.
4. Cria o API Gateway com as rotas `/ixc-webhook` e `/prtg-webhook`.
5. Cria o token (API Key) + usage plan e imprime a URL e a chave.

Em seguida:

```bash
export API_URL="<URL impressa pelo script>"
export API_TOKEN="<token impresso pelo script>"
python3 client_app.py
```

Isso dispara os dois eventos de exemplo e imprime a resposta de cada
Lambda — incluindo a mensagem/e-mail que seria enviado em produção.

## Simulando o IXC e o PRTG (só para o lab)

Em vez de disparar sempre os mesmos payloads fixos, o lab tem dois
"geradores de eventos" que fingem ser o IXC e o PRTG, usando uma base
de clientes 100% fictícia (`data/clientes.json`) — isolada, sem
qualquer ligação com o IXC ou o PRTG reais da empresa.

```bash
pip install requests
export API_URL="<URL impressa pelo setup_ministack.sh>"
export API_TOKEN="<token impresso pelo setup_ministack.sh>"
```

### `simulate_ixc.py` — simula abertura de OS

```bash
# Evento aleatório (cliente e tipo de OS sorteados)
python3 simulate_ixc.py

# Forçar o cenário de repetição: gera 2 OS anteriores nos últimos 90
# dias + a atual, garantindo prioridade ALTA no gatilho
python3 simulate_ixc.py --cliente-id 12345 --forcar-repeticao

# Modo contínuo: dispara um evento a cada 15s, simulando tráfego real
python3 simulate_ixc.py --loop --intervalo 15
```

Cada OS gerada é salva de volta em `data/clientes.json`, então o
histórico do cliente vai crescendo entre execuções — depois de
algumas chamadas para o mesmo cliente, o gatilho passa a disparar
sozinho, sem precisar forçar.

### `simulate_prtg.py` — simula alarmes de sensor

```bash
# Alarme aleatório entre os clientes comerciais cadastrados
python3 simulate_prtg.py

# Forçar cliente e status
python3 simulate_prtg.py --cliente-id 55521 --status Down

# Forçar o horário do alarme, para testar a escala do NOC (0-23h)
python3 simulate_prtg.py --cliente-id 55622 --status Down --hora 3

# Modo contínuo
python3 simulate_prtg.py --loop --intervalo 20
```

Use `--hora` para validar que a Lambda está apontando o operador do
NOC correto conforme o turno (madrugada/manhã/tarde/noite).

### Resetar o cenário

`data/clientes.json` é reescrito pelo `simulate_ixc.py` a cada
execução. Para voltar ao estado inicial, basta restaurar o arquivo
original do lab (ou apagar o `historico_os` de cada cliente
manualmente).

## Próximos passos (evolução do lab)

- Trocar o "log" de saída da Lambda por uma publicação real em SQS/SNS
  do MiniStack, com o N8N (já rodando na sua stack local) consumindo
  a fila e disparando a mensagem no WhatsApp/e-mail de verdade.
- Adicionar autenticação SigV4 real em vez do API Key simples, para
  chegar mais perto do fluxo de produção.
- Persistir o histórico de OS em uma tabela DynamoDB do MiniStack, em
  vez de recebê-lo no payload, simulando uma consulta real ao IXC.
- Escrever testes automatizados (pytest) para as regras de negócio de
  cada Lambda, independente do MiniStack estar no ar.
