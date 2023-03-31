# app.py

# Modules

import json
import boto3
import socket
from flask import Flask,  render_template, request, url_for, jsonify
from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
import traceback

# App Name

app = Flask(__name__)

# Methods

def get_ssm_param(parameter_name: str):
    """Retrieves a parameter from AWS SSM
    Args:
        parameter_name (str): Name of the parameter to get
    Returns:
        str: Value of the parameter
    """

    client = boto3.client('ssm')
    param = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return param.get('Parameter').get('Value')

def get_first_date_of_month(year, month):
    """Return the first date of the month.

    Args:
        year (int): Year
        month (int): Month

    Returns:
        date (datetime): First date of the current month
    """
    first_date = datetime(year, month, 1)
    return first_date.strftime("%Y-%m-%d")

def get_last_date_of_month(year, month):
    """Return the last date of the month.
    
    Args:
        year (int): Year, i.e. 2022
        month (int): Month, i.e. 1 for January

    Returns:
        date (datetime): Last date of the current month
    """
    last_date = datetime(year, month + 1, 1) + timedelta(days=-1)
    return last_date.strftime("%Y-%m-%d")

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

# Access content from Parameter Store

ak = get_ssm_param("tenant1_access_key")
sk = get_ssm_param("tenent1_secret_key")
region = "ap-south-1"
session = boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region)

# Define Boto Clients

budgetClient = session.client('budgets')
costExplorerclient = session.client('ce')
support_client = session.client('support')
rg_client = session.client('resourcegroupstaggingapi')

# Routes

@app.route('/')
def default():
    msg = '''
    “FinOps is the practice of bringing financial accountability to the variable spend model of cloud,
    enabling distributed teams to make business trade-offs between speed, cost, and quality.” 
    
    
    ― Devanshu & Abhay said this, don't know when, but they said this!

    '''
    return msg

@app.route("/site-map")
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))
    # links is now a list of url, endpoint tuples

    return jsonify(links)

@app.route("/connectiontest")
def get_connection():
    return {
        "connectivity": "success",
        "host": socket.gethostname()
    }

@app.route("/getallawsresources")
def get_all_aws_resources():

    response = rg_client.get_resources()
    return response

@app.route("/getawscurrentmonthbill")
def get_aws_month_bill():

    currentMonth = datetime.now().month
    currentYear = datetime.now().year

    first = get_first_date_of_month(currentYear, currentMonth)
    last = get_last_date_of_month(currentYear, currentMonth)

    response = costExplorerclient.get_cost_and_usage(
        TimePeriod={
            'Start': first,
            'End': last
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost',
        ]
    )

    return response

@app.route("/getawslastmonthbill")
def get_aws_lastmonth_bill():

    lastMonth = (datetime.now() + relativedelta(months=-1)).strftime('%m')
    currentYear = datetime.now().year

    first = get_first_date_of_month(currentYear, int(lastMonth))
    last = get_last_date_of_month(currentYear, int(lastMonth))

    response = costExplorerclient.get_cost_and_usage(
        TimePeriod={
            'Start': first,
            'End': last
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost',
        ]
    )

    return response

@app.route("/getawsdailybillforlastmonth")
def get_aws_daily_bill_for_lm():
   
    lastMonth = (datetime.now() + relativedelta(months=-1)).strftime('%m')
    currentYear = datetime.now().year

    first = get_first_date_of_month(currentYear, int(lastMonth))
    last = get_last_date_of_month(currentYear, int(lastMonth))

    response = costExplorerclient.get_cost_and_usage(
        TimePeriod={
            'Start': first,
            'End': last
        },
        Granularity='DAILY',
        Metrics=[
            'AmortizedCost',
        ]
    )

    return response

@app.route("/getawsdailybillforcurmonth")
def get_aws_daily_bill_for_cm():
   
    currentMonth = datetime.now().month
    currentYear = datetime.now().year

    first = get_first_date_of_month(currentYear, currentMonth)
    last = get_last_date_of_month(currentYear, currentMonth)

    response = costExplorerclient.get_cost_and_usage(
        TimePeriod={
            'Start': first,
            'End': last
        },
        Granularity='DAILY',
        Metrics=[
            'AmortizedCost',
        ]
    )

    return response

