import os
import boto3
import json
import time

import botocore
from botocore.exceptions import ClientError
import logging

iam = boto3.client('iam')
sts = boto3.client('sts')
s3_dev = boto3.client('s3')


# Create IAM roles
def create_role(role_name):
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    try:
        return iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"Role {role_name} already exists. Using existing role.")
        return iam.get_role(RoleName=role_name)


# Attach IAM policies to roles
def attach_iam_policy(policy_arn, role_name):
    response = iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_arn
    )
    print(f"Attached policy {policy_arn} to role {role_name}")


# Create or get a custom IAM policy
def create_custom_policy(policy_name, policy_document):
    try:
        # Try to get the policy if it exists
        response = iam.get_policy(
            PolicyArn=f"arn:aws:iam::{iam.get_user()['User']['Arn'].split(':')[4]}:policy/{policy_name}")
        print(f"Policy {policy_name} already exists")
        return response['Policy']['Arn']
    except iam.exceptions.NoSuchEntityException:
        # If the policy doesn't exist, create it
        response = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"Created new policy: {policy_name}")
        return response['Policy']['Arn']


# Create an IAM user and generate access keys
def create_user_and_get_info(username):
    # Create user if not exists
    try:
        response = iam.create_user(UserName=username)
        user_arn = response['User']['Arn']
        print(f"Created new IAM user: {username}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"IAM user {username} already exists")
        # Get ARN for existing user
        try:
            response = iam.get_user(UserName=username)
            user_arn = response['User']['Arn']
        except ClientError as e:
            print(f"Error retrieving user information: {e}")

    # Create access key
    try:
        response = iam.create_access_key(UserName=username)
        access_key = response['AccessKey']
        print(f"Created new access key for user: {username}")
    except ClientError as e:
        print(f"Error creating access key: {e}")

    return user_arn, access_key


# Allow user to assume a specific role by updating the role trust relationship and attaching a policy
def allow_user_to_assume_role(username, role_name):
    account_id = sts.get_caller_identity()['Account']
    policy_name = f"Assume{role_name}Policy"

    # Try to retrieve the policy allowing the user to assume the role
    try:
        existing_policy = iam.get_policy(PolicyArn=f"arn:aws:iam::{account_id}:policy/{policy_name}")
        policy_arn = existing_policy['Policy']['Arn']
    except ClientError as e:
        # If the policy doesn't exist, create a new one
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": f"arn:aws:iam::{account_id}:role/{role_name}"
            }]
        }
        policy_arn = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )['Policy']['Arn']

    # Attach the policy to the user
    try:
        iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
        print(f"Attached {policy_name} to user {username}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidInput':
            print(f"Policy {policy_name} is already attached to user {username}")
        else:
            print(f"Error attaching policy: {e}")

    # update role trust relationship
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": user_arn},
            "Action": "sts:AssumeRole"
        }]
    }
    iam.update_assume_role_policy(
        RoleName=role_name,
        PolicyDocument=json.dumps(trust_policy)
    )
    print(f"Updated trust relationship for role {role_name}")


def assume_role_and_get_s3_client(username, role_name, access_key, session_name='Session'):
    allow_user_to_assume_role(username, role_name)
    print(f"Allowing user '{username}' to assume role '{role_name}'... Waiting for propagation")
    time.sleep(10)

    new_sts = boto3.client('sts',
                           aws_access_key_id=access_key['AccessKeyId'],
                           aws_secret_access_key=access_key['SecretAccessKey'])
    response = new_sts.get_caller_identity()

    # Assume the role
    try:
        assumed_role = new_sts.assume_role(
            RoleArn=f"arn:aws:iam::{response['Account']}:role/{role_name}",
            RoleSessionName=session_name
        )
        print(f"Role {role_name} assumed successfully")
    except botocore.exceptions.ClientError as e:
        print(f"Error assuming role: {e}")
        return None, None

    credentials = assumed_role['Credentials']
    sts_client = boto3.client('sts',
                               aws_access_key_id=credentials['AccessKeyId'],
                               aws_secret_access_key=credentials['SecretAccessKey'],
                               aws_session_token=credentials['SessionToken'])

    s3_client = boto3.client('s3',
                              aws_access_key_id=credentials['AccessKeyId'],
                              aws_secret_access_key=credentials['SecretAccessKey'],
                              aws_session_token=credentials['SessionToken'])

    # Verify the assumed role
    try:
        response = sts_client.get_caller_identity()
        print(f"Current identity after assuming role: {response['Arn']}")
    except botocore.exceptions.ClientError as e:
        print(f"Error verifying assumed role: {e}")
    return s3_client


