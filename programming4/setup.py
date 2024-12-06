# setup.py
import datetime
import io
import json
import time
import boto3
import os
import zipfile

s3 = boto3.client('s3')
sns = boto3.client('sns')
sqs = boto3.client('sqs')
lambda_client = boto3.client('lambda')
dynamodb = boto3.client('dynamodb')
cloudwatch = boto3.client('cloudwatch')
logs = boto3.client('logs')
dynamodb_resource = boto3.resource('dynamodb')

bucket_name = 'test-bucket-ws-999'
table_name = 'S3-object-size-history'
topic_name = 's3-events-topic'
queue_name_tracking = 'size-tracking-queue'
queue_name_logging = 'logging-queue'


def create_bucket(bucket_name):
    s3.create_bucket(Bucket=bucket_name)
    print(f"Created bucket: {bucket_name}")


def create_sns_topic():
    response = sns.create_topic(Name=topic_name)
    topic_arn = response['TopicArn']
    print(f"Created SNS topic: {topic_arn}")
    return topic_arn


def set_sns_policy(topic_arn, bucket_name):
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AllowS3ToPublishToSNS",
            "Effect": "Allow",
            "Principal": {"Service": "s3.amazonaws.com"},
            "Action": "SNS:Publish",
            "Resource": topic_arn,
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": topic_arn.split(":")[4]
                },
                "ArnLike": {
                    "aws:SourceArn": f"arn:aws:s3:*:*:{bucket_name}"
                }
            }
        }]
    }

    sns.set_topic_attributes(
        TopicArn=topic_arn,
        AttributeName='Policy',
        AttributeValue=json.dumps(policy)
    )


def create_sqs_queue(queue_name):
    # Create queue
    response = sqs.create_queue(QueueName=queue_name)
    queue_url = response['QueueUrl']
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['QueueArn']
    )['Attributes']['QueueArn']

    # Set up queue policy to allow SNS
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "sns.amazonaws.com"},
            "Action": "sqs:SendMessage",
            "Resource": queue_arn
        }]
    }

    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            'Policy': json.dumps(policy)
        }
    )

    print(f"Created SQS queue: {queue_url}")
    return queue_url, queue_arn


def create_dynamodb_table(table_name):
    try:
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
        print(f"Created DynamoDB table: {table_name}")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {table_name} already exists")


def setup_s3_notification(bucket_name, topic_arn):
    s3.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration={
            'TopicConfigurations': [{
                'TopicArn': topic_arn,
                'Events': ['s3:ObjectCreated:*', 's3:ObjectRemoved:*']
            }]
        }
    )
    print(f"Set up S3 notifications for bucket: {bucket_name}")


def create_log_group():
    try:
        logs.create_log_group(
            logGroupName='/aws/lambda/logging_lambda'
        )
        print("Created CloudWatch log group: /aws/lambda/logging_lambda")
    except logs.exceptions.ResourceAlreadyExistsException:
        print("Log group already exists")


def create_metric_filter():
    create_log_group()

    try:
        logs.put_metric_filter(
            logGroupName='/aws/lambda/logging_lambda',
            filterName='SizeDeltaMetric',
            filterPattern='{ $.size_delta = * }',
            metricTransformations=[{
                'metricName': 'TotalObjectSize',
                'metricNamespace': 'Assignment4App',
                'metricValue': '$.size_delta',
                'defaultValue': 0
            }]
        )
        print("Created metric filter")
    except logs.exceptions.ResourceAlreadyExistsException:
        print("Metric filter already exists")


def create_alarm():
    try:
        cloudwatch.put_metric_alarm(
            AlarmName='TotalSizeAlarm',
            ComparisonOperator='GreaterThanThreshold',
            EvaluationPeriods=1,
            MetricName='TotalObjectSize',
            Namespace='Assignment4App',
            Period=300,  # 5 minutes
            Statistic='Sum',
            Threshold=20,
            AlarmActions=[lambda_client.get_function(FunctionName='cleaner_lambda_1')['Configuration']['FunctionArn']],
            AlarmDescription='Alarm when total object size exceeds 20 bytes'
        )
        print("Created CloudWatch alarm")
    except cloudwatch.exceptions.ResourceNotFoundException:
        print("Error: Cleaner lambda not found")


def setup_sqs_trigger():
    try:
        lambda_client.create_event_source_mapping(
            EventSourceArn=f'arn:aws:sqs:us-east-1:194722399434:logging-queue',
            FunctionName='logging_lambda_1',
            Enabled=True,
            BatchSize=1
        )
        print("Added SQS trigger to logging lambda")
    except lambda_client.exceptions.ResourceConflictException:
        print("SQS trigger already exists")


def create_lambda_zip(python_file):
    zip_filename = python_file.replace('.py', '.zip')
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(python_file, 'lambda_function.py')
    return zip_filename


if __name__ == "__main__":
    # Create infrastructure
    create_bucket(bucket_name)
    create_dynamodb_table(table_name)
    topic_arn = create_sns_topic()

    # Set up SNS and SQS
    set_sns_policy(topic_arn, bucket_name)
    tracking_queue_url, tracking_queue_arn = create_sqs_queue(queue_name_tracking)
    logging_queue_url, logging_queue_arn = create_sqs_queue(queue_name_logging)

    time.sleep(10)  # Wait for resources to be created

    # Set up SNS subscriptions
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol='sqs',
        Endpoint=tracking_queue_arn
    )
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol='sqs',
        Endpoint=logging_queue_arn
    )

    # Set up S3 notifications
    setup_s3_notification(bucket_name, topic_arn)

    # Deploy lambda functions
    lambda_functions = {
        'size_tracking_lambda_1': 'size_tracking.py',
        'logging_lambda_1': 'log_handler.py',
        'cleaner_lambda_1': 'cleaner.py',
        'driver_lambda_1': 'driver.py',
        'plotting_lambda_1': 'plotting.py'
    }

    for func_name, python_file in lambda_functions.items():
        zip_file = create_lambda_zip(python_file)
        try:
            with open(zip_file, 'rb') as f:
                zip_content = f.read()

            try:
                response = lambda_client.create_function(
                    FunctionName=func_name,
                    Runtime='python3.9',
                    Role='arn:aws:iam::194722399434:role/S3FullAccessRole',
                    Handler='lambda_function.lambda_handler',
                    Code={'ZipFile': zip_content},
                    Description=f'Lambda function for {func_name}',
                    Timeout=15,
                    MemorySize=128,
                    Publish=True
                )
                print(f"Created lambda function: {func_name}")
            except lambda_client.exceptions.ResourceConflictException:
                response = lambda_client.update_function_code(
                    FunctionName=func_name,
                    ZipFile=zip_content
                )
                print(f"Updated lambda function: {func_name}")
        finally:
            os.remove(zip_file)

    # Set up SQS trigger for logging lambda
    setup_sqs_trigger()

    # Set up CloudWatch components
    create_metric_filter()
    create_alarm()

    print("Setup complete!")