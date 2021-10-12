# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda function to reserve available CIDR blocks"""
import os
import logging
import traceback
from utils import cidr_lookups, cidr_lock
from utils.cidr_lookups import InputValidationError, NoValidSubnetError, InvalidCloudProviderError, MissingRegionError

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# CIDR DDB Table
ALLOCATED_CIDR_DDB_TABLE_NAME = os.environ['ALLOCATED_CIDR_DDB_TABLE_NAME']


def handler(event, context):
    """Lambda handler"""
    try:
        LOGGER.info('Received CIDR reserve request event: %s', event)
        try:
            # Extract and validate request params
            request_params = cidr_lookups.extract_post_request_params(event)
        except InputValidationError as err:
            LOGGER.error(err)
            return {
                'statusCode': 400,
                'body': str(err.message)
            }
        # Unpack params
        account_alias = request_params.get('account_alias')
        cidr_size = request_params.get('size')
        region = request_params.get('region')
        cloud_provider = request_params.get('cloud_provider')
        LOGGER.info("Request info: subnet size {}, region {}, account_alias {}, cloud {}"
                    .format(cidr_size, region, region, account_alias, cloud_provider))
        # Get CIDR lock
        try:
            cidr_lock.sync_obtain_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
        except cidr_lock.FailedToGetLockException:
            LOGGER.exception("Returning after failed to get lock:{}".format(cidr_lock.FailedToGetLockException))
            return {
                'statusCode': 500,
                'body': "Failed to get CIDR table lock."
            }
        # Retrieve regions CIDR list
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
        # Retrieve allocated VPC CIDRs in region
        locked_cidr_list = cidr_lookups.retrieve_used_cidrs(region, False, False, cloud_provider.lower(),
                                                            ALLOCATED_CIDR_DDB_TABLE_NAME)
        LOGGER.info('Retrieve locked CIDR blocks in %s: %s', region, locked_cidr_list)
        # Find the next available CIDR, if one exists
        try:
            available_cidr = cidr_lookups.find_available_cidr(region_cidr_list,
                                                              locked_cidr_list,
                                                              cidr_size)
        except NoValidSubnetError as e:
            traceback.print_exc()
            LOGGER.info("No valid subnet found: %s", str(e))
            # Clear CIDR lock
            cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
            return {
                'statusCode': 404,
                'body': "No CIDR blocks of appropriate size found."
            }
        # Reserve CIDR
        LOGGER.info('Allocating CIDR block %s in %s', available_cidr, region)
        response = cidr_lookups.reserve_cidr(available_cidr, region,
                                             account_alias, cloud_provider,
                                             ALLOCATED_CIDR_DDB_TABLE_NAME)
        LOGGER.info('CIDR allocation status: %s', response)
        # Clear CIDR lock
        cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
        return response
    except Exception as error:
        traceback.print_exc()
        LOGGER.error("Error: %s", str(error))
        # Clear CIDR lock
        cidr_lock.clear_table_lock(ALLOCATED_CIDR_DDB_TABLE_NAME)
        return {
            'statusCode': 500,
            'body': str(error)
        }
