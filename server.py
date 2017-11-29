import asyncio

from aiohttp import web, ClientSession
import motor.motor_asyncio as motor
from serializers import AddProxySchema, DeleteProxySchema

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/62.0.3202.94 Safari/537.36'


class ProxyServer:

    def __init__(self, host, port, mongo_url, mongo_db, mongo_collection, test_url):

        self.host = host
        self.port = port

        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        except ImportError:
            pass

        self.loop = asyncio.get_event_loop()
        self.mongo_client = motor.AsyncIOMotorClient(mongo_url)
        self.database = self.mongo_client[mongo_db]
        self.mongo_collection = self.database[mongo_collection]
        self.proxy_schema = AddProxySchema()
        self.delete_schema = DeleteProxySchema()

        self.test_url = test_url
        self.session = ClientSession()

    async def get_working_proxies(self, request):
        proxies = []
        try:
            cursor = self.mongo_collection.find({'working': True})
            data = await cursor.to_list(None)
            for proxy in data:
                ip_add = proxy.get('proxy')
                if ip_add:
                    proxies.append(ip_add)
            return web.json_response({'proxies': proxies}, status=200)
        except Exception as e:
            return web.json_response({'errors': e}, status=500)

    async def add_proxy(self, request):
        data = await request.json()
        input_data, errors = self.proxy_schema.load(data)
        if errors:
            return web.json_response(errors, status=400)
        try:
            await self.mongo_collection.insert_one(input_data)
        except Exception as e:
            return web.json_response({'errors': e}, status=500)
        return web.json_response({'Status': 'Proxy Inserted'})

    async def delete_proxy(self, request):
        data = await request.json()
        input_data, errors = self.delete_schema.load(data)
        if errors:
            return web.json_response(errors, status=400)
        try:
            proxy = input_data.get('proxy')
            await self.mongo_collection.remove({'proxy': proxy})
        except Exception as e:
            return web.json_response({'errors': e}, status=500)
        return web.json_response({'Status': 'Proxy Deleted'}, status=200)

    async def test_request(self, proxy):
        try:
            async with self.session.get(self.test_url, timeout=10, proxy='http://{}'.format(proxy),
                                           headers={'User-Agent': USER_AGENT}) as response:
                await response.read()
                if response.status != 200:
                    return False
                return True
        except Exception:
            return False

    async def status_check(self):
        while True:
            try:
                cursor = self.mongo_collection.find({})
                proxies = await cursor.to_list(None)
                for proxy in proxies:
                    ip_add = proxy.get('proxy')
                    print(ip_add)
                    if ip_add:
                        status = await self.test_request(ip_add)
                        self.mongo_collection.find_one_and_update({'proxy': ip_add}, {'$set': {'working': status}})
            except Exception:
                pass
            await asyncio.sleep(600)

    async def start_background_tasks(self, app):
        app['proxy_check'] = app.loop.create_task(self.status_check())

    async def create_app(self, loop):
        app = web.Application()
        app.router.add_get('/working-proxies', self.get_working_proxies)
        app.router.add_post('/add-proxy', self.add_proxy)
        app.router.add_post('/delete-proxy', self.delete_proxy)
        app.on_startup.append(self.start_background_tasks)
        return app

    def run_server(self):
        loop = self.loop
        app = loop.run_until_complete(self.create_app(loop))
        web.run_app(app, host=self.host, port=self.port)

if __name__ == '__main__':
    s = ProxyServer('127.0.0.1', 8080, 'mongodb://localhost:27017', 'proxydb', 'proxies', 'http://edmundmartin.com')
    s.run_server()