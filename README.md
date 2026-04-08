# bizyair-generate-image-plugin

MaiBot 的文生图插件，为 Bot 添加一个 `generate_image` 动作，调用 BizyAir 平台生成图片并发送到聊天会话。支持自定义决策参数、变量模板、LLM 辅助生成、参数映射等高级功能。

## 功能概览

- **LLM 驱动的生图决策**：Bot 根据对话上下文自主判断何时需要生成图片，并填写生图参数。
- **自定义变量系统**：支持 `literal`（字面值）和 `llm`（调用 LLM 生成）两种变量模式，可从候选值中随机抽取，并引用决策参数。
- **灵活的参数映射**：通过配置表将变量映射到 BizyAir OpenAPI 的实际参数，支持 string / int / boolean / json 四种值类型。
- **失败回复改写**：生图失败时，可调用 LLM 将技术错误改写为自然的中文回复发送给用户。

## 安装

1. 将仓库克隆到 MaiBot 的 `plugins` 目录：

   ```powershell
   cd <maibot根目录>\plugins
   git clone https://github.com/HyperSharkawa/bizyair-generate-image-plugin
   ```
2. 重启 MaiBot，确认启动日志中出现插件名 `bizyair_generate_image_plugin`。
3. 在配置文件中填写 `bizyair_client.bearer_token`，否则生图功能不可用。

## 配置

插件配置分为三个区块：

- `bizyair_client`：BizyAir 接口连接与参数映射配置
- `bizyair_generate_image_plugin`：生图动作行为与决策配置
- `variable_llm_config`：自定义变量 LLM 生成配置

### `bizyair_client` 字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `bearer_token` | `string` | `""` | BizyAir 的 Bearer Token。**必须填写**，留空时生图动作不可用。 |
| `openapi_url` | `string` | `"https://api.bizyair.cn/w/v1/webapp/task/openapi/create"` | BizyAir OpenAPI 的 HTTP 地址。通常无需修改。 |
| `openapi_web_app_id` | `int` | `50835` | BizyAir OpenAPI 的 web_app_id。对应你使用的 BizyAir 工作流应用 ID。 |
| `openapi_parameter_mappings` | `array<object>` | 见下方默认值 | OpenAPI 参数映射表。定义如何将变量映射到 BizyAir 的实际请求参数。 |

#### `openapi_parameter_mappings[]` 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `field` | `string` | OpenAPI 参数名，格式为 `节点ID:节点名.字段名`，例如 `18:BizyAir_NanoBananaProOfficial.prompt` |
| `value_type` | `string` | 参数值类型：`string` / `int` / `boolean` / `json` |
| `value` | `string` | 参数值模板，可引用决策参数 `{参数名}`、自定义变量 `{变量名}` 或内置变量 `{random_seed}` |
| `send_if_empty` | `bool` | 值为空时是否仍然传参。默认 `false`，即空值跳过该参数 |

### `bizyair_generate_image_plugin` 字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `timeout` | `float` | `180` | 调用 OpenAPI 和下载图片的超时时间（秒）。 |
| `send_text_before_image` | `bool` | `false` | 是否在发送图片前额外发送一段提示文本。 |
| `text_before_image` | `string` | `"我给你生成了一张图片"` | 发送图片前的提示文本，仅在开启 `send_text_before_image` 时生效。 |
| `enable_rewrite_failure_reply` | `bool` | `true` | 生图失败时，是否调用 LLM 将错误信息改写为自然语言后发送。 |
| `enable_splitter` | `bool` | `false` | 启用失败回复重写时，是否对重写结果启用分段发送。 |
| `action_parameters` | `array<object>` | 见下方默认值 | 生图动作允许决策传入的参数列表。 |
| `custom_variables` | `array<object>` | 见下方默认值 | 自定义变量列表。 |
| `action_require` | `string` | 见下方默认值 | 生图动作的决策提示词，每行一条，指导 LLM 何时使用该动作、如何填写参数。 |

#### `action_parameters[]` 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `string` | 参数名，例如 `prompt` |
| `description` | `string` | 参数说明，会展示给 LLM 帮助其理解参数用途 |
| `required` | `string` | `必填` 或 `选填` |

#### `custom_variables[]` 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `key` | `string` | 变量名，例如 `english_prompt` |
| `mode` | `string` | `literal`（直接使用字面值）或 `llm`（调用 LLM 生成） |
| `values` | `string` | 候选值列表，支持 JSON 数组字符串或每行一个值。可引用 `{参数名}` |
| `probability` | `float` | 触发概率（`0~1`），`1` 代表必定执行 |

