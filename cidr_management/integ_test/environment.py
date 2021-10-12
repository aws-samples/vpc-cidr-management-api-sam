# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Set up configurations for CIDR integration"""
import json
import os
import sys
import boto3
import logging

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

BASE_PATH = os.path.dirname(__file__)
sys.path.append(os.path.join(BASE_PATH, '..'))
sys.path.append(os.path.join(BASE_PATH, '../..'))
from utils.bdd_utils import bdd_utils

def before_all(context):
    """
    Prepare BDD testing environment

    Args:
        context: behave framework default args
    """
    # Set BDD test vars
    with open('cidr_management/config/config.{}.json'.format('dev')) as env_config_file:
        env_configs = json.load(env_config_file)
        context.cidr_ddb_table_name = env_configs['ENVIRONMENT']['ALLOCATED_CIDR_DDB_TABLE_NAME']
    # Set stack outputs to BDD vars
    stack_outputs = get_stack_outputs()
    api_outputs = [output for output in stack_outputs if output["OutputKey"] == "ServiceEndpoint"]
    api_endpoint = api_outputs[0]["OutputValue"]
    context.hostname = api_endpoint + "/Prod/v1/clouds/"
    context.stack_outputs = stack_outputs
    # Set mock auth token
    context.access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"


def before_scenario(context, scenario):
    # Add BDD CIDRs to CIDR data
    context.cidr_file = bdd_utils.upload_region_cidrs_file()
    # Add BDD data to DDB table
    context.reserved_cidr_data = bdd_utils.add_dynamodb_entry(context.cidr_ddb_table_name)


def after_scenario(context, scenario):
    # Remove BDD data from DDB table
    context.cidr_file = bdd_utils.prune_region_cidrs_file()
    # Remove BDD CIDRs from CIDR data
    bdd_utils.remove_dynamodb_entry(context.cidr_ddb_table_name)


def get_stack_outputs():
    stack_name = os.environ.get("AWS_SAM_STACK_NAME")
    if not stack_name:
        raise Exception(
            "Cannot find env var AWS_SAM_STACK_NAME. \n"
            "Please setup this environment variable with the stack name where we are running integration tests."
        )
    client = boto3.client("cloudformation")
    try:
        response = client.describe_stacks(StackName=stack_name)
    except Exception as e:
        LOGGER.exception("error:{}".format(e))
        raise Exception(
            f"Cannot find stack {stack_name}. \n" f'Please make sure stack with the name "{stack_name}" exists.'
        ) from e

    stacks = response["Stacks"]
    stack_outputs = stacks[0]["Outputs"]
    return stack_outputs
