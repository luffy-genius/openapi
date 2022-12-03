#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/12/3
from pydantic import BaseModel

from fastapi import FastAPI

app = FastAPI()


class Message(BaseModel):
    encrypt: str
    msg_signature: str
    timestamp: int
    nonce: str


@app.post(path='/yizhi')
def callback(message: Message):
    print(message)
    return 'success'
