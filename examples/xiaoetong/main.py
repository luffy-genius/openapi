from openapi.providers.xiaoetong import Client

from examples.config import config

# print(config)
client = Client(**config['xiaoetong'])
client.add_webhook(config['openapi_webhook'])

data = {
    'encrypt': 'jxDtr8HOsOi4JaF9XEFxeB6yj2SyepAOQ8aSTk/IFwgm9y3KG/aEVQZbEbmXncerf1aitm/pdOmRq7unu1otSnHU4oMnsh2Yowsze8UMCCVaXF+bk30Ndb2KOhaR/G06k1zXO+JtI14sw62bEiP88FTsU/IZNw8RozBM4rzySJGrIjFYxmi1EF/o8a3YNdDLy9+vRZps6RTDDOvyaveeUo03KIKDuCjnH+61iUE3N9w/PYAYrHIBR5iapXsZMeYWQEI9MVxZP+PwetCsT5yEryQOPJZa/M+Kk20AOZTPQLBQ6o/ca7zcpRNj6e95mkLSOTr0pbOO1wyEJMnl0bxSldS0+ll7o5dzvq0lEqFj9XUb2jlewex8s8VtsDS51rK5IsOR92iGwmDiQxEdPCwgSIjOussTMP6w+3VA4VDpAC787Po+e/xFXKlfombV8qhotLd9Y+Q2w2iS+Og3Jzh98HwdfuCsOby274L8dltseiR1za2igKAK79wMTnZCydrmg+gyllU+14HxlV21UHy9iwCnk03iuu2LWgh91HD23Mp8K7dkDOpmL/XLf3CHksMHiMRdYLrs5EJXwljRXzjYyZQteh9mWEgxnuZS1K/mYBGopIsezH1+ooCDZeOZVwbDTLO0GpgLMqsV8P+joybC8qztkkEXxUHlsD4mn3EYApk2CfwID0G2/PoJsSZS/Z+KDfDhhw9qt2JuieByKiS6oSHruSsBmPx/3S3qAAnzpVEqp8kne+nAVyJIxbN2CEP8g6+5CXb9tuJQWpjui1Qp8mrYaDPWZ6IEnLF3WQfEpBxcI59Mnhhpeb2nlbwJSLjs+HsqnxSyNWMVoqQGaVgZk28IErEnahRbQ540+NDot6f46ry47KASOvLDDXyU6q9TJ5NsbtgVFgQhbYqyA0LyZkrrBY1gmBvCsx79ygAWbBdDb+2mzD/uHtbUlgh4NCa9n+GiPsokHJnHBhQJSOY3qbCR2FiiYJdwk8VJWmLylGez4AH/KuKvEhNCqqRIbDlztihbGWNSyPUzktk0GAWbGOGyQQNLvm9hfSqpuQSXOZW8lbL8b5t60UZ+WiuOhqFzVKQLd0vlIb2/WSRWZUtzVB7jMQFLR8ycnvM3E943OWSMLX5fEYRfZRxlD37ZNyVHjLI37gEootaD2ptbc9THUGgit3y+CyNrq0wSOGUfWHyhVNlUAfuimSOfqAuH00M1yOea9uj6AlsXt2n6xfk1SgHSJzZePE18IeLH+jfS3vDwTm75ERg85LikdVy0sTY+4+Owsmy8wtOfrl5KgJyPakGujLnhNtpnJovCEmbwbO8XXL1FqPG7CtYTM9lURyTGZSElZ0tZoYZkeQb27JeKZYuNZsx/pwrX9UD5qsKq33EH2ZR1CJJF5LeHiL6eUFGJi4PwLpSZm+Fh7D0xsgWejFv5qjE5uHLE0pQQYbImT0eN9pgmCebCyVbTxhg2aUa79YY+wMiTwU0YT9H30gXLu77+Y2Oo+M+pKoKIOMd4wcg/p758VPYrinPisu/YlRWu69SWtNFLHMUabd8J1WWVgYMsFj22QifVypmydsnxgL67FQwPTQ6k7l5iajsDGVSa658N+RvPi10klPZf8UwoaMZLjI32aU037oPtdORoARjsepxkJ7OE9oJypQIU/ZvwMcUHMqyoKQYqjQJyZnycbSkVyaEpV1i8/0ausncsvqQjVzmhlHipwfTLalQADkyMGwFpH2DhjntR8P9fH7X4TJIvOamJInDUwpo9fRuHMg2Z02QNty4H1vzmkLMLCU61WAkeoiJ0bjqUnHRh9/ZYL9zyERtcWE73F3Z/wmmv0nya/sn4Gw/9xmvgIc1VlYE3MCGxBBhR73T39GsbKhhi1A==',
    'signature': '7c65adabd1c6bbb8e89823965cf4f0d833e2e3a7',
    'timestamp': '1670058185',
    'nonce': '9419866818'
}

result = client.decrypt(**data)
print(result)

# invited_result = client.request(
#     'post', '/xe.distributor.customer.get/1.0.0',
#     data={'uid': 'u_63453bb9e3555_9AQFzrH6iz'}
# )
# print(invited_result)
# 
# 
# client.request(
#     'post', '/xe.order.detail/1.0.0',
#     data={'order_id': 'o_1665481738_63453c0a983e0_95395219'}
# )
