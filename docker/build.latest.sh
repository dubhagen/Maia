#!/bin/bash

unset KUBECONFIG

cd .. && docker build -f docker/Dockerfile.latest \
             -t maia:local .

docker tag maia:local maia:local-$(date +%y%m%d)