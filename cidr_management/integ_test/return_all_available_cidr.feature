@integration_test
@ABGN-8306-query-available-CIDRs
Feature: Test retrieve available CIDR blocks

Scenario Outline: Retrieve CIDR block
  Given The API GET v1/clouds/ exists
  And The example CIDR region data for region is loaded into S3
  And The example reserved CIDR data is loaded into DynamoDB
  When We issue a request with <region>, <size>, <locked>, <cloud>, and <assigned> parameters
  Then The response code of the request is <status>
  And The response message is <return_string>

    Examples: CIDR requests
       | description                                | token   | cloud | region        | size | locked | assigned | status | return_string                                                                     |
       | CIDR too big                               | valid   | aws   | us-east-1-bdd | /15  | false  | false    | 400    | Invalid CIDR Size.                                                                |
       | CIDR too small                             | valid   | aws   | us-east-1-bdd | /29  | false  | false    | 400    | Invalid CIDR Size.                                                                |
       | No region found                            | valid   | aws   | us-east-3-bdd | /27  | false  | false    | 404    | No root CIDR list found for the specified region.                                 |
       | No cloud provider                          | valid   | test  | us-east-1-bdd | /27  | false  | false    | 400    | Invalid cloud provider.                                                           |