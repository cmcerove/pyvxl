#!/usr/bin/env python

"""Used for testing the Daemon class."""

from time import clock
from pyvxl.daemon import Daemon, Task


class ExampleDaemon(Daemon):
    """Used for testing the Daemon class."""

    def __init__(self, *args, **kwargs):
        """."""
        super(ExampleDaemon, self).__init__(*args, file=__file__, **kwargs)
        self.start_time = clock()

    def print_task(self, *args, **kwargs):
        """Print the elapsed time since the daemon started."""
        if not self._is_daemon():
            task = Task(command='print_task', args=args, kwargs=kwargs, **kwargs)
            self._add_task(task)
        else:
            print 'print_task({}, {}) - {} milliseconds'.format(args, kwargs, (clock() - self.start_time) * 1000.0)


if __name__ == '__main__':
    example = ExampleDaemon()
    example.run()
