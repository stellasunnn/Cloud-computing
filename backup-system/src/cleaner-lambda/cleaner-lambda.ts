import { Context } from 'aws-lambda';
import { S3, DynamoDB } from 'aws-sdk';

const s3 = new S3();
const dynamodb = new DynamoDB.DocumentClient();
const dstBucket = process.env.DST_BUCKET_NAME!;
const tableName = process.env.TABLE_NAME!;

export async function lambda_handler(event: any, context: Context) {  // Changed from handler to lambda_handler
  const now = Date.now();
  const cutoffTime = now - 10000;
  
  // Query disowned copies older than 10 seconds
  const disownedCopies = await dynamodb.query({
    TableName: tableName,
    IndexName: 'DisownedIndex',
    KeyConditionExpression: '#status = :status AND deletedAt <= :cutoff',
    ExpressionAttributeNames: {
      '#status': 'status',
    },
    ExpressionAttributeValues: {
      ':status': 'disowned',
      ':cutoff': cutoffTime,
    },
  }).promise();
  
  if (disownedCopies.Items) {
    for (const copy of disownedCopies.Items) {
      // Delete copy from S3
      await s3.deleteObject({
        Bucket: dstBucket,
        Key: copy.copyKey,
      }).promise();
      
      // Delete record from DynamoDB
      await dynamodb.delete({
        TableName: tableName,
        Key: {
          sourceObject: copy.sourceObject,
          timestamp: copy.timestamp,
        },
      }).promise();
    }
  }
}
