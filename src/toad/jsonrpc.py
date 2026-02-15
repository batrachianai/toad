from __future__ import annotations

import asyncio
import json
from asyncio import Future, get_running_loop
from dataclasses import dataclass
from functools import wraps
import inspect
from inspect import signature
from enum import IntEnum
import logging
from types import TracebackType
import weakref

import rich.repr
from typing import Callable, ParamSpec, TypeVar
from typeguard import check_type, CollectionCheckStrategy, TypeCheckError


type MethodType = Callable
type JSONValue = str | int | float | bool | None
type JSONType = dict[str, JSONType] | list[JSONType] | str | int | float | bool | None
type JSONObject = dict[str, JSONType]
type JSONList = list[JSONType]

log = logging.getLogger("jsonrpc")


def expose(name: str = "", prefix: str = ""):
    """Expose a method."""

    def expose_method[T: Callable](callable: T) -> T:
        setattr(callable, "_jsonrpc_expose", f"{prefix}{name or callable.__name__}")
        return callable

    return expose_method


class NoDefault:
    def __repr__(self) -> str:
        return "NO_DEFAULT"


NO_DEFAULT = NoDefault()


class ErrorCode(IntEnum):
    """JSONRPC error codes"""

    # https://www.jsonrpc.org/specification
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class Parameter:
    type: type
    default: JSONType | NoDefault


@dataclass
class Method:
    name: str
    callable: Callable
    parameters: dict[str, Parameter]


@rich.repr.auto
class JSONRPCError(Exception):
    """An error thrown by the JSONRPC system."""

    CODE: ErrorCode = ErrorCode.INTERNAL_ERROR
    """Default code to use (may be overridden in the constructor)."""

    def __init__(
        self, message: str, id: str | int | None = None, code: ErrorCode | None = None
    ) -> None:
        self.message = message
        self.id = id
        self.code = code if code is not None else self.CODE
        super().__init__(message)

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.message
        yield "id", self.id
        yield "code", self.code


class InvalidRequest(JSONRPCError):
    CODE = ErrorCode.INVALID_REQUEST


class InvalidParams(JSONRPCError):
    CODE = ErrorCode.INVALID_PARAMS


class MethodNotFound(JSONRPCError):
    CODE = ErrorCode.METHOD_NOT_FOUND


class InternalError(JSONRPCError):
    CODE = ErrorCode.INTERNAL_ERROR


@rich.repr.auto
class APIError(Exception):
    def __init__(self, code: int, message: str, data: JSONType) -> None:
        self.code = code
        self.message = message
        self.data = data
        if data is None:
            super().__init__(f"{message} ({code})")
        else:
            super().__init__(f"{message} ({code}); data={data!r}")


