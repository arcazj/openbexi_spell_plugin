"""Bounded loopback server for the original schema; no public operational listener."""
# SPDX-License-Identifier: GPL-3.0-or-later
from concurrent.futures import ThreadPoolExecutor
import grpc
from google.protobuf import message_factory
from .stubs import SPELLDriver_pb2 as p
from .operational_journal import CapacityExceeded


class Server:
    def __init__(self, dispatch):
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='spell-driver-rpc')
        self.server = grpc.server(self.pool, maximum_concurrent_rpcs=4, options=[
            ('grpc.max_receive_message_length',65536), ('grpc.max_send_message_length',65536)])
        for service in p.DESCRIPTOR.services_by_name.values():
            methods = {}
            for method in service.methods:
                if method.server_streaming or method.client_streaming:
                    continue  # Original unused EV registration explicitly remains UNIMPLEMENTED.
                path = '/' + service.full_name + '/' + method.name
                def call(request, context, path=path):
                    try:
                        return dispatch(path, request.SerializeToString(deterministic=True))
                    except PermissionError:
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, 'Driver authority rejected')
                    except CapacityExceeded:
                        context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, 'Driver journal capacity reached')
                    except NotImplementedError:
                        context.abort(grpc.StatusCode.UNIMPLEMENTED, 'Driver capability not qualified')
                    except (ValueError, TypeError):
                        context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Driver request rejected')
                    except TimeoutError:
                        context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, 'Driver deadline expired')
                    except Exception:
                        context.abort(grpc.StatusCode.FAILED_PRECONDITION, 'Driver outcome requires reconciliation')
                methods[method.name] = grpc.unary_unary_rpc_method_handler(call,
                    request_deserializer=message_factory.GetMessageClass(method.input_type).FromString,
                    response_serializer=lambda raw:raw)
            self.server.add_generic_rpc_handlers([grpc.method_handlers_generic_handler(service.full_name,methods)])
        self.port = self.server.add_insecure_port('127.0.0.1:0')
        if not self.port:
            self.pool.shutdown(wait=True)
            raise RuntimeError('Could not bind private driver RPC server')
        self.server.start()

    def close(self):
        self.server.stop(0).wait(timeout=5)
        self.pool.shutdown(wait=True, cancel_futures=True)
