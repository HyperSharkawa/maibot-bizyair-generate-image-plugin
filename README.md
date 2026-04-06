# bizyair-generate-image-plugin

MaiBot 的文生图插件，新增一个 `generate_image` 动作，让 bot 能够根据对话上下文和用户的自然语言描述调用 BizyAir 图片生成接口并发送到聊天会话。

## 功能

- **文生图 Action**：当 bot 的决策判断当前场景适合发图时，可以选择 `generate_image` 动作生成图片并发送。
- **BizyAir 接入**：通过 BizyAir 接口生成图片，只需配置 API Token 即可用。
- **支持宽高比与分辨率**：可按需指定图片的比例（如 1:1、16:9）和清晰度（1K/2K/4K），也可使用插件的默认配置。
- **灵活配置**：可通过配置文件单独设置 BizyAir 连接信息、默认使用的接口类型、超时、默认参数、图片前的引导文案以及决策提示词。

## 安装

将插件目录（包含 `plugin.py`、`_manifest.json`、`components/` 和 `clients/`）整体放入 MaiBot 的 `plugins` 目录：

```powershell
cd <maibot根目录>\plugins
git clone https://github.com/HyperSharkawa/maibot-bizyair-generate-image-plugin
```

重启 MaiBot 后，插件会自动注册并在启动日志中出现 `bizyair_generate_image_plugin`。

> **前提条件**：确保运行 environment 已通过 `pip` / `uv` 安装 `httpx` 和 `mcp` 两个包。

## 配置

### `bizyair_client` 字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `provider` | `string` | `"mcp"` | 当前使用的 BizyAir 接口类型。可选值：`mcp`、`openapi`。 |
| `bearer_token` | `string` | `""` | **必须配置**。BizyAir 的 Bearer Token，留空时 action 不可用。 |
| `mcp_url` | `string` | `https://api.bizyair.cn/w/v1/mcp/232` | BizyAir MCP 的 Streamable HTTP 端点地址。 |
| `openapi_url` | `string` | `https://api.bizyair.cn/w/v1/webapp/task/openapi/create` | BizyAir OpenAPI 地址。 |
| `openapi_web_app_id` | `int` | `39429` | BizyAir OpenAPI 的 `web_app_id`。 |
| `openapi_parameter_mappings` | `list` | 见下文 | OpenAPI `input_values` 参数映射表。用于适配不同 app 的字段名和附加参数。 |

### `bizyair_generate_image_plugin` 字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `timeout` | `float` | `180.0` | 调用 MCP 和下载图片的超时时间（秒）。 |
| `default_aspect_ratio` | `string` | `"1:1"` | 未指定时的默认宽高比。可选值：`1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`4:5`、`5:4`、`9:16`、`16:9`、`21:9`、`auto`。 |
| `default_resolution` | `string` | `"1K"` | 未指定时的默认分辨率。可选值：`1K`、`2K`、`4K`、`auto`。 |
| `send_text_before_image` | `bool` | `false` | 是否在发送图片前先发一段引导文本。默认关闭，避免与 reply action 重复。 |
| `text_before_image` | `string` | `"我给你生成了一张图片。"` | 图片前的引导文本，仅在开启 `send_text_before_image` 时生效。 |
| `enable_rewrite_failure_reply` | `bool` | `true` | 当图片生成 action 失败时，是否调用 LLM 将错误改写为自然语言后发送。 |
| `enable_splitter` | `bool` | `false` | 当启用失败回复重写时，是否对重写结果启用分段发送。 |
| `action_require` | `string` | 详见代码 | 该 action 的决策提示词，多行文本，用于辅助大模型在合适时选择该动作。 |

> ⚙️ `bizyair_client.bearer_token` 必须填写才能使 action 正常工作。修改配置后需重启 MaiBot 生效。

### OpenAPI 参数映射

当使用 `openapi` provider 时，插件会根据 `bizyair_client.openapi_parameter_mappings` 构造请求中的 `input_values`。

默认映射：

默认 `web_app_id` 为 `39429`。
```toml
[[bizyair_client.openapi_parameter_mappings]]
field = "17:BizyAir_NanoBananaPro.prompt"
value = "{prompt}"

