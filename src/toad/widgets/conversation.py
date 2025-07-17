from textual import on
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual.widget import Widget

from textual.reactive import var


from toad import messages
from toad.widgets.prompt import Prompt
from toad.widgets.throbber import Throbber
from toad.widgets.welcome import Welcome
from toad.widgets.user_input import UserInput
from toad.widgets.agent_response import AgentResponse


class Conversation(containers.VerticalScroll):
    busy_count = var(0)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one("#contents", containers.VerticalScroll)

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        yield containers.VerticalScroll(id="contents")
        yield Prompt()

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        await self.post(UserInput(event.body))
        agent_response = AgentResponse()
        await self.post(agent_response)
        agent_response.send_prompt(event.body)

    def watch_busy(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    async def on_mount(self) -> None:
        self.contents.anchor()
        await self.post(Welcome())

    async def post(self, widget: Widget) -> None:
        await self.contents.mount(widget)
        self.contents.anchor()
