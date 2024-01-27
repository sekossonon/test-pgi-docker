#!/bin/bash
docker logout
docker compose down --remove-orphans --volumes --rmi=local
