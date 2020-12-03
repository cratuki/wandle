#!/bin/bash

. venv/bin/activate

python3 -B -m wandle.main `pwd`/doc/sample.wandle
#python3 -B -m wandle.main `pwd`/doc/small.wandle


