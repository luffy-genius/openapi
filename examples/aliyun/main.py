from openapi.providers.aliyun import Client

from examples.config import config

print(config['aliyun'])
scene_id = config['aliyun'].pop('scene_id')
client = Client(**config['aliyun'])
client.add_webhook(config['openapi_webhook'])

if __name__ == '__main__':
    # Send sms
    # result = client.request(
    #     'get', 'dysmsapi', 'SendSms', '2017-05-25',
    #     params={
    #         'PhoneNumbers': '',
    #         'SignName': '',
    #         'TemplateCode': '',
    #         'TemplateParam': json.dumps({'code': '123456'})
    #     }
    # )
    # print(result)

    # Vod
    # result = client.request(
    #     'get', 'vod.cn-shanghai', 'GetVideoPlayAuth', '2017-03-21',
    #     params={
    #         'VideoId': '7b07afb2b01b4353a1e7f929b66cc667',
    #         'AuthInfoTimeout': '1800',
    #     }
    # )
    # print(result)

    # Captcha
    result = client.request(
        'post', 'captcha.cn-shanghai', 'VerifyIntelligentCaptcha', '2023-03-05',
        data={
            'CaptchaVerifyParam': '{"sceneId":"186ovepl","certifyId":"mncFIe9hQQ","deviceToken":"V0VCI2FiMDM0ZWMwNjQzZjkxMzk5ZWIzM2UwNjJkYzdmYWUxLWgtMTczNzk1ODEwMDg2NC1jMWM5ZTgxNjhjNzQ0NzhiOTQyZmRjZjAxYzRhNzM4NyNsdE12dzF6cmlUUlpZVDd3Y2t5WExaSU5oRlRNTFU0Uk5LUkVJUFZYbnZtYVBVZFRsZDlDTCtZSXVSbEVUNGJmRlRRZDhBRHA2bWEyRXNyejRBZWo2OUhlQVVtY0MwMVd2L0dzRU9kNitVUmJvdTlCL2VkOHhtRGYzbUI0Q0ZJclJ2a2l1YUNYSWt1SDViL1o1cVJWUi81Z3JZMERQZ3BnaEZtdFVkZzF6VTE4TmIwTmFORURRazhKbmwyUVR5bmcwNnhLOEQraHRCdEljR1ZuV2k5NGQvQzVRdmdHOGdxWCs2OSs5VDNIYlRQNXZyNmh5TjVUZjJUTUY4Ry9mRFFKeXNPT2Z2ZEJkWDF3V1lMRFBFbURocmk4cG0xQy9ZbVB1UzJ0ZCt1RnIyVFUyRnExTDdhZHd4ZUtaYm90d2lJbTJmVEVvYmZVZjc4bXh3d3duZWw3MzlRV0xXYUNrdnZ0VzhkTlpkQys1eHEvNHVhM2ZicWlxWWhHdldVUGdha1ZmTFJGVnJ3cEdmSWRGUFBRcHFJNytvdGZnRWdlNko0QjFYbWJRT2tta3l6Mi9seG9wUEVyQjcycDZmdTBHTHdHdUNJWTUxY3RnRTZlWjVkU1FxM0ZrVlJLY2RyZGx1c2VBMjBkbnRnQ25qZEcrTDBXaTF2YmhnVnlRMXU1ci9KQ0N6aTV5aFZWREpzQWcxemdDKzY0cGMxdmJEUC9YWXhmWERsMFNSb2xDdThiV3c3MVZML1dPb0hiUGg5cmFncjN5SDFodUZsMHhPYTU5eU9ZTjVCS0JFOThWVC9kaTZQMnh1aWxNcHJ1aDNuY2U3Q1BtM1NIUUhQb1Vnc2kyRzVDIzQ4IzMwOTgwYWU2ZmJlYWE2ZjcwNDM4NjA0MTY1NTYwODIz","data":"wDCzPCkbaZTDzB7EySgndPWSSUIvgQ32aeVBFT6Hyk7abaO09grIjv3RnIdRaMfgHkzT5/KDjreeIlXSmV9WvRFJMsiGeArzNmn8oJhoo9Oq3+sloGTVM9YU/PhJDjPVWFycitWbwf3vfKFTNDaWoK27edxTvb3Op8UDl5UrF+NnzQUd6a78Yxwxv/njlG68Pi2a9Sirgaxb04CKqjuPw3FtQsY8b1r0iRwpKLQNgxQM4kfydI1njWNSddS1QYF7pxAvqZv0nn1v9TF8BIzaaMZ3/JTCcC0DuxDPC+q62ymSp20fmnJovUgmrSz1nUVK1wI2UvnovaR+ytK/qgbxlVcEyxMa6AuNRY1v5Su6r+HvYwh3pBJ/joGaP93dNUscbgiu1LMeFCoAfgQ8bfQIuPG+oplgBH/I7eY20zsubdITLD82Ar5jJ4rS6CQzHlGhLTHTbrArZrJooMMlaHlqiG2ACOQEt7AVW0k7V+DUJ3VpbgvuAkSpZ0YZ9P5InqZmiVPE6e17cxw4jZiUqxM1OhdOgLUbQpNiIxXNl/2XKrqyqcTkPlTNZ7edEItj7POs0zuQKwKg0l/sjfsiY0deN3G3ilcWZv2d8Pm7VaZBcvgDsDDMKv6mgTgVYZwv7FpCj7bPwjZxg+vxwK0uZEd4tgnzO5oMSmLEdQ7AlPbSE/UnDUxZHaWi70VEwQRe5/+dndUWNxFzyYT/3oX6fhG1HM5v9B1dn7Mc1Rch7zbbWSY2ia/d9M1VtOV/N4GGRorNhOEdJwePb0rQqv0x8L7Iy0FD5gqc1wvGx2ujkDl/6zjvYRns/pf6RclNBi5hVkaDdaQ0ji0ogpTpEwmLVDZQ7477s7l8ZR+bLLKOHxsjsJD8bzXnZsJ3lyrrWM45Ba2f15BxfoJUxSGrc6x9i4lc+hTgJLUdGQqzgkiGyzqhjiHAdcnU2djEZAjW70t0l1xb2XEExiSXQs9gD4gV51qUPuDRCxNK/KS988/4FbLVOXPp289r4ius1PCKPHqBGedvrwgcTk52TieIwIA9ErEAd4/KwZ6BTm9snAjwoznAi7aTMF9pBBexujW1MzyZWvCrMYSYKhLDSQNzVIbhbZF+cdMTqKKM/9BXO4OpE1TCqJ+ruKuk+hHfhL4/VKOdPaeFBD9iYFzIN+b8B0tN1qOA1sDFcJtYCoQFJiYuMbt58SekYy1P2SdSyg/FIDhK8+7OgfAJlip9hw9nXDDlhG08C7btPzoSb65IWCnYB1EE5krC72ic8PfLdZwJg7xrhBIww4C0j/VP34kkNLsrp0OTyRGUxq+IIyUAfgiX2yb7ImR4ORzvgWdnfTYDiOc+jN6xydPePtyr5/R7wkCsf86326DU6bUC7KPu+qwNWmxsYCyxUC7+8kFtdrAa3YyP1oYTeFuy8nzKXaBO52bvSHjElAJTtTEb431pnScynlVe9ABCfHKkFH7DGHqoB2uI8LQsXJfdn+WL7xcLHowCSFRd9Rtrk2n7GisCWa4OHUYHSlhK7RBtpwmtIt6ZWw+Tv82k"}',
            'SceneId': scene_id,
        }
    )
    print(result)
