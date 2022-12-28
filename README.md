# Fetch Rewards #
## Data Engineering Take Home: ETL off a SQS Queue ##

You may use any programming language to complete this exercise. We strongly encourage you to write a README to explain how to run your application and summarize your thought process.

## What do I need to do?
This challenge will focus on your ability to write a small application that can read from an AWS SQS Queue, transform that data, then write to a Postgres database. This project includes steps for using docker to run all the components locally, **you do not need an AWS account to do this take home.**

Your objective is to read JSON data containing user login behavior from an AWS SQS Queue that is made available via [localstack](https://github.com/localstack/localstack). Fetch wants to hide personal identifiable information (PII). The fields `device_id` and `ip` should be masked, but in a way where it is easy for data analysts to identify duplicate values in those fields.

Once you have flattened the JSON data object and masked those two fields, write each record to a Postgres database that is made available via [Postgres's docker image](https://hub.docker.com/_/postgres). Note the target table's DDL is:

```sql
-- Creation of user_logins table

CREATE TABLE IF NOT EXISTS user_logins(
    user_id             varchar(128),
    device_type         varchar(32),
    masked_ip           varchar(256),
    masked_device_id    varchar(256),
    locale              varchar(32),
    app_version         integer,
    create_date         date
);
```

You will have to make a number of decisions as you develop this solution:

*    How will you read messages from the queue?
*    What type of data structures should be used?
*    How will you mask the PII data so that duplicate values can be identified?
*    What will be your strategy for connecting and writing to Postgres?
*    Where and how will your application run?

**The recommended time to spend on this take home is 2-3 hours.** Make use of code stubs, doc strings, and a next steps section in your README to elaborate on ways that you would continue fleshing out this project if you had the time.

For this assignment an ounce of communication and organization is worth a pound of execution. Please answer the following questions:

* How would you deploy this application in production?
* What other components would you want to add to make this production ready?
* How can this application scale with a growing data set.
* How can PII be recovered later on?

## Explanation and How to Start 

I have created a simple script to process the input from AWS SQS then save into the Postgres database. The task has a number of things that I should make decision. Considering the recommended time to spend on this take home task (2-3 hours),
I created a simple script to perform the requirements. I will discuss what can be enhanced given much time or deployed to production (which requires scaling up).

#### Decisions during development
Out of the process, the first thing to do was how I should read the message from the AWS SQS Queue. As I decided to use Python for processing the data, I decided to use the AWS SDK, as similar as we write them to the queue.

When we receive the message, it is given in json format. In order to flatten and process the data in Python, it is stored in dictionary type.

I used python's default hash library to mask personal identifiable information (PII). Out of multiple options, I used SHA-256 as it encryptes the value in 256 bit so it's less likely to cause hash collision and much secure, which enables
duplication detection. Although the performance is slower than other simpler encryption such as MD5 or SHA-128, the effect is very limited.
The encryption is one-way hash and it's very difficult to recover the PII later. However, if it is necessary to recover the PII, we can consider using two-way hash (encryption and decryption) by importing module like [simple-crypt](https://pypi.org/project/simple-crypt/).

My strategy to connect to Postgres was 'make it simple'. Personally, I prefer to make a minimal product meets the requirement because it's easier to maintain and cost-effeicient. Thus, I decided to use [psycopg2](https://pypi.org/project/psycopg2/) for connection and insertion.
If the project scales up with larger data stream and additional requirements, I would consider creating a flask app with [SQL Alchemy](https://www.sqlalchemy.org/) for better maintenance.

I placed my script along with other python scripts but I didn't include it in the docker image. If the user wants to do the process, the user can simply run the script by run the command `python script/read_and_write_to_db.py` at project's root.

### Answers for the questions

1. How would you deploy this application in production?

-> It depends by the case but if we don't expect a lot of datastream, we can use my script without modification and run it periodically (i.e. by running a cron job).
```
# make/edit a crontab
crontab -e

# inside the vim editor, include the script to run with schedule (in this example, every 5 minute)
# you should edit the path of your python and your script's location
*/5 * * * * /usr/local/bin/python /Users/{your_name}/fetch-rewards-th/scripts/read_and_write_to_db.py
```
The script can be placed in the same docker image or separate docker, then placed to EC2 instance on AWS. However, as I said, it depends by the future requirement.
If we are planning to add more features (i.e. different queries on database), we can create an object relational mapping (ORM) in a microservice.


2. What other components would you want to add to make this production ready?

-> The first thing I would add is validator of the input. Even in given small dataset, there was one invalid input (with 'foo', 'bar' keys). I would improve the validator to filter out those invalid messages.

Moreover, database connection cannot always be guaranteed in real life. In other words, we should expect there can be a glitch anytime. In order to prevent the situation, I would create a class for DB and include `retries` parameters.

Example code snippet is as follows:

```python

class DB():
    def __init__(self, host, user, password, dbname, port):
        self.host = host
        self.user = user
        self.password = password
        self.dbname = dbname
        self.port = port
        self.connection = None

    def connect(self, retries=3):
        if not self.connection:
            try:
                self.connection = psycopg2.connect(host=self.host, user=self.user, password=self.password, port= self.port, dbname=self.database, connect_timeout=3)
                retry_counter = 0
                return self.connection
            except psycopg2.OperationalError as error:
                if not self.reconnect or retries <= 0:
                    raise error
                else:
                    retries -= 1
                    print("Got an error {}. reconnecting...".format(str(error).strip()))
                    time.sleep(5)
                    self.connect(retries)
            except (Exception, psycopg2.Error) as error:
                raise error
    def cursor(self):
        ...

    def execute(self):
        ...

```

Another thing I would do before deploying it to the production, hide the credentials. The credentials including password is exposed and it is wrong practice. 
One way is save those variables in environment and access them by calling `os.getenv(key)`.

3. How can this application scale with a growing data set.

When we have more data coming in, we need more workers. One way is adopting multithreading, and the other way is adding more worker nodes (multi-processing).

Of course, we can adjust the number of messages per response or frequency in cron as well. However, at some point, we might encounter the limit and we need to 
find new ways. We can use multithreading by simply import the multi-thread module and slightly change the job for each thread. For multi-processing, we can put
the job into a docker and spawn on the Kubernetes.

Either we use multi-thread or multi-process, we should be cautious on handling AWS SQS. We should config `visiblity timeout`, a period of time during which SQS prevents
other consuming components from receiving and processing the message, to be sufficient for each thread/process to handle and not resulting in duplicate rows in DB.


4. How can PII be recovered later on?

Current implementation cannot recover the PII as I adopt the one-way hash. However, it is feasible by changing the encrypt module to two-way hashing module.
What we should be careful is we should store and maintain the secret key for encryption and decryption.
Example as follows,

```python
    import os
    from simplecrypt import encrypt
    # retreived from current implementation

    key = os.getenv(KEY);

    if 'user_id' in message_body:
        # encrypt PII (device_id, ip)
        device_id = message_body.get('device_id')
        ip = message_body.get('ip')
        message_body['device_id'] = encrypt(key, device_id) # hashlib.sha256(device_id.encode('utf-8')).hexdigest()
        message_body['ip'] = encrypt(key, ip) # hashlib.sha256(ip.encode('utf-8')).hexdigest()

```

Recovering the PII can be done by following example.

```python
from simplecrypt import decrypt

decrypted_message = decrypt(key, encryted_message) # the key should be identical to encryption key

```

### How to Run and Verify
1. Run `make start` to initiate AWS SQS Queue and Postgres Database.
2. Run `python script/read_and_write_to_db.py` to execute saving the message after masking PII.

## Project Setup
1. Fork this repository to a personal Github, GitLab, Bitbucket, etc... account. We will not accept PRs to this project.
2. You will need the following installed on your local machine
    * make
        * Ubuntu -- `apt-get -y install make`
        * Windows -- `choco install make`
        * Mac -- `brew install make`
    * python3 -- [python install guide](https://www.python.org/downloads/)
    * pip3 -- `python -m ensurepip --upgrade` or run `make pip-install` in the project root
    * awslocal -- `pip install awscli-local`  or run `make pip install` in the project root
    * docker -- [docker install guide](https://docs.docker.com/get-docker/)
    * docker-compose -- [docker-compose install guide]()
3. Run `make start` to execute the docker-compose file in the the project (see scripts/ and data/ directories to see what's going on, if you're curious)
    * An AWS SQS Queue is created
    * A script is run to write 100 JSON records to the queue
    * A Postgres database will be stood up
    * A user_logins table will be created in the public schema
4. Test local access
    * Read a message from the queue using awslocal, `awslocal sqs receive-message --queue-url http://localhost:4566/000000000000/login-queue`
    * Connect to the Postgres database, verify the table is created
    * username = `postgres`
    * database = `postgres`
    * password = `postgres`

```bash
# password: postgres

psql -d postgres -U postgres  -p 5432 -h localhost -W
Password: 

postgres=# select * from user_logins;
 user_id | device_type | hashed_ip | hashed_device_id | locale | app_version | create_date 
---------+-------------+-----------+------------------+--------+-------------+-------------
(0 rows)
```
5. Run `make stop` to terminate the docker containers and optionally run `make clean` to clean up docker resources.

## All done, now what?
Upload your codebase to a public Git repo (GitHub, Bitbucket, etc.) and please submit your Link where it says to - under the exercise via Green House our ATS. Please double-check this is publicly accessible.

Please assume the evaluator does not have prior experience executing programs in your chosen language and needs documentation understand how to run your code
