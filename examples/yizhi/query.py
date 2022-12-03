from openapi.providers.yizhi import Client

from examples.config import config

# print(config)
client = Client(**config['yizhi'])
client.add_webhook(config['openapi_webhook'])

# result = client.request(
#     'post', '/orderList',
#     data={'page': '1', 'type': '1'}
# )
# print(result)

data = {
    'encrypt': 'MRVrmKNDi4ip65bRKLNVzlUYr+s3iI40WzY4fPxpGDlDjV93/v2UEa4KvuyPpGiOJKem7yNYwc6R80qv2zjRGiY8+xqfu5EqW1mo6VSVlFkT3He5Qmj/8TRL+F5YMewhiUOd5iCaZBLnMnfxTqAtFK5GsiHkHnvOAzs12C6WSHLHYwmgHoyRdrP5ZZhsIm3VAqnIlpBQ7UBLKCfnbkyZJoYkq4dL1R6/6onpFXhGI1qWlItJp/6dGKMoPHB7nzVq5XI0lkmNr64tK8PkgfsmF1UvRJoKpgza3zkOx2lAZ+I/OgJ36vYeMUt9HnqvQJRnuZ6YugoWhCwF10c/4ypFeLL000aNok9kh4Sllu2Dma/3hPi9/mqolCWgTTQbIetskvcnkMsMpcTRpQjkxvqaYMoS1dM3k+335UI1PO/EsrEBGLTjreg/Vu2N3/I37Vgif7Zs+lTVMNBGXJFK1KirVnjnbcU6RngQ3qsyBpRhgGkuyvVPMkuN7g5Q6YF+qneg',
    'timestamp': '1670063928',
    'nonce': '0g2EGsVR',
    'signature': '85f46e73437a94f7607e8ed08ce0f042ed3cb403'
}

result = client.decrypt(**data)
print(result)
