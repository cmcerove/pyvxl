#!/usr/bin/env python

"""Run pytest with coverage and generate an html report."""

from sys import argv
from os import system as run

# To run a specific file with debug logging prints:
# py -3 -m pytest test_can.py --log-cli-format="%(asctime)s.%(msecs)d %(levelname)s: %(message)s (%(filename)s:%(lineno)d)" --log-cli-level=debug

def main():  # noqa
    run_str = 'python -m coverage run --include={} --omit=./* -m pytest {} {}'
    arg = ''
    # All source files included in coverage
    includes = '../*'
    if len(argv) >= 2:
        arg = argv[1]
        if ':' in argv[1]:
            includes = argv[1].split('::')[0]
    other_args = ' '.join(argv[2:])

    run(run_str.format(includes, arg, other_args))

    # Generate the html coverage report and ignore errors
    run('python -m coverage html -i')


if __name__ == '__main__':
    main()
