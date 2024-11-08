from programming3_cdk.stacks import StorageStack, LambdaStack
from aws_cdk import App

app = App()

storage_stack = StorageStack(app, "StorageStack")
lambda_stack = LambdaStack(app, "LambdaStack", storage_stack=storage_stack)

app.synth()
