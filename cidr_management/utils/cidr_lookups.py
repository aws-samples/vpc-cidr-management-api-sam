# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared functions for CIDR management"""
import os
import ipaddress
import time
import json
import logging
import traceback
from urllib.parse import unquote
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from utils import cidr_lock

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# Read configurable subnet prefix sizes
SUBNET_PREFIX_LOW = int(os.environ.get('SUBNET_PREFIX_LOW', 16))
SUBNET_PREFIX_HIGH = int(os.environ.get('SUBNET_PREFIX_HIGH', 27))


def retrieve_region_cidr(region, cloud_provider):
    """
    Retrieve CIDR blocks in param store

    Args:
        region: Region for which the root CIDR list needs to be retrieved
        cloud_provider: cloud provider

    Returns: list of top-level blocks allocated to a region
    """
    # Initialize boto client
    ssm_client = boto3.client('ssm')
    # Get region param
    try:
        response = ssm_client.get_parameter(
            Name='/vpcx/aws/regions/{}'.format(region),
        )
        LOGGER.info('Retrieved region param: %s', response['Parameter'])
    except ssm_client.exceptions.ParameterNotFound:
        LOGGER.info("Region not found in parameter store.")
        raise MissingRegionError()
    # Get param value
    param_value = json.loads(response['Parameter']['Value'])
    # Check cloud provider
    if cloud_provider.upper() not in param_value.get('master-cidr', {}):
        raise InvalidCloudProviderError()
    else:
        cidr_list = param_value.get('master-cidr', {}).get(cloud_provider.upper(), {}).get('cidrs', [])
        LOGGER.info("Returning results %s for region %s and provider %s", cidr_list, region, cloud_provider)
        return cidr_list


def retrieve_used_cidrs(region, is_locked, is_assigned, cloud_provider, ddb_table):
    """
    Retrieve CIDRs in use for a region from DDB

    Args:
        region: CIDR region
        is_locked: Parameter to filter scanned entries
        is_assigned: Parameter to filter scanned entries
        cloud_provider: cloud provider
        ddb_table: DynamoDB table used to store CIDR blocks

    Returns: list of CIDRs in use for a region
    """
    LOGGER.info("Details for used cidr table scan are: DDB Table {}, region {} , cloud provider {}"
                .format(ddb_table, region, cloud_provider))
    # Scan the DynamoDB CIDR table
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(ddb_table)
    # If locked is True, then you are looking for all locked CIDRs (assigned can be variable)
    if is_locked:
        filter_expression = Attr("cloud").eq(cloud_provider.upper()) & Attr("region").eq(region.upper()) & \
                            Attr("assigned").eq(is_assigned) & Attr("locked").eq(is_locked)
    # If locked is False, then you are looking for all *available* CIDRs.  To generate this list, we will
    # return all locked values.  The combination of top-level CIDrs and currently locked CIDRs can be used
    # to derive available CIDRs.
    else:
        filter_expression = Attr("cloud").eq(cloud_provider.upper()) & Attr("region").eq(region.upper()) & \
                            Attr("locked").eq(not is_locked)
    projection_expression = 'cidr_block'
    resp = ddb_table.scan(
        FilterExpression=filter_expression,
        ProjectionExpression=projection_expression
    )
    cidr_list = [item['cidr_block'] for item in resp['Items']]
    while 'LastEvaluatedKey' in resp:
        resp = ddb_table.scan(ExclusiveStartKey=resp['LastEvaluatedKey'],
                              FilterExpression=filter_expression,
                              ProjectionExpression=projection_expression
                              )
        cidr_list.extend([item['cidr_block'] for item in resp['Items']])
    LOGGER.info('Used CIDRs: %s', str(cidr_list))
    # If table lock in CIDR list, remove it
    if cidr_lock.LOCKED_KEY in cidr_list:
        cidr_list.remove(cidr_lock.LOCKED_KEY)
    return cidr_list


def find_available_cidr(jnj_root_cidr_list, allocated_cidr_list, subnet_prefix):
    """
    Find an available CIDR of a given size
    
    Args:
        jnj_root_cidr_list: top-level CIDRs allocated to region
        allocated_cidr_list: CIDRs currently in use in region
        subnet_prefix: requested CIDR size

    Returns: locked CIDR
    """
    available_cidr_list = list_all_available_cidr(jnj_root_cidr_list, allocated_cidr_list, subnet_prefix)
    if available_cidr_list:
        return ipaddress.IPv4Network(available_cidr_list[0])
    # No found subnets of size
    raise NoValidSubnetError()


