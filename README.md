# sst-docker-airflow


This repository contains **Dockerfile** of apache airflow.  This is build based on custom version of [apache-airflow](https://github.com/umg/sstumg-incubator-airflow.git)
Build based on core framework from puckel airflow(https://github.com/puckel/docker-airflow).
  
## Docker image Informations

* Based on Python (2.7-stretch) official Image [python:2.7-stretch](https://hub.docker.com/_/python/) and uses the official [Postgres](https://hub.docker.com/_/postgres/) as backend and [Redis](https://hub.docker.com/_/redis/) as queue
* Install [Docker](https://www.docker.com/)
* Install [Docker Compose](https://docs.docker.com/compose/install/)
* Following the custom Airflow  from github [Airflow](https://github.com/umg/sstumg-incubator-airflow.git)
* Install Java 1.8
* Google cloud SDK
* google cloud component beta
* google bigquery python module



## Airflow(celery executor) Informations
* Local drive **/opt/app** mapped to **/opt/app** in container
* Local drive **/opt/airflow/dags** mapped to **/usr/local/airflow/dags** in container
* environment variable **PROJECT_NAME** is set to umg-swift
* Logs are copied to google cloud storage under the project bucket
* all plugins under plugins dir is copied to airflow home
* Airflow home is /usr/local/airflow
* Note: Env variable to load examples is set to 'N' , LOAD_EX=n . Dont change it to 'Y'. there is issue in dag execution.

##public Docker account credential
        username : sstumgdocker
        password: 01music

## Installation  on google compute engine

1. Install Docker.
2. Install docker compose
3. copy the docker-compose-CeleryExecutor-version-1-8-1-custom.yml to compute engine.
4. Create local drive /opt/app and /opt/airflow/dags on compute engine
5. trigger airflow container by 

        sudo docker-compose -f docker-compose-CeleryExecutor-version-1-8-1-custom.yml up -d
        
        scale worker containers by
        docker-compose scale worker=5
6. scp the dag file to /opt/airflow/dags. give it a few mins to sync with airflow container.
7. create folder based on application name in /opt/app
8. scp jar file or code to /opt/app/{app_name}.

## General Installation commands

Pull the image from the Docker repository.

        docker pull sstumgdocker/docker-airflow:1.8.1-custom

## Build

        docker build --rm -t sstumgdocker/docker-airflow .
        docker tag sstumgdocker/docker-airflow:latest sstumgdocker/docker-airflow:1.8.1-custom

## Usage

By default, docker-airflow runs Airflow with **SequentialExecutor** :

        docker run -d -p 8080:8080 sstumgdocker/docker-airflow:1.8.1-custom

If you want to run another executor, use the other docker-compose.yml files provided in this repository.

For **LocalExecutor** :

        docker-compose -f docker-compose-LocalExecutor.yml up -d

For **CeleryExecutor** :

        docker-compose -f docker-compose-CeleryExecutor-version-1-8-1-custom.yml up -d

## Note : 
don't load examples while starting the docker container. There is a issue and it doesn't allow any dags to trigger. set LOAD_EX=n always :

`LOAD_EX=n`

        docker run -d -p 8080:8080 -e LOAD_EX=n puckel/docker-airflow

If you want to use Ad hoc query, make sure you've configured connections:
Go to Admin -> Connections and Edit "postgres_default" set this values (equivalent to values in airflow.cfg/docker-compose*.yml) :
- Host : postgres
- Schema : airflow
- Login : airflow
- Password : airflow

For encrypted connection passwords (in Local or Celery Executor), you must have the same fernet_key. By default docker-airflow generates the fernet_key at startup, you have to set an environment variable in the docker-compose (ie: docker-compose-LocalExecutor.yml) file to set the same key accross containers. To generate a fernet_key :

        python -c "from cryptography.fernet import Fernet; FERNET_KEY = Fernet.generate_key().decode(); print FERNET_KEY"



## Install custom python package

- Create a file "requirements.txt" with the desired python modules
- Mount this file as a volume `-v $(pwd)/requirements.txt:/requirements.txt`
- The entrypoint.sh script execute the pip install command (with --user option)

## UI Links

- Airflow: [localhost:8080](http://localhost:8080/)
- Flower: [localhost:5555](http://localhost:5555/)


## Scale the number of workers

Easy scaling using docker-compose:

        docker-compose scale worker=5




