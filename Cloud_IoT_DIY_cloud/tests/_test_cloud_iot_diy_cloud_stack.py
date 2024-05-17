import aws_cdk as core
import aws_cdk.assertions as assertions

from cloud_iot_diy_cloud.cloud_iot_diy_cloud_stack import CloudIoTDiyCloudStack

from cloud_iot_diy_cloud.default_options import default_lambda_props, default_s3bucket_props

# example tests. To run these tests, uncomment this file along with the example
# resource in cloud_iot_diy_cloud/cloud_iot_diy_cloud_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CloudIoTDiyCloudStack(app, "cloud-iot-diy-cloud")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })

def test_default_props():
    verify_s3_props = core.aws_s3.BucketProps(**default_s3bucket_props)
    verify_lambda_default_props = core.aws_lambda.FunctionProps(*default_lambda_props)