def list_all_available_cidr(jnj_root_cidr_list, allocated_cidr_list, subnet_prefix):
    """
    Find all CIDRs of specified size from the provided top level CIDR list in the region

    Args:
        jnj_root_cidr_list: top-level CIDRs allocated to region
        allocated_cidr_list: CIDRs currently in use in region
        subnet_prefix: requested CIDR size

    Returns: locked CIDR
    """
    # Initialize result array
    available_cidr_list = []
    # Iterate through root level CIDRs
    for cidr in jnj_root_cidr_list:
        # Cast top-level CIDR string to network objet
        cidr = ipaddress.IPv4Network(cidr)
        # If top-level CIDR is smaller than requested CIDR, skip this top-level CIDR
        if int(cidr.prefixlen) > int(subnet_prefix):
            continue
        # Iterate through already allocated CIDRs
        allocated_cidr_in_master_list = [ipaddress.IPv4Network(cidr_block) for cidr_block in allocated_cidr_list if
                                         ipaddress.IPv4Network(cidr_block).overlaps(cidr)]
        # Divide the top-level CIDR into a CIDRs of the requested size
        cidr_subnets = list(cidr.subnets(new_prefix=int(subnet_prefix)))
        # Iterate through theoretical subnets and search for overlap
        for subnet in cidr_subnets:
            # Search for overlap with already allocated CIDRs
            subnet_conflict_flag = False
            for allocated_cidr in allocated_cidr_in_master_list:
                if subnet.overlaps(allocated_cidr):
                    subnet_conflict_flag = True
                    break
            # Found a conflict
            if subnet_conflict_flag:
                continue
            # This subnet has no conflicts, append to list of available subnets
            else:
                available_cidr_list.append(subnet.with_prefixlen)
    # Return results
    return available_cidr_list


def reserve_cidr(available_cidr, region, account_alias, cloud_provider, ddb_table):
    """
    Reserve a CIDR, add Entry to DynamoDB

    Args:
        available_cidr: CIDR that will be reserved
        region: Region where CIDR is requested
        account_alias: Alias that will be associated with CIDR, value inserted into DDB
        cloud_provider: Value for cloud provider, inserted into DynamoDB
        ddb_table: DynamoDB table used to store CIDR blocks

    Returns: new object status
    """
    LOGGER.info("Reserving CIDR %s", available_cidr)
    # Initialize boto client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(ddb_table)
    try:
        response = ddb_table.put_item(
            Item={
                'cidr_block': str(available_cidr),  # Required param
                'account_alias': account_alias.upper(),  # Required param
                'lock_date': time.ctime(),
                'assigned': False,
                'locked': True,
                'region': region.upper(),  # Required param
                'cloud': cloud_provider.upper()
            },
            ConditionExpression=(Attr("cidr_block").not_exists() | Attr("locked").eq(False))
        )
        LOGGER.info('CIDR reserve response: %s', response)
        # Evaluate results
        if response['ResponseMetadata']['HTTPStatusCode'] in [200, 201]:
            return {
                'statusCode': 200,
                'body': '{}'.format(available_cidr)
            }
        else:
            raise Exception('Failed to reserve CIDR block.')
    except ClientError as e:
        LOGGER.error("Error writing row to DynamoDB: %s.", str(e))
        traceback.print_exc()
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            LOGGER.error('CIDR already exists.')
            return {
                'statusCode': 400,
                'body': 'CIDR block already exists.'
            }
        else:
            raise e


def update_cidr_flag(cidr_block, is_assigned, cloud_provider, region, ddb_table):
    """
    Update CIDR flag.  Only the value of assigned may be adjusted.

    Args:
        cidr_block: CIDR Block
        is_assigned: assigned flag (boolean)
        cloud_provider: cloud provider
        region: region
        ddb_table: DynamoDB table used to store CIDR blocks

    Returns: new object status
    """
    LOGGER.info("Updating %s flags. Assigned %s.", cidr_block, is_assigned)
    # Initialize boto client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(ddb_table)
    # Set update expression
    update_expression = 'set assigned=:assigned_val'
    expression_attribute_values = {
        ':assigned_val': is_assigned
    }
    # Only CIDRs that are locked can have their assigned status updated
    locked_check_expression = Attr("locked").eq(True)
    # If attempting to set assigned to True, then ensure assigned is False.  This is because we want to
    # prevent people from attempting to assign the same CIDR twice
    if is_assigned:
        assigned_check_expression = Attr("assigned").eq(False)
    # If attempting to set assigned to False, then you are "un-assigning" a CIDR.  The value of assigned can be
    # either True or False.
    else:
        assigned_check_expression = (Attr("assigned").eq(False) | Attr("assigned").eq(True))
    # Update Item
    try:
        response = ddb_table.update_item(
            Key={
                'cidr_block': str(cidr_block)
            },
            ConditionExpression=Attr("cidr_block").exists() &
                                Attr("cloud").eq(cloud_provider.upper()) &
                                Attr("region").eq(region.upper()) &
                                locked_check_expression &
                                assigned_check_expression,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW"
        )
        LOGGER.info('CIDR update response: %s', response)
        # Evaluate results
        if response['ResponseMetadata']['HTTPStatusCode'] in [200, 201]:
            return {
                'statusCode': 200,
                'body': 'CIDR flag updated.'
            }
        else:
            raise Exception('Failed to update CIDR block.')
    except ClientError as e:
        LOGGER.error("Error updating row in DynamoDB: %s.", str(e))
        traceback.print_exc()
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            LOGGER.error('ConditionalCheckFailed for CIDR update request.')
            return {
                'statusCode': 400,
                'body': 'CIDR cannot be assigned.'
            }
        else:
            raise e


