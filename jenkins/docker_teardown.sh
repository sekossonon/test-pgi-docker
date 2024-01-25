#!/bin/bash
docker compose down --remove-orphans --rmi=local --volumes
docker logout
