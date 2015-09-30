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
"""Project data model controller."""

import os
import shutil
from tau import logger, util
from tau.error import InternalError, ConfigurationError
from tau.core.mvc import Controller, with_key_attribute
from tau.core.storage import PROJECT_STORAGE

LOGGER = logger.get_logger(__name__)


@with_key_attribute('name')
class Project(Controller):
    """Project data controller."""
    
    def prefix(self):
        return os.path.join(self['prefix'], self['name'])

    def on_create(self):
        super(Project,self).on_create()
        prefix = self.prefix()
        try:
            util.mkdirp(prefix)
        except Exception as err:
            raise ConfigurationError("Cannot create directory '%s': %s" % (prefix, err),
                                     "Check that you have `write` access")

    def on_delete(self):
        # pylint: disable=broad-except
        super(Project,self).on_delete()
        prefix = self.prefix()
        try:
            shutil.rmtree(prefix)
        except Exception as err:
            if os.path.exists(prefix):
                LOGGER.error("Could not remove project data at '%s': %s", prefix, err)
    
    @classmethod
    def get_project(cls):
        """Gets the current project's configuration data.
        
        Asserts that there is exactly one project in the project storage container.
        
        Returns:
            Project: Controller for the current project's data.
        """
        ctrl = cls(PROJECT_STORAGE)
        projects = ctrl.all()
        if not projects:
            raise InternalError("No projects found at '%s'" % ctrl.storage.prefix)
        elif len(projects) > 1:
            project_names = ', '.join([proj['name'] for proj in projects])
            raise InternalError("Multiple projects found at '%s': %s" % (ctrl.storage.prefix, project_names))
        else:
            return projects[0]

    @classmethod
    def get_selected(cls):
        """Gets the selected Experiment.
        
        Returns:
            Experiment: Controller for the currently selected experiment data or None if no selection has been made.
        """
        from tau.core.experiment import Experiment
        proj = cls.get_project()
        experiment_id = proj['selected']
        if experiment_id:
            found = Experiment(PROJECT_STORAGE).one(eid=experiment_id)
            if not found:
                raise InternalError('Invalid experiment ID: %r' % experiment_id)
            return found
        return None
