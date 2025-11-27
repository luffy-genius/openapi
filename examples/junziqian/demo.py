import time
import json
import hashlib
from enum import IntEnum

import httpx

from typing import Literal, Optional, List, Union, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

EncryMethod = Literal['md5', 'sha1', 'sha256', 'sha3_256']


def _hexdigest(s: str, method: EncryMethod) -> str:
    algo = {'md5': hashlib.md5, 'sha1': hashlib.sha1,
            'sha256': hashlib.sha256, 'sha3_256': hashlib.sha3_256}[method]
    return algo(s.encode('utf-8')).hexdigest().lower()


def compute_sign(app_key: str, secret: str,
                 ts_ms: Optional[int] = None,
                 encry_method: EncryMethod = 'sha256',
                 nonce: Optional[str] = None) -> dict:
    ts_ms = ts_ms or int(time.time() * 1000)
    # 若未传入，则用 ts 的 md5（32 位）
    nonce = nonce or _hexdigest(str(ts_ms), 'md5')
    if len(nonce) != 32:
        raise ValueError('nonce 必须是 32 位字符串（建议使用 ts 的 md5）')
    plain = f'nonce{nonce}ts{ts_ms}app_key{app_key}app_secret{secret}'
    sign = _hexdigest(plain, encry_method)
    return {
        'ts': ts_ms,
        'nonce': nonce,
        'sign': sign,
        'app_key': app_key,
        'encry_method': encry_method,
    }


class PublicParam(BaseModel):
    ts: int
    app_key: str
    sign: str
    nonce: str
    encry_method: EncryMethod


class FileType(IntEnum):
    WORD = 1
    PDF = 2
    HTML = 3
    FORM = 4


class PositionType(IntEnum):
    COORDINATE = 0
    FORM_FIELD = 1
    KEYWORD = 2


# ===== 公共：关键字/表单域/坐标位置信息 =====
class ChapterJsonItem(BaseModel):
    chapte_name: Optional[str] = Field(None, alias='chapteName')
    search_key: Optional[str] = Field(None, alias='searchKey')
    search_extend: Optional[dict] = Field(None, alias='searchExtend')
    search_convert_extend: Optional[dict] = Field(None, alias='searchConvertExtend')
    key_search_type: Optional[int] = Field(None, alias='keySearchType')
    font_size: Optional[int] = Field(None, alias='fontSize')
    width: Optional[int] = Field(None, alias='width')
    height: Optional[int] = Field(None, alias='height')
    content: Optional[str] = Field(None, alias='content')
    position_type: Optional[int] = Field(None, alias='positionType')  # 0/1/2


# ===== signatories（签约方） =====
class Signatory(BaseModel):
    # 必填
    full_name: str = Field(alias='fullName', max_length=50)
    identity_type: int = Field(alias='identityType',
                               description='1身份证,2护照,3回乡证,4港澳居住证,11营业执照,12统一社会信用代码')
    identity_card: str = Field(alias='identityCard')

    # 常用联系/排序
    mobile: Optional[str] = Field(None, alias='mobile')
    email: Optional[str] = Field(None, alias='email')
    order_num: Optional[int] = Field(None, alias='orderNum', ge=0, le=100,
                                     description='配合 orderFlag=1 使用')

    # 位置/章定义
    chapte_json: Optional[List[ChapterJsonItem]] = Field(None, alias='chapteJson')
    chapte_name: Optional[str] = Field(None, alias='chapteName')      # positionType=1 时通常需要
    search_key: Optional[str] = Field(None, alias='searchKey')        # positionType=2 时通常需要

    # 认证/签章参数（按文档保留）
    auth_level: Optional[List[int]] = Field(None, alias='authLevel',
                                            description='认证等级数组，示例：10短信、11人脸等')
    auth_level_range: Optional[int] = Field(None, alias='authLevelRange')
    sign_level: Optional[int] = Field(None, alias='signLevel')
    no_need_verify: Optional[int] = Field(0, alias='noNeedVerify')
    server_ca_auto: Optional[int] = Field(0, alias='serverCaAuto')
    sign_id: Optional[int] = Field(None, alias='signId')
    qi_feng_offset: Optional[float] = Field(None, alias='qiFengOffset')

    @model_validator(mode='after')
    def _contact_for_person(self):
        # 个人时建议至少提供一个联系方式
        if self.identity_type in (1, 2, 3, 4) and not (self.mobile or self.email):
            raise ValueError('个人签约方建议至少提供 mobile 或 email 之一')
        return self


# ===== sequenceInfo（多合同顺序签批量信息） =====
class SequenceInfo(BaseModel):
    business_no: str = Field(alias='businessNo')
    sequence_order: int = Field(alias='sequenceOrder', ge=1)
    total_num: int = Field(alias='totalNum', ge=1)


# ===== 备注能力（可选） =====
class RemarkText(BaseModel):
    chapte_json: List[ChapterJsonItem] = Field(alias='chapteJson')
    chapte_name: Optional[str] = Field(None, alias='chapteName')
    search_key: Optional[str] = Field(None, alias='searchKey')
    search_extend: Optional[dict] = Field(None, alias='searchExtend')
    search_convert_extend: Optional[dict] = Field(None, alias='searchConvertExtend')
    key_search_type: Optional[int] = Field(None, alias='keySearchType')
    font_size: Optional[int] = Field(None, alias='fontSize')
    width: Optional[int] = Field(None, alias='width')
    height: Optional[int] = Field(None, alias='height')
    content: Optional[str] = Field(None, alias='content')
    position_type: Optional[int] = Field(None, alias='positionType')


