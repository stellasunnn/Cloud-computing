import datetime
import io
import json
import time
import boto3
import random
import string

import boto3
from boto3.dynamodb.conditions import Key
from matplotlib import pyplot as plt

s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.client('dynamodb')
dynamodb_resource = boto3.resource('dynamodb')
bucket_name = 'test-bucket-ws-999'
table_name = 'S3-object-size-history'


def create_bucket(bucket_name):
    s3.create_bucket(Bucket=bucket_name)
    response = s3.list_buckets()
    buckets = [bucket['Name'] for bucket in response['Buckets']]
    print("Bucket List: %s" % buckets)


def create_dynamodb_table(table_name):
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "bucket_name", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "bucket_name", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "N"},
        ],
        ProvisionedThroughput={
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        }
    )


if __name__ == "__main__":
    create_bucket(bucket_name)
    create_dynamodb_table(table_name)
    time.sleep(10)

    # deploy three lambda functions
    with open('/Users/Stella/Documents/Git/Cloud-computing/programming2/size_tracking_lambda.zip', 'rb') as f:
        zip_content = f.read()

    response = lambda_client.create_function(
        FunctionName='size_tracking_lambda',
        Runtime='python3.9',
        Role='arn:aws:iam::194722399434:role/S3FullAccessRole',
        Handler='lambda_function.size_tracking_lambda',
        Code={'ZipFile': zip_content},
        Description='Track bucket size changes and update data to Dynamodb table',
        Timeout=15,
        MemorySize=128,
        Publish=True
    )
    print(response)

    with open('/Users/Stella/Documents/Git/Cloud-computing/programming2/driver_lambda.zip', 'rb') as f:
        zip_content = f.read()

    response = lambda_client.create_function(
        FunctionName='driver_lambda',
        Runtime='python3.9',
        Role='arn:aws:iam::194722399434:role/S3FullAccessRole',  # Replace with your IAM Role ARN
        Handler='lambda_function.driver_lambda',
        Code={'ZipFile': zip_content},
        Description='Driver Lambda function to manage S3 and DynamoDB operations',
        Timeout=15,  # Maximum execution time in seconds
        MemorySize=128,  # Memory size in MB
        Publish=True
    )
    print(response)

    with open('/Users/Stella/Documents/Git/Cloud-computing/programming2/plotting_lambda.zip', 'rb') as f:
        zip_content = f.read()

    response = lambda_client.create_function(
        FunctionName='plotting_lambda',
        Runtime='python3.9',
        Role='arn:aws:iam::194722399434:role/S3FullAccessRole',
        Handler='lambda_function.plotting_lambda',
        Code={'ZipFile': zip_content},
        Description='Plotting Lambda function to create plot for Dynamodb table',
        Timeout=15,
        MemorySize=128,
        Publish=True
    )
    print(response)
