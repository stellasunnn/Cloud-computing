import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as path from 'node:path';

interface ReplicatorStackProps extends cdk.StackProps {
  srcBucketName: string;
  dstBucketName: string;
  tableName: string;
}

export class ReplicatorStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ReplicatorStackProps) {
    super(scope, id, props);

    const { srcBucketName, dstBucketName, tableName } = props;
    const lambda_bucket = s3.Bucket.fromBucketName(this, "codebucket", 
    "mylambda1101")
    // Define the Replicator Lambda function
    const replicatorLambda = new lambda.Function(this, 'ReplicatorLambda', {
      runtime: lambda.Runtime.NODEJS_LATEST,
      handler: 'replicator-lambda.lambda_handler',
      code: lambda.Code.fromAsset(path.join(path.dirname(__dirname), 'src', 'replicator-lambda')),
      environment: {
        DST_BUCKET_NAME: dstBucketName,
        TABLE_NAME: tableName,
      },
    });

    // Grant permissions for Replicator Lambda
    replicatorLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
        resources: [`arn:aws:s3:::${dstBucketName}/*`],
      })
    );


    // Grant permissions for Replicator Lambda
    replicatorLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
        resources: [`arn:aws:s3:::${srcBucketName}/*`],
      })
    );

    replicatorLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:PutItem', 'dynamodb:Query', 'dynamodb:UpdateItem', 'dynamodb:DeleteItem'],
        resources: [`arn:aws:dynamodb:${this.region}:${this.account}:table/${tableName}`],
      })
    );

    // Add CloudWatch Permissions
//    replicatorLambda.addToRolePolicy(
 //     new iam.PolicyStatement({
  //      actions: [
  //        'logs:CreateLogGroup',
   //       'logs:CreateLogStream',
    //      'logs:PutLogEvents'
     //   ],
       // resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/lambda/${replicatorLambda.functionName}:*`]
      //})
    //);

    // Add S3 Event Notification for PUT and DELETE events
    const srcBucket = s3.Bucket.fromBucketName(this, 'ImportedSrcBucket', srcBucketName);
    srcBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(replicatorLambda)
    );
    srcBucket.addEventNotification(
      s3.EventType.OBJECT_REMOVED,
      new s3n.LambdaDestination(replicatorLambda)
    );
  }
}
