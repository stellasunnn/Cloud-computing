import json
import time
import logging
import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')


def lambda_handler(event, context):
    bucket_name = 'test-bucket-ws-999'

    s3.put_object(Bucket=bucket_name, Key='assignment1.txt', Body='Empty Assignment 1')
    time.sleep(2)
    s3.put_object(Bucket=bucket_name, Key='assignment1.txt', Body='Empty Assignment 2222222222')
    time.sleep(2)
    s3.delete_object(Bucket=bucket_name, Key='assignment1.txt')
    time.sleep(2)
    s3.put_object(Bucket=bucket_name, Key='assignment2.txt', Body='33')
    time.sleep(2)
    plotting_api_url = 'https://34wwjdo4xh.execute-api.us-east-1.amazonaws.com/stage/plot'
    logger.info(f"Calling plotting API at {plotting_api_url}.")

    response = requests.get(plotting_api_url, timeout=15, headers={"Key": "test-key"})
    response.raise_for_status()

    logger.info(f"API call successful. Status code: {response.status_code}")
    logger.info(f"API response: {response.text}")

    return {
        'statusCode': 200,
        'body': json.dumps('Driver lambda completed successfully. Plotting lambda called.')
    }