[[bizyair_client.openapi_parameter_mappings]]
field = "17:BizyAir_NanoBananaPro.aspect_ratio"
value = "{aspect_ratio}"

[[bizyair_client.openapi_parameter_mappings]]
field = "17:BizyAir_NanoBananaPro.resolution"
value = "{resolution}"
```

当前支持的基础占位符：

- `{prompt}`：本次生成使用的提示词
- `{aspect_ratio}`：本次生成使用的宽高比
- `{resolution}`：本次生成使用的分辨率
- `{random_seed}`：运行时生成一个随机的 32 位非负整数

例如适配 `https://bizyair.cn/community/app/40062`：

该 app 的 id 为 `41240` ，请注意填写正确的 `web_app_id` 。
```toml
[[bizyair_client.openapi_parameter_mappings]]
field = "8:BizyAir_NanoBanana2.prompt"
value = "{prompt}"

[[bizyair_client.openapi_parameter_mappings]]
field = "8:BizyAir_NanoBanana2.seed"
value = "{random_seed}"

[[bizyair_client.openapi_parameter_mappings]]
field = "8:BizyAir_NanoBanana2.aspect_ratio"
value = "{aspect_ratio}"

[[bizyair_client.openapi_parameter_mappings]]
field = "8:BizyAir_NanoBanana2.resolution"
value = "{resolution}"
```

适配 `web_app_id` `45944`：
```toml
[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.prompt"
value = "{prompt}"

[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.aspect_ratio"
value = "{aspect_ratio}"

[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.resolution"
value = "{resolution}"

[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.seed"
value = "{random_seed}"

[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.temperature"
value = "1"

[[bizyair_client.openapi_parameter_mappings]]
field = "19:BizyAir_NanoBananaProOfficial.top_p"
value = "1"
```

`value` 不限于纯占位符，也可以是普通常量，或在一个字符串里混合占位符，例如 `"seed={random_seed}"`。复杂对象与数组也会递归替换其中的字符串值。

## Action 参数（由决策模型自动填充）

| 参数 | 是否必填 | 说明 |
| --- | --- | --- |
| `prompt` | **必填** | 图片描述词，应尽量具体，包含主体、风格、场景、构图等信息。 |
| `aspect_ratio` | 可选 | 本次生成的宽高比，如不填则使用插件默认值。 |
| `resolution` | 可选 | 本次生成的分辨率，如不填则使用插件默认值。 |

## Action 行为

当 bot 决策选择 `generate_image` 后，插件会：

1. 获取 `action_data` 中的 `prompt`，以及可选的 `aspect_ratio`、`resolution`。
2. 读取 `bizyair_client.provider`，决定使用 MCP 或 OpenAPI。
3. 使用 `bizyair_client` 配置节中的连接参数调用 BizyAir 接口生成图片。
4. 下载生成的图片并转为 base64。
5. （可选）若开启 `send_text_before_image`，先发一段引导文本。
6. 将图片以 `image` 类型发送到当前聊天会话。
7. 记录 action 执行信息，供后续上下文使用。

当调用失败时，插件会先构造原始错误信息；如果开启 `enable_rewrite_failure_reply`，则会调用 MaiBot 的回复重写，将错误改写成自然语言文本再发送；重写失败时发送原始错误信息。

## 示例场景

- 用户说"画一只可爱的蓝白猫娘" → bot 生成图片。
- 用户要求"来一张赛博朋克风格的夜景，16:9 横图，高清" → bot 按宽高比和分辨率参数生成并发送。
- 用户让 bot 为某段文字配图，模型根据上下文自行组织出 prompt 后发图。


## 免责声明

- 本插件通过外部 MCP 服务生成图片，**图片质量与可用性由 BizyAir MCP 提供方决定**。
- 请遵守当地法律法规及 MCP 服务的用户协议，合法合规地使用生成功能。
- 开发者对第三方服务的稳定性、图片内容或因使用本插件产生的任何后果不承担责任。