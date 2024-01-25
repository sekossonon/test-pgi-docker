#!/bin/bash
docker compose down --remove-orphans --rmi	--volumes
docker logout