@app.route("/getawsbillforecast")
def get_cost_forecast():

    today = datetime.today().strftime('%Y-%m-%d')

    end_date = (datetime.now() + relativedelta(months=+1)).strftime('%Y-%m-%d')

    response = costExplorerclient.get_cost_forecast(
        TimePeriod={
            'Start': today,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metric='AMORTIZED_COST'
    )

    return response

@app.route("/refreshawsrecommendations")
def refresh_aws_recommendations():

    ta_checks = support_client.describe_trusted_advisor_checks(language='en')
    for check in ta_checks['checks']:
        support_client.refresh_trusted_advisor_check(checkId=check['id'])

    return "Refreshed"

@app.route("/getawsrecommendations")
def get_aws_recommendations():
    try:
        #support_client = boto3.client('support', region_name='us-east-1')
        ta_checks = support_client.describe_trusted_advisor_checks(language='en')
        checks_list = {ctgs: [] for ctgs in list(set([checks['category'] for checks in ta_checks['checks']]))}
        for checks in ta_checks['checks']:
            print('Getting check:' + checks['name'])
            try:
                x = str(re.findall(r'<b>Recommended Action</b>(.*?)<b>Additional Resources</b>',str(checks['description']),re.DOTALL))
                recommended_action = (x.replace("<br>", "").replace("\\n", "").replace("<br/>", "").replace("<br />", ""))
                check_summary = support_client.describe_trusted_advisor_check_summaries(
                                checkIds=[checks['id']])['summaries'][0]
                if check_summary['status'] != 'not_available' and check_summary['status'] != 'ok':
                    checks_list[checks['category']].append(
                       [checks['name'], check_summary['status'],
                        str(check_summary['resourcesSummary']['resourcesProcessed']),
                        str(check_summary['resourcesSummary']['resourcesFlagged']),
                        str(check_summary['resourcesSummary']['resourcesSuppressed']),
                        str(check_summary['resourcesSummary']['resourcesIgnored']),
                        str(recommended_action)])
            except:
                print('Failed to get check: ' + checks['id'] + ' --- ' + checks['name'])
                traceback.print_exc()
                continue
        return jsonify(checks_list)
    except:
        print('Failed! Debug further.')
        traceback.print_exc() 

@app.route("/getrightsizerecc")
def get_rightsize_recc():
    response = costExplorerclient.get_rightsizing_recommendation(
        Configuration={
            'RecommendationTarget': 'CROSS_INSTANCE_FAMILY',
            'BenefitsConsidered': True
        },
        Service = "AmazonEC2"
    )

    return response

@app.route("/getec2costs")
def get_ec2_costs():

    today = date.today()
    fourteenDaysAgo = today - timedelta(14)

    response = costExplorerclient.get_cost_and_usage_with_resources(
    Granularity='DAILY',
    Metrics=["BlendedCost", "UnblendedCost", "UsageQuantity"],
    TimePeriod={
        'Start': str(fourteenDaysAgo),
        'End': str(today)
    },
    Filter={
        "Dimensions": {
            "Key": "SERVICE",
            "Values": ["Amazon Elastic Compute Cloud - Compute"]
        }
    },
    GroupBy=[{
        "Type": "DIMENSION",
        "Key": "RESOURCE_ID"
    }])

    return response

@app.route("/getrdscosts")
def get_rds_costs():

    today = date.today()
    fourteenDaysAgo = today - timedelta(14)

    response = costExplorerclient.get_cost_and_usage_with_resources(
    Granularity='DAILY',
    Metrics=["BlendedCost", "UnblendedCost", "UsageQuantity"],
    TimePeriod={
        'Start': str(fourteenDaysAgo),
        'End': str(today)
    },
    Filter={
        "Dimensions": {
            "Key": "SERVICE",
            "Values": ["RDS"]
        }
    },
    GroupBy=[{
        "Type": "DIMENSION",
        "Key": "RESOURCE_ID"
    }])

    return response

"""
Function to create Budget and associated Notification 

Arguments:                                                                                                                            
  accId: Account ID                                                                                                                   
  budgetName: Name for the Budget                                                                                                     
  limitAmt : The cost or usage amount that is associated with a budget forecast, actual spend, or budget threshold.                   
  limitUnit: The unit of measurement that is used for the budget forecast, actual spend, or budget threshold, such as dollars or GB.  
  timeUnit: The length of time until a budget resets the actual and forecasted spend. Can be 'DAILY'|'MONTHLY'|'QUARTERLY'|'ANNUALLY' 
  thresholdPercent: The threshold that is associated with a notification. Thresholds are always a percentage                          
  emailToNotify: The email address that AWS sends budget notifications to                                                             
Request Call:                                                                                                                         
  dictToSend = {                                                                                                                      
      'accountId':'what is the answer?',                                                                                              
      'budgetName': '',                                                                                                               
      'limitAmt': '',                                                                                                                 
      'limitUnit': '',                                                                                                                
      'timeUnit': '',                                                                                                                 
      'thresholdPercent': '',                                                                                                         
      'emailToNotify': ''                                                                                                             
  }                                                                                                                                   
  res = requests.post('http://localhost:5000/create/budgetnotification', json=dictToSend)

"""
@app.route("/create/budgetnotification", methods=['POST'])
def budget_notification():
    data_to_be_used = json.loads(request.get_json(force=True))
    accId = data_to_be_used["accountId"]
    budgetName = data_to_be_used["budgetName"]
    limitAmt = data_to_be_used["limitAmt"]
    limitUnit = data_to_be_used["limitUnit"]
    timeUnit = data_to_be_used["timeUnit"]
    thresholdPercent = data_to_be_used["thresholdPercent"]
    emailToNotify = data_to_be_used["emailToNotify"]

    responseBudgetCreation = budgetClient.create_budget(
        AccountId=accId,
        Budget={
            'BudgetName': budgetName,
            'BudgetLimit': {
                'Amount': limitAmt,
                'Unit': limitUnit
            },
            'CostTypes': {
                'IncludeTax': True,
                'IncludeSubscription': True,
                'UseBlended': True,
                'IncludeOtherSubscription': True,
                'IncludeSupport': True,
                'IncludeDiscount': True
            },
            'TimeUnit': timeUnit,
            'BudgetType': 'USAGE'
        },
        NotificationsWithSubscribers=[
            {
                'Notification': {
                    'NotificationType': 'ACTUAL',
                    'ComparisonOperator': 'GREATER_THAN',
                    'Threshold': thresholdPercent,
                    'ThresholdType': 'PERCENTAGE',
                    'NotificationState': 'ALARM'
                },
                'Subscribers': [
                    {
                        'SubscriptionType': 'EMAIL',
                        'Address': emailToNotify
                    },
                ]
            },
        ]
    )

    return jsonify(responseBudgetCreation)

# Invoke Application
if __name__ == '__main__':
 app.run()