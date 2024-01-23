#!/bin/bash
echo $DOCKERHUB_CREDS_PSW | docker login -u  $DOCKERHUB_CREDS_USR --password-stdin
docker build -t my-pgi-16.0:latest -t my-pgi-16.0:$BUILD_ID  .
docker logout