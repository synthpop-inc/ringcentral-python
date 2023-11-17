from .platform import Platform, PlatformAsync
from .websocket import WebSocketClient
from .deprecated_pubnub_subscription import Subscription
from .http import AsyncClient, Client, MultipartBuilder, MultipartBuilderAsync
import warnings


class SDK:
    def __init__(self, key, secret, server, name='', version='', redirect_uri=None, known_prefixes=None):
        self._client = Client()
        self._platform = Platform(self._client, key, secret, server, name, version, redirect_uri, known_prefixes)

    def platform(self):
        return self._platform

    def create_subscription(self):
        warnings.warn("PubNub support is deprecated. Please migrate your application to WebSockets.")
        return Subscription(self._platform)
    
    def create_web_socket_client(self):
        return WebSocketClient(self._platform)

    def create_multipart_builder(self):
        return MultipartBuilder(self._platform)


class AsyncSDK:
    """
    The async version of the SDK supports the same platform API as SDK. Subscriptions are deprecated
    and hence not supported and websockets already provide an async notification API.
    """

    def __init__(self, key, secret, server, name='', version='', redirect_uri=None, known_prefixes=None):
        self._client = AsyncClient()
        self._platform = PlatformAsync(self._client, key, secret, server, name, version, redirect_uri, known_prefixes)

    def platform(self):
        return self._platform

    def create_multipart_builder(self):
        return MultipartBuilderAsync(self._platform)
