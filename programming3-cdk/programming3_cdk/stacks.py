from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_s3_notifications as s3n,
    aws_apigateway as apigw,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    Fn,
    CfnOutput,
)
from constructs import Construct


class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bucket_name = Fn.join('-', [
            'data-bucket',
            Fn.ref('AWS::AccountId'),
            Fn.ref('AWS::Region'),
            'storage'
        ])

        self.bucket = s3.Bucket(
            self,
            "TestBucket",
            bucket_name=self.bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.table = dynamodb.Table(
            self,
            "S3ObjectSizeHistory",
            partition_key={"name": "bucket_name", "type": dynamodb.AttributeType.STRING},
            sort_key={"name": "timestamp", "type": dynamodb.AttributeType.NUMBER},
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        self.table.add_global_secondary_index(
            index_name="TimeBasedQuery",
            partition_key={"name": "bucket_name", "type": dynamodb.AttributeType.STRING},
            sort_key={"name": "timestamp", "type": dynamodb.AttributeType.NUMBER},
        )


class LambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, storage_stack: StorageStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_arn = Fn.join('', [
            'arn:aws:s3:::',
            storage_stack.bucket_name
        ])

        # Create API Gateway
        api = apigw.RestApi(
            self, 'PlottingApi',
            rest_api_name='Plotting Service'
        )

        # Store the API URL
        api_url = f"https://{api.rest_api_id}.execute-api.{Stack.of(self).region}.amazonaws.com/{api.deployment_stage.stage_name}/"
        CfnOutput(self, "ApiUrl", value=api_url)

        # Create driver lambda with layer
        requests_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "RequestsLayer",
            "arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p39-requests:19"
        )

        self.driver_lambda = lambda_.Function(
            self, 'DriverLambda',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('lambda/driver'),
            timeout=Duration.seconds(300),
            layers=[requests_layer],
            environment={
                'TABLE_NAME': storage_stack.table.table_name,
                'BUCKET_NAME': storage_stack.bucket_name,
                'API_URL': api_url,
            },
        )

        # Create size-tracking lambda
        self.size_tracking_lambda = lambda_.Function(
            self, 'SizeTrackingLambda',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('lambda/size_tracking'),
            timeout=Duration.seconds(60),
            environment={
                'TABLE_NAME': storage_stack.table.table_name,
                'BUCKET_NAME': storage_stack.bucket_name,
            },
        )

        # Updated S3 permissions for size tracking lambda
        self.size_tracking_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    's3:GetObject',
                    's3:ListBucket',
                    's3:GetObjectAttributes',
                    's3:GetObjectTagging'
                ],
                resources=[
                    bucket_arn,
                    f"{bucket_arn}/*"
                ]
            )
        )

        # Create plotting lambda with layer
        matplotlib_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "MatplotlibLayer",
            "arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p39-matplotlib:1"
        )

        self.plotting_lambda = lambda_.Function(
            self, 'PlottingLambda',
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=lambda_.Code.from_asset('lambda/plotting'),
            timeout=Duration.seconds(60),
            layers=[matplotlib_layer],
            environment={
                'TABLE_NAME': storage_stack.table.table_name,
                'BUCKET_NAME': storage_stack.bucket_name,
            },
        )

        # Add DynamoDB permissions for plotting lambda
        self.plotting_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'dynamodb:Scan',
                    'dynamodb:Query',
                    'dynamodb:GetItem',
                    'dynamodb:DescribeTable'
                ],
                resources=[storage_stack.table.table_arn]
            )
        )

        # Add permissions for the Global Secondary Index if needed
        self.plotting_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'dynamodb:Scan',
                    'dynamodb:Query',
                ],
                resources=[f"{storage_stack.table.table_arn}/index/*"]
            )
        )

        # Add Lambda integration to API
        plotting_integration = apigw.LambdaIntegration(self.plotting_lambda)
        api.root.add_method('GET', plotting_integration)

        # Add permissions
        storage_stack.table.grant_read_write_data(self.size_tracking_lambda)
        storage_stack.table.grant_read_data(self.plotting_lambda)

        # Add S3 permissions for plotting lambda
        self.plotting_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    's3:PutObject',
                    's3:GetObject',
                    's3:ListBucket'
                ],
                resources=[
                    bucket_arn,
                    f"{bucket_arn}/*"
                ]
            )
        )

        # S3 permissions for driver lambda
        self.driver_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    's3:PutObject',
                    's3:GetObject',
                    's3:DeleteObject',
                    's3:ListBucket'
                ],
                resources=[
                    bucket_arn,
                    f"{bucket_arn}/*"
                ]
            )
        )

        # Add execute-api permission
        self.driver_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=['execute-api:Invoke'],
                resources=[f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:{api.rest_api_id}/*"]
            )
        )

        # Add notifications
        bucket = s3.Bucket.from_bucket_name(
            self, 'ImportedBucket', storage_stack.bucket_name
        )

        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.size_tracking_lambda),
            s3.NotificationKeyFilter(suffix='.txt')
        )

        bucket.add_event_notification(
            s3.EventType.OBJECT_REMOVED,
            s3n.LambdaDestination(self.size_tracking_lambda),
            s3.NotificationKeyFilter(suffix='.txt')
        )