# Calculate total size of objects with prefix
def calculate_total_size(bucket_name, prefix):
    total_size = 0
    object_count = 0

    try:
        # List objects
        response = s3_user.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            for obj in response['Contents']:
                total_size += obj['Size']
                object_count += 1
    except Exception as e:
        logging.error(f"Error retrieving objects from bucket {bucket_name} with prefix {prefix}: {e}")
        return None, None

    return total_size, object_count


def delete_all_objects_and_bucket(s3, bucket_name):
    # List all objects in the bucket
    response = s3.list_objects_v2(Bucket=bucket_name)

    # If the bucket has objects, delete them
    if 'Contents' in response:
        for obj in response['Contents']:
            s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
            print(f"Deleted object {obj['Key']} from bucket [{bucket_name}]")
    else:
        print(f"No objects found in {bucket_name}")

    # Now delete the bucket
    s3.delete_bucket(Bucket=bucket_name)
    print(f"Deleted bucket [{bucket_name}]")


if __name__ == '__main__':
    # custom user policy
    user_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket",
                    "s3:GetObject"
                ],
                "Resource": "*"
            }
        ]
    }

    # create dev and user role
    dev_role = create_role('Dev')
    user_role = create_role('User')

    # attach policy to the role
    attach_iam_policy("arn:aws:iam::aws:policy/AmazonS3FullAccess", 'Dev')
    user_policy_arn = create_custom_policy("UserPolicy30", user_policy_document)
    attach_iam_policy(user_policy_arn, 'User')

    username = 'user138'
    user_arn, access_key = create_user_and_get_info(username)

    s3_dev = assume_role_and_get_s3_client(username, 'Dev', access_key)

    # Create bucket and add objects
    bucket_name = 'lecture1-weizesun'
    s3_dev.create_bucket(Bucket=bucket_name)
    s3_dev.put_object(Bucket=bucket_name, Key='assignment1.txt', Body='Empty Assignment 1')
    s3_dev.put_object(Bucket=bucket_name, Key='assignment2.txt', Body='Empty Assignment 2')

    current_directory = os.getcwd()
    image_path = os.path.join(current_directory, 'image.jpg')
    with open(image_path, 'rb') as image:
        s3_dev.put_object(Bucket=bucket_name, Key='recording1.jpg', Body=image)

    # Check if files added successfully
    objects = s3_dev.list_objects_v2(Bucket=bucket_name)
    for obj in objects['Contents']:
        print(f"Added object {obj['Key']} to bucket [{bucket_name}]")

    # Switch to user role
    s3_user = assume_role_and_get_s3_client(username, 'User', access_key)

    prefix = 'assignment'
    total_size, object_count = calculate_total_size(bucket_name, prefix)
    print(f"Bucket: {bucket_name}")
    print(f"  Objects with prefix '{prefix}': {object_count}")
    print(f"  Total size: {total_size} bytes")

    # Switch back to user role
    s3_dev = assume_role_and_get_s3_client(username, 'Dev', access_key)

    # Delete all the objects and bucket
    delete_all_objects_and_bucket(s3_dev, bucket_name)

    # Make sure everything is deleted
    buckets = s3_dev.list_buckets().get('Buckets', [])
    if buckets:
        print("Buckets found")
    else:
        print("No buckets found.")
