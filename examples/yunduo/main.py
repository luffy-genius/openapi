from openapi.providers.crm.yunduo import Client, SignType

from examples.config import config

yunduo_config = config['yunduo']

client = Client(company_id=yunduo_config['company_id'])
client.add_webhook(config['openapi_webhook'])

"""
code=200 data={'id': None} message=None msg='操作成功'
code=600 data=None message=None msg='根据crm中的唯一标识,此数据已经存在'
code=200 data={'fc_6363': 'S090', 'uniqueCustomerId': '62e0f95d3953fa0001370d51', 'saleUserName': '', 'saleUserRealName': '', 'recentSaleUserName': '', 'recentSaleUserRealName': '', 'firstBelongSaleUserName': '', 'firstBelongSaleUserRealName': ''} message=None msg='成功'
"""


mobile = '19999999999'


if __name__ == '__main__':
    # 客户数据同步
    result = client.request(
        'post', f'/api/dataSync/customer/{client.company_id}',
        sign_key=yunduo_config['token'], sign_type=SignType.SHA256,
        params={'router_id': client.company_id},
        json={
            'contactPhone': mobile,
            'gender': '1',
            'birthdate': '1989-05-28',
            'spreadCity': '深圳市',
            'customerSource': '官网',
            'customerName': '谷爱凌',
            'consultType': '官网',
            'remarks': '【官网】官网测试',
            'tag': '自动分',
            'distribute_name': '未知',
            'fc_7581': 'S011'
        }
    )
    print(result)

    # 通用数据同步
    result = client.request(
        'post',
        f'/external/clue/standardClueAccept/v2/{client.company_id}/61ed22bc8ab9950001daf9a0',
        sign_key=yunduo_config['general_token'], sign_type=SignType.MD5,
        params={'router_id': client.company_id},
        json={
            'mobile': mobile,
            'memo': '【官网】Mysql 开发基础入门',
            'consultType': '官网',
            'distribute_name': '未知'
        }
    )
    print(result)

    # 客户信息查询
    result = client.request(
        'post',
        f'/api/dataSync/customerInfo/{client.company_id}',
        sign_key=yunduo_config['token'], sign_type=SignType.SHA256,
        params={'router_id': client.company_id},
        json={
            'contactPhone': mobile,
            'includes': ['fc_6363']
        }
    )
    print(result)
