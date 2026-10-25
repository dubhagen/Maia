#!/bin/bash

cd `dirname $0`/..
export BASE_DIR=`pwd`
pid=`ps ax | grep -i app.py | grep "${BASE_DIR}" | grep python3 | grep -v grep | awk '{print $1}'`
if [ -z "$pid" ] ; then
        echo "No Maia process running."
        exit -1;
fi

echo "Maia (${pid}) is running..."

kill ${pid}

echo "Sent shutdown request to Maia (${pid})"
