# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared methods for BDD"""
import boto3
import os
import json
import logging

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

# Initialize Logger
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def upload_region_cidrs_file():
    """
    Set mock CIDRs for BDD in S3

    Returns: operation completed successfully
    """
    # Initialize S3 client
    ssm_client = boto3.client('ssm')
    # Read mock BDD data
    file_reader = open('cidr_management/utils/test/mock_data/bdd_data_upload/us-east-1-bdd-param.json', 'r')
    mock_cidr_data = json.loads(file_reader.read())
    file_reader.close()
    # Upload BDD region 1
    ssm_client.put_parameter(
        Name='/vpcx/aws/regions/us-east-1-bdd',
        Description='Parameter for BDD',
        Value=json.dumps(mock_cidr_data),
        Type='String',
        Overwrite=True,
        Tier='Standard'
    )
    # Read mock BDD data
    file_reader = open('cidr_management/utils/test/mock_data/bdd_data_upload/us-east-2-bdd-param.json', 'r')
    mock_cidr_data = json.loads(file_reader.read())
    file_reader.close()
    # Upload BDD region 2
    ssm_client.put_parameter(
        Name='/vpcx/aws/regions/us-east-2-bdd',
        Description='Parameter for BDD',
        Value=json.dumps(mock_cidr_data),
        Type='String',
        Overwrite=True,
        Tier='Standard'
    )
    return True


def prune_region_cidrs_file():
    """
    Reset mock CIDRs for BDD in S3

    Returns: operation completed successfully
    """
    # Initialize S3 client
    ssm_client = boto3.client('ssm')
    # Delete BDD region 1
    ssm_client.delete_parameter(
        Name='/vpcx/aws/regions/us-east-1-bdd'
    )
    # Upload BDD region 2
    ssm_client.delete_parameter(
        Name='/vpcx/aws/regions/us-east-2-bdd'
    )
    return True


def add_dynamodb_entry(dynamodb_table):
    """
    Add entries to dynamodb_table before BDD execution

    Args:
        dynamodb_table: ddb table name

    Returns: Operation completed successfully
    """
    # Initialize DDB client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(dynamodb_table)
    # Read mock data
    file_reader = open('cidr_management/utils/test/mock_data/bdd_data_upload/dynamodb_entry.json', 'r')
    input_data = json.loads(file_reader.read())
    file_reader.close()
    # Add data to DDB
    for entry in input_data:
        raw_data = input_data[entry]
        response = ddb_table.put_item(
            Item={
                'cidr_block': raw_data['cidr-block'],
                'region': raw_data['region'].upper(),
                'locked': raw_data['locked'],
                'assigned': raw_data['assigned'],
                'cloud': raw_data['cloud'].upper()
            }
        )
        LOGGER.info("Response for put item is {}".format(response))
        if response['ResponseMetadata']['HTTPStatusCode'] not in [200, 201]:
            raise Exception('Failed to put items in DDB')
    # Return success
    return True


def remove_dynamodb_entry(dynamodb_table):
    """
    Remove entries to dynamodb_table after BDD execution

    Args:
        dynamodb_table: ddb table name

    Returns: Operation completed successfully
    """
    # Initialize DDB client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(dynamodb_table)
    # Read DDB data
    resp = ddb_table.scan()
    # Delete everything that has 'bdd' in the region
    for entry in resp['Items']:
        if '-BDD' in entry['region']:
            operation = ddb_table.delete_item(Key={'cidr_block': entry['cidr_block']})
            LOGGER.info("Remove item response for entry {} is {} ".format(entry['cidr_block'], operation))
    # Return success
    return True


def get_dynamodb_entry(cidr, dynamodb_table):
    """
    Retrieve CIDR from DDB for BDD evaluation

    Args:
        cidr: primary key
        dynamodb_table: ddb table name

    Returns: CIDR data from DDB
    """
    # Initialize DDB client
    ddb_resource = boto3.resource('dynamodb')
    ddb_table = ddb_resource.Table(dynamodb_table)
    # Try to find item
    try:
        resp = ddb_table.get_item(
            Key={
                'cidr_block': cidr,
            }
        )
        if 'Item' in resp:
            return {
                'statusCode': 200,
                'body': resp['Item']
            }
        else:
            raise Exception('Item not found.')
    except Exception as e:
        return {
            'statusCode': 404,
            'body': str(e)
        }
