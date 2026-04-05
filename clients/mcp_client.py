from __future__ import annotations

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from .base import BizyAirBaseClient, BizyAirImageResult


class BizyAirMcpError(Exception):
    """BizyAir MCP 调用异常"""


class BizyAirMcpProtocolError(BizyAirMcpError):
    """BizyAir MCP 返回结果与预期不符"""


class BizyAirMcpClient(BizyAirBaseClient):
    """
    BizyAir 文生图 MCP 的 Python Client。
    """

    MCP_URL = "https://api.bizyair.cn/w/v1/mcp/232"
    TOOL_NAME = "banana_text_to_image"

    PROMPT_KEY = "116:BizyAir_NanoBananaPro.prompt"
    ASPECT_RATIO_KEY = "116:BizyAir_NanoBananaPro.aspect_ratio"
    RESOLUTION_KEY = "116:BizyAir_NanoBananaPro.resolution"

    ALLOWED_ASPECT_RATIOS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"}
    ALLOWED_RESOLUTIONS = {"1K", "2K", "4K", "auto"}

    def __init__(self, bearer_token: str, mcp_url: str | None = None, timeout: float = 180.0) -> None:
        super().__init__(bearer_token=bearer_token, timeout=timeout)
        self.mcp_url = mcp_url or self.MCP_URL

    def _validate_aspect_ratio(self, aspect_ratio: str) -> None:
        self._validate_choice(aspect_ratio, self.ALLOWED_ASPECT_RATIOS, "aspect_ratio")

    def _validate_resolution(self, resolution: str) -> None:
        self._validate_choice(resolution, self.ALLOWED_RESOLUTIONS, "resolution")

    async def generate_image(self, prompt: str, aspect_ratio: str = "1:1", resolution: str = "1K") -> BizyAirImageResult:
        prompt = self._require_non_empty_text(prompt, "prompt")
        resolution = self._normalize_resolution(resolution)
        self._validate_aspect_ratio(aspect_ratio)
        self._validate_resolution(resolution)

        arguments = {
            self.PROMPT_KEY: prompt,
            self.ASPECT_RATIO_KEY: aspect_ratio,
            self.RESOLUTION_KEY: resolution,
        }

        async with httpx.AsyncClient(
                headers=self._build_headers(),
                timeout=self.timeout,
                follow_redirects=True,
        ) as http_client:
            async with streamable_http_client(self.mcp_url, http_client=http_client) as (
                    read_stream,
                    write_stream,
                    _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(self.TOOL_NAME, arguments=arguments)
                    return self._parse_generate_result(result)

    def _parse_generate_result(self, result: CallToolResult) -> BizyAirImageResult:
        if result.isError:
            raise BizyAirMcpError(f"MCP tool 调用失败: {result}")

        if result.structuredContent is not None:
            raise BizyAirMcpProtocolError(f"返回 structuredContent 不为 None，与预期不符: {result.structuredContent}")

        if len(result.content) != 1:
            raise BizyAirMcpProtocolError(f"返回 content 数量不是 1，与预期不符: {len(result.content)}")

        item = result.content[0]
        if not isinstance(item, TextContent):
            raise BizyAirMcpProtocolError(f"返回 content[0] 不是 TextContent，与预期不符: {type(item)}")

        image_url = item.text.strip()
        try:
            image_url = self._validate_url(image_url, "image_url")
        except ValueError as exc:
            raise BizyAirMcpProtocolError(str(exc)) from exc

        return BizyAirImageResult(image_url=image_url)
