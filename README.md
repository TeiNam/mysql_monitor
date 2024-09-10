# Welcome

## 프로젝트 구조
mysql_monitor/ \
│ \
├── README.md \
├── apis/ \
│   ├── __init__.py \
│   ├── main.py \
│   └── routes/ \
│       ├── __init__.py \
│       ├── instance_setup.py \
│       ├── mysql_com_status.py \
│       ├── mysql_disk_usage.py \
│       ├── slow_query.py \
│       ├── slow_query_explain.py \
│       └── slow_query_stat.py \
├── asgi.py \
├── collectors/ \
│   ├── __init__.py \
│   ├── collectors.py \
│   ├── mysql_command_status.py \
│   ├── mysql_disk_status.py \
│   ├── mysql_slow_queries.py \
│   └── rds_instance_status.py \
├── configs/ \
│   ├── __init__.py \
│   ├── app_conf.py \
│   ├── crypto_conf.py \
│   ├── log_conf.py \
│   ├── mongo_conf.py \
│   ├── mysql_conf.py \
│   ├── rds_instance_conf.py \
│   └── slack_conf.py \
├── frontend/ \
│   ├── img/ \
│   │   └── favicon.ico \
│   ├── static/ \
│   │   ├── css/ \
│   │   │   ├── explain.css \
│   │   │   └── instance_setup.css \
│   │   └── js/ \
│   │       ├── explainHander.js \
│   │       └── formHandler.js \
│   └── templates/ \
│       ├── instance_setup.html \
│       └── sql_explain.html \
├── modules/ \
│   ├── __init__.py \
│   ├── crypto_utils.py \
│   ├── load_instance.py \
│   ├── mongodb_connector.py \
│   ├── mysql_connector.py \
│   ├── slack_utils.py \
│   └── time_utils.py \
├── report_tools/ \
│   └── __init__.py \
├── requirements.txt \
└── test_main.http \


## .env 환경변수
```
## encrypt key
AES_KEY=
AES_IV=

## mongodb
MONGODB_URI=
MONGODB_DB_NAME=mgmt_db

## slack
SLACK_WEBHOOK_URL=
SLACK_API_TOKEN=
```