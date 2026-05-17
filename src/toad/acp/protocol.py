from typing_extensions import Any, TypedDict, Required, Literal


class SchemaDict(TypedDict, total=False, extra_items=Any):
    pass


# ---------------------------------------------------------------------------------------
# Types


class FileSystemCapability(SchemaDict, total=False, extra_items=Any):
    readTextFile: bool
    writeTextFile: bool


# https://agentclientprotocol.com/protocol/schema#clientcapabilities
class ClientCapabilities(SchemaDict, total=False, extra_items=Any):
    fs: FileSystemCapability
    terminal: bool


# https://agentclientprotocol.com/protocol/schema#implementation
class Implementation(SchemaDict, total=False, extra_items=Any):
    name: Required[str]
    title: str | None
    version: Required[str]


# https://agentclientprotocol.com/protocol/schema#promptcapabilities
class PromptCapabilities(SchemaDict, total=False, extra_items=Any):
    audio: bool
    embeddedContent: bool
    image: bool


# https://agentclientprotocol.com/protocol/schema#agentcapabilities
class AgentCapabilities(SchemaDict, total=False, extra_items=Any):
    loadSession: bool
    promptCapabilities: PromptCapabilities


class AuthMethod(SchemaDict, total=False, extra_items=Any):
    description: str | None
    id: Required[str]
    name: Required[str]


