from argparse import ArgumentParser
from datetime import datetime
from glob import glob
from json import load, dump, dumps
from logging import CRITICAL, ERROR, WARN, INFO, DEBUG, StreamHandler, FileHandler, Formatter, getLogger
from os import listdir, makedirs, mkdir, readlink, rename, statvfs, symlink, unlink
from os.path import abspath, expanduser, sep, join, exists, relpath, realpath, dirname
import subprocess
from sys import stdout
from traceback import format_exc
from __builtin__ import exit
from re import sub

# set at the module level so that IndentedOutput instances that share a GIL share logging state
INDENT_SIZE = 0
INDENT_STRING = '| '
CONSOLE = StreamHandler(stdout)


def getCurrentDateTimeDict():
    dt = datetime.today()
    return {'year': dt.year,
            'month': dt.month,
            'day': dt.day,
            'hour': dt.hour,
            'minute': dt.minute,
            }


def dateString(dateTimeDict=None):
    if dateTimeDict is None:
        dateTimeDict = getCurrentDateTimeDict()

    return '%d-%02d-%02d %02d:%02d' % (dateTimeDict['year'],
                                       dateTimeDict['month'],
                                       dateTimeDict['day'],
                                       dateTimeDict['hour'],
                                       dateTimeDict['minute'],
                                       )


def bytesLabel(size):
    suffix = 'B'
    suffixes = ['PB', 'TB', 'GB', 'MB', 'KB']
    while size >= 1024 and len(suffixes) > 0:
        size = float(size) / 1024.0
        suffix = suffixes.pop()
    return '%.1f %s' % (size, suffix)


def getSortedUnglobbedPaths(pathArgs):

    if not isinstance(pathArgs, list):
        pathArgs = [pathArgs]
    unglobbedPaths = []
    for pathArg in pathArgs:
        unglobbedPaths += glob(abspath(pathArg))
    return sorted(unglobbedPaths)


def camelToSnake(s0):
    s1 = sub(r'(.)([A-Z][A-Z]+)', r'\1_\2', s0)  # MiddleACRONYMS > Middle_ACRONYMS
    s2 = sub(r'([a-z0-9])([A-Z][a-z])', r'\1_\2', s1)  # middleChars > Middle_Chars
    s3 = sub(r'([a-z0-9])([A-Z][a-z])', r'\1_\2', s2)  # middleChars > Middle_Chars
    s4 = sub(r'([a-z0-9])([A-Z])$', r'\1_\2', s3)  # endS > end_S
    s5 = sub(r' ', r'_', s4)  # space separations > space_separations
    s6 = sub(r'__', r'_', s5)  # duplicate__separators > duplicate_separators
    return s6.lower()  # Mixed_Separators > mixed_separators


def check_output(command, stdout=None, stderr=subprocess.STDOUT, cwd=None, acceptedReturnCodes=[0], throwOnFail=True, logLevel=DEBUG, out=None, **kwargs):
    '''
    a convenient subprocess.check_output wrapper that allows non-zero return codes and logs results, if called as such.
    '''
    if out: out.put('running command: ' + command.__str__(), logLevel)
    # copied/modified from check_output()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr, cwd=cwd)
    result, errors = process.communicate()
    returncode = process.poll()
    if returncode and returncode not in acceptedReturnCodes:
        summary = 'Command output:\n%s\n\nStderr output:\n%s\n' % (result, errors)
        logLevel = ERROR
        if throwOnFail:
            raise subprocess.CalledProcessError(returncode, command, output=summary)
    if out: out.put("subprocess.check_output() call got result:\n" + result, logLevel=logLevel)
    return result  # return result + errors?


def check_call(command, logLevel=DEBUG, out=None, **kwargs):
    if out: out.put('running command: ' + command.__str__(), logLevel)
    return subprocess.check_call(command, **kwargs)


def initGitRepo(localPath, remotePath=None, branch=None, out=None):
    '''
    if a Git repository (a local clone of a remote origin)
    has not been cloned/initialized yet, clone it and return
    the new Repo; otherwise return a Repo for the existing one.
    '''
    from git import Repo, GitCommandError

    if branch is None:
        branch = 'master'

    gitMetadataDir = join(localPath, '.git')
    if exists(gitMetadataDir):
        repo = Repo(localPath)
    elif remotePath is None:
        out.put("no existing repo, and no remotePath given, so doing 'git init'")
        repo = Repo.init(localPath)
    else:
        # need to clone it.
        if out: out.put('Cloning into %s...' % localPath)
        repo = Repo.init(localPath)
        repo.create_remote('origin', remotePath)
        repo.remotes.origin.fetch()

        head = repo.create_head(branch, repo.remotes.origin.refs[branch])
        head.set_tracking_branch(repo.remotes.origin.refs[branch])
        head.checkout()

    if not repo.remotes.origin.exists():
        if out: out.error("Repository remote %s does not appear to exist." % remotePath)
    else:
        try:
            repo.head.set_reference(repo.heads[branch])
            repo.head.reset(index=True, working_tree=True)
            repo.remotes.origin.pull()

            return repo  # happy path

        except GitCommandError as exception:
            if out:
                out.error('Got exception initializing Git repo: %s' % str(exception))
                out.indent()
                out.error('local repo: %s' % localPath)
                out.error('remote repo: %s' % remotePath)
                if exception.stdout:
                    out.error('stdout was:' + exception.stdout)
                if exception.stderr:
                    out.error('stderr was:' + exception.stderr)

    return None


def gitCommit(repo, filenames, commitMessage=None, tagName=None):

    if type(filenames) == str or type(filenames) == unicode:
        filenames = [filenames]

    # silently ignore missing files - I'm assuming this can be handled more elegantly in calling code
    filenames = [relpath(f, repo.working_tree_dir) for f in filenames if exists(f)]

    if commitMessage is None:
        commitMessage = "Added/updated: %s" % ', '.join(filenames)

    repo.index.add(filenames)
    repo.index.commit(commitMessage)
    if tagName is not None:
        repo.create_tag(tagName)


def gitPush(repo):
    from git.remote import PushInfo

    repo.remotes.origin.pull()
    pushResults = repo.remotes.origin.push()

    for pushResult in pushResults:
        if pushResult.flags & PushInfo.ERROR:
            raise Exception("Unable to push to Git because: %s" % pushResult.summary)


class IndentedOutput:
    '''
    A `logging.Logger`-like object which is auto-configured and returned by Job.__init__()
    in the .out field of the Job object
    '''

    def __init__(self, name, filename=None, logLevel=INFO):
        self.name = name
        self.logger = getLogger(name)
        self.indentString = INDENT_STRING
        self.enableTimestamps = False  # hard-code to True for debugging (not really a runtime thing)

        if len(self.logger.handlers) == 0:
            # only initialize the console once, since we potentially share logger instances
            self.logger.setLevel(DEBUG)
            CONSOLE.setLevel(logLevel)
            self.logger.addHandler(CONSOLE)

            if filename is None:
                filename = join(expanduser('~'), '.%s' % camelToSnake(name), 'log')
                if not exists(dirname(filename)):
                    makedirs(dirname(filename))
            self.logHandler = FileHandler(realpath(filename))
            self.logHandler.setLevel(DEBUG)
            self.logHandler.setFormatter(Formatter('%(asctime)s %(levelname)-8s %(message)s'))
            self.logger.addHandler(self.logHandler)
        else:
            # already initialized, so assume the [0] index is suitable and set self.logHandler
            self.logHandler = self.logger.handlers[0]

        # convenience function map for put()
        self.logPut = {CRITICAL:self.logger.critical,
                       ERROR:self.logger.error,
                       WARN:self.logger.warn,
                       INFO:self.logger.info,
                       DEBUG:self.logger.debug,
                       }

    def put(self, msg='', logLevel=INFO):
        global INDENT_SIZE

        # standardize output for objects, multi-line strings, etc.
        if type(msg) == str or type(msg) == unicode:
            msg = msg.splitlines()
        elif not hasattr(msg, '__iter__'):
            # probably an int/float/object/etc.
            msg = [msg]
        for msgLine in msg:
            try:
                msgLine = str(msgLine)
            except:
                msgLine = unicode(msgLine)
            if self.enableTimestamps:
                indentedMsg = '%s%s %s' % (self.indentString * INDENT_SIZE, datetime.now().isoformat(), msgLine)
            else:
                indentedMsg = '%s%s' % (self.indentString * INDENT_SIZE, msgLine)
            self.logPut[logLevel](indentedMsg)

    def critical(self, msg):
        self.put(msg, CRITICAL)

    def error(self, msg):
        self.put(msg, ERROR)

    def warn(self, msg):
        self.put(msg, WARN)

    def info(self, msg):
        self.put(msg, INFO)

    def debug(self, msg):
        self.put(msg, DEBUG)

    def dumpExceptionInfo(self, logMessage):
        with self.indent(logMessage, logLevel=ERROR):
            for line in format_exc().split('\n'):
                self.error(line.rstrip())

    class IndentContext:

        def __init__(self, out):
            self.out = out

        def __enter__(self):
            return self.out

        def __exit__(self, *args, **kwargs):
            self.out.unIndent()

    # logLevel is weird here. It will still indent, but not print the message, if logLevel doesn't trigger.
    # I guess just make sure that INFO is always enabled.
    def indent(self, msg=None, listOfIndentedMessages=None, logLevel=INFO):
        global INDENT_SIZE
        result = None
        try:
            if msg is not None:
                self.put(msg, logLevel)

            INDENT_SIZE += 1

            if listOfIndentedMessages is None:
                # will stay indented after the call returns, so return a while-param
                result = IndentedOutput.IndentContext(self)
            else:
                # one call per list item, or one total for strings.
                # (string values are re-split & indented inside of put())
                if type(listOfIndentedMessages) == str or type(listOfIndentedMessages) == unicode:
                    listOfIndentedMessages = [listOfIndentedMessages]
                [self.put(root, logLevel) for root in listOfIndentedMessages]
        finally:
            if listOfIndentedMessages is not None:
                self.unIndent()

        return result

    def unIndent(self):
        global INDENT_SIZE
        INDENT_SIZE = max(INDENT_SIZE - 1, 0)


class MinimalJob(object):
    '''
    The bare essentials needed for the most basic uses of the Job class - 
    tools that don't require configs, logging, etc:
    - image tools
    - slide exporter
    
    This class can be copied into other code bases, for instance a tool that needs to be published externally.
    '''

    def __init__(self, name, logLevel):
        super(MinimalJob, self).__init__()
        self.name = name
        self.out = IndentedOutput(name, logLevel=logLevel)
        self.parser = ArgumentParser(description=self.name)
        self.parser.add_argument('-v',
                                 '--verbose',
                                 action='store_true',
                                 default=False,
                                 help="Verbose messaging",
                                 )

    def start(self):
        self.parseArgs()

        if self.arguments['verbose']:
            CONSOLE.setLevel(DEBUG)

    def popen(self, command, cwd=None, stderr=None, stdout=None):
        if stderr == None:
            stderr = subprocess.PIPE
        if stdout == None:
            stdout = subprocess.PIPE
        self.out.debug('running command: ' + command.__str__())
        with self.out.indent():
            self.systemCallCounter += 1
            process = subprocess.Popen(command, cwd=cwd, stdin=None, stdout=stdout, stderr=stderr, universal_newlines=True)
        return process

    def finish(self, exitCode=0):
        '''
        override this to do any housekeeping before exit
        WARNING: not guaranteed to fire, specifically with uncaught exceptions
        '''
        exit(exitCode)


