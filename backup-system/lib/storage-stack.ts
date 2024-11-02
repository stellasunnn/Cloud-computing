import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

export class StorageStack extends cdk.Stack {
  public readonly srcBucketName: string;
  public readonly dstBucketName: string;
  public readonly tableName: string;
  public readonly tableArn: string;

  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const srcBucket = new s3.Bucket(this, 'SrcBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    this.srcBucketName = srcBucket.bucketName;

    const dstBucket = new s3.Bucket(this, 'DstBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    this.dstBucketName = dstBucket.bucketName;

    const table = new dynamodb.Table(this, 'TableT', {
      partitionKey: { name: 'sourceObject', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.NUMBER },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    this.tableName = table.tableName;
    this.tableArn = table.tableArn;
    
    table.addGlobalSecondaryIndex({
      indexName: 'DisownedIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'deletedAt', type: dynamodb.AttributeType.NUMBER }, 
      projectionType: dynamodb.ProjectionType.ALL,
    });

  }
}
