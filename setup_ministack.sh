#!/usr/bin/env bash
# ============================================================
# Lab: Automações de provedor (IXC + PRTG) via Lambda no MiniStack
# ============================================================
# Sobe o MiniStack, cria a role IAM, as duas Lambdas, o API Gateway
# (REST) com um API Key ("token" da aplicação) e imprime a URL e a
# chave para você testar com o client_app.py
#
# Requisitos: docker, aws cli v2, zip
# ============================================================

set -euo pipefail

ENDPOINT="http://localhost:4566"
REGION="us-east-1"
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-role"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=$REGION

aws_local() {
  aws --endpoint-url="$ENDPOINT" --region "$REGION" "$@"
}

echo "==> 1. Subindo o MiniStack (se ainda não estiver rodando)"
if ! docker ps --format '{{.Names}}' | grep -q '^ministack$'; then
  docker run -d -p 4566:4566 --name ministack ministackorg/ministack
  echo "    Aguardando o MiniStack ficar pronto..."
  sleep 5
else
  echo "    Já está rodando."
fi

echo "==> 2. Criando a role IAM da Lambda"
aws_local iam create-role \
  --role-name lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  >/dev/null 2>&1 || echo "    Role já existe, seguindo."

echo "==> 3. Empacotando e publicando as Lambdas"
cd "$(dirname "$0")/lambdas"

zip -q -j ixc_retencao.zip ixc_retencao.py
zip -q -j prtg_alerta.zip prtg_alerta.py

aws_local lambda create-function \
  --function-name ixc-os-retencao \
  --runtime python3.12 \
  --handler ixc_retencao.handler \
  --zip-file fileb://ixc_retencao.zip \
  --role "$ROLE_ARN" \
  >/dev/null 2>&1 || \
aws_local lambda update-function-code \
  --function-name ixc-os-retencao \
  --zip-file fileb://ixc_retencao.zip >/dev/null

aws_local lambda create-function \
  --function-name prtg-alerta-comercial \
  --runtime python3.12 \
  --handler prtg_alerta.handler \
  --zip-file fileb://prtg_alerta.zip \
  --role "$ROLE_ARN" \
  >/dev/null 2>&1 || \
aws_local lambda update-function-code \
  --function-name prtg-alerta-comercial \
  --zip-file fileb://prtg_alerta.zip >/dev/null

cd - >/dev/null

echo "==> 4. Criando o API Gateway (REST API)"
API_ID=$(aws_local apigateway create-rest-api --name isp-automation-api --query 'id' --output text)
ROOT_ID=$(aws_local apigateway get-resources --rest-api-id "$API_ID" --query 'items[0].id' --output text)

criar_rota() {
  local path_part=$1
  local funcao=$2

  local resource_id
  resource_id=$(aws_local apigateway create-resource \
    --rest-api-id "$API_ID" --parent-id "$ROOT_ID" --path-part "$path_part" \
    --query 'id' --output text)

  aws_local apigateway put-method \
    --rest-api-id "$API_ID" --resource-id "$resource_id" \
    --http-method POST --authorization-type NONE --api-key-required \
    >/dev/null

  aws_local apigateway put-integration \
    --rest-api-id "$API_ID" --resource-id "$resource_id" \
    --http-method POST --type AWS_PROXY --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:000000000000:function:${funcao}/invocations" \
    >/dev/null

  echo "    Rota /$path_part -> $funcao criada"
}

criar_rota "ixc-webhook" "ixc-os-retencao"
criar_rota "prtg-webhook" "prtg-alerta-comercial"

echo "==> 5. Publicando o stage 'lab'"
aws_local apigateway create-deployment --rest-api-id "$API_ID" --stage-name lab >/dev/null

echo "==> 6. Criando o token (API Key) e o usage plan"
API_KEY_ID=$(aws_local apigateway create-api-key \
  --name "cliente-app-token" --enabled \
  --query 'id' --output text)

API_KEY_VALUE=$(aws_local apigateway get-api-key \
  --api-key "$API_KEY_ID" --include-value \
  --query 'value' --output text)

USAGE_PLAN_ID=$(aws_local apigateway create-usage-plan \
  --name "isp-automation-plan" \
  --api-stages "apiId=${API_ID},stage=lab" \
  --query 'id' --output text)

aws_local apigateway create-usage-plan-key \
  --usage-plan-id "$USAGE_PLAN_ID" \
  --key-id "$API_KEY_ID" --key-type API_KEY >/dev/null

BASE_URL="${ENDPOINT}/restapis/${API_ID}/lab/_user_request_"

echo ""
echo "============================================================"
echo " Lab pronto!"
echo "============================================================"
echo " URL evento IXC   : ${BASE_URL}/ixc-webhook"
echo " URL evento PRTG  : ${BASE_URL}/prtg-webhook"
echo " Token (x-api-key): ${API_KEY_VALUE}"
echo "============================================================"
echo ""
echo "Exporte para usar no client_app.py:"
echo "  export API_URL=\"${BASE_URL}\""
echo "  export API_TOKEN=\"${API_KEY_VALUE}\""
