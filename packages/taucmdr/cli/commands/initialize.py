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
"""``initialize`` subcommand."""

import os
import platform
from taucmdr import util
from taucmdr import EXIT_SUCCESS, EXIT_WARNING
from taucmdr.error import InternalError, ConfigurationError, ProjectSelectionError
from taucmdr.model.project import Project
from taucmdr.model.target import Target
from taucmdr.model.application import Application
from taucmdr.cli import arguments
from taucmdr.cli.command import AbstractCommand
from taucmdr.cli.arguments import ParseBooleanAction
from taucmdr.cli.commands.target.create import COMMAND as target_create_cmd
from taucmdr.cli.commands.application.create import COMMAND as application_create_cmd
from taucmdr.cli.commands.measurement.create import COMMAND as measurement_create_cmd
from taucmdr.cli.commands.project.create import COMMAND as project_create_cmd
from taucmdr.cli.commands.project.select import COMMAND as project_select_cmd
from taucmdr.cli.commands.select import COMMAND as select_cmd
from taucmdr.cli.commands.dashboard import COMMAND as dashboard_cmd
from taucmdr.cf.storage.project import ProjectStorageError
from taucmdr.cf.storage.levels import PROJECT_STORAGE, STORAGE_LEVELS


HELP_PAGE = """
TAU Commander Initialize:
============================================================================

To begin Initialize TAU Commander, enter: `tau initialize` or simply 
`tau init`.  
This first initialization will take quite a bit of time.  Not only is this 
command creating a project it is also downloading and building the 
TAU Performance System® and associated libraries that it depends on.  
Let this run and check for successful completion. When it completes it will 
display the tau dashboard (which can be viewed at anytime by entering: 
'tau dashboard').

Many parameters may be defined at initialization.  The full list of options is 
displayed below this help section.   It is easier to define options at 
initialization (eg. tau init --MPI T) than it is to edit application and 
measurement later.
___________________________________________________________________________

"""


