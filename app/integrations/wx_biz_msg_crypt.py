"""微信开放平台/公众平台消息加解密（WXBizMsgCrypt 算法）。"""

from __future__ import annotations

import base64
import hashlib
import logging
import struct
from typing import Final

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

_BLOCK_SIZE: Final[int] = 32


class WxBizMsgCryptError(Exception):
    """加解密或签名校验失败。"""


def _decode_aes_key(encoding_aes_key: str) -> bytes:
    key = (encoding_aes_key or "").strip()
    if len(key) != 43:
        raise WxBizMsgCryptError("EncodingAESKey 长度须为 43")
    try:
        return base64.b64decode(key + "=")
    except Exception as e:
        raise WxBizMsgCryptError("EncodingAESKey 无效") from e


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise WxBizMsgCryptError("解密结果为空")
    pad = data[-1]
    if pad < 1 or pad > _BLOCK_SIZE:
        raise WxBizMsgCryptError("PKCS7 填充无效")
    if data[-pad:] != bytes([pad]) * pad:
        raise WxBizMsgCryptError("PKCS7 填充无效")
    return data[:-pad]


def _sha1_signature(*parts: str) -> str:
    items = sorted(str(p) for p in parts)
    return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()


def _aes_cbc_decrypt(ciphertext: bytes, aes_key: bytes) -> bytes:
    if len(ciphertext) < _BLOCK_SIZE or len(ciphertext) % _BLOCK_SIZE != 0:
        raise WxBizMsgCryptError("密文长度无效")
    iv = aes_key[:16]
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plain = decryptor.update(ciphertext) + decryptor.finalize()
    return _pkcs7_unpad(plain)


def _extract_message(plain: bytes, appid: str) -> str:
    if len(plain) < 20:
        raise WxBizMsgCryptError("解密明文过短")
    msg_len = struct.unpack("!I", plain[16:20])[0]
    start = 20
    end = start + msg_len
    if end > len(plain):
        raise WxBizMsgCryptError("消息长度无效")
    msg = plain[start:end].decode("utf-8")
    recv_appid = plain[end:].decode("utf-8", errors="replace")
    expected = (appid or "").strip()
    if expected and recv_appid != expected:
        raise WxBizMsgCryptError("AppId 校验失败")
    return msg


class WxBizMsgCrypt:
    """第三方平台 component 回调加解密。"""

    def __init__(self, *, token: str, encoding_aes_key: str, appid: str) -> None:
        self.token = (token or "").strip()
        self.appid = (appid or "").strip()
        self.aes_key = _decode_aes_key(encoding_aes_key)

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypt: str) -> None:
        expected = _sha1_signature(self.token, timestamp, nonce, encrypt)
        if (msg_signature or "").strip() != expected:
            raise WxBizMsgCryptError("msg_signature 校验失败")

    def decrypt(self, encrypt: str, *, msg_signature: str = "", timestamp: str = "", nonce: str = "") -> str:
        enc = (encrypt or "").strip()
        if msg_signature:
            self.verify_signature(msg_signature, timestamp, nonce, enc)
        try:
            ciphertext = base64.b64decode(enc)
        except Exception as e:
            raise WxBizMsgCryptError("Encrypt Base64 无效") from e
        plain = _aes_cbc_decrypt(ciphertext, self.aes_key)
        return _extract_message(plain, self.appid)

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """GET 回调 URL 校验：解密 echostr 并返回明文。"""
        return self.decrypt(echostr, msg_signature=msg_signature, timestamp=timestamp, nonce=nonce)


def component_msg_crypt_from_settings() -> WxBizMsgCrypt | None:
    """按 .env 构造 component 加解密器；凭证不全时返回 None。"""
    from app.core.config import get_settings

    s = get_settings()
    token = (s.WX_OPEN_COMPONENT_TOKEN or "").strip()
    aes_key = (s.WX_OPEN_COMPONENT_AES_KEY or "").strip()
    appid = (s.WX_OPEN_COMPONENT_APPID or "").strip()
    if not (token and aes_key and appid):
        return None
    try:
        return WxBizMsgCrypt(token=token, encoding_aes_key=aes_key, appid=appid)
    except WxBizMsgCryptError:
        logger.exception("component 加解密器初始化失败")
        return None
