import { S3Event, Context } from 'aws-lambda';
import { S3, DynamoDB } from 'aws-sdk';

const s3 = new S3();
const dynamodb = new DynamoDB.DocumentClient();
const dstBucket = process.env.DST_BUCKET_NAME!;
const tableName = process.env.TABLE_NAME!;

export async function lambda_handler(event: S3Event, context: Context) {
  console.log('Received event:', event);

  for (const record of event.Records) {
    const sourceObject = decodeURIComponent(record.s3.object.key);
    
    if (record.eventName.startsWith('ObjectCreated')) {
      // Handle PUT event
      const timestamp = Date.now();
      const copyKey = `${sourceObject}_${timestamp}`;
      
      console.log('dstBucket: ', dstBucket, 'copyKey:', copyKey)
      // Copy object to destination bucket
      await s3.copyObject({
        Bucket: dstBucket,
        Key: copyKey,
        CopySource: `${record.s3.bucket.name}/${sourceObject}`,
      }).promise();
      
      // Get existing copies - Fixed ProjectionExpression with ExpressionAttributeNames
      const existingCopies = await dynamodb.query({
        TableName: tableName,
        KeyConditionExpression: 'sourceObject = :src',
        ExpressionAttributeValues: {
          ':src': sourceObject,
        },
        ExpressionAttributeNames: {
          '#ts': 'timestamp',
          '#ck': 'copyKey'
        },
        ProjectionExpression: '#ck, #ts',
        ScanIndexForward: true, // ascending order by timestamp
      }).promise();
      
      // Delete oldest copy if exists
      if (existingCopies.Items && existingCopies.Items.length > 0) {
        const oldestCopy = existingCopies.Items[0];
        await s3.deleteObject({
          Bucket: dstBucket,
          Key: oldestCopy.copyKey,
        }).promise();
        
        await dynamodb.delete({
          TableName: tableName,
          Key: {
            sourceObject: sourceObject,
            timestamp: oldestCopy.timestamp,
          },
        }).promise();
      }
      
      await dynamodb.put({
        TableName: tableName,
        Item: {
          sourceObject,
          timestamp,
          copyKey,
          status: 'active',
        },
      }).promise();
      
    } else if (record.eventName.startsWith('ObjectRemoved')) {
      // Handle DELETE event
      const now = Date.now();
      
      // Mark copies as disowned
      const copies = await dynamodb.query({
        TableName: tableName,
        KeyConditionExpression: 'sourceObject = :src',
        ExpressionAttributeValues: {
          ':src': sourceObject,
        },
      }).promise();
      
      if (copies.Items) {
        for (const copy of copies.Items) {
          await dynamodb.update({
            TableName: tableName,
            Key: {
              sourceObject: copy.sourceObject,
              timestamp: copy.timestamp,
            },
            UpdateExpression: 'SET #status = :status, deletedAt = :deletedAt',
            ExpressionAttributeNames: {
              '#status': 'status',
            },
            ExpressionAttributeValues: {
              ':status': 'disowned',
              ':deletedAt': now,
            },
          }).promise();
        }
      }
    }
  }
}
