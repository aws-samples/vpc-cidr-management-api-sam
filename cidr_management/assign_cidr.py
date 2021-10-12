# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda function to flag available CIDR blocks"""
import os
import logging
import traceback
from utils import cidr_lookups
from utils.cidr_lookups import InputValidationError, InvalidCloudProviderError

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# CIDR DDB Table
ALLOCATED_CIDR_DDB_TABLE_NAME = os.environ['ALLOCATED_CIDR_DDB_TABLE_NAME']


def handler(event, context):
    """Lambda handler"""
    try:
        LOGGER.info('Received CIDR flag request event: %s', event)
        try:
            # Extract and validate request params
            request_params = cidr_lookups.extract_put_request_params(event)
        except InputValidationError as err:
            LOGGER.error(err)
            return {
                'statusCode': 400,
                'body':  str(err.message)
            }
        # Unpack params
        cidr_block = request_params.get('cidr_block')
        is_assigned = request_params.get('assigned')
        cloud_provider = request_params.get('cloud_provider')
        region = request_params.get('region')
        # Update CIDR flag
        return cidr_lookups.update_cidr_flag(cidr_block, is_assigned, cloud_provider,
                                             region, ALLOCATED_CIDR_DDB_TABLE_NAME)
    except Exception as error:
        traceback.print_exc()
        LOGGER.error("Error: %s", str(error))
        return {
            'statusCode': 500,
            'body': str(error)
        }
