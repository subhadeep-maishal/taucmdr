# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, ParaTools, Inc.
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
"""Test functions.

Asserts that pylint score doesn't drop below minimum.
"""

import os
import sys
import subprocess
from taucmdr import TAUCMDR_HOME
from taucmdr import tests


class PylintTest(tests.TestCase):
    """Runs Pylint to make sure the code scores at least 9.0"""
       
    def run_pylint(self, *args):
        cmd = [sys.executable, "-m", "pylint", '--rcfile=' + os.path.join(TAUCMDR_HOME, "pylintrc")]
        cmd.extend(args)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=False, env=env, universal_newlines=True)
        return process.communicate()
    
    def test_pylint_version(self):
        stdout, stderr = self.run_pylint('--version')
        self.assertFalse(stderr)
        try:
            version_parts = stdout.split(',')[0].split('__main__.py ')[1].split('.')
        except IndexError:
            self.fail("Unable to parse pylint version string:\n%s" % stdout)           
        version = tuple(int(x) for x in version_parts)
        self.assertGreaterEqual(version, (1, 5, 2), "Pylint version %s is too old!" % str(version))
    
    def test_pylint(self):
        stdout, stderr = self.run_pylint(os.path.join(TAUCMDR_HOME, "packages", "taucmdr"))
        self.assertFalse(stderr)
        self.assertIn('Your code has been rated at', stdout)
        score = float(stdout.split('Your code has been rated at')[1].split('/10')[0])
        self.assertGreaterEqual(score, 9.0, "%s\nPylint score %s/10 is too low!" % (stdout, score))

