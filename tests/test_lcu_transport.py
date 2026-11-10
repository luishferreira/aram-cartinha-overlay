import copy
import io
import json
import unittest
from urllib.error import HTTPError

from tools.items.lcu import Connection,Lcu,LcuError


class TransportTests(unittest.TestCase):
    def client(self):
        return Lcu(Connection(1234,'secret-session-token'))

    def test_compact_collection_fits_limit_without_losing_other_apps_data(self):
        body = {'accountId':456,'itemSets':[{'uid':'foreign','title':'ação de outro app '*300,
                                          'extra':{'keep':True},'blocks':[]}]}
        saved = copy.deepcopy(body)
        old_size = len(json.dumps(body).encode())
        client = self.client()
        class LimitedServer:
            def open(self,request,timeout=None):
                self.received = request.data
                if len(request.data)>=old_size:
                    raise HTTPError(request.full_url,413,'too large',{},None)
                return io.BytesIO(b'{}')
        server = client.opener = LimitedServer()
        client.put_collection(123456789,body)
        self.assertEqual(json.loads(server.received),saved)
        self.assertEqual(body,saved)
        self.assertLess(len(server.received),old_size)
        self.assertIn('ação'.encode('utf8'),server.received)

    def test_413_diagnostic_has_size_and_endpoint_without_account_or_credentials(self):
        client = self.client()
        class RejectingServer:
            def open(self,request,timeout=None):
                self.data = request.data
                raise HTTPError(request.full_url,413,'too large',{},None)
        server = client.opener = RejectingServer()
        with self.assertRaises(LcuError) as error:
            client.put_collection(123456789,{'accountId':456,'itemSets':[{'uid':'private-title'}]})
        value = error.exception
        self.assertEqual(value.status,413)
        self.assertEqual(value.method,'PUT')
        self.assertEqual(value.path,'/lol-item-sets/v1/item-sets/{summonerId}/sets')
        self.assertEqual(value.request_bytes,len(server.data))
        self.assertEqual(value.item_sets,1)
        for secret in ('123456789','456','secret-session-token','private-title'):
            self.assertNotIn(secret,str(value))