def extract_request_params(event):
    """
    Extract and validate path and querystring params

    Args:
        event: elb-lambda event

    Returns: request_params dict
    """
    # Get path and query params
    query_string_params = event['queryStringParameters']
    path_params = event['pathParameters']
    LOGGER.info("Path parameters: {}".format(path_params))
    LOGGER.info("Query parameters: {}".format(query_string_params))
    # Extract cloud provider
    cloud_provider = path_params.get('cloud').upper()
    # Validate CIDR prefix
    subnet_prefix = (query_string_params.get('size', '/' + str(SUBNET_PREFIX_HIGH))).split("/")[1]
    if int(subnet_prefix) < SUBNET_PREFIX_LOW or int(subnet_prefix) > SUBNET_PREFIX_HIGH:
        raise InputValidationError("Invalid CIDR Size.")
    # Validate query params
    assigned = str_to_bool(query_string_params.get('assigned', 'False'))
    locked = str_to_bool(query_string_params.get('locked', 'False'))
    # Scenario of assigned == True, locked == False is not allowed
    if assigned and not locked:
        raise InputValidationError('Invalid values input for flags.')
    # Return results
    return {
        'region': path_params.get('region'),
        'assigned': assigned,
        'locked': locked,
        'size': subnet_prefix,
        'cloud_provider': cloud_provider
    }


def extract_put_request_params(event):
    """
    Extract and validate path params and request body of PUT request

    Args:
        event: elb-lambda event

    Returns: request_params dict
    """
    # Get path and body params
    body = json.loads(event['body'])
    path_params = event['pathParameters']
    LOGGER.info("Path parameters: {}".format(path_params))
    LOGGER.info("Event Body: {}".format(str(body)))
    # Get flags from request body request body
    assigned = str_to_bool(str(body.get('assigned')))
    # Return results
    return {
        'region': path_params.get('region'),
        'assigned': assigned,
        'cidr_block': unquote(path_params.get('cidr')),
        'cloud_provider': path_params.get('cloud').upper()
    }


def extract_post_request_params(event):
    """
    Extract and validate path params and request body of POST (reserve cidr) request

    Args:
        event: elb-lambda event

    Returns: request_params dict
    """
    # Unpack request params
    body = json.loads(event['body'])
    path_params = event['pathParameters']
    LOGGER.info("Path split list: {}".format(path_params))
    LOGGER.info("Event Body: {}".format(str(body)))
    # Validate CIDR prefix
    subnet_prefix = (body.get('size', '/' + str(SUBNET_PREFIX_HIGH))).split("/")[1]
    LOGGER.info("subnet_prefix: {}".format(str(subnet_prefix)))
    if int(subnet_prefix) < SUBNET_PREFIX_LOW or int(subnet_prefix) > SUBNET_PREFIX_HIGH:
        raise InputValidationError("Invalid CIDR Size.")
    # Missing account alias
    account_alias = body.get('account_alias', None)
    if not account_alias:
        raise InputValidationError('Missing account alias.')
    # Add request metadata
    request_metadata = {
        'event': event
    }
    # Return event object
    return {
        'size': subnet_prefix,
        'account_alias': account_alias,
        'region': path_params.get('region'),
        'request_metadata': request_metadata,
        'cloud_provider': path_params.get('cloud').upper()
    }


class NoValidSubnetError(Exception):
    """
    Exception raised when a valid subnet is not found.

    Attributes:
        message: Description of this error
    """

    def __init__(self, message="No free CIDR range found."):
        self.message = message
        super().__init__(self.message)


class SubnetSizeError(Exception):
    """
    Exception raised when a subnet request is too small or too large.

    Attributes:
        message: Description of this error
    """

    def __init__(self, message="Invalid subnet size.."):
        self.message = message
        super().__init__(self.message)


class InputValidationError(Exception):
    """
    Exception raised when input validation fails

    Attributes:
        message -- Description of the error
    """

    def __init__(self, message="Bad Request"):
        self.message = message
        super().__init__(self.message)


class InvalidCloudProviderError(Exception):
    """
    Exception raised when no cloud provider found

    Attributes:
        message -- Description of the error
    """

    def __init__(self, message="Invalid cloud provider."):
        self.message = message
        super().__init__(self.message)


class MissingRegionError(Exception):
    """
    Exception raised when no region is found in param store

    Attributes:
        message -- Description of the error
    """

    def __init__(self, message="Region missing in param store."):
        self.message = message
        super().__init__(self.message)


def str_to_bool(param):
    """
    Convert string value to boolean

    Attributes:
        param -- inout query parameter
    """
    if param.upper() == 'TRUE':
        return True
    elif param.upper() in ['FALSE', None]:
        return False
    else:
        raise InputValidationError(
            'Invalid query parameter. Param is {} and param type is {}'.format(param, type(param)))
