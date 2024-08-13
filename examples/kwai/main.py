from openapi.providers.kwai import Client

from examples.config import config

client = Client('', '', config['kuaishou']['message_key'])


if __name__ == '__main__':
    # 快手消息解密
    print(client.decrypt('2FXtJpaJ1ftNz39omFhoWQ=='))
