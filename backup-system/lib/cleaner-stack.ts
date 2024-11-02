import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets'; 

import * as path from 'node:path';


interface CleanerStackProps extends cdk.StackProps {
  dstBucketName: string;
  tableName: string;
}

export class CleanerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: CleanerStackProps) {
    super(scope, id, props);

    const { dstBucketName, tableName } = props;

    const cleanerLambda = new lambda.Function(this, 'CleanerLambda', {
      runtime: lambda.Runtime.NODEJS_LATEST,
      handler: 'cleaner-lambda.lambda_handler',
      code: lambda.Code.fromAsset(path.join(path.dirname(__dirname), 'src', 'cleaner-lambda')),
      environment: {
        DST_BUCKET_NAME: dstBucketName,
        TABLE_NAME: tableName,
      },
    });
    
    // Grant permissions for Cleaner Lambda
    cleanerLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:DeleteObject'],
        resources: [`arn:aws:s3:::${dstBucketName}/*`],
      })
    );

    // Updated DynamoDB permissions to include GSI access
    cleanerLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'dynamodb:PutItem',
          'dynamodb:Query',
          'dynamodb:UpdateItem',
          'dynamodb:DeleteItem'
        ],
        resources: [
          // Permission for the table
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${tableName}`,
          // Permission for the GSI
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${tableName}/index/*`
        ],
      })
    );

    // Schedule the Cleaner Lambda function to run every minute
    new events.Rule(this, 'CleanerSchedule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(1)),
      targets: [new targets.LambdaFunction(cleanerLambda)],
    });
  }
}