# https://agentclientprotocol.com/protocol/schema#envvariable
class EnvVariable(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    name: Required[str]
    value: Required[str]


# https://agentclientprotocol.com/protocol/schema#terminalexitstatus
class TerminalExitStatus(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    exitCode: int | None
    signal: str | None


# https://agentclientprotocol.com/protocol/schema#mcpserver
class McpServer(SchemaDict, total=False, extra_items=Any):
    args: list[str]
    command: str
    env: list[EnvVariable]
    name: str


# https://modelcontextprotocol.io/specification/2025-06-18/server/resources#annotations
class Annotations(SchemaDict, total=False, extra_items=Any):
    audience: list[str]
    priority: float
    lastModified: str


class TextContent(SchemaDict, total=False, extra_items=Any):
    type: Required[str]
    text: Required[str]
    annotations: Annotations


class ImageContent(SchemaDict, total=False, extra_items=Any):
    type: Required[str]
    data: Required[str]
    mimeType: Required[str]
    url: str
    annotations: Annotations


class AudioContent(SchemaDict, total=False, extra_items=Any):
    type: Required[str]
    data: Required[str]
    mimeType: Required[str]
    Annotations: Annotations


class EmbeddedResourceText(SchemaDict, total=False, extra_items=Any):
    uri: Required[str]
    text: Required[str]
    mimeType: str


class EmbeddedResourceBlob(SchemaDict, total=False, extra_items=Any):
    uri: Required[str]
    blob: Required[str]
    mimeType: str


# https://agentclientprotocol.com/protocol/content#embedded-resource
class EmbeddedResourceContent(SchemaDict, total=False, extra_items=Any):
    type: Required[str]
    resource: EmbeddedResourceText | EmbeddedResourceBlob


class ResourceLinkContent(SchemaDict, total=False, extra_items=Any):
    annotations: Annotations | None
    description: str | None
    mimeType: str | None
    name: Required[str]
    size: int | None
    title: str | None
    type: Required[str]
    uri: Required[str]


# https://agentclientprotocol.com/protocol/schema#contentblock
type ContentBlock = (
    TextContent
    | ImageContent
    | AudioContent
    | EmbeddedResourceContent
    | ResourceLinkContent
)


# https://agentclientprotocol.com/protocol/schema#param-user-message-chunk
class UserMessageChunk(SchemaDict, total=False, extra_items=Any):
    content: Required[ContentBlock]
    sessionUpdate: Required[Literal["user_message_chunk"]]


class AgentMessageChunk(SchemaDict, total=False, extra_items=Any):
    content: Required[ContentBlock]
    sessionUpdate: Required[Literal["agent_message_chunk"]]


class AgentThoughtChunk(SchemaDict, total=False, extra_items=Any):
    content: Required[ContentBlock]
    sessionUpdate: Required[Literal["agent_thought_chunk"]]


class ToolCallContentContent(SchemaDict, total=False, extra_items=Any):
    content: Required[ContentBlock]
    type: Required[Literal["content"]]


# https://agentclientprotocol.com/protocol/schema#param-diff
class ToolCallContentDiff(SchemaDict, total=False, extra_items=Any):
    newText: Required[str]
    oldText: str | None
    path: Required[str]
    type: Required[Literal["diff"]]


class ToolCallContentTerminal(SchemaDict, total=False, extra_items=Any):
    terminalId: Required[str]
    type: Required[Literal["terminal"]]


# https://agentclientprotocol.com/protocol/schema#toolcallcontent
type ToolCallContent = (
    ToolCallContentContent | ToolCallContentDiff | ToolCallContentTerminal
)

# https://agentclientprotocol.com/protocol/schema#toolkind
type ToolKind = Literal[
    "read",
    "edit",
    "delete",
    "move",
    "search",
    "execute",
    "think",
    "fetch",
    "switch_mode",
    "other",
]

type ToolCallStatus = Literal["pending", "in_progress", "completed", "failed"]


class ToolCallLocation(SchemaDict, total=False, extra_items=Any):
    line: int | None
    path: Required[str]


type ToolCallId = str


# https://agentclientprotocol.com/protocol/schema#toolcall
class ToolCall(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    content: list[ToolCallContent]
    kind: ToolKind
    locations: list[ToolCallLocation]
    rawInput: dict
    rawOutput: dict
    sessionUpdate: Required[Literal["tool_call"]]
    status: ToolCallStatus
    title: Required[str]
    toolCallId: Required[ToolCallId]


# https://agentclientprotocol.com/protocol/schema#toolcallupdate
class ToolCallUpdate(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    content: list[ToolCallContent] | None
    kind: ToolKind | None
    locations: list | None
    rawInput: dict
    rawOutput: dict
    sessionUpdate: Required[Literal["tool_call_update"]]
    status: ToolCallStatus | None
    title: str | None
    toolCallId: Required[ToolCallId]


# https://agentclientprotocol.com/protocol/schema#param-tool-call
# Use in the session/request_permission call (not the same as ToolCallUpdate)
class ToolCallUpdatePermissionRequest(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    content: list[ToolCallContent] | None
    kind: ToolKind | None
    locations: list | None
    rawInput: dict
    rawOutput: dict
    status: ToolCallStatus | None
    title: str | None
    toolCallId: Required[ToolCallId]


class PlanEntry(SchemaDict, total=False, extra_items=Any):
    content: Required[str]
    priority: Literal["high", "medium", "low"]
    status: Literal["pending", "in_progress", "completed"]


type SessionModeId = str


# https://agentclientprotocol.com/protocol/schema#sessionmode
class SessionMode(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    description: str | None
    id: Required[SessionModeId]
    name: Required[str]


class SessionModeState(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    availableModes: Required[list[SessionMode]]
    currentModeId: Required[SessionModeId]


type ModelId = str


# https://agentclientprotocol.com/protocol/schema#modelinfo
class ModelInfo(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    description: str | None
    modelId: Required[ModelId]
    name: Required[str]


# https://agentclientprotocol.com/protocol/schema#sessionmodelstate
class SessionModelState(SchemaDict, total=False, extra_items=Any):
    _meta: dict
    availableModels: Required[list[ModelInfo]]
    currentModelId: Required[ModelId]


# https://agentclientprotocol.com/protocol/schema#param-plan
class Plan(SchemaDict, total=False, extra_items=Any):
    entries: Required[list[PlanEntry]]
    sessionUpdate: Required[Literal["plan"]]


class AvailableCommandInput(SchemaDict, total=False, extra_items=Any):
    hint: Required[str]


class AvailableCommand(SchemaDict, total=False, extra_items=Any):
    description: Required[str]
    input: AvailableCommandInput | None
    name: Required[str]


class AvailableCommandsUpdate(SchemaDict, total=False, extra_items=Any):
    availableCommands: Required[list[AvailableCommand]]
    sessionUpdate: Required[Literal["available_commands_update"]]


class CurrentModeUpdate(SchemaDict, total=False, extra_items=Any):
    currentModeId: Required[str]
    sessionUpdate: Required[Literal["current_mode_update"]]


type SessionUpdate = (
    UserMessageChunk
    | AgentMessageChunk
    | AgentThoughtChunk
    | ToolCall
    | ToolCallUpdate
    | Plan
    | AvailableCommandsUpdate
    | CurrentModeUpdate
)


class SessionNotification(TypedDict, total=False, extra_items=Any):
    sessionId: str
    update: SessionUpdate


type PermissionOptionKind = Literal[
    "allow_once", "allow_always", "reject_once", "reject_always"
]
type PermissionOptionId = str


class PermissionOption(TypedDict, total=False, extra_items=Any):
    _meta: dict
    kind: Required[PermissionOptionKind]
    name: Required[str]
    optionId: Required[PermissionOptionId]


class OutcomeCancelled(TypedDict, total=False, extra_items=Any):
    outcome: Literal["cancelled"]


class OutcomeSelected(TypedDict, total=False, extra_items=Any):
    optionId: Required[PermissionOptionId]
    outcome: Literal["selected"]


# https://agentclientprotocol.com/protocol/schema#requestpermissionoutcome
type RequestPermissionOutcome = OutcomeSelected | OutcomeCancelled

# ---------------------------------------------------------------------------------------
# RPC responses


class InitializeResponse(SchemaDict, total=False, extra_items=Any):
    agentCapabilities: AgentCapabilities
    authMethods: list[AuthMethod]
    protocolVersion: Required[int]


# https://agentclientprotocol.com/protocol/schema#newsessionresponse
class NewSessionResponse(SchemaDict, total=False, extra_items=Any):
    _meta: object
    sessionId: Required[str]
    # Unstable from here
    models: SessionModelState | None
    modes: SessionModeState | None


# https://agentclientprotocol.com/protocol/schema#loadsessionresponse
class LoadSessionResponse(SchemaDict, total=False, extra_items=Any):
    _meta: object
    modes: SessionModeState | None


class SessionPromptResponse(SchemaDict, total=False, extra_items=Any):
    stopReason: Required[
        Literal[
            "end_turn",
            "max_tokens",
            "max_turn_requests",
            "refusal",
            "cancelled",
        ]
    ]


# https://agentclientprotocol.com/protocol/schema#requestpermissionresponse
class RequestPermissionResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict
    outcome: Required[RequestPermissionOutcome]


# https://agentclientprotocol.com/protocol/schema#createterminalresponse
class CreateTerminalResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict
    terminalId: Required[str]


# https://agentclientprotocol.com/protocol/schema#killterminalcommandresponse
class KillTerminalCommandResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict


# https://agentclientprotocol.com/protocol/schema#terminaloutputresponse
class TerminalOutputResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict
    exitStatus: TerminalExitStatus | None
    output: Required[str]
    truncated: Required[bool]


# https://agentclientprotocol.com/protocol/schema#releaseterminalresponse
class ReleaseTerminalResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict


# https://agentclientprotocol.com/protocol/schema#waitforterminalexitresponse
class WaitForTerminalExitResponse(TypedDict, total=False, extra_items=Any):
    _meta: dict
    exitCode: int | None
    signal: str | None


# https://agentclientprotocol.com/protocol/schema#setsessionmoderesponse
class SetSessionModeResponse(TypedDict, total=False, extra_items=Any):
    meta: dict


# ---------------------------------------------------------------------------------------
