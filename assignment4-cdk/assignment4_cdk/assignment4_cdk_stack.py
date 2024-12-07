from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_lambda_event_sources as lambda_events,
    aws_sns_subscriptions as sns_subs,
    aws_iam as iam,
    aws_s3_notifications as s3_notifications,  # Added this import
    aws_cloudwatch_actions as cloudwatch_actions,  # Added this import too
    Duration,
    RemovalPolicy,
    CfnOutput
)

from constructs import Construct
import os


class Assignment4Stack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Resource names
        bucket_name = 'test-bucket-ws-000'
        table_name = 'S3-size-history'
        topic_name = 's3-events-topic'
        queue_name_tracking = 'size-tracking-queue'
        queue_name_logging = 'logging-queue'

        # Create S3 bucket
        bucket = s3.Bucket(
            self, 'EventBucket',
            bucket_name=bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create DynamoDB table
        table = dynamodb.Table(
            self, 'SizeHistoryTable',
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name='bucket_name',
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name='timestamp',
                type=dynamodb.AttributeType.NUMBER
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=5,
            write_capacity=5
        )

        # Create SNS topic
        topic = sns.Topic(
            self, 'S3EventsTopic',
            topic_name=topic_name
        )

        # Create SQS queues
        tracking_queue = sqs.Queue(
            self, 'SizeTrackingQueue',
            queue_name=queue_name_tracking
        )

        logging_queue = sqs.Queue(
            self, 'LoggingQueue',
            queue_name=queue_name_logging
        )

        # Subscribe queues to SNS topic
        topic.add_subscription(sns_subs.SqsSubscription(tracking_queue))
        topic.add_subscription(sns_subs.SqsSubscription(logging_queue))

        # Configure S3 to send notifications to SNS
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.SnsDestination(topic)
        )
        bucket.add_event_notification(
            s3.EventType.OBJECT_REMOVED,
            s3_notifications.SnsDestination(topic)
        )

        # Lambda functions configuration
        lambda_functions = {
            'size_tracking_lambda_1': 'size_tracking',
            'logging_lambda_1': 'logging',
            'cleaner_lambda_1': 'cleaner',
            'driver_lambda_1': 'driver',
            'plotting_lambda_1': 'plotting'
        }

        created_functions = {}
        for func_name, folder_name in lambda_functions.items():
            lambda_path = os.path.join('lambda', folder_name)
            created_functions[func_name] = lambda_.Function(
                self, func_name,
                function_name=func_name,
                runtime=lambda_.Runtime.PYTHON_3_9,
                handler='lambda_function.lambda_handler',
                code=lambda_.Code.from_asset(lambda_path),
                timeout=Duration.seconds(15),
                memory_size=128,
                environment={
                    'BUCKET_NAME': bucket.bucket_name,
                    'TABLE_NAME': table.table_name,
                }
            )

        # Grant permissions
        bucket.grant_read_write(created_functions['size_tracking_lambda_1'])
        bucket.grant_read_write(created_functions['cleaner_lambda_1'])
        table.grant_read_write_data(created_functions['size_tracking_lambda_1'])

        # Create CloudWatch Log Group
        log_group = logs.LogGroup(
            self, 'LoggingLambdaLogGroup',
            log_group_name='/aws/lambda/logging_lambda_1',
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create CloudWatch Metric Filter
        metric_filter = logs.MetricFilter(
            self, 'SizeDeltaMetricFilter',
            log_group=log_group,
            metric_namespace='Assignment4App',
            metric_name='TotalObjectSize',
            filter_pattern=logs.FilterPattern.literal('{ $.size_delta = * }'),
            metric_value='$.size_delta'
        )

        # Create CloudWatch Alarm
        alarm = cloudwatch.Alarm(
            self, 'TotalSizeAlarm',
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            threshold=20,
            metric=cloudwatch.Metric(
                namespace='Assignment4App',
                metric_name='TotalObjectSize',
                statistic='Sum',
                period=Duration.minutes(5)
            )
        )

        # ... [rest of the code remains the same] ...

        # Add Lambda triggers
        created_functions['size_tracking_lambda_1'].add_event_source(
            lambda_events.SqsEventSource(tracking_queue)
        )
        created_functions['logging_lambda_1'].add_event_source(
            lambda_events.SqsEventSource(logging_queue)
        )

        # Add CloudWatch Alarm action
        alarm.add_alarm_action(
            cloudwatch_actions.LambdaAction(created_functions['cleaner_lambda_1'])
        )

        # Output important resource information
        CfnOutput(
            self, 'BucketName',
            value=bucket.bucket_name,
            description='Name of the S3 bucket'
        )
        CfnOutput(
            self, 'TopicArn',
            value=topic.topic_arn,
            description='ARN of the SNS topic'
        )
        CfnOutput(
            self, 'TableName',
            value=table.table_name,
            description='Name of the DynamoDB table'
        )