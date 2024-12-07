import json
import time
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
sqs = boto3.client('sqs')


def lambda_handler(event, context):
    queue_url = 'https://sqs.us-east-1.amazonaws.com/194722399434/size-tracking-queue'

    # Process messages from SQS
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10
    )

    for message in response.get('Messages', []):
        body = json.loads(message['Body'])
        s3_event = json.loads(body['Message'])

        bucket_name = s3_event['Records'][0]['s3']['bucket']['name']

        # Calculate total bucket size
        total_size = 0
        total_objects = 0
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get('Contents', []):
                total_size += obj['Size']
                total_objects += 1

        # Store in DynamoDB
        timestamp = int(time.time())
        dynamodb.put_item(
            TableName='S3-object-size-history',
            Item={
                'bucket_name': {'S': bucket_name},
                'timestamp': {'N': str(timestamp)},
                'total_size': {'N': str(total_size)},
                'total_objects': {'N': str(total_objects)}
            }
        )

        # Delete processed message
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )

