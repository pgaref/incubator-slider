#!/usr/bin/env python

'''
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import json
import logging
import os
import subprocess
import pprint
import threading
from threading import Thread
from Grep import Grep
import shell
import sys
import platform
import Constants
from AgentToggleLogger import AgentToggleLogger


logger = logging.getLogger()


class PythonExecutor:
  """
  Performs functionality for executing python scripts.
  Warning: class maintains internal state. As a result, instances should not be
  used as a singleton for a concurrent execution of python scripts
  """

  NO_ERROR = "none"
  grep = Grep()
  event = threading.Event()
  python_process_has_been_killed = False

  def __init__(self, tmpDir, config, agentToggleLogger):
    self.tmpDir = tmpDir
    self.config = config
    self.agentToggleLogger = agentToggleLogger
    pass

  def run_file(self, script, script_params, tmpoutfile, tmperrfile, timeout,
               tmpstructedoutfile, logger_level, override_output_files=True,
               environment_vars=None):
    """
    Executes the specified python file in a separate subprocess.
    Method returns only when the subprocess is finished.
    Params arg is a list of script parameters
    Timeout meaning: how many seconds should pass before script execution
    is forcibly terminated
    override_output_files option defines whether stdout/stderr files will be
    recreated or appended
    """
    if override_output_files: # Recreate files
      tmpout = open(tmpoutfile, 'w')
      tmperr = open(tmperrfile, 'w')
    else: # Append to files
      tmpout = open(tmpoutfile, 'a')
      tmperr = open(tmperrfile, 'a')

    # need to remove this file for the following case:
    # status call 1 does not write to file; call 2 writes to file;
    # call 3 does not write to file, so contents are still call 2's result
    try:
      os.unlink(tmpstructedoutfile)
    except OSError:
      pass # no error

    script_params += [tmpstructedoutfile, logger_level, self.config.getWorkRootPath()]
    pythonCommand = self.python_command(script, script_params)
    self.agentToggleLogger.log("Running command " + pprint.pformat(pythonCommand))
    process = self.launch_python_subprocess(pythonCommand, tmpout, tmperr,
                                            environment_vars)
    logger.debug("Launching watchdog thread")
    self.event.clear()
    self.python_process_has_been_killed = False
    thread = Thread(target=self.python_watchdog_func, args=(process, timeout))
    thread.start()
    # Waiting for the process to be either finished or killed
    if self._is_stop_command(pythonCommand):
      out, err = process.communicate()
      logger.info("stop command output: " + str(out) + " err: " + str(err))
    else:
      process.communicate()
    self.event.set()
    thread.join()
    # Building results
    error = self.NO_ERROR
    returncode = process.returncode
    out = open(tmpoutfile, 'r').read()
    error = open(tmperrfile, 'r').read()

    structured_out = {}
    try:
      with open(tmpstructedoutfile, 'r') as fp:
        structured_out = json.load(fp)
    except Exception as e:
      if os.path.exists(tmpstructedoutfile):
        errMsg = 'Unable to read structured output from ' + tmpstructedoutfile + ' ' + str(e)
        structured_out = {
          'msg': errMsg
        }
        logger.warn(structured_out)

    if self.python_process_has_been_killed:
      error = str(error) + "\n Python script has been killed due to timeout"
      returncode = 999
    result = self.condenseOutput(out, error, returncode, structured_out)
    self.agentToggleLogger.log("Result: %s" % result)
    return result

  def _is_stop_command(self, command):
    for cmd in command:
      if cmd == "STOP":
        return True

    return False


  def launch_python_subprocess(self, command, tmpout, tmperr,
                               environment_vars=None):
    """
    Creates subprocess with given parameters. This functionality was moved to separate method
    to make possible unit testing
    """
    close_fds = None if platform.system() == "Windows" else True
    env = os.environ.copy()
    if environment_vars:
      for k, v in environment_vars:
        self.agentToggleLogger.log("Setting env: %s to %s", k, v)
        env[k] = v
    if self._is_stop_command(command):
      command_str = ''
      for itr in command:
        command_str = command_str + ' ' + itr

      logger.info("command str: " + command_str)
      return subprocess.Popen(command_str, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True)

    else:
      return subprocess.Popen(command,
                              stdout=tmpout,
                              stderr=tmperr, close_fds=close_fds, env=env)

  def isSuccessfull(self, returncode):
    return not self.python_process_has_been_killed and returncode == 0

  def python_command(self, script, script_params):
    #we need manually pass python executable on windows because sys.executable will return service wrapper
    python_binary = os.environ['PYTHON_EXE'] if 'PYTHON_EXE' in os.environ else sys.executable
    if not python_binary:
      python_binary = '/usr/bin/python'
      self.agentToggleLogger.log( " Unable to determine python interpreter from sys.executable. Using /usr/bin/python default. python_bin")
    python_command = [python_binary, "-S", script] + script_params
    return python_command

  def condenseOutput(self, stdout, stderr, retcode, structured_out):
    log_lines_count = self.config.get('heartbeat', 'log_lines_count')

    grep = self.grep
    result = {
      Constants.EXIT_CODE: retcode,
      "stdout": grep.tail(stdout,
                          log_lines_count) if log_lines_count else stdout,
      "stderr": grep.tail(stderr,
                          log_lines_count) if log_lines_count else stderr,
      "structuredOut": structured_out
    }

    return result

  def python_watchdog_func(self, python, timeout):
    self.event.wait(timeout)
    if python.returncode is None:
      logger.error("Subprocess timed out and will be killed")
      shell.kill_process_with_children(python.pid)
      self.python_process_has_been_killed = True
    pass
