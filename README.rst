Scutwork
++++++++

A replacement for cron, primarily intended for use in containers.

Requirements
============

    - `Python`_ 3.5.x
    - `click`_
    - `crontab`_
    - `pytimeparse`_

.. _Python: http://www.python.org/
.. _click: http://click.pocoo.org/
.. _crontab: http://click.pocoo.org/
.. _pytimeparse: http://click.pocoo.org/

Usage
=====

.. code-block:: sh

    $ scutwork jobs.json

Options
=======

**-v, --verbose**
    Verbose output. Environment variable: ``SCUTWORK_VERBOSE``

**--localtime**
    Use local time for log timestamps. The default is to use UTC timestamps.
    Environment variable: ``SCUTWORK_LOCALTIME``

**--logformat <format>**
    The log format. See the `relevant <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_ section in the python manual.
    Environment variable: ``SCUTWORK_LOGFORMAT``

**--logconfig <filename>**
    Configure logging using the supplied configuration file. See python `manual <https://docs.python.org/3/library/logging.config.html>`_.
    The name of the logger for the jobs is ``job``.
    Environment variable: ``SCUTWORK_LOGCONFIG``

**--help**
    Show the help message.

Environment
===========
All jobs inherit their environment from the main ``scutwork`` process. If ``SHELL`` is not set it
will be set to ``/bin/sh``. If ``PATH`` is not set it will be set to ``/usr/bin;/bin``.
The environment for each job can be customized using the ``env`` job option (see below).

Error handling
==============
As opposed to cron, scutwork will only log the output of a job if the exit status is not 0
or there was some error output.
If the processes exited with a status other than 0 the stderr output is logged and if there
is no stderr output the stdout output will be logged, if any.
Note that process output is temporary stored on disk so it's advisable to avoid producing
large amounts of output.
In short, scutwork expects jobs to behave well and exit with a non-zero status on error and
only produce error output if there's an error or other situation that warrants attention.

Job Configuration
=================

Configuration can be either a JSON file or a YAML file, the latter requiring that PyYAML is installed.

**name**
    The name of the job

**cmd**
    The command to run. Unless ``shell`` is set to ``true`` this should be an array.
    If ``shell`` is set to ``true`` it should be a string.

**when**
    When to run this job. Depending on the format this is either a crontab-style
    time specification (``5 * * * *``) or a pytimeparse-style interval (``15s``). The default
    for ``crontab`` is ``* * * * *``.

**format**
    Format of the ``when`` property. Can be either ``crontab`` or ``interval``. Default is ``crontab``.

**cwd**
    The working directory.

**shell**
    If set to ``true`` the command will be run in a shell. Default is ``false``.

**env**
    This is an object with environment variable names and values.

**ignore_stderr**
    Normally scutwork will log any output to stderr but if you have a process
    that misbehaves and produces errant stderr output you can ignore it by setting
    this to ``true``. This option has no effect if the process exits with non-zero status.

Examples
--------
.. code-block:: json

    [
        {
            "name": "This will run every minute",
            "cmd": [
                "/bin/sleep",
                "15"
            ]
        },
        {
            "name": "This will run every 15 seconds",
            "cmd": ["/bin/date"],
            "when": "15s",
            "format": "interval"
        },
        {
            "name": "This will run 5 minutes after midnight with working dir /var/run",
            "cmd": ["/bin/date"],
            "when": "5 0 * * *",
            "cwd": "/var/run"
        },
        {
            "name": "This will run in a shell",
            "cmd": "/bin/date || wc -l",
            "shell": true
        },
        {
            "name": "Run with some env variables",
            "cmd": ["/bin/date"],
            "env": {
                "USERNAME": "kermit",
                "TZ": "Asia/Manila"
            }
        }
    ]

YAML files work the same way.

.. code-block:: yaml

    ---
        - name: Some job
          cmd:
              - /bin/date
          when: 5 * * * *
          cwd: /var/run
          env:
              TZ: Asia/Manila
        - name: Other job
          cmd: ["/bin/sleep"]
