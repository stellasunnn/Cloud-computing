import json
import time
import boto3
import urllib3

s3 = boto3.client('s3')
http = urllib3.PoolManager()


def lambda_handler(event, context):
    bucket_name = 'test-bucket-ws-999'

    # Create assignment1.txt
    s3.put_object(
        Bucket=bucket_name,
        Key='assignment1.txt',
        Body='Empty Assignment 11'  # 19 bytes
    )
    time.sleep(10)  # Wait for processing

    # Create assignment2.txt
    s3.put_object(
        Bucket=bucket_name,
        Key='assignment2.txt',
        Body='Empty Assignment 2222222222'  # 28 bytes
    )
    time.sleep(10)  # Wait for alarm to trigger and cleaner to run

    # Create assignment3.txt
    s3.put_object(
        Bucket=bucket_name,
        Key='assignment3.txt',
        Body='33'  # 2 bytes
    )
    time.sleep(10)  # Wait for alarm to trigger and cleaner to run

    # Call plotting lambda API
    plotting_api_url = 'https://34wwjdo4xh.execute-api.us-east-1.amazonaws.com/stage/plot'
    response = http.request('GET', plotting_api_url, timeout=15.0)

    # Check if request was successful
    if response.status == 200:
        return {
            'statusCode': 200,
            'body': json.dumps('Driver lambda completed successfully')
        }
    else:
        return {
            'statusCode': response.status,
            'body': json.dumps('Error calling plotting API')
        }