from openapi.providers.sms.submail import Client

from examples.config import config

client = Client(**config['sms']['submail'])
client.add_webhook(config['openapi_webhook'])

content = """【路飞学城】您已成功购买黑金VIP实战课，请联系您的专属班主任，领取代码课件，点击添加：http://link.luffycity.com/{link} 。
观看步骤：
1、请用下单手机号，电脑端登录路飞学城官网：www.luffycity.com（推荐使用谷歌浏览器）；
2、登录后在实战课页面，可看到黑金vip专属权限；
3、点击去学习按钮，即可观看实战课中所有的课程视频；
退订回N。""".format(link='123456')

# For testing
result = client.request(
    'post', '/message/send.json',
    json={'content': content, 'to': config['sms']['to']}
)
print(result)
print(result.status == client.codes.SUCCESS)
