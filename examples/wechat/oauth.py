from openapi.providers.wechat.open import Client

from examples.config import config

wechat_config = config['wechat']
mobile_client = Client(app_id=wechat_config['app_id'], secret=wechat_config['secret'])
mobile_client.add_webhook(config['openapi_webhook'])

wechat_open_config = config['wechat_open']
pc_client = Client(app_id=wechat_open_config['app_id'], secret=wechat_open_config['secret'])
pc_client.add_webhook(config['openapi_webhook'])


qrcode_url = mobile_client.get_qrcode_url(
    state='wechat',
    redirect_uri=wechat_config['oauth_redirect_uri']
)
print(qrcode_url)

qrcode_url = pc_client.get_qrcode_url(
    state='wechat',
    redirect_uri=wechat_open_config['oauth_redirect_uri']
)
print(qrcode_url)


authorize_url = mobile_client.get_authorize_url(
    scope='snsapi_userinfo', state='wechat',
    redirect_uri=wechat_config['oauth_redirect_uri']
)
print(authorize_url)