### `variable_llm_config` 字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `llm_group` | `string` | `"utils"` | 自定义变量生成时使用的 LLM 模型分组。 |
| `llm_list` | `list[string]` | `[]` | 优先使用的模型名称列表。为空时使用 `llm_group` 对应配置。 |
| `max_tokens` | `int` | `512` | 自定义变量生成时使用的最大输出 token 数。 |
| `temperature` | `float` | `0.7` | 自定义变量生成时使用的温度。 |
| `slow_threshold` | `float` | `30` | 慢请求阈值（秒）。 |
| `selection_strategy` | `string` | `"balance"` | 模型选择策略：`balance`（负载均衡）或 `random`（随机）。 |

## 默认预设配置详解

插件自带了一套开箱即用的默认配置，理解它们有助于你快速上手或按需修改。

### 1. 决策参数（`action_parameters`）

默认定义了三个参数：

| 参数名 | 必填 | 说明 |
| --- | --- | --- |
| `prompt` | 必填 | 用于生成图片的描述词。LLM 会根据用户输入填写此字段。 |
| `aspect_ratio` | 选填 | 图片宽高比，必须是 `1:1`、`4:3`、`16:9`、`9:16`、`auto` 之一，默认 `1:1`。 |
| `resolution` | 选填 | 图片分辨率，必须是 `1K`、`2K`、`4K`、`auto` 之一，默认 `1k`。 |

LLM 在决策生图时，会根据这些参数的描述来填写对应的值。

### 2. 自定义变量（`custom_variables`）

默认预设了一个变量 `english_prompt`：

```toml
[[bizyair_generate_image_plugin.custom_variables]]
key = "english_prompt"
mode = "llm"
values = "[\"这是一个用于画图的提示词。请将其变成更适合画图ai的英文标签形式。你的输出会被直接输入到绘图ai中，因此请直接输出内容，不要添加多余的解释。以下是提示词: {prompt}\"]"
probability = 1
```

**含义**：
- 变量名为 `english_prompt`
- 模式为 `llm`，即会调用 LLM 来生成这个变量的值
- `values` 中只有一条候选值，其中引用了 `{prompt}`（即 LLM 填写的决策参数）
- 运行时，插件会把 `{prompt}` 替换为实际的描述词，然后发送给 LLM，让 LLM 将中文描述翻译为适合绘图 AI 使用的英文标签形式
- `probability = 1` 表示必定触发



### 3. 参数映射（`openapi_parameter_mappings`）

默认预设了三条映射规则：

```toml
[[bizyair_client.openapi_parameter_mappings]]
field = "18:BizyAir_NanoBananaProOfficial.prompt"
value_type = "string"
value = "{english_prompt}"

[[bizyair_client.openapi_parameter_mappings]]
field = "18:BizyAir_NanoBananaProOfficial.aspect_ratio"
value_type = "string"
value = "{aspect_ratio}"

[[bizyair_client.openapi_parameter_mappings]]
field = "18:BizyAir_NanoBananaProOfficial.resolution"
value_type = "string"
value = "{resolution}"
```

**含义**：
- 将 `english_prompt` 变量的值映射到 BizyAir 工作流中 `BizyAir_NanoBananaProOfficial` 节点的 `prompt` 字段
- 将 `aspect_ratio` 决策参数映射到 `aspect_ratio` 字段
- 将 `resolution` 决策参数映射到 `resolution` 字段
- `field` 的格式为 `节点ID:节点名.字段名`，需要与你 BizyAir 工作流中的实际节点对应

### 4. 决策提示词（`action_require`）

默认预设了多条决策规则，用于指导 LLM 何时使用生图动作、如何填写 `prompt` 参数。核心规则包括：

- 当用户明确要求画图、生成图片时使用该动作
- 当图片比纯文字更适合满足需求时使用
- `prompt` 参数只传入与图片生成直接相关的内容，不要传入称呼、寒暄等无关内容
- 如果用户已给出具体详细的图片描述，必须保持原样、一字不差，不允许改写
- 如果用户要求自由发挥，则由 LLM 补全 prompt，但不得擅自修改用户已明确指定的内容
- 如果用户描述过于宽泛，则自动补充合理的细节内容

这些规则确保 LLM 在生图时能正确处理用户的各种输入方式。

## 完整运行流程

下面从 **Bot 进行了一个生图决策** 开始，完整介绍插件的运行流程，并在每个步骤中说明相关配置项是如何工作的。

### 步骤 1：LLM 决策是否生图

