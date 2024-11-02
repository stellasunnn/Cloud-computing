import * as cdk from 'aws-cdk-lib';
import { StorageStack } from '../lib/storage-stack';
import { ReplicatorStack } from '../lib/replicator-stack';
import { CleanerStack } from '../lib/cleaner-stack';


const app = new cdk.App();

const storageStack = new StorageStack(app, 'StorageStack');

new ReplicatorStack(app, 'ReplicatorStack', {
  srcBucketName: storageStack.srcBucketName,
  dstBucketName: storageStack.dstBucketName,
  tableName: storageStack.tableName,
});

new CleanerStack(app, 'CleanerStack', {
  dstBucketName: storageStack.dstBucketName,
  tableName: storageStack.tableName,
});