class RemarkDate(BaseModel):
    chapte_json: List[ChapterJsonItem] = Field(alias='chapteJson')
    chapte_name: Optional[str] = Field(None, alias='chapteName')
    search_key: Optional[str] = Field(None, alias='searchKey')
    search_extend: Optional[dict] = Field(None, alias='searchExtend')
    search_convert_extend: Optional[dict] = Field(None, alias='searchConvertExtend')
    key_search_type: Optional[int] = Field(None, alias='keySearchType')
    font_size: Optional[int] = Field(None, alias='fontSize')
    width: Optional[int] = Field(None, alias='width')
    height: Optional[int] = Field(None, alias='height')
    # 0:yyyy年MM月dd日, 1:yyyy-MM-dd, 2:yyyy/MM/dd, 3:自定义
    date_format_type: Optional[int] = Field(0, alias='dateFormatType')
    position_type: Optional[int] = Field(None, alias='positionType')


# ===== 主请求：API 模板发起 =====
class ApplySign(PublicParam):
    # * 必填
    contract_name: str = Field(alias='contractName', max_length=100)
    signatories: Union[str, List[Signatory]]
    server_ca: int = Field(0, alias='serverCa')
    deal_type: int = Field(0, alias='dealType')
    file_type: FileType = Field(alias='fileType')

    # 模板相关（fileType=2,4 必填）
    template_no: Optional[str] = Field(None, alias='templateNo')
    template_params: Optional[dict] = Field(
        None, alias='templateParams',
        description='模板参数 JSON 字符串（或可传字典，见校验器自动转字符串）'
    )

    # 其它可选
    add_page: Optional[int] = Field(0, alias='addPage')
    position_type: Optional[PositionType] = Field(0, alias='positionType')
    face_threshold: Optional[int] = Field(None, alias='faceThreshold', ge=1, le=100)
    order_flag: Optional[int] = Field(0, alias='orderFlag')  # 1=按顺序
    sequence_info: Optional[SequenceInfo] = Field(None, alias='sequenceInfo')
    notify_url: Optional[HttpUrl] = Field(None, alias='notifyUrl')
    no_ebq_sign: Optional[int] = Field(0, alias='noEbqSign')
    attach_files: Optional[List[Any]] = Field(None, alias='attachFiles')
    need_qifeng_sign: Optional[int] = Field(0, alias='needQifengSign')
    no_border_sign: Optional[int] = Field(0, alias='noBorderSign')

    # 备注能力
    remark_text: Optional[RemarkText] = Field(None, alias='remarkText')
    remark_date: Optional[RemarkDate] = Field(None, alias='remarkDate')

    @classmethod
    @field_validator('signatories', mode='before')
    def _parse_signatories(cls, v):
        # 允许传 JSON 字符串
        if isinstance(v, str):
            try:
                arr = json.loads(v)
            except Exception as e:
                raise ValueError(f'signatories 非法 JSON: {e}')
            if not isinstance(arr, list):
                raise ValueError('signatories 解析后必须是数组')
            return [Signatory.model_validate(i) for i in arr]
        return v

    @classmethod
    @field_validator('template_params', mode='before')
    def _ensure_tpl_params_str(cls, v):
        # 模板参数接受 dict/list，自动转字符串
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return v

    @model_validator(mode='after')
    def _conditional_checks(self):
        if self.file_type in (FileType.PDF, FileType.FORM):
            if not self.template_no:
                raise ValueError('fileType 为 2/4 时，templateNo 为必填')
            if not self.template_params:
                raise ValueError('fileType 为 2/4 时，templateParams 为必填(JSON 字符串)')
        if self.order_flag == 1:
            for idx, s in enumerate(self.signatories or []):
                if getattr(s, 'order_num', None) is None:
                    raise ValueError(f'orderFlag=1 时，第 {idx+1} 个签约方缺少 orderNum')
        if self.position_type == PositionType.FORM_FIELD:
            pass
        if self.position_type == PositionType.KEYWORD:
            pass
        return self

    class Config:
        populate_by_name = True
        use_enum_values = True


if __name__ == '__main__':
    p = PublicParam.model_validate(compute_sign(app_key='63145c723c860c51', secret='6645f6f163145c723c860c51876ed1b7'))
    print(p)
    req = ApplySign(
        ts=p.ts, app_key=p.app_key, sign=p.sign, nonce=p.nonce, encry_method=p.encry_method,
        contractName="模板发起-合作协议",
        fileType=4,  # PDF 模板
        templateNo="0DE608C398C141C8948EC6F9C9E4611E",
        templateParams={"partyA": "甲方公司", "partyB": "乙方个人", "amount": "9999.00"},
        signatories=[
            {"fullName": "谢广亮", "identityType": 1, "identityCard": "13130119991111041X",
             "mobile": "13800000000", "orderNum": 1},
            {"fullName": "北京路飞学城教育科技有限公司", "identityType": 12, "identityCard": "91110114MA0181QE4T",
             "email": "www.luffycity.com", "orderNum": 2, "signId": 123456}
        ],
        orderFlag=1,
    )
    base_uri = 'https://api.sandbox.junziqian.com/v2/sign/applySign'

    print(base_uri)
    print(req.model_dump(by_alias=True, exclude_none=True))

    headers = {
        'Content-Type': 'multipart/form-data',
    }
    resp = httpx.post(url=base_uri, data=req.model_dump(), headers=headers)
    print(resp.status_code)
    print(resp.content)
