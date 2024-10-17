from datetime import datetime
import io
import json
import boto3
from boto3.dynamodb.conditions import Key
from matplotlib import pyplot as plt

bucket_name = 'test-bucket-ws-999'
table_name = 'S3-object-size-history'
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


def plotting_lambda(event, context):
    plot_key = 'plot'

    end_time = int(datetime.now().timestamp())
    start_time = end_time - 12  # add buffer ensure we capture all the actions

    table = dynamodb.Table(table_name)
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
        'body': json.dumps('Plot created and saved to S3')
    }
