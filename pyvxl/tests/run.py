#!/usr/bin/env python

"""Run pytest with coverage and generate an html report."""

from sys import argv
from os import system as run


def main():
    """."""
    run_str = 'coverage run --include={} --omit=./* -m pytest {}'
    arg = ''
    # All source files included in coverage
    includes = '../*'
    if len(argv) == 1:
        pass
    elif len(argv) == 2:
        arg = argv[1]
        if ':' in argv[1]:
            includes = argv[1].split(':')[0]
    else:
        raise NotImplementedError('More than one argument hasn\'t been '
                                  'implemented')

    run(run_str.format(includes, arg))

    # Generate the html coverage report and ignore errors
    run('coverage html -i')

if __name__ == '__main__':
    main()
