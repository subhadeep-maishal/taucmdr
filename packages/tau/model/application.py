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
"""Application data model.

:any:`Application` fully describes the application configuration to be profiled, 
including the features the application uses, e.g. OpenMP, MPI, CUDA, etc.
Each specific application **configuration** has its own application record.  
For example, if an application can operate with or without OpenMP then there 
are potentially two application records for the same application code: one 
specifying OpenMP is used and the other specifying OpenMP is not used.
"""

import os
from tau.error import IncompatibleRecordError, ConfigurationError
from tau.mvc.model import Model
from tau.cf.compiler.mpi import MPI_COMPILERS
from tau.cf.compiler.shmem import SHMEM_COMPILERS


def attributes():
    from tau.model.project import Project
    from tau.model.target import Target
    from tau.model.measurement import Measurement
    from tau.cli.arguments import ParseBooleanAction
    return {
        'projects': { 
            'collection': Project,
            'via': 'applications',
            'description': 'projects using this application'
        },
        'name': {
            'primary_key': True,
            'type': 'string',
            'description': 'application configuration name',
            'unique': True,
            'argparse': {'metavar': '<application_name>'}
        },
        'openmp': {
            'type': 'boolean', 
            'description': 'application uses OpenMP',
            'default': False,
            'argparse': {'flags': ('--use-openmp',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'on_change': Application.attribute_changed
        },
        'pthreads': {
            'type': 'boolean',
            'description': 'application uses pthreads',
            'default': False,
            'argparse': {'flags': ('--use-pthreads',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'on_change': Application.attribute_changed
        },
        'mpi': {
            'type': 'boolean',
            'default': False,
            'description': 'application uses MPI',
            'argparse': {'flags': ('--use-mpi',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'compat': {True: Measurement.require('mpi', True)},
            'on_change': Application.attribute_changed
        },
        'cuda': {
            'type': 'boolean',
            'default': False,
            'description': 'application uses NVIDIA CUDA',
            'argparse': {'flags': ('--use-cuda',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'compat': {True: Target.require('cuda')},
            'on_change': Application.attribute_changed
        },
        'opencl': {
            'type': 'boolean',
            'default': False,
            'description': 'application uses OpenCL',
            'argparse': {'flags': ('--use-opencl',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'compat': {True: (Target.require('cuda'),
                              Measurement.encourage('opencl', True))},
            'on_change': Application.attribute_changed
        },
        'shmem': {
            'type': 'boolean',
            'default': False,
            'description': 'application uses SHMEM',
            'argparse': {'flags': ('--use-shmem',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'on_change': Application.attribute_changed
        },
        'mpc': {
            'type': 'boolean',
            'default': False,
            'description': 'application uses MPC',
            'argparse': {'flags': ('--use-mpc',),
                         'metavar': 'T/F',
                         'nargs': '?',
                         'const': True,
                         'action': ParseBooleanAction},
            'on_change': Application.attribute_changed
        },
        'select_file': {
            'type': 'string',
            'description': 'specify selective instrumentation file',
            'argparse': {'flags': ('--select-file',),
                         'metavar': 'path'},
            'compat': {True: Measurement.exclude('source_inst', 'never')},
            'on_change': Application.attribute_changed
        }
    }
        

class Application(Model):
    """Application data model."""
    
    __attributes__ = attributes
    
    @classmethod
    def attribute_changed(cls, model, attr, new_value):
        if model.is_selected():
            old_value = model.get(attr, None)
            cls.controller(model.storage).push_to_topic('rebuild_required', {attr: (old_value, new_value)})

    def _check_select_file(self):
        try:
            select_file = self['select_file']
        except KeyError:
            pass
        else:
            if not os.path.exists(select_file):
                raise ConfigurationError("Selective instrumentation file '%s' not found" % select_file)
    
    def on_create(self):
        self._check_select_file()

    def on_update(self):
        from tau.error import ImmutableRecordError
        from tau.model.experiment import Experiment
        expr_ctrl = Experiment.controller(self.storage)
        found = expr_ctrl.search({'application': self.eid})
        using_app = [expr['name'] for expr in found if expr.data_size() > 0]
        if using_app:
            raise ImmutableRecordError("Application '%s' cannot be modified because "
                                       "it is used by these experiments: %s" % (self['name'], ', '.join(using_app)))
        for expr in found:
            try:
                expr.verify()
            except IncompatibleRecordError as err:
                raise ConfigurationError("Changing application '%s' in this way will create an invalid condition "
                                         "in experiment '%s':\n    %s." % (self['name'], expr['name'], err),
                                         "Delete experiment '%s' and try again." % expr['name'])
        self._check_select_file()

    def is_selected(self):
        """Returns True if this target configuration is part of the selected experiment, False otherwise."""
        from tau.model.project import Project, ProjectSelectionError, ExperimentSelectionError
        try:
            selected = Project.controller().selected().experiment()
        except (ProjectSelectionError, ExperimentSelectionError):
            return False
        return selected['application'] == self.eid
    
    def check_compiler(self, compiler):
        """Checks a compiler for compatibility with this application configuration.
        
        Args:
            compiler (InstalledCompiler): The compiler.
            
        Raises:
            ConfigurationError: The compiler or command line arguments are incompatible with this target.
        """
        if self['mpi'] and compiler.info.family not in MPI_COMPILERS.families.values():
            raise ConfigurationError("Application '%s' uses MPI but %s is not an MPI compiler." % 
                                     (self['name'], compiler.absolute_path))
        if self['shmem'] and compiler.info.family not in SHMEM_COMPILERS.families.values():
            raise ConfigurationError("Application '%s' uses SHMEM but %s is not a SHMEM compiler." % 
                                     (self['name'], compiler.absolute_path))
        

