import boto3
import time
import os


def handler(event, context):
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')

    bucket_name = os.environ['BUCKET_NAME']
    table_name = os.environ['TABLE_NAME']
    table = dynamodb.Table(table_name)

    total_size = 0
    total_objects = 0

    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        if 'Contents' in page:
            for obj in page['Contents']:
                total_size += obj['Size']
                total_objects += 1

    # Store in DynamoDB
    timestamp = int(time.time())
    table.put_item(
        Item={
            'bucket_name': bucket_name,
            'timestamp': timestamp,
            'total_size': total_size,
            'total_objects': total_objects
        }
    )

    return {
        'statusCode': 200,
        'body': f'Updated size: {total_size}, objects: {total_objects}'
    }