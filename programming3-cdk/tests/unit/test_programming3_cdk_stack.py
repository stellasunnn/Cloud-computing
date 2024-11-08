import aws_cdk as core
import aws_cdk.assertions as assertions

from programming3_cdk.storage_stack import Programming3CdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in programming3_cdk/storage_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = Programming3CdkStack(app, "programming3-cdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
