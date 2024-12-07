# logging_lambda.py
import json
import boto3
import logging

# Initialize logger and set log level
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize CloudWatch Logs client
logs_client = boto3.client('logs')


def lambda_handler(event, context):
    logger.info(f"Incoming event: {json.dumps(event)}")

    try:
        # Parse the SQS message body
        body = json.loads(event['Records'][0]['body'])  # Parse the SQS body
        s3_event = json.loads(body['Message'])  # Parse the SNS message inside the body
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing event: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps("Failed to process event")
        }

    # Check if the SNS event contains the 'Records' key
    if 'Records' not in s3_event:
        logger.error("Key 'Records' not found in SNS message")
        return {
            'statusCode': 400,
            'body': json.dumps("Invalid event structure")
        }

    # Get the first record from the SNS event
    s3_record = s3_event['Records'][0]
    event_name = s3_record.get('eventName', 'UnknownEvent')
    object_key = s3_record['s3']['object']['key']

    logger.info(f"Processing event: {event_name} for object: {object_key}")

    try:
        # Handle creation events
        if 'ObjectCreated' in event_name:
            size_delta = s3_record['s3']['object'].get('size', 0)
            logger.info(f"Created object with size: {size_delta}")

        # Handle removal events
        elif 'ObjectRemoved' in event_name:
            logger.info(f"Searching logs for object: {object_key}")
            response = logs_client.filter_log_events(
                logGroupName='/aws/lambda/logging_lambda_1',
                filterPattern=f'"{object_key}"'
            )

            creation_size = 0
            for event in response.get('events', []):
                try:
                    event_data = json.loads(event['message'])
                    if event_data.get('object_name') == object_key and event_data.get('size_delta', 0) > 0:
                        creation_size = event_data['size_delta']
                        logger.info(f"Found creation size: {creation_size}")
                        break
                except (KeyError, json.JSONDecodeError) as e:
                    logger.error(f"Error parsing log event message: {str(e)}")
                    continue

            size_delta = -creation_size  # Make it negative for deletion
            logger.info(f"Set deletion size delta to: {size_delta}")

        else:
            logger.warning(f"Unhandled event type: {event_name}")
            return {
                'statusCode': 200,
                'body': json.dumps("Event type not processed")
            }

        # Log the event details
        log_event = {
            'object_name': object_key,
            'size_delta': size_delta
        }
        logger.info(f"Log event: {json.dumps(log_event)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps("Internal server error")
        }

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed log event')
    }
