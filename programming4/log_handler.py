# logging_lambda.py
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

logs_client = boto3.client('logs')


def lambda_handler(event, context):
    # Process events directly from the event parameter
    for record in event['Records']:
        # Parse the messages
        body = json.loads(record['body'])
        s3_event = json.loads(body['Message'])

        # Get S3 event details
        s3_record = s3_event['Records'][0]
        event_name = s3_record['eventName']
        object_key = s3_record['s3']['object']['key']

        if 'ObjectCreated' in event_name:
            size_delta = s3_record['s3']['object'].get('size', 0)
        else:  # ObjectRemoved
            # Search for this object's creation event
            response = logs_client.filter_log_events(
                logGroupName='/aws/lambda/logging_lambda_1',
                filterPattern=f'{{"object_name": "{object_key}"}}'
            )

            # Look for the most recent creation event for this object
            creation_size = 0
            for event in response.get('events', []):
                event_data = json.loads(event['message'])
                if event_data['size_delta'] > 0:  # This was a creation event
                    creation_size = event_data['size_delta']
                    break

            size_delta = -creation_size  # Make it negative for deletion

        # Log the event
        log_event = {
            'object_name': object_key,
            'size_delta': size_delta
        }

        logger.info(json.dumps(log_event))

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed log event')
    }