class Server:
    def __init__(self) -> None:
        self._methods: dict[str, Method] = {}

    async def call(self, json: JSONObject | JSONList) -> JSONType:
        if isinstance(json, dict):
            # Single call
            response = await self._dispatch_object(json)
        else:
            # Batch call
            response = await self._dispatch_batch(json)
        log.debug(f"OUT {response}")
        return response

    def expose_instance(self, instance: object) -> None:
        """Add methods from the given instance."""
        for method_name in dir(instance):
            try:
                method = getattr(instance, method_name)
            except AttributeError:
                continue
            if (jsonrpc_expose := getattr(method, "_jsonrpc_expose", None)) is not None:
                self.method(jsonrpc_expose)(method)

    async def _dispatch_object(self, json: JSONObject) -> JSONType | None:
        json_id = json.get("id")
        if isinstance(json_id, (int, str)):
            request_id = json_id
        else:
            request_id = None
        try:
            return await self._dispatch_object_call(request_id, json)
        except JSONRPCError as error:
            return {
                "jsonrpc": "2.0",
                "id": error.id,
                "error": {
                    "code": int(error.code),
                    "message": error.message,
                },
            }
        except Exception as error:
            log.exception("Error dispatching JSONRPC request")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": int(ErrorCode.INTERNAL_ERROR),
                    "message": f"An error occurred handling your request: {error!r}",
                },
            }

    async def _dispatch_object_call(
        self, request_id: int | str | None, json: JSONObject
    ) -> JSONType | None:
        """Dispatch a JSONRPC call.

        Args:
            request_id: The request ID.
            json: JSON object with the remote call information.

        Returns:
            Result encoding in a JSONRPC result object, or `None` if the call is a notification
                and doesn't require a result.
        """
        if (jsonrpc := json.get("jsonrpc")) != "2.0":
            raise InvalidRequest(
                f"jsonrpc attribute should be '2.0'; found {jsonrpc!r}", id=request_id
            )
        if (method_name := json.get("method")) is None:
            raise InvalidRequest(
                "Invalid request; no value for 'method' given", id=request_id
            )

        if not isinstance(method_name, str):
            raise InvalidRequest(
                "Invalid request; 'method' should be a string type", id=request_id
            )

        if (method := self._methods.get(method_name)) is None:
            raise MethodNotFound(
                f"Method not found; {method_name!r} is not an exposed method",
                id=request_id,
            )

        no_params: JSONList = []
        params = json.get("params", no_params)

        if not isinstance(params, (list, dict)):
            raise InvalidRequest(
                "Invalid request; 'params' attribute should be a list or an object"
            )

        arguments: dict[str, JSONType | Server | NoDefault] = {
            name: parameter.default for name, parameter in method.parameters.items()
        }

        def validate(value: JSONType, parameter_type: type) -> None:
            """Validate types."""
            try:
                check_type(
                    value,
                    parameter_type,
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                )
            except TypeCheckError as error:
                raise InvalidParams(
                    f"Parameter is not the expected type ({parameter_type}); {error}",
                    id=request_id,
                )

        if isinstance(params, list):
            parameter_items = [
                (name, parameter)
                for name, parameter in method.parameters.items()
                if not issubclass(parameter.type, Server)
            ]
            for (parameter_name, parameter), value in zip(parameter_items, params):
                if issubclass(parameter.type, Server):
                    value = self
                else:
                    validate(value, parameter.type)
                arguments[parameter_name] = value
        else:
            for parameter_name, value in params.items():
                if parameter := method.parameters.get(parameter_name):
                    validate(value, parameter.type)
                    arguments[parameter_name] = value

        for name, parameter in method.parameters.items():
            if inspect.isclass(parameter.type) and issubclass(parameter.type, Server):
                arguments[name] = self

        try:
            call_result = method.callable(**arguments)
            if inspect.isawaitable(call_result):
                result = await call_result
            else:
                result = call_result
        except JSONRPCError as error:
            error.id = request_id
            raise error
        except Exception as error:
            raise
            # print("JSON error", repr(error))
            # log.debug(f"Error in exposed JSONRPC method; {error}")
            print("INTERNAL ERROR", error)
            raise InternalError(str(error), id=request_id)

        if request_id is None:
            # Notification
            return None

        response_object = {"jsonrpc": "2.0", "result": result, "id": request_id}
        return response_object

    async def _dispatch_batch(self, json: JSONList) -> list[JSONType]:
        batch_results: list[JSONType] = []
        for request in json:
            if not isinstance(request, dict):
                continue
            result = await self._dispatch_object(request)
            if result is not None:
                batch_results.append(result)
        return batch_results

    def process_callable(
        self, callable: Callable[[MethodType], MethodType]
    ) -> Callable[[MethodType], MethodType]:
        return callable

    def method[MethodT: Callable](
        self,
        name: str = "",
        *,
        prefix: str = "",
    ) -> Callable[[MethodT], MethodT]:
        """Decorator to expose a method via JSONRPC.

        Args:
            name: The name of the exposed method. Leave blank to auto-detect.
            prefix: A prefix to be applied to the name.

        Returns:
            Decorator.
        """

        def expose_method[T: Callable](callable: T) -> T:
            nonlocal name
            if not name:
                name = callable.__name__
            name = f"{prefix}{name}"

            parameters = {
                name: Parameter(
                    (
                        eval(parameter.annotation)
                        if isinstance(parameter.annotation, str)
                        else parameter.annotation
                    ),
                    (
                        NO_DEFAULT
                        if parameter.default is inspect._empty
                        else parameter.default
                    ),
                )
                for name, parameter in signature(callable).parameters.items()
            }
            self._methods[name] = Method(name, callable, parameters)
            return callable

        return expose_method


@rich.repr.auto
class MethodCall[ReturnType]:
    def __init__(
        self, method: str, id: int | None, parameters: dict[str, JSONType]
    ) -> None:
        self.method = method
        self.id = id
        self.parameters = parameters
        self.notification = False
        self.future: Future[ReturnType] = get_running_loop().create_future()

    def __rich_repr__(self) -> rich.repr.Result:
        yield "method", self.method
        yield "id", self.id, None
        yield "parameters", self.parameters
        yield "notification", self.notification, False

    @property
    def as_json_object(self) -> JSONType:
        json: JSONType
        if self.id is None:
            json = {
                "jsonrpc": "2.0",
                "method": self.method,
                "params": self.parameters,
            }
        else:
            json = {
                "jsonrpc": "2.0",
                "method": self.method,
                "params": self.parameters,
                "id": self.id,
            }
        return json

    async def wait(self, timeout: float | None = None) -> ReturnType | None:
        if self.id is None:
            return None
        async with asyncio.timeout(timeout):
            return await self.future


P = ParamSpec("P")  # Captures parameter types
T = TypeVar("T")  # Original return type


