import base64
import time
from unittest.mock import patch

import pytest

from services.bizyair_media_upload import (
    _get_cached_url,
    _is_base64_string,
    _is_local_file_path,
    _is_url,
    _set_cached_url,
    _url_cache,
    clear_cache,
    upload_and_get_url,
    CACHE_TTL_SECONDS,
)


class TestIsUrl:
    def test_http(self):
        assert _is_url("http://example.com/image.png") is True

    def test_https(self):
        assert _is_url("https://example.com/image.png") is True

    def test_not_url(self):
        assert _is_url("/path/to/file.png") is False

    def test_empty(self):
        assert _is_url("") is False

    def test_base64_is_not_url(self):
        assert _is_url("iVBORw0KGgoAAAANSUhEUg==") is False


class TestIsLocalFilePath:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG")
        assert _is_local_file_path(str(f)) is True

    def test_nonexistent_file(self):
        assert _is_local_file_path("/nonexistent/path/to/file.png") is False

    def test_empty(self):
        assert _is_local_file_path("") is False


class TestIsBase64String:
    def test_valid_base64(self):
        data = base64.b64encode(b"\x89PNG" + b"\x00" * 20).decode()
        assert _is_base64_string(data) is True

    def test_short_string(self):
        assert _is_base64_string("abc") is False

    def test_empty(self):
        assert _is_base64_string("") is False

    def test_invalid_base64(self):
        assert _is_base64_string("not!valid!base64!data!string") is False


class TestUrlCache:
    def setup_method(self):
        clear_cache()

    def teardown_method(self):
        clear_cache()

    def test_set_and_get(self):
        _set_cached_url("/path/to/file.png", 1000.0, "https://oss.example.com/file.png")
        result = _get_cached_url("/path/to/file.png", 1000.0)
        assert result == "https://oss.example.com/file.png"

    def test_cache_miss_wrong_path(self):
        _set_cached_url("/path/to/file.png", 1000.0, "https://oss.example.com/file.png")
        result = _get_cached_url("/path/to/other.png", 1000.0)
        assert result is None

    def test_cache_miss_wrong_mtime(self):
        """文件被修改后 mtime 变化，缓存应失效"""
        _set_cached_url("/path/to/file.png", 1000.0, "https://oss.example.com/file.png")
        result = _get_cached_url("/path/to/file.png", 2000.0)
        assert result is None

    def test_cache_expired(self):
        """缓存超过 TTL 后应失效"""
        _set_cached_url("/path/to/file.png", 1000.0, "https://oss.example.com/file.png")
        # 手动将缓存时间回拨使其过期
        key = ("/path/to/file.png", 1000.0)
        url, _ = _url_cache[key]
        _url_cache[key] = (url, time.time() - CACHE_TTL_SECONDS - 1)

        result = _get_cached_url("/path/to/file.png", 1000.0)
        assert result is None
        # 过期条目应被清理
        assert key not in _url_cache

    def test_clear_cache(self):
        _set_cached_url("/a", 1.0, "https://a")
        _set_cached_url("/b", 2.0, "https://b")
        clear_cache()
        assert _get_cached_url("/a", 1.0) is None
        assert _get_cached_url("/b", 2.0) is None


class TestUploadAndGetUrl:
    @pytest.mark.asyncio
    async def test_url_passthrough(self):
        """已有 URL 直接透传，不调用任何上传逻辑"""
        result = await upload_and_get_url(
            api_key="test-key",
            image_data="https://example.com/image.png",
        )
        assert result == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_empty_image_data_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            await upload_and_get_url(api_key="key", image_data="")

    @pytest.mark.asyncio
    async def test_unrecognized_input_raises(self):
        """既不是 URL，也不是文件路径，也不是 base64 时应抛错"""
        with pytest.raises(ValueError, match="无法识别"):
            await upload_and_get_url(api_key="key", image_data="random_text")

    @pytest.mark.asyncio
    async def test_local_file_uploads_and_caches(self, tmp_path):
        """本地文件应触发上传并写入缓存"""
        clear_cache()
        f = tmp_path / "test_ref.png"
        f.write_bytes(b"\x89PNG" + b"\x00" * 100)

        fake_url = "https://oss.example.com/uploaded.png"

        with (
            patch("services.bizyair_media_upload.get_upload_token") as mock_token,
            patch("services.bizyair_media_upload.upload_bytes_to_oss") as mock_upload,
        ):
            mock_token.return_value = {
                "file": {"object_key": "inputs/test.png", "access_key_id": "a", "access_key_secret": "b", "security_token": "c"},
                "storage": {"endpoint": "oss.example.com", "bucket": "test", "region": "cn-shanghai"},
            }
            mock_upload.return_value = fake_url

            result = await upload_and_get_url(api_key="test-key", image_data=str(f))
            assert result == fake_url
            mock_token.assert_called_once()
            mock_upload.assert_called_once()

            # 第二次调用应命中缓存
            mock_token.reset_mock()
            mock_upload.reset_mock()

            result2 = await upload_and_get_url(api_key="test-key", image_data=str(f))
            assert result2 == fake_url
            mock_token.assert_not_called()
            mock_upload.assert_not_called()

        clear_cache()

    @pytest.mark.asyncio
    async def test_base64_uploads_without_cache(self):
        """base64 输入应触发上传但不缓存"""
        clear_cache()
        raw_data = b"\x89PNG" + b"\x00" * 100
        b64_data = base64.b64encode(raw_data).decode()
        fake_url = "https://oss.example.com/b64.png"

        with (
            patch("services.bizyair_media_upload.get_upload_token") as mock_token,
            patch("services.bizyair_media_upload.upload_bytes_to_oss") as mock_upload,
        ):
            mock_token.return_value = {
                "file": {"object_key": "inputs/upload.png", "access_key_id": "a", "access_key_secret": "b", "security_token": "c"},
                "storage": {"endpoint": "oss.example.com", "bucket": "test", "region": "cn-shanghai"},
            }
            mock_upload.return_value = fake_url

            result = await upload_and_get_url(api_key="test-key", image_data=b64_data)
            assert result == fake_url

            # 第二次调用不应命中缓存，应再次上传
            mock_token.reset_mock()
            mock_upload.reset_mock()

            result2 = await upload_and_get_url(api_key="test-key", image_data=b64_data)
            assert result2 == fake_url
            mock_token.assert_called_once()
            mock_upload.assert_called_once()

        clear_cache()
