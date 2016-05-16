"""
Definition of commands

This could be also split into two parts: generic framework part, application specific part
"""

import logging

from sen.tui.commands.default_keybinds import key_mapping


logger = logging.getLogger(__name__)

# command -> Class
commands_mapping = {}


class KeyNotMapped(Exception):
    pass


class NoSuchCommand(Exception):
    pass


class NoSuchOptionOrArgument(Exception):
    pass


# class decorator to register commands
def register_command(kls):
    commands_mapping[kls.name] = kls
    return kls


class CommandPriority:
    pass


class BackendPriority(CommandPriority):
    """ command takes long to execute """


class FrontendPriority(CommandPriority):
    """ command needs to be executed ASAP """


class SameThreadPriority(CommandPriority):
    """ run the task in same thread as UI """


def true_action(val=None):
    return True


class ArgumentBase:
    def __init__(self, name, description, action=true_action, default=None):
        self.name = name
        self.description = description
        self.default = default
        self.action = action


class Argument(ArgumentBase):
    def __init__(self, name, description, action=true_action, aliases=None, default=None):
        super().__init__(name, description, action=action, default=default)
        self.aliases = aliases or []


class Option(ArgumentBase):
    pass


def normalize_arg_name(name):
    return name.replace("-", "_")  # so we access names-with-dashes


class ArgumentProcessor:
    """
    responsible for parsing given list of arguments
    """
    def __init__(self, arguments, options):
        """
        :param arguments: list of arguments
        :param options: list of options
        """
        self.given_arguments = {}
        self.arguments = {}
        for a in arguments:
            self.arguments[a.name] = a
            self.given_arguments[normalize_arg_name(a.name)] = a.default
            for alias in a.aliases:
                self.arguments[alias] = a
        self.options = options
        logger.info("arguments = %s", arguments)

    def process(self, argument_list):
        """
        :param argument_list: list of str, input from user
        :return: dict:
            {"cleaned_arg_name": "value"}
        """
        option_index = 0
        for a in argument_list:
            arg_and_val = a.split("=", 1)
            arg_first = arg_and_val[0]
            try:
                # argument
                argument = self.arguments[arg_first]
            except KeyError:
                # options
                try:
                    argument = self.options[option_index]
                except KeyError:
                    logger.error("option/argument %r not specified", a)
                    raise NoSuchOptionOrArgument("No such option or argument: %r" % arg_first)

            safe_arg_name = argument.name.replace("-", "_")  # so we access names-with-dashes
            if isinstance(argument, Option):
                option_index += 1
                self.given_arguments[safe_arg_name] = arg_first
            else:
                try:
                    arg_val = argument.action(arg_and_val[1])
                except IndexError:
                    arg_val = argument.action()
                self.given_arguments[safe_arg_name] = arg_val
        return self.given_arguments


class CommandArgumentsGetter:
    def __init__(self, given_arguments):
        self.given_arguments = given_arguments

    def set_argument(self, arg_name, value):
        self.given_arguments[arg_name] = value

    def __getattr__(self, item):
        try:
            return self.given_arguments[item]
        except KeyError:
            # this is an error in code, not user error
            logger.error("no argument/option defined: %r", item)
            raise AttributeError("No such option or argument: %r" % item)


class Command:
    # command name, unique identifier, used also in prompt
    name = ""
    # message explaining what's about to happen
    pre_info_message = ""
    # message explaining what has happened
    post_info_message = ""
    # how long it takes to run the command - in which queue it should be executed
    priority = None
    # used in help message
    description = ""
    # define arguments
    argument_definitions = []
    # define options
    option_definitions = []

    def __init__(self, ui=None, docker_backend=None, docker_object=None, buffer=None, size=None):
        """

        :param ui:
        :param docker_backend:
        :param docker_object:
        :param buffer:
        """
        logger.debug(
            "command %r initialized: ui=%r, docker_backend=%r, docker_object=%r, buffer=%r",
            self.name, ui, docker_backend, docker_object, buffer)
        self.ui = ui
        self.docker_backend = docker_backend
        self.docker_object = docker_object
        self.buffer = buffer
        self.size = size
        self.argument_processor = ArgumentProcessor(self.argument_definitions,
                                                    self.option_definitions)
        self.arguments = None

    def process_args(self, arguments):
        """

        :param arguments: dict
        :return:
        """
        given_arguments = self.argument_processor.process(arguments)
        logger.info("given arguments = %s", given_arguments)
        self.arguments = CommandArgumentsGetter(given_arguments)

    def run(self):
        raise NotImplementedError()


# TODO: implement
class CommandAlias(Command):
    pass


class FrontendCommand(Command):
    priority = FrontendPriority()


class BackendCommand(Command):
    priority = BackendPriority()


class SameThreadCommand(Command):
    priority = SameThreadPriority()


class Commander:
    """
    Responsible for managing commands: it's up to workers to do the commands actually.
    """
    def __init__(self, ui, docker_backend):
        self.ui = ui
        self.docker_backend = docker_backend
        self.modifier_keys_pressed = []
        logger.debug("available commands: %s", commands_mapping)

    def get_command(self, command_input, docker_object=None, buffer=None, size=None):
        """
        return command instance which is the actual command to be executed

        :param command_input: str, command name and its args: "command arg arg2=val opt"
        :param docker_object:
        :param buffer:
        :param size: tuple, so we can call urwid.keypress(size, ...)
        :return: instance of Command
        """
        logger.debug("get command for command input %r", command_input)

        if not command_input:
            # noop, don't do anything
            return

        command_input_list = command_input.split(" ")
        command_name = command_input_list[0]
        unparsed_command_args = command_input_list[1:]

        try:
            CommandClass = commands_mapping[command_name]
        except KeyError:
            logger.info("no such command: %r", command_name)
            raise NoSuchCommand("There is no such command: %s" % command_name)
        else:
            cmd = CommandClass(ui=self.ui, docker_backend=self.docker_backend,
                               docker_object=docker_object, buffer=buffer, size=size)
            cmd.process_args(unparsed_command_args)
            return cmd

    def get_command_input_by_key(self, key):
        logger.debug("get command input for key %r", key)

        modifier_keys = ["g"]  # FIXME: we should be able to figure this out from existing keybinds

        inp = "".join(self.modifier_keys_pressed) + key

        try:
            command_input = key_mapping[inp]
        except KeyError:
            if key in modifier_keys:
                # TODO: inform user maybe
                self.modifier_keys_pressed.append(key)
                logger.info("modifier keys pressed: %s", self.modifier_keys_pressed)
                return
            else:
                logger.info("no such keybind: %r", inp)
                raise KeyNotMapped("No such keybind: %r." % inp)
        else:
            self.modifier_keys_pressed.clear()
            return command_input
