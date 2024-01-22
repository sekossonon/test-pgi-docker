#!/bin/bash
echo $DOCKERHUB_CREDS_PSW | docker login -u  $DOCKERHUB_CREDS_USR --password-stdin