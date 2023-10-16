import json
import os
import urllib3
import boto3

HOOK_URL=os.getenv('HOOK_URL')
CHANNEL_NAME=os.getenv('CHANNEL_NAME')    

http = urllib3.PoolManager()
SESSION_KEY={
    "aws_access_key_id":"",
        "aws_secret_access_key":"",
        "aws_session_token":""
    
}

class GetResourceHookURL:
    def __init__(self,accountId):
        self.sts_client=boto3.client('sts');

        #get session to target aws account.
        response = self.sts_client.assume_role(
            RoleArn=get_ssm_parameters_role(accountId),
            RoleSessionName="temp-session"
            )
        #set aws access config
        SESSION_KEY["aws_access_key_id"]=response['Credentials']['AccessKeyId']
        SESSION_KEY["aws_secret_access_key"]=response['Credentials']['SecretAccessKey']
        SESSION_KEY["aws_session_token"]=response['Credentials']['SessionToken']
        
    def get_ec2_name(self,instanceId):
        #get target instance tags (Alarm tags)
        ec2_name=instanceId
        ec2_client=boto3.client('ec2',  aws_access_key_id=SESSION_KEY["aws_access_key_id"],
        aws_secret_access_key=SESSION_KEY["aws_secret_access_key"],
        aws_session_token=SESSION_KEY["aws_session_token"]
        )

        #ec2_client=boto3.client('ec2');
        ec2_info=ec2_client.describe_instances(InstanceIds=[instanceId])
        for tags in ec2_info['Reservations'][0]['Instances'][0]['Tags']:
            print("###")
            print(tags)
            if tags['Key'] == 'Name':
                ec2_name=ec2_name + " (" + tags['Value'] +")"

        return ec2_name
        

def get_ssm_parameters(accountId):
    ssm_client = boto3.client('ssm');
    svc_name=ssm_client.get_parameters(Names=['SERVICE_NAME'])['Parameters'];
    
    value=svc_name[0]['Value']
# using json.loads()
# convert dictionary string to dictionary
    res = json.loads(value)
    
    return res[accountId]
 
# print result
def get_ssm_parameters_role(accountId):
    ssm_client = boto3.client('ssm');
    chnl_name=ssm_client.get_parameters(Names=['CW_IAM_ROLE_ARN'])['Parameters'];
    value=chnl_name[0]['Value']
    # using json.loads()
    # convert dictionary string to dictionary
    res = json.loads(value)
    print("IAM_ROLE_ARN : "+res[accountId])
    return res[accountId]


def affected_entites(detail,slack_msg,accountId):
    aws_svc = detail['service']
    ec2_client=GetResourceHookURL(accountId);
    
    print("########################")
    print(len(detail['affectedEntities']))

        #"value":detail['affectedEntities'][i]['entityValue']

    add_field={
        "title":"AFFECTED_ENTITY ",
        "value":"NO AFFECTED ENTITIES"
    }


    
    for i in range(len(detail['affectedEntities'])):
        if aws_svc == "EC2" and "MAINTENANCE" in aws_svc:
            slack_msg['attachments'][0]['fields'].append({
                "title":"AFFECTED_ENTITY " + str(i+1),
                "value":ec2_client.get_ec2_name(detail['affectedEntities'][i]['entityValue'])
                })
        else:
            slack_msg['attachments'][0]['fields'].append({
                "title":"AFFECTED_ENTITY " + str(i+1),
                "value":detail['affectedEntities'][i]['entityValue']
                })

    return slack_msg
    
    


def lambda_handler(event, context):
    svcAccount=event['account']
    #print(svcAccount)

    print(json.dumps(event));

    details =  str(
        event['detail']['eventDescription'][0]['latestDescription']  +
        '\n\n<https://phd.aws.amazon.com/phd/home?region=us-east-1#/event-log?eventID=' +
        event['detail']['eventArn'] +
        '|Click here> for details.'
    )
    json.dumps(details)

    slack_msg= {
            'attachments': [
                {
                    'title': ":AWS Health Event Alert:",
                    'fields': [
                        {
                            "title": "AWS ACCOUNT",
                            "value": get_ssm_parameters(svcAccount),
                        },
                        {
                            "title": "START TIME",
                            "value": event['detail']['startTime'],
                        },
                        {
                            "title": "EVENT TYPE",
                            "value": event['detail']['eventTypeCode'],
                        },
                        {
                            "title": "EVENT REGION",
                            "value": event['detail']['eventRegion']
                        }
                    ]
                }
            ]
        }
    
    msg=affected_entites(event['detail'],slack_msg,event['account'])
    
    encoded_msg = json.dumps(msg).encode("utf-8")
    resp = http.request("POST", HOOK_URL, body=encoded_msg)

    
    # TODO implement
    return {
        'body': encoded_msg
    }
