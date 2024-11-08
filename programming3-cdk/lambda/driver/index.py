import boto3
import time
import os
import requests
import json


def handler(event, context):
    s3 = boto3.client('s3')
    bucket_name = os.environ['BUCKET_NAME']

    s3.put_object(Bucket=bucket_name, Key='assignment1.txt', Body='Empty Assignment 1')
    time.sleep(5)
    s3.put_object(Bucket=bucket_name, Key='assignment1.txt', Body='Empty Assignment 2222222222')
    time.sleep(5)
    s3.delete_object(Bucket=bucket_name, Key='assignment1.txt')
    time.sleep(5)
    s3.put_object(Bucket=bucket_name, Key='assignment2.txt', Body='33')
    time.sleep(5)

    # Call plotting API
    api_url = os.environ['API_URL']
    response = requests.get(api_url)
    return {
        'statusCode': 200,
        'body': 'Driver lambda completed successfully'
    }