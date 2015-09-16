# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, ParaTools, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# (1) Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
# (2) Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
# (3) Neither the name of ParaTools, Inc. nor the names of its contributors may
#     be used to endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
"""Trial data model.

Every application of an :any:`Experiment` produces a new :any:`Trial`.  The trial
record completely describes the hardware and software environment that produced
the performance data.
"""

import os
import glob
import shutil
import errno
from datetime import datetime
from tau import logger, util, storage
from tau.error import ConfigurationError
from tau.model import Controller

LOGGER = logger.get_logger(__name__)


class TrialError(ConfigurationError):
    """Indicates there was an error while performing an experiment trial."""
    message_fmt = ("\n"
                   "%(value)s\n"
                   "\n"
                   "%(hints)s\n"
                   "\n"
                   "Please check the selected configuration for errors or"
                   " email '%(logfile)s' to  %(contact)s for assistance.")


class Trial(Controller):
    """Trial data controller."""

    def prefix(self):
        experiment = self.populate('experiment')
        return os.path.join(experiment.prefix(), str(self['number']))

    def on_create(self):
        prefix = self.prefix()
        try:
            util.mkdirp(prefix)
        except Exception as err:
            raise ConfigurationError('Cannot create directory %r: %s' % (prefix, err),
                                     'Check that you have `write` access')

    def on_delete(self):
        # pylint: disable=broad-except
        prefix = self.prefix()
        try:
            shutil.rmtree(prefix)
        except Exception as err:
            if os.path.exists(prefix):
                LOGGER.error("Could not remove trial data at '%s': %s", prefix, err)
                
    @classmethod
    def _next_trial_number(cls, expr):
        trials = expr.populate('trials')
        for i, j in enumerate(sorted([trial['number'] for trial in trials])):
            if i != j:
                return i
        return len(trials)
    
    def profile_files(self):
        """Get this trial's profile files.
        
        Returns paths to profile files (profile.X.Y.Z).  If the trial produced 
        MULTI__ directories then paths to every profile below every MULTI__ 
        directory are returned. 
        
        Returns:
            list: Paths to profile files.
        """
        list_profiles = lambda path: glob.glob(os.path.join(path, 'profile.*.*.*'))
        prefix = self.prefix()
        profiles = []
        for multi_dir in glob.iglob(os.path.join(prefix, 'MULTI__*')):
            profiles.extend(list_profiles(multi_dir))
        profiles.extend(list_profiles(prefix))
        return profiles
    
    def execute_command(self, expr, cmd, cwd, env):
        """Execute a command as part of an experiment trial.
        
        Creates a new subprocess for the command and checks for TAU data files
        when the subprocess exits.
        
        Args:
            expr (Experiment): Experiment data.
            cmd (str): Command to profile, with command line arguments.
            cwd (str): Working directory to perform trial in.
            env (dict): Environment variables to set before performing the trial.
            
        Returns:
            int: Subprocess return code.
        """
        cmd_str = ' '.join(cmd)
        LOGGER.info(cmd_str)
        try:
            retval = util.create_subprocess(cmd, cwd=cwd, env=env)
        except OSError as err:
            target = expr.populate('target')
            errno_hint = {errno.EPERM: "Check filesystem permissions",
                          errno.ENOENT: "Check paths and command line arguments",
                          errno.ENOEXEC: "Check that this host supports '%s'" % target['host_arch']}
            raise TrialError("Couldn't execute %s: %s" % (cmd_str, err), errno_hint.get(err.errno, None))
        if retval:
            LOGGER.warning("Return code %d from '%s'", retval, cmd_str)
        measurement = expr.populate('measurement')
        if measurement['profile']:
            profiles = self.profile_files()
            if profiles:
                LOGGER.info("Trial produced %d profile files.", len(profiles))
            elif retval != 0:
                raise TrialError("Program died without producing performance data.",
                                 "Verify that the right input parameters were specified.",
                                 "Check the program output for error messages.",
                                 "Does the selected application configuration correctly describe this program?",
                                 "Does the selected measurement configuration specifiy the right measurement methods?",
                                 "Does the selected target configuration match the runtime environment?")
            else:
                raise TrialError("Application completed successfuly but did not produce any performance data.")
        return retval

    @classmethod
    def perform(cls, expr, cmd, cwd, env):
        """Performs a trial of an experiment.
        
        Args:
            expr (Experiment): Experiment data.
            cmd (str): Command to profile, with command line arguments.
            cwd (str): Working directory to perform trial in.
            env (dict): Environment variables to set before performing the trial.
        """
        def banner(mark, name, time):
            headline = '{:=<{}}'.format('== %s %s (%s) ==' % (mark, name, time), logger.LINE_WIDTH)
            LOGGER.info(headline)

        cmd_str = ' '.join(cmd)
        begin_time = str(datetime.utcnow())
        trial_number = cls._next_trial_number(expr)
        LOGGER.debug("New trial number is %d", trial_number)

        banner('BEGIN', expr.name(), begin_time)
        fields = {'number': trial_number,
                  'experiment': expr.eid,
                  'command': cmd_str,
                  'cwd': cwd,
                  'environment': 'FIXME',
                  'begin_time': begin_time}
        trial = cls.create(fields)
        
        # Tell TAU to send profiles and traces to the trial prefix
        prefix = trial.prefix()
        env['PROFILEDIR'] = prefix
        env['TRACEDIR'] = prefix

        try:
            retval = trial.execute_command(expr, cmd, cwd, env)
        except:
            cls.delete(eids=[trial.eid])
            end_time = str(datetime.utcnow())
            raise
        else:
            data_size = sum(os.path.getsize(os.path.join(prefix, f)) for f in os.listdir(prefix))
            shutil.copy(storage.USER_STORAGE.dbfile, prefix)
            end_time = str(datetime.utcnow())
            cls.update({'end_time': end_time,
                        'return_code': retval,
                        'data_size': data_size}, eids=[trial.eid])
        finally:
            banner('END', expr.name(), end_time)
        return retval


Trial.attributes = {
    'number': {
        'type': 'integer',
        'required': True,
        'description': 'trial unique identifier'
    },
    'experiment': {
        'model': 'Experiment',
        'required': True,
        'description': "this trial's experiment"
    },
    'command': {
        'type': 'string',
        'required': True,
        'description': "command line executed when performing the trial"
    },
    'cwd': {
        'type': 'string',
        'required': True,
        'description': "directory the trial was performed in",
    },
    'environment': {
        'type': 'string',
        'required': True,
        'description': "shell environment the trial was performed in"
    },
    'begin_time': {
        'type': 'datetime',
        'description': "date and time the trial began"
    },
    'end_time': {
        'type': 'datetime',
        'description': "date and time the trial ended"
    },
    'return_code': {
        'type': 'integer',
        'description': "return code of the command executed when performing the trial"
    },
    'data_size': {
        'type': 'integer',
        'description': "the size in bytes of the trial data"
    },
}

