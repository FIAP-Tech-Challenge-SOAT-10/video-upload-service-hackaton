import boto3
from .config import settings

_session = boto3.session.Session(region_name=settings.aws_region)

s3 = _session.client("s3", endpoint_url=settings.aws_endpoint_url)
ddb = _session.resource("dynamodb", endpoint_url=settings.aws_endpoint_url)
sqs = _session.client("sqs", endpoint_url=settings.aws_endpoint_url)

table_videos = ddb.Table(settings.ddb_table)