class Request:
    def __init__(self, api: API, callback: Callable[[Request], None] | None) -> None:
        self.api = api
        self._calls: list[MethodCall] = []
        self._callback = callback

    def add_call(self, call: MethodCall) -> None:
        self._calls.append(call)

    def __enter__(self) -> Request:
        self.api._requests.append(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: type[BaseException],
        exc_tb: TracebackType,
    ) -> None:
        self.api._requests.pop()
        if self._callback is not None:
            self._callback(self)

    @property
    def body(self) -> JSONType | None:
        """The un-encoded JSON.

        Returns:
            The body, or `None` if no calls present on the request.
        """
        if not self._calls:
            return None
        calls = self._calls
        if len(calls) == 1:
            method_call = calls[0]
            return method_call.as_json_object
        else:
            return [method_call.as_json_object for method_call in calls]

    @property
    def body_json(self) -> bytes:
        """Dump the body as encoded json."""
        body_json = json.dumps(self.body).encode("utf-8")
        return body_json


class API:
    def __init__(self) -> None:
        self._request_id = 0
        self._requests: list[Request] = []
        self._calls: weakref.WeakValueDictionary[int, MethodCall] = (
            weakref.WeakValueDictionary()
        )

    def request(self, callback: Callable[[Request], None] | None = None) -> Request:
        """Create a Request context manager."""
        request = Request(self, callback)
        return request

    def _process_method_response(self, response: JSONObject) -> None:
        if (id := response.get("id")) is not None and isinstance(id, int):
            if (method_call := self._calls.get(id)) is not None:
                try:
                    result = response["result"]
                except KeyError:
                    if (error := response.get("error")) is not None:
                        if isinstance(error, dict):
                            code = error.get("error", -1)
                            if not isinstance(code, int):
                                code = -1
                            message = str(error.get("message", "unknown error"))
                            data = error.get("data", None)
                            method_call.future.set_exception(
                                APIError(code, message, data)
                            )
                else:
                    method_call.future.set_result(result)

    def process_response(self, response: JSONType) -> None:
        if isinstance(response, list):
            for response_object in response:
                if isinstance(response_object, dict):
                    self._process_method_response(response_object)
        elif isinstance(response, dict):
            self._process_method_response(response)

    def method(
        self, name: str = "", *, prefix: str = "", notification: bool = False
    ) -> Callable[[Callable[P, T]], Callable[P, MethodCall[T]]]:
        """Decorator to define a method.

        Args:
            name: Name of the method, or "" to auto-detect.
            prefix: String to prefix the name.

        Returns:
            Decorator.
        """

        def decorator(func: Callable[P, T]) -> Callable[P, MethodCall[T]]:
            nonlocal name
            if not name:
                name = func.__name__
            name = f"{prefix}{name}"

            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> MethodCall[T]:
                parameters = signature(func).parameters
                call_parameters = {}
                for arg, parameter_name in zip(args, parameters):
                    call_parameters[parameter_name] = arg
                for parameter_name, arg in kwargs:
                    call_parameters[parameter_name] = arg
                if notification:
                    method_call = MethodCall(name, None, call_parameters)
                else:
                    self._request_id += 1
                    method_call = MethodCall(name, self._request_id, call_parameters)
                self._requests[-1].add_call(method_call)
                if method_call.id is not None:
                    self._calls[method_call.id] = method_call
                return method_call

            return wrapper

        return decorator

    def notification(
        self,
        name: str = "",
        *,
        prefix: str = "",
    ) -> Callable[[Callable[P, T]], Callable[P, MethodCall[T]]]:
        return self.method(name, prefix=prefix, notification=True)


if __name__ == "__main__":
    from rich import print

    server = Server()

    @server.method()
    def hello(name: str) -> str:
        return f"hello {name}"

    @server.method()
    def add(server: Server, a: int, b: int) -> int:
        print("SERVER", server)
        return a + b

    # print("!", add(1, 2))
    print(server._methods)

    # print(
    #     server.call(
    #         [
    #             {
    #                 "jsonrpc": "2.0",
    #                 "method": "hello",
    #                 "params": {"name": "Will"},
    #                 "id": "1",
    #             },
    #             {
    #                 "jsonrpc": "2.0",
    #                 "method": "add",
    #                 "params": {"a": 10, "b": 20},
    #                 "id": "2",
    #             },
    #             {"jsonrpc": "2.0", "method": "alert", "params": {"message": "Alert!"}},
    #         ]
    #     )
    # )

    async def test_proxy():
        api = API()

        @api.method()
        def add(a: int, b: int) -> int: ...

        @api.method()
        def greet(name: str) -> str: ...

        @api.notification()
        def alert(text: str) -> None: ...

        with api.request() as request:
            add(2, 4)
            greeting = greet("Will")
            alert("test")
            # add(1, "not a number")

        # greeting = await greeting.wait()
        # print(greeting)

        print(greeting)

        print(request.body)

    asyncio.run(test_proxy())
