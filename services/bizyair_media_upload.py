from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import alibabacloud_oss_v2 as oss
import httpx

from src.common.logger import get_logger

logger = get_logger("bizyair_generate_image_plugin")

UPLOAD_TOKEN_URL = "https://api.bizyair.cn/x/v1/upload/token"
UPLOAD_TOKEN_TIMEOUT = 30.0
CACHE_TTL_SECONDS = 8 * 3600

# 模块级 URL 缓存
# key = (absolute_path, mtime)，value = (url, cache_timestamp)
_url_cache: dict[tuple[str, float], tuple[str, float]] = {}


async def get_upload_token(api_key: str, file_name: str) -> dict[str, Any]:
    """
    使用 BizyAir API Key 获取阿里云 OSS 临时上传凭证

    :param api_key: str，BizyAir API Key
    :param file_name: str，待上传文件名称（含扩展名）
    :return: dict[str, Any]，包含 file 和 storage 两个子字典的凭证数据
    """

    if not api_key:
        raise ValueError("api_key 不能为空")
    if not file_name:
        raise ValueError("file_name 不能为空")

    async with httpx.AsyncClient(timeout=UPLOAD_TOKEN_TIMEOUT) as client:
        response = await client.get(
            UPLOAD_TOKEN_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "file_name": file_name,
                "file_type": "inputs",
            },
        )

    response.raise_for_status()
    response_json = response.json()

    if response_json.get("code") != 20000 or response_json.get("status") is not True:
        raise ValueError(f"获取上传凭证失败: {response_json}")

    data = response_json.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"上传凭证响应缺少 data 字段: {response_json}")

    file_info = data.get("file")
    storage_info = data.get("storage")
    if not isinstance(file_info, dict) or not isinstance(storage_info, dict):
        raise ValueError(f"上传凭证响应结构不符合预期: {response_json}")

    required_file_keys = ["object_key", "access_key_id", "access_key_secret", "security_token"]
    required_storage_keys = ["endpoint", "bucket", "region"]

    for required_key in required_file_keys:
        if not file_info.get(required_key):
            raise ValueError(f"上传凭证 file 缺少字段 {required_key}: {response_json}")

    for required_key in required_storage_keys:
        if not storage_info.get(required_key):
            raise ValueError(f"上传凭证 storage 缺少字段 {required_key}: {response_json}")

    return data


def _upload_to_oss_sync(
        file_path: str,
        region: str,
        endpoint: str,
        bucket: str,
        object_key: str,
        access_key_id: str,
        access_key_secret: str,
        security_token: str,
) -> None:
    """
    同步方式将本地文件上传到阿里云 OSS，供 asyncio.to_thread 调用

    :param file_path: str，本地文件路径
    :param region: str，OSS Region（如 oss-cn-shanghai）
    :param endpoint: str，OSS Endpoint
    :param bucket: str，OSS Bucket 名称
    :param object_key: str，OSS 对象 Key
    :param access_key_id: str，STS 临时凭证 Access Key ID
    :param access_key_secret: str，STS 临时凭证 Access Key Secret
    :param security_token: str，STS 临时凭证 Security Token
    :return: None，无返回值
    """

    # 使用环境变量方式传递凭证给 SDK
    os.environ["OSS_ACCESS_KEY_ID"] = access_key_id
    os.environ["OSS_ACCESS_KEY_SECRET"] = access_key_secret
    os.environ["OSS_SESSION_TOKEN"] = security_token

    cfg = oss.config.load_default()
    cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

    # SDK 要求 region 不带 "oss-" 前缀
    normalized_region = region[4:] if region and region.startswith("oss-") else region
    cfg.region = normalized_region
    cfg.endpoint = endpoint or f"oss-{normalized_region}.aliyuncs.com"

    client = oss.Client(cfg)
    client.put_object_from_file(
        oss.PutObjectRequest(bucket=bucket, key=object_key),
        file_path,
    )


async def upload_bytes_to_oss(file_data: bytes, file_name: str, token_data: dict[str, Any]) -> str:
    """
    将文件字节数据上传到阿里云 OSS 并返回可访问的 URL

    :param file_data: bytes，待上传的文件字节数据
    :param file_name: str，文件名称（含扩展名），用于临时文件后缀
    :param token_data: dict[str, Any]，get_upload_token 返回的凭证数据
    :return: str，上传成功后的 OSS 文件 URL
    """

    file_info = token_data["file"]
    storage_info = token_data["storage"]

    # 写入临时文件后通过 SDK 上传
    suffix = Path(file_name).suffix or ".bin"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(tmp_fd, file_data)
        os.close(tmp_fd)

        await asyncio.to_thread(
            _upload_to_oss_sync,
            file_path=tmp_path,
            region=storage_info["region"],
            endpoint=storage_info["endpoint"],
            bucket=storage_info["bucket"],
            object_key=file_info["object_key"],
            access_key_id=file_info["access_key_id"],
            access_key_secret=file_info["access_key_secret"],
            security_token=file_info["security_token"],
        )
    finally:
        # 确保临时文件被清理
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    url = f"https://{storage_info['bucket']}.{storage_info['endpoint']}/{file_info['object_key']}"
    return url


