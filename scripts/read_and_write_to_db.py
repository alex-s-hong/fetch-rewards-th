import datetime
import hashlib
import json

import psycopg2
import localstack_client.session as boto3

QUEUE_NAME = "login-queue"


def save_to_db(message_body : dict):
    """
    Insert the message into the database

    message_body: recipe message body for saving, ip and device_id are already masked
    """
    sql = """ INSERT INTO user_logins(user_id, device_type, masked_ip, masked_device_id, locale, app_version, create_date) 
        VALUES (%s, %s, %s, %s, %s, %s, %s);"""


    with psycopg2.connect(host='localhost', dbname='postgres', user='postgres', password='postgres', port=5432) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (message_body['user_id'], 
                            message_body['device_type'], 
                            message_body['ip'], 
                            message_body['device_id'], 
                            message_body['locale'], 
                            int(message_body['app_version'].split('.')[0]), # app_version contains decimals but striping all the decimals
                            datetime.date.today())
                        )
        cursor.close()


def read_message():
    """
    This function will read a message from AWS SQS Queue, then save to the db
    Each response contains 10 messages
    """
    sqs = boto3.client("sqs")
    queue_url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=5
    )

    for message in response.get("Messages", []):
        message_body = json.loads(message['Body'])
        receipt_handle = message['ReceiptHandle']
        
        if 'user_id' in message_body:
            # encrypt PII (device_id, ip)
            device_id = message_body.get('device_id')
            ip = message_body.get('ip')
            message_body['device_id'] = hashlib.sha256(device_id.encode('utf-8')).hexdigest()
            message_body['ip'] = hashlib.sha256(ip.encode('utf-8')).hexdigest()

            save_to_db(message_body)
            print("The message has been saved: {}".format(message_body))


def main():
    for i in range(10):
        read_message()


if __name__ == '__main__':
    print("script starts")
    main()