当用户发送消息后，MaiBot 的 LLM 会根据 `action_require` 中的决策提示词判断是否需要调用生图动作。

**配置项作用**：
- `action_require`：告诉 LLM 什么情况下应该使用生图动作。例如用户说"帮我画一只猫"，LLM 识别到画图意图，决定调用 `generate_image` 动作。

### 步骤 2：LLM 填写决策参数

LLM 决定生图后，会根据 `action_parameters` 中定义的参数列表和描述，填写对应的参数值。

**配置项作用**：
- `action_parameters`：定义了 LLM 可以填写的参数有哪些、每个参数的含义、哪些是必填。例如 LLM 会填写 `prompt`（必填），可选填写 `aspect_ratio` 和 `resolution`。
- 如果用户说了"画一张横图的猫"，LLM 会根据 `aspect_ratio` 的描述知道应该填 `16:9`。

### 步骤 3：解析自定义变量

插件收集 LLM 填写的决策参数后，开始解析 `custom_variables` 中定义的变量。

**配置项作用**：
- `custom_variables`：对于每个变量，先从 `values` 中随机抽取一条候选值，并将将抽到的值中的占位符（如 `{prompt}`）替换为实际决策参数值。如果 `mode` 为 `literal` ，则将该文本直接作为该变量的值;如果 `mode` 是 `llm`，则将该文本发送给 LLM ，LLM 的输出内容为最终变量值。
- `probability`：在解析变量前会做概率判定，未通过则直接返回空值。
- `variable_llm_config`：控制调用 LLM 生成变量值时使用的模型、温度、最大 token 等参数。

**以默认配置为例**：
- 变量 `english_prompt` 的 `values` 中有一条模板，包含 `{prompt}` 占位符
- 插件将 `{prompt}` 替换为 LLM 填写的实际描述词
- 然后调用 LLM，让 LLM 将中文描述翻译为英文绘图标签
- 得到 `english_prompt` 的最终值

### 步骤 4：构建 OpenAPI 请求参数

插件将决策参数和自定义变量的值合并为模板上下文，然后根据 `openapi_parameter_mappings` 构建最终发送给 BizyAir 的 `input_values`。

**配置项作用**：
- `openapi_parameter_mappings`：每条映射定义了一个 BizyAir 参数的字段名、值类型、值模板。插件会将值模板中的占位符（如 `{english_prompt}`、`{aspect_ratio}`）替换为实际值。
- `value_type`：决定最终值的类型转换方式（字符串、整数、布尔值或 JSON 对象）。
- `send_if_empty`：如果替换后的值为空，是否仍然传参。默认 `false` 即空值跳过。
- `{random_seed}`：内置变量，每次调用自动生成一个随机整数，可用于需要随机种子的场景。

**以默认配置为例**：
- `18:BizyAir_NanoBananaProOfficial.prompt` 的值会被设置为 `english_prompt` 变量的值（即 LLM 翻译后的英文提示词）
- `18:BizyAir_NanoBananaProOfficial.aspect_ratio` 的值会被设置为 `aspect_ratio` 决策参数的值
- `18:BizyAir_NanoBananaProOfficial.resolution` 的值会被设置为 `resolution` 决策参数的值

### 步骤 5：调用 BizyAir OpenAPI

插件使用构建好的 `input_values` 调用 BizyAir OpenAPI 创建生图任务。

**配置项作用**：
- `bizyair_client.bearer_token`：用于 API 认证的 Bearer Token。
- `bizyair_client.openapi_url`：API 请求地址。
- `bizyair_client.openapi_web_app_id`：对应 BizyAir 中的工作流应用 ID。
- `bizyair_generate_image_plugin.timeout`：请求超时时间（秒）。

### 步骤 6：下载图片

BizyAir 返回任务结果后，插件从返回的 URL 下载图片数据。

**配置项作用**：
- `timeout` 同样适用于图片下载阶段。

### 步骤 7：发送图片

图片下载完成后，插件将图片发送到聊天会话。

**配置项作用**：
- `send_text_before_image`：如果为 `true`，会在发送图片前先发送一段提示文本。
- `text_before_image`：定义这段提示文本的内容，默认为"我给你生成了一张图片"。

### 步骤 8：失败处理（可选）

如果上述任何步骤发生错误（如 API 调用失败、图片下载失败、发送失败等），插件会进入失败处理流程。

