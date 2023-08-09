from typing import Dict
from openapi.providers.wechat.open import Client, Result

from examples.config import config


class OrderDetailResult(Result):
    order: Dict


d = {
    'ToUserName': 'gh_52dd8ab5ef3c',
    'Encrypt': '/lJ+CuKVDhs2lKp667TAj0hWhvdC+4RbKLcAVS/OoT97+tDATGPShJWE0+h0pQ2Dkl7kX+fQqEa50m7M8ucyMPT3DTjI8zyd4pWQXVqPokn9SDeWATkUQQHBUvyruB9vRsBKkiy+fp44zx6vUd4qoq4/FukF2E+/Vox9dk0G4vT11R/pr1ZwcocYWppzSWjBRv8bSUXF/4VhcaW+mscmBEADWbi8VVU63nV9MRCQK322xsVIFX1ZfOOq9+WRWxcSTDnZepPnqmGzIOfhBelkNNsQAlkDrs3Tr+mHSFR186wwxiYCxQT27fPtk2XII1a5wrZ70uPDfZwFy78g29yuzw=='
}

signature = '80e59b3963a4fc0bdf18428fc52151a778cd0e7e'
timestamp = '1691591499'
nonce = '1355383148'
openid = 'oGKF45TzFbDCkIw53Qi54BzkUKT4'
encrypt_type = 'aes'
msg_signature = 'd96fc6dd703606937b42f639ed8ece9bc29560e6'

client = Client(**config['wechat_channels'])
result = client.decrypt(
    d['Encrypt'],
    timestamp=timestamp, nonce=nonce, signature=msg_signature
)

# client.add_webhook(config['openapi_webhook'])
result = client.request(
    'POST', endpoint='/channels/ec/order/get',
    data={
        'order_id': result.data['order_info']['order_id']
    }, is_oauth=False, result_processor=OrderDetailResult
)
print(result)
