#!/usr/bin/env python
# encoding: utf-8
import json
import httpx

from .api_response import ApiResponseAsync as ApiResponse
from .api_exception import ApiException
from ..core import urlencode, iterator


class AsyncClient:
    def __init__(self):
        self._async_client = httpx.AsyncClient()

    async def send(self, request: httpx.Request):
        response = None

        if not isinstance(request, httpx.Request):
            assert False, f"SEND CALLED ON {type(request)}"

        try:
            response = await self.load_response(request)
            if response.ok():
                return response
            else:
                print(f"BAD RESPONSE: {response}")
                response.response.raise_for_status()
        except Exception as e:
            if response is None:
                response = ApiResponse(request)
            raise ApiException(response, e)

    async def load_response(self, request):
        # TODO Persist between requests?
        session = None

        try:
            response = await self._async_client.send(request)
            return ApiResponse(request, response)

        except Exception:
            if session:
                session.close()
            raise

    def create_request(self, method='', url='', query_params=None, body=None, headers=None) -> httpx.Request:
        """
        :param method:
        :param url:
        :param query_params:
        :param body:
        :param headers:
        :return:requests.Request
        """
            
        content_type = None
        
        if headers is None:
            headers = {}

        it = iterator(headers)

        for key, value in it:
            if key.lower().find('content-type') >= 0:
                content_type = value
            if key.lower().find('accept') >= 0:
                headers['Accept'] = value

        if content_type is None:
            content_type = 'application/json'
            headers['Content-Type'] = content_type

            
        if content_type.lower().find('application/json') >= 0:
            body = json.dumps(body) if body else None
        elif content_type.lower().find('application/x-www-form-urlencoded') >= 0:
            body = urlencode(body) if body else None

        return self._async_client.build_request(
            method,
            url,
            params=query_params,
            headers=headers,
            data=body
        )
