from pydantic import BaseModel, Field

from openapi.providers.polyv import Client as PolyvClient, Result

from examples.config import config

class VideoToken(BaseModel):
    token: str
    user_id: str = Field(..., alias='userId')
    app_id: str | None = Field(..., alias='appId')
    video_id: str = Field(..., alias='videoId')
    viewer_ip: str = Field(..., alias='viewerIp')
    viewer_id: str = Field(..., alias='viewerId')
    viewer_name: str = Field(..., alias='viewerName')
    extra_params: str = Field(..., alias='extraParams')
    ttl: int
    created_time: int = Field(..., alias='createdTime')
    expired_time: int = Field(..., alias='expiredTime')
    iswxa: int
    disposable: bool


if __name__ == '__main__':
    client = PolyvClient(user_id=config['polyv']['user_id'], secret=config['polyv']['secret'])
    r: Result[VideoToken] = client.request('post', '/service/v1/token', data={
        'videoId': 'd1977c4d68c73c1580638dd834d7635a_d',
        'viewerIp': '127.0.0.1',
        'viewerId': 'example',
        'viewerName': 'example',
        'extraParams': 'HTML5'
    }, model=VideoToken)
    print(r)
