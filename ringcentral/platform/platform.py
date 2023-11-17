import sys
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from observable import Observable
from functools import reduce
from .auth import Auth
from .events import Events
from ..core import base64encode
import warnings
import httpx

ACCOUNT_ID = '~'
ACCOUNT_PREFIX = '/account/'
URL_PREFIX = '/restapi'
TOKEN_ENDPOINT = '/restapi/oauth/token'
REVOKE_ENDPOINT = '/restapi/oauth/revoke'
AUTHORIZE_ENDPOINT = '/restapi/oauth/authorize'
API_VERSION = 'v1.0'
ACCESS_TOKEN_TTL = 3600  # 60 minutes
REFRESH_TOKEN_TTL = 604800  # 1 week
KNOWN_PREFIXES = [
    URL_PREFIX,
    '/rcvideo',
    '/video',
    '/webinar',
    '/analytics',
    '/ai',
    '/team-messaging',
    '/scim'
]


class Platform(Observable):
    def __init__(self, client, key='', secret='', server='', name='', version='', redirect_uri='',
                 known_prefixes=None):

        Observable.__init__(self)
        if(server == None):
            raise Exception("SDK init error: RINGCENTRAL_SERVER_URL value not found.")
        if(key == None):
            raise Exception("SDK init error: RINGCENTRAL_CLIENT_ID value not found.")
        if(secret == None):
            raise Exception("SDK init error: RINGCENTRAL_CLIENT_SECRET value not found.")

        self._server = server
        self._key = key
        self._name = name if name else 'Unnamed'
        self._version = version if version else '0.0.0'
        self._redirect_uri = redirect_uri
        self._secret = secret
        self._client = client
        self._auth = Auth()
        self._account = ACCOUNT_ID
        self._known_prefixes = known_prefixes if known_prefixes else KNOWN_PREFIXES
        self._userAgent = ((self._name + ('/' + self._version if self._version else '') + ' ') if self._name else '') + \
                          sys.platform + '/VERSION' + ' ' + \
                          'PYTHON/VERSION ' + \
                          'RCPYTHONSDK/VERSION'

    def auth(self):
        return self._auth

    def create_url(self, url, add_server=False, add_method=None, add_token=False):
        built_url = ''
        has_http = url.startswith('http://') or url.startswith('https://')

        if add_server and not has_http:
            built_url += self._server

        if not reduce(lambda res, prefix: res if res else url.find(prefix) == 0, self._known_prefixes, False) and not has_http:
            built_url += URL_PREFIX + '/' + API_VERSION

        if url.find(ACCOUNT_PREFIX) >= 0:
            built_url = built_url.replace(ACCOUNT_PREFIX + ACCOUNT_ID, ACCOUNT_PREFIX + self._account)

        built_url += url

        if add_method:
            built_url += ('&' if built_url.find('?') >= 0 else '?') + '_method=' + add_method

        if add_token:
            built_url += ('&' if built_url.find('?') >= 0 else '?') + 'access_token=' + self._auth.access_token()

        return built_url

    def logged_in(self):
        try:
            return self._auth.access_token_valid() or self.refresh()
        except:
            return False

    def login_url(self, redirect_uri, state='', challenge='', challenge_method='S256'):
        built_url = self.create_url( AUTHORIZE_ENDPOINT, add_server=True )
        built_url += '?response_type=code&client_id=' + self._key + '&redirect_uri=' + urllib.parse.quote(redirect_uri)
        if state:
            built_url += '&state=' + urllib.parse.quote(state)
        if challenge:
            built_url += '&code_challenge=' + urllib.parse.quote(challenge) + '&code_challenge_method=' + challenge_method
        return built_url
        
    async def login(self, username='', extension='', password='', code='', redirect_uri='', jwt='', verifier=''):
        try:
            if not code and not username and not password and not jwt:
                raise Exception('Either code, or username with password, or jwt has to be provided')
            if username and password:
                warnings.warn("username-password login will soon be deprecated. Please use jwt or OAuth instead.")
            if not code and not jwt:
                body = {
                    'grant_type': 'password',
                    'username': username,
                    'password': password,
                    'access_token_ttl': ACCESS_TOKEN_TTL,
                    'refresh_token_ttl': REFRESH_TOKEN_TTL
                }
                if extension:
                    body['extension'] = extension
            elif jwt:
                body = {
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': jwt
                }
            else:
                print("Warning: Redirect URI handling is likely broken w. async code.")
                body = {
                    'grant_type': 'authorization_code',
                    'redirect_uri': redirect_uri if redirect_uri else self._redirect_uri,
                    'code': code
                }
                if verifier:
                    body['code_verifier'] = verifier

            built_url = self.create_url( TOKEN_ENDPOINT, add_server=True )
            response = await self._request_token( built_url, body=body)
            self._auth.set_data(response.json_dict())
            self.trigger(Events.loginSuccess, response)
            return response
        except Exception as e:
            self.trigger(Events.loginError, e)
            raise e

    async def refresh(self):
        try:
            if not self._auth.refresh_token_valid():
                raise Exception('Refresh token has expired')
            response = await self._request_token(TOKEN_ENDPOINT, body={
                'grant_type': 'refresh_token',
                'refresh_token': self._auth.refresh_token(),
                'access_token_ttl': ACCESS_TOKEN_TTL,
                'refresh_token_ttl': REFRESH_TOKEN_TTL
            })
            self._auth.set_data(response.json_dict())
            self.trigger(Events.refreshSuccess, response)
            return response
        except Exception as e:
            self.trigger(Events.refreshError, e)
            raise e

    async def logout(self):
        try:
            response = await self._request_token(REVOKE_ENDPOINT, body={
                'token': self._auth.access_token()
            })
            self._auth.reset()
            self.trigger(Events.logoutSuccess, response)
            return response
        except Exception as e:
            self.trigger(Events.logoutError, e)
            raise e

    async def inflate_request(self, request, skip_auth_check=False):
        if not skip_auth_check:
            await self._ensure_authentication()
            request.headers['Authorization'] = self._auth_header()

        request.headers['User-Agent'] = self._userAgent
        request.headers['X-User-Agent'] = self._userAgent
        request.url = httpx.URL(self.create_url(str(request.url), add_server=True))
        request.headers["host" ] = request.url.host
        return request

    async def send_request(self, request, skip_auth_check=False):
        return await self._client.send(await self.inflate_request(request, skip_auth_check=skip_auth_check))

    async def get(self, url, query_params=None, headers=None, skip_auth_check=False):
        request = self._client.create_request('GET', url, query_params=query_params, headers=headers)
        return await self.send_request(request, skip_auth_check=skip_auth_check)

    async def post(self, url, body=None, query_params=None, headers=None, skip_auth_check=False):
        request = self._client.create_request('POST', url, query_params=query_params, headers=headers, body=body)
        return await self.send_request(request, skip_auth_check=skip_auth_check)

    async def put(self, url, body=None, query_params=None, headers=None, skip_auth_check=False):
        request = self._client.create_request('PUT', url, query_params=query_params, headers=headers, body=body)
        return await self.send_request(request, skip_auth_check=skip_auth_check)

    async def patch(self, url, body=None, query_params=None, headers=None, skip_auth_check=False):
        request = self._client.create_request('PATCH', url, query_params=query_params, headers=headers, body=body)
        return await self.send_request(request, skip_auth_check=skip_auth_check)

    async def delete(self, url, query_params=None, headers=None, skip_auth_check=False):
        request = self._client.create_request('DELETE', url, query_params=query_params, headers=headers)
        return await self.send_request(request, skip_auth_check=skip_auth_check)

    async def _request_token(self, path='', body=None):
        headers = {
            'Authorization': 'Basic ' + self._api_key(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        request = self._client.create_request('POST', path, body=body, headers=headers)
        return await self.send_request(request, skip_auth_check=True)

    def _api_key(self):
        return base64encode(self._key + ':' + self._secret)

    def _auth_header(self):
        return self._auth.token_type() + ' ' + self._auth.access_token()

    async def _ensure_authentication(self):
        if not self._auth.access_token_valid():
            await self.refresh()
