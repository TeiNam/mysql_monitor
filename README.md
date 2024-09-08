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
│       └── instance_setup.py \
├── apis.py \
├── asgi.py \
├── collectors/ \
├── collectors.py \
├── configs/ \
│   ├── __init__.py \
│   ├── app_conf.py \
│   ├── crypto_conf.py \
│   ├── log_conf.py \
│   ├── mongo_conf.py \
│   └── slack_conf.py \
├── frontend/ \
│   ├── img/ \
│   │   └── favicon.ico \
│   ├── static/ \
│   │   ├── css/ \
│   │   │   └── instance_setup.css \
│   │   └── js/ \
│   │       └── formHandler.js \
│   └── templates/ \
│       └── instance_setup.html \
├── logs/ \
├── modules/ \
│   ├── __init__.py \
│   ├── crypto_utils.py  \
│   ├── mongodb_connector.py \
│   ├── slack_utils.py \
│   └── time_utils.py \
├── report_tools/ \
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