# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lock CIDR table to prevent concurrency issues"""
import logging
import time
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError


# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# Define constant for locked key in DDB
LOCKED_KEY = 'LOCKED'


def sync_obtain_table_lock(lock_table_name):
    """
    Obtain a lock on the CIDR table.  If currently locked, then wait

    Args:
        lock_table_name: table name used for DynamoDB locks on CIDR table

    Returns: bool (locked)
    """
    LOGGER.info("Attempting to obtain CIDR table lock")
    # Initialize boto client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(lock_table_name)
    # Get lock
    lock_obtained = False
    backoff = 5
    while not lock_obtained:
        # Define expiry time for lock.  After 60 seconds, lock auto-expires
        expiry_time = int(time.time()) + 60
        try:
            ddb_table.put_item(
                Item={
                    'cidr_block': LOCKED_KEY,
                    'lock_expiration': expiry_time
                },
                ConditionExpression=Attr("cidr_block").not_exists()
            )
            lock_obtained = True
            LOGGER.info('Lock obtained.  Expiry time %s', str(expiry_time))
        except ClientError as e:
            LOGGER.exception(e)
            # If conditional check failed, then try again
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # If backoff is greater than 30 seconds, then raise exception
                if backoff > 60:
                    raise FailedToGetLockException()
                else:
                    LOGGER.info("Failed to obtain lock. Retrying after %s seconds")
                    time.sleep(backoff)
                    backoff += (backoff * 1.5)
            # If other error, then raise it
            else:
                raise e
    return lock_obtained


def clear_table_lock(lock_table_name):
    """
    Clear a lock on the DDB CIDR table

    Args:
        lock_table_name: table name used for DynamoDB locks on CIDR table

    Returns: bool (lock cleared)
    """
    LOGGER.info("Attempting to clear CIDR table lock")
    # Initialize boto client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(lock_table_name)
    try:
        ddb_table.delete_item(
            Key={
                'cidr_block': LOCKED_KEY
            }
        )
        LOGGER.info("Successfully CIDR table lock")
    except ClientError as e:
        LOGGER.info("Failed to clear CIDR lock: %s", str(e))
        LOGGER.exception(e)
    return True


class FailedToGetLockException(Exception):
    """
    Exception raised when failed to obtain lock

    Attributes:
        message -- Description of the error
    """

    def __init__(self, message="Failed to obtain lock."):
        self.message = message
        super().__init__(self.message)