def _get_cached_url(absolute_path: str, mtime: float) -> str | None:
    """
    从内存缓存中查找本地文件对应的 OSS URL

    :param absolute_path: str，本地文件绝对路径
    :param mtime: float，文件最后修改时间戳
    :return: str | None，缓存命中时返回 URL，未命中或已过期返回 None
    """

    cache_key = (absolute_path, mtime)
    cached = _url_cache.get(cache_key)
    if cached is None:
        return None

    url, cache_time = cached
    if time.time() - cache_time > CACHE_TTL_SECONDS:
        # 缓存已过期，移除
        _url_cache.pop(cache_key, None)
        return None

    return url


def _set_cached_url(absolute_path: str, mtime: float, url: str) -> None:
    """
    将本地文件对应的 OSS URL 写入内存缓存

    :param absolute_path: str，本地文件绝对路径
    :param mtime: float，文件最后修改时间戳
    :param url: str，上传后获得的 OSS URL
    :return: None，无返回值
    """

    _url_cache[(absolute_path, mtime)] = (url, time.time())


def _is_url(value: str) -> bool:
    """
    判断字符串是否为 HTTP/HTTPS URL

    :param value: str，待判断的字符串
    :return: bool，是否为 URL
    """

    return value.startswith("http://") or value.startswith("https://")


def _is_local_file_path(value: str) -> bool:
    """
    判断字符串是否为已存在的本地文件路径

    :param value: str，待判断的字符串
    :return: bool，是否为已存在的本地文件
    """

    try:
        return Path(value).is_file()
    except (OSError, ValueError):
        return False


def _is_base64_string(value: str) -> bool:
    """
    判断字符串是否为合法的 base64 编码数据

    :param value: str，待判断的字符串
    :return: bool，是否为合法的 base64 字符串
    """

    if not value or len(value) < 16:
        return False
    try:
        decoded = base64.b64decode(value, validate=True)
        return len(decoded) > 0
    except Exception:
        return False


async def upload_and_get_url(api_key: str, image_data: str, file_name: str = "upload.png") -> str:
    """
    将图片数据上传到 BizyAir OSS 并返回 URL，支持多种输入格式

    输入判断优先级：
    1. 已有 URL（http/https 开头）→ 直接返回
    2. 本地文件路径（文件存在）→ 检查缓存 → 未命中则读取并上传 → 写入缓存
    3. base64 字符串 → 解码后上传（不缓存）
    4. 以上均不匹配 → 抛出 ValueError

    :param api_key: str，BizyAir API Key
    :param image_data: str，图片数据（URL / 本地文件路径 / base64 字符串）
    :param file_name: str，上传时使用的文件名称
    :return: str，可访问的图片 URL
    """

    if not image_data or not isinstance(image_data, str):
        raise ValueError("image_data 不能为空")
    image_data = image_data.strip()

    # 情况 1：已经是 URL，直接透传
    if _is_url(image_data):
        logger.debug(f"[媒体上传] 输入已是 URL，直接透传: {image_data[:80]}")
        return image_data

    # 情况 2：本地文件路径
    if _is_local_file_path(image_data):
        path = Path(image_data).resolve()
        absolute_path = str(path)
        mtime = path.stat().st_mtime

        # 检查缓存
        cached_url = _get_cached_url(absolute_path, mtime)
        if cached_url is not None:
            logger.info(f"[媒体上传] 本地文件缓存命中: path={absolute_path}, url={cached_url[:80]}")
            return cached_url

        logger.info(f"[媒体上传] 开始上传本地文件: path={absolute_path}")
        file_data = path.read_bytes()
        upload_file_name = path.name or file_name

        token_data = await get_upload_token(api_key, upload_file_name)
        url = await upload_bytes_to_oss(file_data, upload_file_name, token_data)

        _set_cached_url(absolute_path, mtime, url)
        logger.info(f"[媒体上传] 本地文件上传完成: path={absolute_path}, url={url[:80]}")
        return url

    # 情况 3：base64 字符串
    if _is_base64_string(image_data):
        logger.info(f"[媒体上传] 开始上传 base64 数据: length={len(image_data)}")
        file_data = base64.b64decode(image_data)

        token_data = await get_upload_token(api_key, file_name)
        url = await upload_bytes_to_oss(file_data, file_name, token_data)

        logger.info(f"[媒体上传] base64 数据上传完成: url={url[:80]}")
        return url

    raise ValueError(
        f"无法识别 image_data 的类型（非 URL、非本地文件路径、非 base64 字符串）: {image_data[:100]}"
    )


def clear_cache() -> None:
    """
    清空模块级 URL 缓存

    :return: None，无返回值
    """

    _url_cache.clear()
