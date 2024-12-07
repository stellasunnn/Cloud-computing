#!/usr/bin/env python3
import os

import aws_cdk as cdk

from assignment4_cdk.assignment4_cdk_stack import Assignment4Stack


app = cdk.App()
Assignment4Stack(app, "Assignment4Stack")

app.synth()
