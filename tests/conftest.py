import os
import time
import pytest
import boto3
from botocore.exceptions import ClientError

AWS_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture(scope="session")
def dynamodb_resource():
    # Credenciais “dummy” para LocalStack
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_REGION", AWS_REGION)

    return boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT)


@pytest.fixture(scope="session")
def videos_table(dynamodb_resource):
    table_name = os.getenv("DDB_TABLE", "videos")

    # Cria a tabela se não existir
    try:
        table = dynamodb_resource.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "id_video", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id_video", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # Espera ficar ativa (LocalStack é rápido, mas garantimos)
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceInUseException":
            raise
        table = dynamodb_resource.Table(table_name)

    # Limpa a tabela entre sessões? (opcional)
    # Aqui mantemos como está; cada teste usa chaves únicas.

    return table
