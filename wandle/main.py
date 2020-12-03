#!/usr/bin/env python3

from .arpeggio_parse import arpeggio_parse_debug
from .arpeggio_parse import arpeggio_parse_go
from .wandle_model import wandle_model_build

import argparse
import os
import pprint
import sys
from types import SimpleNamespace as Ns


def read_file(path):
    f_ptr = open(path)
    data = f_ptr.read()
    f_ptr.close()
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('model_filename',
        help='File containing the model.')
    ns_args = parser.parse_args()

    model_filename = ns_args.model_filename
    if not os.path.exists(model_filename):
        print('ERROR: %s does not exist.'%(model_filename))
        sys.exit(1)
    if not os.path.isfile(model_filename):
        print('ERROR: %s is not a file.'%(model_filename))
        sys.exit(1)

    # Transform Wandle DSL into a parse tree
    wandle_src = read_file(model_filename)
    parse_tree = arpeggio_parse_go(wandle_src)

    # Build the data model
    wandle_model = wandle_model_build(
        parse_tree=parse_tree)

    # xxx debug 
    #print(wandle_model.as_code())

    print('Model is valid.')

if __name__ == '__main__':
    main()
