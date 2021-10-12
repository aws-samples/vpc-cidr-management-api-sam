# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=duplicate-code
"""Lambda function to return available CIDR blocks"""
import os
import json
import traceback
import logging
from utils import cidr_lookups, cidr_lock
from utils.cidr_lookups import InputValidationError, InvalidCloudProviderError, MissingRegionError

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# CIDR DDB Table
ALLOCATED_CIDR_DDB_TABLE_NAME = os.environ['ALLOCATED_CIDR_DDB_TABLE_NAME']


def handler(event, context):
    """Lambda handler"""
    try:
        LOGGER.info('Received CIDR return available event: %s', event)
        try:

            # Extract and validate request params
            request_params = cidr_lookups.extract_request_params(event)
        except InputValidationError as err:
            LOGGER.error("Invalid input params to validate: %s", err)
            return {
                'statusCode': 400,
                'body': str(err.message)
            }
        # Unpack params
        subnet_prefix = request_params.get('size')
        region = request_params.get('region')
        is_assigned = request_params.get('assigned')
        is_locked = request_params.get('locked')
        cloud_provider = request_params.get('cloud_provider')
        LOGGER.info("Request info: subnet size {}, region {}, assigned {}, locked {}, cloud {}"
                    .format(subnet_prefix, region, is_assigned, is_locked, cloud_provider))
        # Get CIDR lock
        try:
            cidr_lock.sync_obtain_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
        except cidr_lock.FailedToGetLockException:
            return {
                'statusCode': 500,
                'body': "Failed to get CIDR table lock."
            }
        # Retrieve top-level CIDRs for a region
        try:
            region_cidr_list = cidr_lookups.retrieve_region_cidr(region, cloud_provider)
        except InvalidCloudProviderError:
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                'statusCode': 400,
                'body': "Invalid cloud provider."
            }
        except MissingRegionError:
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                'statusCode': 404,
                'body': "No root CIDR list found for the specified region."
            }
        LOGGER.info("Retrieved region CIDR list: %s", region_cidr_list)
        # Retrieve list of CIDRs that are already allocated
        used_cidr_list = cidr_lookups.retrieve_used_cidrs(region, is_locked, is_assigned,
                                                          cloud_provider.lower(), ALLOCATED_CIDR_DDB_TABLE_NAME)
        LOGGER.info('Retrieve used CIDR blocks in %s: %s', region, used_cidr_list)
        # If requested locked or assigned CIDRs, return this list
        if is_locked:
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "cidrs": used_cidr_list
                })
            }
        # If requested all CIDRs, find all all available in region
        allocated_cidr_list = cidr_lookups.list_all_available_cidr(region_cidr_list,
                                                                   used_cidr_list,
                                                                   subnet_prefix)
        LOGGER.info('All available CIDRs in %s: %s', region, allocated_cidr_list)
        # If requested all available CIDRs, return this list
        if allocated_cidr_list:
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "cidrs": allocated_cidr_list
                })
            }
        # If none found, return empty
        else:
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                    'statusCode': 404,
                    'body': "No CIDR blocks of appropriate size found."
            }
    except Exception as error:
        traceback.print_exc()
        LOGGER.error("Error: %s", str(error))
        # Clear CIDR lock
        cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
        return {
            'statusCode': 500,
            'body': str(error)
        }