**配置项作用**：
- `enable_rewrite_failure_reply`：如果为 `true`（默认），插件会调用 LLM 将技术错误信息改写为简洁自然的中文回复发送给用户。例如将 `"ConnectionError: timeout"` 改写为 `"抱歉，图片生成超时了，请稍后再试~"`。
- `enable_splitter`：如果为 `true`，改写后的回复会使用分段发送功能（适用于较长的错误说明）。
- 如果 `enable_rewrite_failure_reply` 为 `false`，则直接发送原始错误信息。

## 高级用法

### 添加更多决策参数

在 `action_parameters` 中添加新的参数定义，LLM 就可以在决策时填写这些参数。例如添加一个 `style` 参数控制画风：

```toml
[[bizyair_generate_image_plugin.action_parameters]]
name = "style"
description = "可选，图片风格。例如：二次元、写实、水彩、油画等"
required = "选填"
```

然后在 `openapi_parameter_mappings` 中添加对应的映射规则即可。

### 添加更多自定义变量

在 `custom_variables` 中添加新的变量。例如添加一个固定风格提示：

```toml
[[bizyair_generate_image_plugin.custom_variables]]
key = "style_hint"
mode = "literal"
values = '["masterpiece, best quality, highres", "anime style, vibrant colors"]'
probability = 0.8
```

- `mode = "literal"` 表示直接使用 `values` 中的值，不调用 LLM
- 每次会从 `values` 中随机抽取一个
- `probability = 0.8` 表示 80% 概率触发，20% 概率返回空值

### 修改参数映射以适配不同的 BizyAir 工作流

`openapi_parameter_mappings` 中的 `field` 字段需要与你 BizyAir 中使用的 app 对应。如果你使用了不同的 app ，需要修改 `field` 的值以匹配你的 app 。

### 使用多个候选值模板

`custom_variables` 的 `values` 支持多条候选值，每次随机抽取一条。例如：

```toml
[[bizyair_generate_image_plugin.custom_variables]]
key = "english_prompt"
mode = "llm"
values = """[
  "请将以下描述转换为英文绘图标签: {prompt}",
  "Translate this to English image generation tags: {prompt}",
  "Convert to AI art prompt tags: {prompt}"
]"""
probability = 1
```

每次会随机选择其中一条提示词模板发送给 LLM，增加生成结果的多样性。

## 常见问题

- **生图动作不触发**：
  - 检查 `bizyair_client.bearer_token` 是否已填写
  - 检查 `action_require` 是否包含适合你使用场景的决策规则
  - 查看日志确认 LLM 是否正确识别了生图意图
- **报错"插件未配置 bearer_token"**：
  - 在 `bizyair_client` 区块中填写 `bearer_token`
- **生成的图片不符合预期**：
  - 调整 `action_require` 中的决策提示词，更精确地指导 LLM 如何填写 `prompt`
  - 修改 `custom_variables` 中的 LLM 提示词模板，优化翻译效果
  - 检查 `openapi_parameter_mappings` 中的 `field` 是否与 BizyAir 工作流节点匹配
- **报错"模板中引用了未定义的变量"**：
  - 检查 `openapi_parameter_mappings` 中的 `{变量名}` 是否在 `custom_variables` 或 `action_parameters` 中有对应定义
- **LLM 翻译效果不好**：
  - 调整 `variable_llm_config` 中的模型配置，使用更强的模型
  - 修改 `custom_variables` 中的 `values` 提示词模板
- **生图超时**：
  - 增加 `bizyair_generate_image_plugin.timeout` 的值
  - 检查 BizyAir API 服务状态
- **失败回复太长或太技术化**：
  - 确保 `enable_rewrite_failure_reply = true`
  - 检查 LLM 连接是否正常

## 后续开发计划

| 功能 | 说明 | 状态 |
| --- | --- | --- |
| **决策参数引用自定义变量** | 让 LLM 在决策参数中可以直接引用用户设置的自定义变量，实现更灵活的参数组装 | 🚧 计划中 |
| **变量间相互引用** | 允许自定义变量之间相互引用，以制定更强大的工作流 | 🚧 计划中 |
| **更多内置变量** | 添加群聊内最近的聊天上下文、当前时间、当前日程等内置变量，丰富决策上下文 | 🚧 计划中 |
| **条件判断功能** | 支持数字大小、文本字数、文本包含/不包含、正则表达式匹配、LLM 判断等条件，根据判断结果选择不同的变量值 | 🚧 计划中 |
| **变量持久化** | 提供全局 KV 缓存功能，可以把"想留给下次任务使用的信息"存到变量中，在下次任务里读取，实现生图上下文连贯性 | 🚧 计划中 |

> ⚙️ 修改配置后需重启 MaiBot 生效。