class Job(MinimalJob):
    '''
    Sample usage of Job():

    >>> job = Job('JobName')
    >>>
    >>> # do any context-specific job init
    >>>
    >>> job.start()             # print an intro message and indent
    >>>
    >>> # Do what you came to do; use the job fields to orchestrate your program:
    >>> job.out                 # IndentedOutput instance for logging
    >>> job.arguments           # dict parsed from the command line arguments
    >>> job.config              # dict parsed from config file
    >>> job.configFile          # str filename that job.config was parsed from
    >>>
    >>>
    >>> job.finish()            # un-indent and print a summary message
    '''

    def __init__(self, name, logFilename=None, logLevel=INFO, quiet=False, readOnly=False):
        super(Job, self).__init__(name)
        self.quiet = quiet
        self.readOnly = readOnly
        self.configDir = join(expanduser('~'), '.' + camelToSnake(name))
        if not exists(self.configDir):
            mkdir(self.configDir)  # better to create parents if missing?
        self.configFilename = None
        self.config = {'lastRunDateTime': None}  # default config before config file is read
        self.out = IndentedOutput(name, logFilename, logLevel)
        self.parser.add_argument('-c',
                                 '--config-file',
                                 help="Name of the config file to use for mapping, reporting, etc. (default: <filename>/config.json)",
                                 )

    def parseArgs(self):
        self.arguments = vars(self.parser.parse_args())  # converts Namespace to {}

    def start(self, allowMissingConfigFile=True):
        super(Job, self).start()

        if not self.quiet:
            self.out.indent('%s job started at %s' % (self.name, dateString()))

        # load config file
        if self.configFilename is None:
            if self.arguments['config_file']:
                self.configFilename = self.arguments['config_file']
            else:
                self.configFilename = join(self.configDir, 'config.json')
        if not self.quiet:
            self.out.put('Loading config from %s...' % self.configFilename)

        if not exists(self.configFilename):
            if not allowMissingConfigFile:
                raise Exception("No config file found, and allowMissingConfigFile is set to False")
            if not self.quiet:
                self.out.put('No config file found. Continuing with default config...')
        else:
            with open(self.configFilename) as configFile:
                try:
                    configJson = load(configFile)
                    self.config.update(configJson)
                except ValueError as e:
                    if not self.quiet:
                        with self.out.indent("Config file couldn't be parsed!"):
                            with open(self.configFilename) as configFileForPrinting:
                                self.out.error(configFileForPrinting.read())
                    raise e

        if not self.quiet and not self.readOnly:
            if not self.config['lastRunDateTime']:
                self.out.put('This appears to be the first run.')
            else:
                self.out.put('Last successful run: %s' % dateString(self.config['lastRunDateTime']))

    def finish(self, exitCode=0):
        if not self.readOnly:
            self.saveConfig()
        if not self.quiet:
            self.out.unIndent()
            self.out.put('%s job finished at %s' % (self.name, dateString()))
        super(Job, self).finish(exitCode)

    def saveConfig(self):
        lastRunDateTime = getCurrentDateTimeDict()
        self.config['lastRunDateTime'] = lastRunDateTime
        configContent = dumps(self.config, indent=4, sort_keys=True)
        with open(self.configFilename, 'w+') as configFile:
            for line in configContent.splitlines():
                configFile.write(line.rstrip() + '\n')

    def getEmailConfigFromArgsAndConfigFile(self):
        result = {}
        missingFields = False

        for k in ['email_from', 'email_to', 'email_password']:
            value = self.arguments.get(k) or self.config.get(k)
            if value:
                result[k] = value
            else:
                self.out.warn('Disabling email because no parameter or config value was given for %s.' % k)
                missingFields = True

        if missingFields:
            result['email_enabled'] = False
        elif 'email_enabled' in self.arguments:
            result['email_enabled'] = self.arguments['email_enabled']
        else:
            result['email_enabled'] = self.config.get('email_enabled', True)

        self.out.debug('using email config: %s' % dumps(result, indent=4, sort_keys=True))

        return result


if __name__ == '__main__':
    j = Job('Test')
    j.start()
    j.out.indent('indent title 1', ['indent', 'parameters'])
    with j.out.indent('indent title 2'):
        j.out.put('put() call inside the with:')
    j.out.put('put() call after the with:')
    j.finish()
