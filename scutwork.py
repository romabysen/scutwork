#!/usr/bin/env python
import os
import os.path
import json
import threading
import time
import subprocess
import logging
import signal
from collections import Counter
from tempfile import TemporaryFile
from sched import scheduler

import click
import pytimeparse
from crontab import CronTab
try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_SHELL = '/bin/sh'
DEFAULT_PATH = '/usr/bin;/bin'
DEFAULT_CRONTAB = '* * * * *'
DEFAULT_FORMAT = 'crontab'
DEFAULT_LOG_FORMAT = '[%(asctime)s] %(levelname)s: %(name)s: %(message)s'
YAML_EXTENSIONS = ['.yaml', '.yml']
MAX_OUTPUT = 262144  # 256Kb


class JobAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '{}: {}'.format(self.extra['jobname'], msg), kwargs


class JobThread(threading.Thread):
    def __init__(self, job):
        super().__init__(name=job['name'])
        self._logger = JobAdapter(logging.getLogger('job'), {'jobname': job['name']})
        self._cmd = job['cmd']
        self._cwd = job.get('cwd')
        self._shell = job.get('shell', False)
        self._env = _create_env(job.get('env'))
        self._ignore_stderr = job.get('ignore_stderr', False)

    def run(self):
        self._logger.debug('Running command: {}'.format(self._cmd))
        with TemporaryFile() as stdout_file, TemporaryFile() as stderr_file:
            try:
                subprocess.run(self._cmd, stdout=stdout_file, stderr=stderr_file,
                               env=self._env, cwd=self._cwd, shell=self._shell, check=True)
            except FileNotFoundError as exc:
                self._logger.error('File not found: {}'.format(str(exc)))
            except subprocess.CalledProcessError as exc:
                self._logger.error('Command "{}" exited with code {}'.format(self._cmd, exc.returncode))
                if stderr_file.tell() > 0:
                    stderr_file.seek(0)
                    self._logger.error('Output: {}'.format(stderr_file.read(MAX_OUTPUT).decode('utf-8', 'ignore')))
                elif stdout_file.tell() > 0:
                    stdout_file.seek(0)
                    self._logger.error('Output: {}'.format(stdout_file.read(MAX_OUTPUT).decode('utf-8', 'ignore')))
                else:
                    self._logger.debug('Error but no output')
            else:
                if stderr_file.tell() > 0 and not self._ignore_stderr:
                    self._logger.error('Command was successful but produced some error output.')
                    stderr_file.seek(0)
                    self._logger.error('Output: {}'.format(stderr_file.read(MAX_OUTPUT).decode('utf-8', 'ignore')))


def _run_job(sch, job):
    JobThread(job).start()
    _schedule_job(sch, job)


def _schedule_job(sch, job):
    fmt = job.get('format', DEFAULT_FORMAT)
    if fmt == 'interval':
        interval = pytimeparse.parse(job['when'])
        sch.enter(interval, 1, _run_job, (sch, job))
    elif fmt == 'crontab':
        ct = CronTab(job.get('when', DEFAULT_CRONTAB))
        sch.enter(ct.next(), 1, _run_job, (sch, job))
    else:
        raise RuntimeError('Invalid format for "when"')


def _load_jobs(jobs_file):
    name, ext = os.path.splitext(jobs_file.name)
    if ext in YAML_EXTENSIONS and yaml:
        return yaml.load(jobs_file)
    elif ext in YAML_EXTENSIONS and not yaml:
        raise RuntimeError('PyYAML must be installed to use YAML files.')
    else:
        return json.load(jobs_file)


def _create_env(job_env):
    env = os.environ.copy()
    if 'SHELL' not in env:
        env['SHELL'] = DEFAULT_SHELL
    if 'PATH' not in env:
        env['PATH'] = DEFAULT_PATH
    if job_env:
        env.update(job_env)
    return env


def _setup_logging(verbose, logformat, localtime, logconfig):
    if logconfig:
        logging.config.fileConfig(logconfig)
    else:
        level = logging.INFO
        if verbose:
            level = logging.DEBUG
        handler = logging.StreamHandler()
        formatter = logging.Formatter(logformat)
        if not localtime:
            formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logging.basicConfig(level=level, handlers=[handler])


def _create_scheduler(jobs):
    sch = scheduler()
    for job in jobs:
        _schedule_job(sch, job)
    return sch


def _do_exit(signum, frame):
    raise SystemExit


def _shutdown(logger):
    isjobthread = Counter(isinstance(t, JobThread) for t in threading.enumerate())
    logger.info('Waiting for {} running jobs to finish...'.format(isjobthread[True]))
    while isjobthread[True] > 0:
        time.sleep(1)
        isjobthread = Counter(isinstance(t, JobThread) for t in threading.enumerate())
    logger.info('Shutting down.')
    logging.shutdown()


@click.command(context_settings={'auto_envvar_prefix': 'SCUTWORK'})
@click.option('--verbose', '-v', is_flag=True, help='Verbose output.')
@click.option('--localtime', is_flag=True, help='Use local time for log timestamps.')
@click.option('--logformat', default=DEFAULT_LOG_FORMAT, help='The log format.')
@click.option('--logconfig', type=click.File(), help='Logging configuration.')
@click.argument('jobs_file', type=click.File())
def main(verbose, localtime, logformat, logconfig, jobs_file):
    _setup_logging(verbose, logformat, localtime, logconfig)
    logger = logging.getLogger('system')
    jobs = _load_jobs(jobs_file)
    logger.info('Loaded {} jobs.'.format(len(jobs)))
    sch = _create_scheduler(jobs)
    signal.signal(signal.SIGTERM, _do_exit)
    signal.signal(signal.SIGHUP, _do_exit)
    logger.info('Processing jobs')
    try:
        sch.run(blocking=True)
    except (KeyboardInterrupt, SystemExit):
        _shutdown(logger)


if __name__ == '__main__':
    main()
