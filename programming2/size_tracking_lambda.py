import time
import boto3

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
table_name = 'S3-object-size-history'


def lambda_handler(event, context):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    total_size = 0
    total_objects = 0
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get('Contents', []):
            total_size += obj['Size']
            total_objects += 1

    timestamp = int(time.time())
    dynamodb.put_item(
        TableName=table_name,
        Item={
            'bucket_name': {'S': bucket_name},
            'timestamp': {'N': str(timestamp)},
            'total_size': {'N': str(total_size)},
            'total_objects': {'N': str(total_objects)}
        }
    )
