import boto3
import os
import json
import matplotlib.pyplot as plt
from boto3.dynamodb.conditions import Key
from datetime import datetime
import io


def handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    s3 = boto3.client('s3')
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    bucket_name = os.environ['BUCKET_NAME']

    plot_key = 'plot'
    end_time = int(datetime.now().timestamp())
    start_time = end_time - 12  # add buffer ensure we capture all the actions

    response = table.query(
        KeyConditionExpression=Key('bucket_name').eq(bucket_name) & Key('timestamp').between(start_time, end_time),
        ScanIndexForward=True
    )

    # get the plot data
    timestamps = []
    sizes = []
    for item in response.get('Items', []):
        timestamps.append(datetime.fromtimestamp(int(item['timestamp'])))
        sizes.append(int(item['total_size']))

    # get the historical size response query
    historical_sizes_response = table.query(
        KeyConditionExpression=Key('bucket_name').eq(bucket_name),
        ProjectionExpression='total_size'
    )

    # get the max historical size
    historical_sizes = []
    for item in historical_sizes_response.get('Items', []):
        historical_sizes.append(int(item['total_size']))

    if historical_sizes:
        historical_max = max(historical_sizes)
    else:
        historical_max = 0

    # create plot
    plt.figure(figsize=(12, 8))
    plt.plot(timestamps, sizes, marker='o', label='Recent Sizes')
    plt.axhline(y=historical_max, color='r', linestyle='--', label='Historical High')
    plt.xlabel('Timestamp')
    plt.ylabel('Size (bytes)')
    plt.title('TestBucket Size Change (Last 10 Seconds)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()

    # Save the plot to a bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Upload the plot to S3
    s3.put_object(Bucket=bucket_name, Key=plot_key, Body=buf.getvalue(), ContentType='image/png')

    return {
        'statusCode': 200,
        'body': json.dumps('Plot created successfully'),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
