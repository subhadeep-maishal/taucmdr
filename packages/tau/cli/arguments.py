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
"""TAU Commander command line interface (CLI).

Extensions to :any:`argparse` to support the TAU Commander command line interface.
"""

import os
import argparse
import textwrap
from tau import logger, util
from operator import attrgetter

SUPPRESS = argparse.SUPPRESS
"""Suppress attribute creation in parsed argument namespace."""

REMAINDER = argparse.REMAINDER
"""All the remaining command-line arguments are gathered into a list."""


class MutableGroupArgumentParser(argparse.ArgumentParser):
    """Argument parser with mutable groups and better help formatting.

    :py:class:`argparse.ArgumentParser` doesn't allow groups to change once set 
    and generates "scruffy" looking help, so we fix this problems in this subclass.
    """

    def get_group(self, title):
        """Returns an argument group.
        
        If the group doesn't exist it will be created.
        
        Args:
            title (str): Group title.
            
        Returns:
            An argument group object.
        """
        for group in self._action_groups:
            if group.title == title:
                return group
        return self.add_argument_group(title=title)

    def format_help(self):
        """Format command line help string."""
        # We're changing the behavior of the superclass so we need to access protected members in this function
        # pylint: disable=protected-access
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, self._actions, self._mutually_exclusive_groups)
        formatter.add_text(self.description)
        for action_group in self._sorted_groups():
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(sorted(action_group._group_actions, key=attrgetter('option_strings')))
            formatter.end_section()
        formatter.add_text(self.epilog)
        return formatter.format_help()

    def _sorted_groups(self):
        """Iterate over action groups."""
        positional_title = 'positional arguments'
        optional_title = 'optional arguments'
        groups = sorted(self._action_groups, key=lambda x: x.title.lower())
        for group in groups:
            if group.title == positional_title:
                yield group
                break
        for group in groups:
            if group.title == optional_title:
                yield group
                break
        for group in groups:
            if group.title not in [positional_title, optional_title]:
                yield group


class ArgparseHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help string formatter for argument parser.
    
    Provide proper help message alignment, line width, and formatting.
    Uses console line width (:any:`logger.LINE_WIDTH`) to format help 
    messages appropriately so they don't wrap in strange ways.
    
    Args:
        prog (str): Name of the program.
        indent_increment (int): Number of spaces to indent wrapped lines.
        max_help_position (int): Column on which to begin subsequent lines of wrapped help strings.
        width (int): Maximum help message length before wrapping.
    """

    def __init__(self, prog, indent_increment=2, max_help_position=30, width=logger.LINE_WIDTH):
        super(ArgparseHelpFormatter, self).__init__(prog, indent_increment, max_help_position, width)

    def _split_lines(self, text, width):
        parts = []
        for line in text.splitlines():
            parts.extend(textwrap.wrap(line, width))
        return parts

    def _get_help_string(self, action):
        indent = ' ' * self._indent_increment
        helpstr = action.help
        choices = getattr(action, 'choices', None)
        if choices:
            helpstr += '\n%s- %s: %s' % (indent, action.metavar, ', '.join(choices))
        if '%(default)' not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    if isinstance(action.default, list):
                        default_str = ', '.join(action.default)
                    else:
                        default_str = str(action.default)
                    helpstr += '\n%s' % indent + '- default: %s' % default_str
        return helpstr


class ParsePackagePathAction(argparse.Action):
    """Argument parser action for software package paths.
    
    This action checks that an argument's value is one of these cases:
    1) The path to an existing software package installation.
    2) The path to an archive file containing the software package.
    3) A URL to an archive file containing the software package.
    4) The magic word "download" or value that parses to True via :any:`tau.util.parse_bool`.
    5) A value that parses to False via :any:`parse_bool`.
    """
    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, flag, unused_option_string=None):
        """Sets the `self.dest` attribute in `namespace` to the parsed value of `flag`.
        
        If `flag` parses to a boolean True value then the attribute value is 'download'.
        If `flag` parses to a boolean False value then the attribute value is ``None``.
        Otherwise the attribute value is the value of `flag`.
            
        Args:
            parser (str): Argument parser object this group belongs to.
            namespace (object): Namespace to receive parsed value via setattr.
            flag (str): Value parsed from the command line.
        """
        flag_as_bool = util.parse_bool(flag, additional_true=['download'])
        if flag_as_bool == True:
            value = 'download'
        elif flag_as_bool == False:
            value = None
        elif util.is_url(flag):
            value = flag
        else:
            value = os.path.abspath(os.path.expanduser(flag))
            if not os.path.isdir(value) and not util.file_accessible(value):
                raise argparse.ArgumentError(self, "Boolean, 'download', valid path, or URL required: %s" % flag)
        setattr(namespace, self.dest, value)


class ParseBooleanAction(argparse.Action):
    """Argument parser action for boolean values.
    
    Essentially a wrapper around :any:`tau.util.parse_bool`.
    """
    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, flag, unused_option_string=None):
        """Sets the `self.dest` attribute in `namespace` to the parsed value of `flag`.
        
        If `flag` parses to a boolean via :any:`tau.util.parse_bool` then the 
        attribute value is that boolean value.
            
        Args:
            parser (str): Argument parser object this group belongs to.
            namespace (object): Namespace to receive parsed value via setattr.
            flag (str): Value parsed from the command line/
        """
        bool_value = util.parse_bool(flag)
        if bool_value == None:
            raise argparse.ArgumentError(self, 'Boolean value required')
        setattr(namespace, self.dest, bool_value)


def get_parser(prog=None, usage=None, description=None, epilog=None):
    """Builds an argument parser.
    
    The returned argument parser accepts no arguments.
    Use :any:`argparse.ArgumentParser.add_argument` to add arguments.
    
    Args:
        prog (str): Name of the program.
        usage (str): Description of the program's usage.
        description (str): Text to display before the argument help.
        epilog (str): Text to display after the argument help.

    Returns:
        MutableGroupArgumentParser: The customized argument parser object.
    """
    return MutableGroupArgumentParser(prog=prog,
                                      usage=usage,
                                      description=description,
                                      epilog=epilog,
                                      formatter_class=ArgparseHelpFormatter)


def get_parser_from_model(model, use_defaults=True, prog=None, usage=None, description=None, epilog=None):
    """Builds an argument parser from a model's attributes.
    
    The returned argument parser will accept arguments as defined by the model's `argparse` 
    attribute properties, where the arguments to :any:`argparse.ArgumentParser.add_argument` 
    are specified as keyword arguments.
    
    Examples:
        Given this model attribute:
        ::
        
            'openmp': {
                'type': 'boolean', 
                'description': 'application uses OpenMP',
                'default': False, 
                'argparse': {'flags': ('--openmp',),
                             'metavar': 'yes/no',
                             'nargs': '?',
                             'const': True,
                             'action': ParseBooleanAction},
            }

        The returned parser will accept the ``--openmp`` flag accepting zero or one arguments 
        with 'yes/no' as the metavar.  If ``--openmp`` is omitted the default value of False will
        be used.  If ``--openmp`` is provided with zero arguments, the const value of True will
        be used.  If ``--openmp`` is provided with one argument then the provided argument will
        be passed to a ParseBooleanAction instance to generate a boolean value.  The argument's
        help description will appear as "application uses OpenMP" if the ``--help`` argument is given.
    
    Args:
        use_defaults (bool): If True, use the model attribute's default value 
                             as the argument's value if argument is not specified. 
        prog (str): Name of the program.
        usage (str): Description of the program's usage.
        description (str): Text to display before the argument help.
        epilog (str): Text to display after the argument help.

    Returns:
        MutableGroupArgumentParser: The customized argument parser object.        
    """
    parser = MutableGroupArgumentParser(prog=prog,
                                        usage=usage,
                                        description=description,
                                        epilog=epilog,
                                        formatter_class=ArgparseHelpFormatter)
    groups = {}
    for attr, props in model.attributes.iteritems():
        try:
            options = dict(props['argparse'])
        except KeyError:
            continue
        if use_defaults:
            options['default'] = props.get('default', argparse.SUPPRESS) 
        else:
            options['default'] = argparse.SUPPRESS
        try:
            options['help'] = props['description']
        except KeyError:
            pass
        try:
            group_name = options['group'] + ' arguments'
        except KeyError:
            group = parser
        else:
            del options['group']
            groups.setdefault(
                group_name, parser.add_argument_group(group_name))
            group = groups[group_name]
        try:
            flags = options['flags']
        except KeyError:
            flags = (attr,)
        else:
            del options['flags']
            options['dest'] = attr
        group.add_argument(*flags, **options)
    return parser