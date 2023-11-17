import json
import httpx


class MultipartBuilder:
    def __init__(self, platform):
        self._body = None
        self._contents = []
        self._boundary = ''
        self._multipart_mixed = False
        self._platform = platform

    def set_multipart_mixed(self, multipart_mixed):
        print("This is likely broken with async support")
        self._multipart_mixed = multipart_mixed
        return self

    def set_body(self, body):
        self._body = body
        return self

    def body(self):
        return self._body

    def contents(self):
        return self._contents

    def add(self, attachment, name='attachment'):
        """
        Possible attachment formats:

        1. Downloaded: ('filename.ext', urllib.urlopen('https://...').read(), 'image/png')
        2. Local file: ('report.xls', open('report.xls', 'rb'), 'application/vnd.ms-excel', {'Expires': '0'})
        3. Direct local file w/o meta: open('report.xls', 'rb')
        4. Plain text: ('report.csv', 'some,data,to,send')

        :param attachment:
        :param name='attachment':
        :return:
        """
        self._contents.append((name, attachment))
        return self

    def request(self, url, method='POST'):
        files = [('json', ('request.json', json.dumps(self._body), 'application/json'))] + self._contents

        client = httpx.AsyncClient()
        request = client.build_request(method, url, files=files)
        
        if self._multipart_mixed: # Ref: https://github.com/requests/requests/issues/1736#issuecomment-28470217
            request.headers['Content-Type'] = request.headers['Content-Type'].replace('multipart/form-data;', 'multipart/mixed;')
        return request
