import logging

import urwid

from sen.exceptions import NotifyError
from sen.tui.buffer import HelpBuffer, TreeBuffer
from sen.tui.commands.base import register_command, SameThreadCommand

logger = logging.getLogger(__name__)


@register_command
class QuitCommand(SameThreadCommand):
    name = "quit"

    def run(self):
        self.ui.worker.shutdown(wait=False)
        self.ui.ui_worker.shutdown(wait=False)
        raise urwid.ExitMainLoop()


@register_command
class KillBufferCommand(SameThreadCommand):
    name = "kill-buffer"  # this could be named better

    def __init__(self, close_if_no_buffer=True, **kwargs):
        super().__init__(**kwargs)
        self.close_if_no_buffer = close_if_no_buffer

    def run(self):
        buffers_left = self.ui.remove_current_buffer(close_if_no_buffer=self.close_if_no_buffer)
        if buffers_left is None:
            self.ui.notify_message("Last buffer will not be removed.")
        elif buffers_left == 0:
            self.ui.run_command(QuitCommand.name)


@register_command
class RemoveBufferCommand(KillBufferCommand):
    name = "remove-buffer"

    def __init__(self, **kwargs):
        super().__init__(close_if_no_buffer=False, **kwargs)


@register_command
class SelectBufferCommand(SameThreadCommand):
    name = "select-buffer"

    def __init__(self, index=None, **kwargs):
        super().__init__(**kwargs)
        if index is None:
            self.ui.notify_message("Please specify index of a buffer to display.")
        self.index = index

    def run(self):
        self.ui.pick_and_display_buffer(self.index)


@register_command
class SelectNextBufferCommand(SelectBufferCommand):
    name = "select-next-buffer"

    def __init__(self, **kwargs):
        super().__init__(index=self.ui.current_buffer_index + 1, **kwargs)


@register_command
class SelectPreviousBufferCommand(SelectBufferCommand):
    name = "select-previous-buffer"

    def __init__(self, **kwargs):
        super().__init__(index=self.ui.current_buffer_index - 1, **kwargs)


@register_command
class DisplayBufferCommand(SameThreadCommand):
    name = "display-buffer"

    def __init__(self, buffer=None, **kwargs):
        super().__init__(**kwargs)
        if buffer is None:
            raise NotifyError("Please specify buffer you would like to display.")
        self.buffer = buffer

    def run(self):
        self.ui.add_and_display_buffer(self.buffer)


@register_command
class DisplayHelpCommand(DisplayBufferCommand):
    name = "help"

    def __init__(self, **kwargs):
        super().__init__(buffer=HelpBuffer(), **kwargs)


@register_command
class DisplayLayersCommand(DisplayBufferCommand):
    name = "layers"

    def __init__(self, **kwargs):
        super().__init__(buffer=TreeBuffer(self.docker_backend, self.ui), **kwargs)


"""
@log_traceback
def search(ui, oldfooter, edit_widget, text_input):
    logger.debug("%r %r", edit_widget, text_input)
    if text_input.endswith("\n"):
        # TODO: implement incsearch
        #   - match needs to be highlighted somehow, not with focus though
        ui.mainframe.prompt_bar = None
        ui.mainframe.set_footer(oldfooter)
        try:
            ui.current_buffer.find_next(text_input[:-1])
        except NotifyError as ex:
            logger.error(repr(ex))
            ui.notify_message(str(ex), level="error")
        ui.mainframe.set_focus("body")
        ui.reload_footer()


@log_traceback
def filter(ui, oldfooter, edit_widget, text_input):
    logger.debug("%r %r", edit_widget, text_input)
    if text_input.endswith("\n"):
        ui.mainframe.prompt_bar = None
        ui.mainframe.set_footer(oldfooter)
        try:
            ui.current_buffer.filter(text_input[:-1])
        except NotifyError as ex:
            logger.error(repr(ex))
            ui.notify_message(str(ex), level="error")
        ui.mainframe.set_focus("body")
        ui.reload_footer()

"""