class InitializeCommand(AbstractCommand):
    """``tau initialize`` subcommand."""
       
    def _construct_parser(self):
        """Constructs the command line argument parser.
         
        Returns:
            A command line argument parser instance.
        """
        def _default_target_name():
            node_name = platform.node()
            if not node_name:
                return 'default_target'
            return node_name.split('.')[0]

        usage = "%s [arguments]" % self.command
        parser = arguments.get_parser(prog=self.command, usage=usage, description=self.summary)
        parser.add_argument('--bare',
                            help="Initialize project storage but don't configure anything",
                            nargs='?',
                            const=True,
                            default=False,
                            metavar='T/F',
                            action=ParseBooleanAction)
        
        default_project_name = os.path.basename(os.getcwd()) or 'default_project'
        project_group = parser.add_argument_group('project arguments')
        project_group.add_argument('--project-name',
                                   help="Name of the new project",
                                   metavar='<name>',
                                   default=default_project_name)
        project_group.add_argument('--storage-level',
                                   help='location of installation directory',
                                   choices=STORAGE_LEVELS.keys(),
                                   metavar='<levels>', default=arguments.SUPPRESS)

        parser.merge(target_create_cmd.parser, group_title='target arguments')
        target_group = parser.add_argument_group('target arguments')
        target_group.add_argument('--target-name',
                                  help="Name of the new target configuration",
                                  metavar='<name>',
                                  default=_default_target_name())

        parser.merge(application_create_cmd.parser, group_title='application arguments')
        default_application_name = os.path.basename(os.getcwd()) or 'default_application'
        application_group = parser.add_argument_group('application arguments')
        application_group.add_argument('--application-name',
                                       help="Name of the new application configuration",
                                       metavar='<name>',
                                       default=default_application_name)

        parser.merge(measurement_create_cmd.parser, group_title='measurement arguments')
        return parser

    def _split_args(self, cmd, argv):
        _, unparsed = cmd.parser.parse_known_args(argv)
        known, unknown = [], []
        for arg in argv:
            (unknown if arg in unparsed else known).append(arg)
        return known, unknown
        
    def _create_project(self, args):
        project_name = args.project_name
        options = [project_name]
        try:
            project_create_cmd.main(options)
        except ConfigurationError:
            PROJECT_STORAGE.disconnect_filesystem()
            util.rmtree(PROJECT_STORAGE.prefix, ignore_errors=True)
            raise
        else:
            project_select_cmd.main([project_name])
            
    def _populate_project(self, argv, args):
        def _safe_execute(cmd, argv):
            retval = cmd.main(argv)
            if retval != EXIT_SUCCESS:
                raise InternalError("return code %s: %s %s" % (retval, cmd, ' '.join(argv)))

        # Parse and strip application arguments to avoid ambiguous arguments like '--mpi' in `measurement create`
        application_name = args.application_name
        application_argv, argv = self._split_args(application_create_cmd, [application_name] + argv)
        _safe_execute(application_create_cmd, application_argv)
        
        # Parse and strip target arguments.
        target_name = args.target_name
        target_argv, argv = self._split_args(target_create_cmd, [target_name] + argv)
        _safe_execute(target_create_cmd, target_argv)

        # Target was created so let's see if we can use binutils on this target.
        targ = Target.controller(PROJECT_STORAGE).one({'name': target_name})
        if not targ['binutils_source']:
            self.logger.info("GNU binutils unavailable: disabling sampling and compiler-based instrumentation")
            args.sample = False
            args.compiler_inst = 'never'
        
        # At this point, anything in argv is either an argument to `measurement create` or invalid.    
        # Get application features so we can turn on measurements for those features.
        app = Application.controller(PROJECT_STORAGE).one({'name': application_name})
        measurement_args = argv + ['--%s=%s' % (attr, app.get(attr, False)) 
                                   for attr in 'mpi', 'cuda', 'opencl', 'shmem']

        # Create measurements
        measurement_names = []
        _safe_execute(measurement_create_cmd, 
                      ['baseline', 
                       '--baseline=True',
                       '--profile=tau',
                       '--trace=none',
                       '--sample=False',
                       '--source-inst=never',
                       '--compiler-inst=never'])
        if args.sample:
            trace = args.trace if args.profile == 'none' else 'none'
            _safe_execute(measurement_create_cmd, 
                          ['sample', 
                           '--profile', args.profile, 
                           '--trace', trace, 
                           '--sample=True',
                           '--source-inst=never', 
                           '--compiler-inst=never'] 
                          + measurement_args)
            measurement_names.append('sample')
        if args.profile != 'none':
            _safe_execute(measurement_create_cmd, 
                          ['profile', 
                           '--profile', args.profile, 
                           '--trace=none', 
                           '--sample=False',
                           '--source-inst', args.source_inst, 
                           '--compiler-inst', args.compiler_inst] 
                          + measurement_args)
            measurement_names.append('profile')
        if args.trace != 'none':
            _safe_execute(measurement_create_cmd, 
                          ['trace', 
                           '--profile=none', 
                           '--trace', args.trace, 
                           '--sample=False', 
                           '--callpath=0', 
                           '--source-inst', args.source_inst, 
                           '--compiler-inst', args.compiler_inst] 
                          + measurement_args)
            measurement_names.append('trace')
        # Baseline should be the default only if no other measurements exist
        measurement_names.append('baseline')

        select_cmd.main(['--target', target_name, 
                         '--application', application_name, 
                         '--measurement', measurement_names[0]])

    def main(self, argv):
        args, argv = self.parser.parse_known_args(argv)
        if not (args.baseline or args.profile or args.trace or args.sample):
            self.parser.error('You must specify at least one measurement.')

        proj_ctrl = Project.controller()
        try:
            proj = proj_ctrl.selected()
        except ProjectStorageError:
            self.logger.debug("No project found, initializing a new project.")
            PROJECT_STORAGE.connect_filesystem()
            try:
                self._create_project(args)
                if not args.bare:
                    self._populate_project(argv, args)
            except:
                PROJECT_STORAGE.destroy()
                raise
            return dashboard_cmd.main([])
        except ProjectSelectionError as err:
            err.value = "The project has been initialized but no project configuration is selected."
            raise err
        else:
            self.logger.warning("Tau is already initialized and the selected project is '%s'. Use commands like"
                                " `tau application edit` to edit the selected project or delete"
                                " '%s' to reset to a fresh environment.", proj['name'], proj_ctrl.storage.prefix)
            return EXIT_WARNING

COMMAND = InitializeCommand(__name__, help_page_fmt=HELP_PAGE, summary_fmt="Initialize TAU Commander.") 
