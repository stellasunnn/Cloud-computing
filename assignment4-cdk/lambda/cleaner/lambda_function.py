import boto3

s3 = boto3.client('s3')


def lambda_handler(event, context):
    bucket_name = 'test-bucket-ws-999'

    # Find largest object
    largest_size = 0
    largest_key = None

    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get('Contents', []):
            if obj['Size'] > largest_size:
                largest_size = obj['Size']
                largest_key = obj['Key']

    # Delete largest object
    if largest_key:
        s3.delete_object(
            Bucket=bucket_name,
            Key=largest_key
        )
        return {
            'statusCode': 200,
            'body': f'Deleted object {largest_key} of size {largest_size} bytes'
        }

    return {
        'statusCode': 404,
        'body': 'No objects found in bucket'
    }
