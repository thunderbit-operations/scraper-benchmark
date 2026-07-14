# lxml Review Research Materials

Date: 2026-07-14。能力/保真测试本机实跑；计时/内存分布**复用 selectolax pack**（同机同 venv，benchmarks as-of 2026-07-13）。

Status: 未来 Thunderbit 单工具评测文章的证据底稿。**不是终稿，不得原样发布。**

## 这是「视角评测」，不是重测

lxml 已在 **selectolax pack 里作为对照库被完整测过**（计时 / 内存 / CSS / 鲁棒 / 编码，as-of 2026-07-13）。本 pack **不重跑那些计时 benchmark**（会 CPU 争抢污染 + 重复劳动）；而是：

1. **复用** selectolax pack 已有的 lxml 计时/内存分布数据，引用时标「同实验台 selectolax bench 复用，as-of 2026-07-13」并指向具体文件字段。**本 pack 自己不产任何计时数。**
2. **以 lxml 为主角**重组视角（不再是 selectolax 的对照附庸）。
3. **补 lxml 特有维度**（信息增益——selectolax 没覆盖、lxml 独有的能力）：XPath 全能力、两套 API、iterparse 流式、命名空间、XPath vs CSS、深度上限 + huge_tree、读写 DOM/序列化/生命周期。这些是**非计时的能力/保真测试**，用 selectolax 的 venv 实跑（纯 Python 秒级，不涉计时对比）。

### Material Boundary

证据面：`lxml`（`lxml/lxml`，libxml2/libxslt 的 Python 绑定）。本 pack 含：一套 **37 项 XPath 特性矩阵**（预注册预期集 + 找茬 pass）、**两套 API（etree 严格 / html 宽容 / recover）行为对照**、**iterparse 流式的有界内存证明**（峰值 RSS + 已知重锚点校准）、**12 项命名空间处理**（RSS/SVG/默认 NS）、**XPath vs cssselect 能力缺口量化**、**11 个真实脏页上 lxml.html 的保真度 + 与复用 lxml 计数交叉核对**、**读写 DOM/序列化/编码/节点生命周期能力核验**、**深度上限 + huge_tree 旁路**。计时/内存分布**全部复用** selectolax pack。终稿的结构、截图、角度、Thunderbit 定位留给后续写作阶段。

所有能力测试在一台机器（macOS arm64 / Python 3.14.2 / lxml 6.1.1 / libxml2 2.14.6）上，脚本见 `tests/`；每个 `artifacts/raw/*.json` 字段由运行计算，非手写。未测项进 **Gaps**。

### 怎么读 findings

每条 `FINDING-NN` 带两个标签：

- **置信度**：`[triple-run]`（复用 selectolax 三 run 分布数据，仅计时/内存类）、`[single-observation]`（本 pack 单次能力测量——能力测试是确定性的布尔/枚举，单次即稳定）、`[hypothesis]`（提机制但未做归因实验）；
- **新颖性**（来自 §新颖性核验的预注册搜索）：`[EXCLUSIVE]`、`[KNOWN-ISSUE: link]`、`[DOCUMENTED: link]`。

**诚实前置**：lxml 是 20 年老库（2011 建仓，底层 libxml2 更久），XPath / 两套 API / iterparse / 命名空间行为**全是官方文档明载**。本 pack **没有任何 EXCLUSIVE 独家**——这对一个成熟库是正常的，不硬造独家。本 pack 的贡献是**系统化、可复现、量化、把复用数据组织成 lxml 视角**，不是「发现秘密」。

## Source Snapshot

lxml 由 Stefan Behnel 维护，定位为 *"the most feature-rich and easy-to-use library for processing XML and HTML in the Python language"*（[lxml.de](https://lxml.de/)）。它是 C 库 **libxml2 + libxslt** 的 Python 绑定，提供 ElementTree 兼容 API、完整 **XPath 1.0**、XSLT 1.0、schema 校验等。

Point-in-time 元数据（GitHub API + PyPI，抓于 **2026-07-14**）：

| Field | Value |
|---|---|
| Repo | [lxml/lxml](https://github.com/lxml/lxml) |
| Stars | **3,043** |
| Forks | **620** |
| Open issues | **16** |
| License | **BSD-3-Clause** |
| Default branch | **master** |
| Created | **2011-02-11** |
| Last push | **2026-07-02** |
| PyPI stable tested | **6.1.1**（2026-05-18） |
| PyPI Python requirement | **`>=3.8`** |
| Bundled engine | **libxml2 2.14.6** + libxslt 1.1.43（wheel 静态链接） |
| GitHub 上更新的 tag | **7.0.0a3**（alpha，2026-06-16，未上 stable PyPI） |

原始快照：[github_repo_snapshot_2026-07-14.json](artifacts/raw/github_repo_snapshot_2026-07-14.json)。

### License / 安装

- **BSD-3-Clause**（比 selectolax 干净：selectolax binding 是 MIT 但 wheel 里捆 LGPL-2.1 Modest + Apache-2.0 Lexbor；lxml 捆的 libxml2/libxslt 均为 **MIT** 许可，全链条宽松无 copyleft）。
- lxml 发布预编译 wheel（静态链接 libxml2/libxslt），`pip install lxml` 一般**不需要系统 libxml2、不需要编译器**——与从源码编译不同。安装事实见 [install-note.log](artifacts/logs/install-note.log)（未在本 pack 重新安装，因为复用了 selectolax 的 venv 以保证计时口径完全一致）。

## 新颖性核验（预注册搜索）

每条候选 finding 写下前，都搜了三处：上游 issue tracker（lxml **及底层 libxml2**）、官方文档/FAQ、SERP 前 ~20。分类 `EXCLUSIVE`（三处零命中）、`KNOWN-ISSUE`（有 issue，附链）、`DOCUMENTED`（文档已载，附链）。

| 候选 finding | 判定 | 记录 |
|---|---|---|
| XPath 支持轴/谓词/函数（`text()`/`contains()`/`starts-with()`/`position()`/`last()`）、命名空间绑定 | **DOCUMENTED** | [lxml XPath and XSLT](https://lxml.de/xpathxslt.html)（"lxml supports XPath 1.0 ... in a standards compliant way"）；ElementTree API |
| XPath 2.0-only 语法（`matches()`/序列/`if-then`/`except`）不被支持、被引擎报错 | **DOCUMENTED** | 同上（明示 XPath **1.0**，非 2.0）；SERP 多处（Saxon 才有 2.0）。libxml2 XPath 1.0 引擎的直接后果 |
| XPath 无默认命名空间概念，必须绑前缀 | **DOCUMENTED** | [lxml XPath docs](https://lxml.de/xpathxslt.html)（"XPath does not have a notion of a default namespace. The empty prefix is therefore undefined for XPath"） |
| 两套 API：`lxml.etree`（严格 raise）vs `lxml.html`（宽容）+ `recover=True` 容错 | **DOCUMENTED** | [lxml.html 文档](https://lxml.de/lxmlhtml.html)、[parsing 文档](https://lxml.de/parsing.html)（`recover` 选项） |
| `iterparse` 增量解析 + fast_iter（`elem.clear()` + 删前序兄弟）有界内存 | **DOCUMENTED** | [lxml parsing 文档 iterparse](https://lxml.de/parsing.html#iterparse-and-iterwalk)；Stefan Behnel 本人博客 [faster XML stream processing](http://blog.behnel.de/posts/faster-xml-stream-processing/)；经典 fast_iter 模式（Liza Daly / IBM developerWorks） |
| 深嵌套（>256 层）静默丢内容；`huge_tree=True` 可抬升 | **KNOWN-ISSUE / DOCUMENTED** | libxml2 默认 256 层嵌套上限是 **DoS 安全防护**，`XML_PARSE_HUGE` 旁路——[lxml launchpad #65510](https://answers.launchpad.net/lxml/+question/65510)；selectolax pack 的 adversarial.json 也已记录 lxml `has_deep=false`（as-of 2026-07-13）。本 pack 精确化了「默认上限 + huge_tree 恢复 + 第二道更硬天花板」 |
| XML 声明里编码别名 `latin-1` 报错、规范名 `ISO-8859-1` 正确 | **DOCUMENTED** | 编码声明处理是 lxml 已载设计（[launchpad #613302](https://bugs.launchpad.net/lxml/+bug/613302)、[#1703810](https://bugs.launchpad.net/lxml/+bug/1703810)）；libxml2 用 IANA 规范编码名。别名 vs 规范名的具体对比是本 pack 补的细节，但根因文档已载 |
| lxml 在非 UTF-8 bytes 上正确恢复口音字符（对照 selectolax 静默损坏） | **DOCUMENTED**（对照来自 selectolax pack） | selectolax pack §ENC 已把 lxml 记为干净参照；本 pack 直接复现 lxml 侧 `café éè` |

**给写作者：本 pack 无独家。** 所有行为都能在 lxml 文档 / libxml2 / issue tracker 找到根。价值在**把它们系统化测出来 + 量化 + 用 lxml 视角组织 + 接上复用的计时数据**，措辞必须是「文档已载 / 已知问题的可复现量化」，不是「发现」。

## 测试环境

| Item | Value |
|---|---|
| Machine | macOS arm64（Apple Silicon） |
| Python | **3.14.2** |
| lxml | **6.1.1**（prebuilt `cp314` wheel） |
| libxml2 / libxslt | **2.14.6 / 1.1.43**（wheel 内静态链接） |
| cssselect | **1.4.0**（XPath vs CSS 对照用） |
| venv | **复用 `../selectolax/.venv`** —— 与复用的计时数据是**同一环境**，口径完全一致 |
| Scripts | `tests/`（见 Raw Artifact Index） |

环境日志：[environment.log](artifacts/logs/environment.log)。

> **为什么复用 venv**：selectolax pack 的计时/内存分布就是在这个 venv（lxml 6.1.1 / libxml2 2.14.6 / Py 3.14.2）里测的。本 pack 的能力测试也在同一 venv 跑，保证「复用的计时数」与「本 pack 的能力测」环境零漂移。能力测试是确定性的（布尔/枚举），不受这台机器负载影响，因此单次运行即稳定。

## 1. XPath 全能力矩阵（lxml 的杀手锏；selectolax / bs4 都无原生 XPath）

**37 项**预注册矩阵：轴 / 谓词 / 内建函数 / 返回类型 + **5 项找茬 pass**（XPath 2.0-only 语法，预期不支持）。**每条预期集在跑之前写死在源码里**（反偏向，方法论 v3 §9）；PASS = 返回值 exactly equal 预期。数据：[xpath_matrix.json](artifacts/raw/xpath_matrix.json)，脚本 [xpath_matrix.py](tests/xpath_matrix.py)。

| 类别 | 覆盖 | 结果 |
|---|---|---|
| 轴 axes | child / descendant / parent / ancestor / following-sibling / preceding-sibling / self / attribute / following / preceding | 10/10 PASS |
| 谓词 predicates | index `[1]` / `last()` / `position()<n` / 属性等值 / 属性存在 / and / or / 嵌套 `[.//a]` / `not()` | 9/9 PASS |
| 内建函数 functions | `text()` / `contains()` / `starts-with()` / `count()` / `string-length()` / `normalize-space()` / `concat()` / `substring()` / `name()` / `string()` | 10/10 PASS |
| 返回类型 return | boolean / number 标量返回 | 3/3 PASS |
| **找茬 pass** | `matches()`（2.0）/ 序列 `(1,2,3)`（2.0）/ `if-then-else`（2.0）/ `except`（2.0）/ 语法错误 | **5/5 正确拒绝（报错，非静默错集）** |

**FINDING-01 [single-observation] [DOCUMENTED: [lxml XPath docs](https://lxml.de/xpathxslt.html)]:** lxml 的 `xpath()` 在 32 项功能性 case（轴 / 谓词 / 函数 / 返回类型）上**全部 PASS**，且在 5 项找茬 case 上**全部正确报错**——`matches()`、序列表达式、`if/then/else`、`except` 这些 XPath 2.0-only 语法被 libxml2 的 XPath 1.0 引擎**抛 `XPathEvalError` 拒绝，而不是静默返回错集**。所以这是**找茬后的满分**（37/37），不是构造满分。这是 lxml 相对 selectolax（CSS-only，无任何 XPath，见 §4）的**头号能力护城河**。

> **闸门自查（预期集写错 → 改 harness，非怪 lxml）**：初版预期把 `//div[.//a[@href]]` 写成命中 `{wrap, ft}`，跑出来只有 `{wrap}`。核查发现 `ft` 是 `<footer>` 不是 `<div>`——是**我的预期写错**，非 lxml 错。依方法论 Part6§4 先排除 harness 问题，改正预期集后 PASS。这条留在源码注释里作为诚实记录。

## 2. 两套 API：`lxml.etree`（严格）vs `lxml.html`（宽容）+ recover 容错

同一畸形输入喂三条路径，预注册每条的**预期行为类别**（raises / recovers / accepts），行为标签**由运行时 `error_log` 计算**（非硬编码）。数据：[two_api_behavior.json](artifacts/raw/two_api_behavior.json)，脚本 [two_api_behavior.py](tests/two_api_behavior.py)。

| 畸形输入 | etree 严格 | etree recover=True | lxml.html 宽容 |
|---|---|---|---|
| 未闭合标签 `<root><a>x</root>` | **raises** | recovers（吞错恢复） | accepts |
| 错误嵌套 `<b><i></b></i>` | **raises** | recovers | accepts |
| 未定义实体 `&nbsp;` | **raises** | recovers | accepts |
| 裸 `&`（`Tom & Jerry`） | **raises** | recovers | accepts |
| 多根 `<a>1</a><b>2</b>` | **raises** | recovers | accepts |
| well-formed XML | accepts | accepts（0 错） | accepts |
| HTML 布尔属性 `<input disabled>` | **raises** | recovers | accepts |

预注册 **7/7 全部符合**。

**FINDING-02 [single-observation] [DOCUMENTED: [lxml.html](https://lxml.de/lxmlhtml.html) / [parsing](https://lxml.de/parsing.html)]:** lxml 提供**三档解析严格度**，行为清晰可预测：`lxml.etree`（严格 XML）对 6 类畸形输入**全部 raise `XMLSyntaxError`**；同一 parser 加 `recover=True` 则**吞错并尽力恢复**（且 `parser.error_log` 里能枚举被吞的每个错误——lxml 独有的诊断能力，selectolax 无错误日志）；`lxml.html`（宽容 HTML）对同样输入**全部接受**。判据由 `error_log` 长度驱动：well-formed 输入在 recover 模式下 `error_log` 为空、被正确归类为 accepts（非 recovers）。**实践含义**：需要「严格校验，坏了就报错」用 `lxml.etree`；需要「脏 HTML 尽力抓」用 `lxml.html`；需要「宽容但要知道哪儿坏了」用 `recover=True` + 读 `error_log`。selectolax 只有一档（宽容），无严格模式、无错误日志。

> 闸门自查：初版 `classify()` 把任何 `recover=True` 结果都标 recovers，导致 well-formed 输入被误判。改成**按实测 `error_log` 是否非空**判定后 7/7 符合——分类判据本身也做到由运行数据驱动（闸门3）。

## 3. iterparse 流式解析 —— selectolax 完全无此能力

selectolax 只吃整串 `str`（whole-string parse），**无增量/流式接口**。lxml 的 `iterparse` 能在文档未读完时就吐已闭合元素，配合 fast_iter 模式（`elem.clear()` + 删前序兄弟）实现**有界内存**。

本测试**不产计时数**，测的是**内存特性**：300,000 条 `<record>` 的 XML（约 15 MB），三个 subject 各在**独立进程**跑，用**峰值 RSS**（`ru_maxrss`）度量。用高水位合法（方法论 Part6§3）：每个 subject 全新进程（无前序高负载致盲），且 `full_parse`（已知把整树载入）作**已知重锚点**证明仪器对量级差敏感。数据：[iterparse_streaming.json](artifacts/raw/iterparse_streaming.json)，脚本 [iterparse_streaming.py](tests/iterparse_streaming.py)。

| 模式 | 峰值 RSS delta（代表性运行） | 说明 |
|---|---:|---|
| `iterparse` + clear（fast_iter，有界） | **~1-2 MB** | 处理完即释放，常驻不随条目数增长 |
| `iterparse` 不 clear（累积） | ~386 MB | 保留引用不释放——和全载一样重 |
| `etree.parse`（全载，**校准锚点**） | ~386 MB | 已知重；证明仪器读得出量级差 |

（RSS 有 allocator 噪声，有界档在 ~1-2 MB 抖动、全载/不 clear 在 ~386 MB 抖动；比值稳定在 **0.3-0.4% 量级**。以量级差判定，非小数位。当前 JSON 值见 [iterparse_streaming.json](artifacts/raw/iterparse_streaming.json)。）

**FINDING-03 [single-observation] [DOCUMENTED: [lxml iterparse 文档](https://lxml.de/parsing.html#iterparse-and-iterwalk) / [Behnel blog](http://blog.behnel.de/posts/faster-xml-stream-processing/)]:** `iterparse` + fast_iter 处理 30 万条记录（约 15 MB）时峰值 RSS delta 仅 **~1-2 MB**，是一次性全载（~386 MB）的 **0.3-0.4% 量级**（比值 ~0.003-0.004）；且首个 record 事件在文档读完前就产出（`got_event_before_eof: true`）——真增量。**反例对照**：同样 iterparse 但不 clear，常驻涨到 ~386 MB（≈全载），证明**关键在 clear**、不在 iterparse 本身。校准锚点 `full_parse`（~386 MB）读数远高于有界模式，证明该 RSS 仪器对「全载 vs 有界」的量级差是敏感的（不是失明读 0）。**这是 lxml 相对 selectolax 的一个硬能力差**：selectolax 无流式接口，超内存文档只能靠 lxml 这类流式解析器。

## 4. XPath vs CSS 能力缺口量化（对 selectolax CSS-only 的直接增益）

lxml 同时给 `.xpath()` 和 `.cssselect()`（后者经 cssselect 把 CSS 翻成 XPath）。本测试量化「XPath 能表达、cssselect 不能」的具体缺口——即 lxml 相对 CSS-only 工具（selectolax）的核心增益。预注册每条 XPath 预期命中；cssselect 那侧探测「能不能做到」。数据：[xpath_vs_css.json](artifacts/raw/xpath_vs_css.json)，脚本 [xpath_vs_css.py](tests/xpath_vs_css.py)。

| 目标 | XPath | CSS（cssselect）可行？ |
|---|---|---|
| 按文本内容筛（`contains(text(),"bargain")`） | ✅ | ❌ 无文本谓词 |
| 按子节点反选父（`//b/parent::p`） | ✅ | ❌ 无父选择器 |
| 直接取属性值作结果（`//a/@href`） | ✅ | ❌ 只能返回元素 |
| 直接取文本节点（`//p/text()`） | ✅ | ❌ 不能返回文本节点 |
| 祖先轴（`//td/ancestor::div`） | ✅ | ❌ 无向上导航 |
| 按子元素计数筛父（`//ul[count(li)=4]`） | ✅ | ❌ 无计数谓词 |
| 按文本长度筛（`string-length(text())>5`） | ✅ | ❌ 无字符串长度谓词 |
| `nth-child` / `last-child` / 相邻兄弟 | ✅ | ✅（3 项 baseline，两者都行） |

**FINDING-04 [single-observation] [DOCUMENTED]:** 在 10 项目标里，**7 项 CSS 根本无法表达**（文本内容筛选、父/祖先导航、属性值/文本节点抽取、计数谓词），只有 3 项 CSS 有等价（`nth-child`/`last-child`/相邻兄弟）——XPath 全 10/10 PASS。selectolax 是 **CSS-only**（selectolax pack §2 已证其 `xpath()` 不存在、`::text` 也不支持），因此这 7 类查询在 selectolax 里要么绕成多步 Python 循环、要么做不到。**这是「从 selectolax 迁到 lxml 能多做什么」的量化答案**，也是 selectolax pack 说的「XPath 是最大迁移墙」的反向证据。

> 闸门自查：`string-length>5` 初版预期误写 `[]`，实际 `second`(6)/`fourth`(6) 命中 → 改正为 `{l2,l4}`。又一处 harness 预期写错、非工具错。

## 5. 命名空间处理（RSS / SVG / 默认 NS）—— selectolax（HTML-only）覆盖不到

12 项命名空间 case，含 RSS（content:encoded / dc:creator / atom:link 三命名空间）、SVG（默认 NS + xlink）、默认命名空间 XML。预注册每条命中数，运行时计数。数据：[namespaces.json](artifacts/raw/namespaces.json)，脚本 [namespaces.py](tests/namespaces.py)。**12/12 PASS。**

**FINDING-05 [single-observation] [DOCUMENTED: [lxml XPath namespaces](https://lxml.de/xpathxslt.html)]:** lxml 正确处理真实多命名空间文档——RSS 里 `//dc:creator/text()` 精确取到 `["Alice","Bob"]`、`//atom:link/@href`、`//content:encoded`（跨三个命名空间）；SVG 里 `//s:rect` + `//s:use/@xlink:href`（第二命名空间）；`QName` 把 Clark notation `{uri}local` 拆成 localname/namespace；`nsmap` 内省。**已载的关键坑**：XPath **没有默认命名空间概念**——对 `xmlns="urn:..."` 的文档，`//book`（不绑前缀）命中 **0**，必须绑一个人工前缀（`//c:book` + `namespaces={"c":...}` → 命中 3）或用 `//*[local-name()='book']`（命中 3）。这不是 bug 而是 XPath 规范 + lxml 文档明示的行为。selectolax 是 HTML5-only，不处理任意 XML 命名空间，这整个维度对它不适用。

## 6. 真实脏 HTML —— lxml.html 保真度 + 与复用 lxml 计数交叉核对

**复用** selectolax pack 的 11 个已入库真实抓取（`../selectolax/fixtures/real/`，as-of 2026-07-10），以 lxml 为主角测 `lxml.html` 宽容解析器的保真与容错（非计时）。数据：[real_world_lxml.json](artifacts/raw/real_world_lxml.json)，脚本 [real_world_lxml.py](tests/real_world_lxml.py)。

| Fixture | 大小 | links | libxml2 恢复错误数 | 严格 XML |
|---|---:|---:|---:|---|
| news_bbc.html | 398 KB | 255 | 4 | **ok** |
| docs_mdn_array.html | 243 KB | 508 | 0 | raised |
| wiki_scraping.html | 227 KB | 460 | 0 | raised |
| gov_whitehouse.html | 289 KB | 154 | 0 | raised |
| oldstyle_craigslist.html | 561 KB | 351 | 0 | raised |
| forum_reddit.html | 129 KB | 318 | 0 | raised |
| docs_python.html | 80 KB | 341 | 2 | raised |
| ecommerce_books.html | 51 KB | 94 | 0 | raised |
| news_hackernews.html | 35 KB | 229 | 0 | raised |
| ecommerce_webscraper_allinone.html | 16 KB | 35 | 0 | raised |
| spa_quotes_js.html | 6 KB | 5 | 0 | raised |

**FINDING-06 [single-observation] [DOCUMENTED: [lxml.html](https://lxml.de/lxmlhtml.html)]:** 11 个真实页 `lxml.html` **全部成功解析（11/11）**，抽取的 link/heading/img 计数与**复用的 selectolax pack lxml 计数 11/11 完全一致**（交叉核对 `all_crosscheck_match: true`）——证明本 pack 的复用口径与 selectolax pack 对齐、apples-to-apples。**副发现**：严格 XML 解析器对 **10/11** 页 raise（真实网页普遍非 well-formed，靠 libxml2 HTML 恢复模式吃下），唯独 **BBC News（Next.js 渲染）well-formed 到严格 XML 都能过**——不是所有「HTML」都需要恢复路径。

**FINDING-06a [single-observation] [DOCUMENTED（harness 口径差异，非 lxml 行为）]:** docs_python.html 上 `//a[@href]`（属性存在计）得 343，而 selectolax pack 的 `if n.get("href")`（真值计）得 341——差的 2 个是 **`href=""` 空串链接**。这是**计数口径差异（属性存在 vs 真值），非 lxml 行为差异**；对齐口径后交叉核对一致。抓取时值得知道：空 href 是否计入取决于你的过滤谓词。（selectolax pack 也记过一处 parsel +2 的同类口径差。）

## 7. 深度嵌套上限 + huge_tree 旁路（精确化 selectolax pack 的 FINDING-11a）

selectolax pack 记录 lxml 在 1000/5000 深 `<div>` 下 `has_deep=false`（复用来源：其 adversarial.json，as-of 2026-07-13），当时框成「lxml 静默丢最深内容」。本 pack 用**默认 parser vs `huge_tree=True`**对照，把它从「疑似 bug」精确化为「libxml2 的 DoS 安全上限，可配置抬升」。数据：[depth_limit.json](artifacts/raw/depth_limit.json)，脚本 [depth_limit.py](tests/depth_limit.py)。

| 请求深度 | 默认 parser 实际可达 | huge_tree=True 实际可达 |
|---:|---:|---:|
| 300 | 253（丢内容） | **299（恢复）** |
| 1000 | 253（丢内容） | **999（恢复）** |
| 5000 | 253（丢内容） | 2045（**仍丢**） |

**FINDING-07 [single-observation] [KNOWN-ISSUE / DOCUMENTED: [lxml launchpad #65510](https://answers.launchpad.net/lxml/+question/65510)]:** lxml 默认 parser 在**约 253 层**截断嵌套并静默丢更深内容——这是 **libxml2 的 DoS 防护默认上限（~256 层）**，不是 bug。`huge_tree=True` 能**完全恢复**深度 300 和 1000（`XML_PARSE_HUGE` 旁路该上限）；但深度 5000 时即便 huge_tree 也只到 2045——存在**第二道更硬的 libxml2 递归天花板**，huge_tree 也吃不满。**机制 [DOCUMENTED]**：256 层是安全设计（防递归 DoS）。**动作项**：解析可信来源的深层标记时用 `lxml.html.HTMLParser(huge_tree=True)`。这把 selectolax pack「lxml 静默丢深内容」的**现象**补上了**机制 + 可配置解法 + 二级天花板**——是本 pack 对复用数据的信息增益。

## 8. 读写 DOM / 序列化 / 编码 / 节点生命周期

非计时能力核验，每步断言。数据：[api_capabilities.json](artifacts/raw/api_capabilities.json)，脚本 [api_capabilities.py](tests/api_capabilities.py)。

**读写 DOM（8/8 PASS）**：`SubElement`/`insert`/`remove`/`replace`、`strip_tags`（去标签保内容）、`strip_elements`（连内容删）、`drop_tree`（lxml.html 专有）、**text/tail 模型**（`<p>head<b>bold</b>tail</p>` → `p.text="head"`, `b.text="bold"`, `b.tail="tail"`——lxml 的经典双文本槽模型）。lxml 是完整读写树。

**序列化（5/5 PASS）**：`tostring(method="xml")`、`tostring(method="html")`（void 元素不自闭合）、`pretty_print`、**C14N 规范化**（`method="c14n"`——lxml 独有的标准化序列化，selectolax 无）、round-trip 保真。

**FINDING-08 [single-observation] [DOCUMENTED（对照源自 selectolax pack §ENC）]:** 非 UTF-8 bytes 上，**lxml 正确恢复口音字符**：`"<p>café éè</p>".encode("latin-1")` 经 `lxml.html.fromstring` 得回 **`café éè`**（无 U+FFFD 替换符、无丢字节）。这直接复现 selectolax pack §ENC 里 lxml 作为「干净参照」的角色——**对照 selectolax 两引擎在同输入上的静默损坏**（Lexbor → `caf� ��` 替换符；Modest → `caf ` 丢字节；见 selectolax [encoding_probe.json](../selectolax/results/encoding_probe.json)）。lxml 的编码恢复（libxml2 charset 检测）更稳。

**FINDING-08a [single-observation] [DOCUMENTED: [lxml launchpad #613302](https://bugs.launchpad.net/lxml/+bug/613302)]:** XML 声明里的编码**别名**处理严格：`encoding="latin-1"`（别名）→ `etree.fromstring` 抛 `XMLSyntaxError: Unsupported encoding: latin-1`；`encoding="ISO-8859-1"`（IANA 规范名）→ 正确解出 `café`。libxml2 只认规范编码名。根因（编码声明处理）文档已载；「别名 vs 规范名」的具体对比是本 pack 补的操作细节。

**FINDING-09 [single-observation] [DOCUMENTED]:** 节点生命周期（stale-handle 安全）——三个场景在**独立子进程**跑（硬崩溃=非零退出），实测 `hard_crash: false`：① 持节点让树 GC 后仍可用（`node.text` 正常，lxml 靠节点持树引用防 use-after-free）；② `drop_tree()` 后句柄仍可读；③ `remove()` 后节点 `getparent() is None` 且仍可用。无 segfault。与 selectolax pack 的 FINDING-17（selectolax 也无 stale-handle 崩溃）一致——两库在这点都安全。

## 复用了 selectolax pack 的哪些数据（计时 / 内存，本 pack 自己不产）

以下全部**引用**自 selectolax pack（同机 / 同 venv / lxml 6.1.1 / libxml2 2.14.6，benchmarks as-of 2026-07-13），本 pack **未重跑**。汇总见 [lxml-test-summary.json](artifacts/raw/lxml-test-summary.json) 的 `reused_selectolax_timing_for_lxml` 段（该段字段由 build_summary.py 从复用 JSON 计算，非手写）。

**解析速度（复用，as-of 2026-07-13）**：

| 维度 | lxml 数值 | 复用来源字段 |
|---|---|---|
| 纯解析 p50（10MB） | **77.9 ms**（比 selectolax-Lexbor 快 ~33-34%；换算 Lexbor 慢 ~50%） | [bench_isolate.json](../selectolax/results/bench_isolate.json) `parse_only.10mb.lxml` |
| 全任务 parse+extract p50（1MB / 10MB） | 14.18 ms / 172.9 ms（100KB/1MB 与 Lexbor 打平；10MB Lexbor 反超 8%） | [bench_parse.json](../selectolax/results/bench_parse.json) `results.*.lxml` |
| 100k 节点 CSS 吞吐 | **3,002,646 nodes/s**（三 C 引擎里最快档，与 Modest 打平、比 Lexbor 快 ~15%、比 parsel/bs4 快 ~6-7x） | [bench_isolate.json](../selectolax/results/bench_isolate.json) `throughput_100k.lxml` |
| 两套 lxml API 交叉核对 | `lxml.html.fromstring` 与 `lxml.etree.HTMLParser` 两 API 在 100KB/1MB/10MB 互差 <4%，都比 Lexbor 快 | [etree_crosscheck.json](../selectolax/results/etree_crosscheck.json) |

**内存 / 导入（复用）**：

| 维度 | lxml 数值 | 复用来源字段 |
|---|---|---|
| 10MB RSS delta（tracemalloc OFF） | **128.9 MB**（六解析器里最省，比 bs4 省 ~1.7x） | [bench_memory_import.json](../selectolax/results/bench_memory_import.json) `memory_rss.page_10mb.html.lxml` |
| import 冷启动 | 14.1 ms（与 selectolax 相当，比 bs4/parsel 快 ~2.3x） | 同上 `import_cold.lxml.html` |

**生产维度（复用，single-observation）**：

| 维度 | lxml 数值 | 复用来源字段 |
|---|---|---|
| 4 线程 wall-clock 加速比 | **1.21x**（gil_release_signal: inconclusive，共享默认 parser 场景） | [production_dims.json](../selectolax/results/production_dims.json) `thread_scaling.lxml` |
| 2000 次 parse+drop 内存增长 | `no_monotonic_growth_bounded_working_set`（有界，无泄漏） | 同上 `mem_growth.lxml` |

**FINDING-10 [triple-run（复用 selectolax 三 run）] [DOCUMENTED: [lxml FAQ threading](https://lxml.de/FAQ.html)]:** 复用数据显示 lxml 4 线程加速比 **1.21x（inconclusive）**——但这是**共享默认 parser**的场景。lxml FAQ 明载：**GIL 在解析时释放的条件是「用默认 parser（每线程复制）或每线程自建 parser」**，而**共享 parser 会串行化访问**。本 pack 结构性核验了这个条件的 API 面（非计时）：`XMLParser.copy()` 存在、`get/set_default_parser` 存在、`XPathEvaluator` 有内部锁（[api_capabilities.json](artifacts/raw/api_capabilities.json) `thread_api_surface`）。**所以「lxml 线程加速只有 1.21x」的正确读法是「在未按 FAQ 做 per-thread parser 的默认共享路径下」**，不是 lxml 的能力上限。**机制是文档明载 [DOCUMENTED]，加速比数值是复用观测 [single-observation]**；per-thread parser 下的加速比本 pack 未测（Gaps——那会是新的计时测量，本 pack 不产计时数）。

## Key Findings for the Writer

1. **XPath 是头号护城河（FINDING-01, -04）**：37/37 找茬后满分；相对 selectolax（CSS-only）有 **7 类 CSS 表达不出的查询**（文本筛选、父/祖先导航、属性/文本节点抽取、计数谓词）。这是「为什么选 lxml 而非 selectolax」的核心。（§1, §4）
2. **三档解析严格度（FINDING-02）**：etree 严格 raise / recover 吞错+error_log / lxml.html 宽容——selectolax 只有宽容一档、无错误日志。（§2）
3. **iterparse 流式（FINDING-03）**：30 万条记录峰值 RSS 仅 ~1-2 MB（全载的 0.3-0.4% 量级），且增量产出——**selectolax 无此能力**，超内存文档的硬差异。（§3）
4. **命名空间（FINDING-05）**：RSS/SVG/多 NS 全 PASS；默认 NS 必须绑前缀（文档已载行为）。selectolax HTML-only 不适用此维度。（§5）
5. **深度上限精确化（FINDING-07）**：默认 ~253 层截断=libxml2 DoS 防护；`huge_tree=True` 恢复到 ~2045，5000 有二级天花板。补齐 selectolax pack 现象的机制+解法。（§7）
6. **编码（FINDING-08, -08a）**：lxml 正确恢复 latin-1 口音（对照 selectolax 静默损坏）；XML 声明编码名要规范（`ISO-8859-1` 行、`latin-1` 别名报错）。（§8）
7. **速度/内存（复用，FINDING-10 + 复用表）**：纯解析比 selectolax-Lexbor 快 ~33-34%；100k 吞吐三 C 引擎最快档；10MB RSS 最省（比 bs4 省 1.7x）；线程 1.21x 但受 FAQ 的 per-thread-parser 条件约束。**全部复用，本 pack 零计时产出。**
8. **许可更干净**：BSD-3-Clause + 捆的 libxml2/libxslt 均 MIT，全链宽松无 copyleft（对照 selectolax wheel 捆 LGPL-2.1 Modest）。
9. **无独家**：lxml 是 20 年老库，所有行为文档/issue 已载——本 pack 价值是系统化+量化+lxml 视角+接复用数据，不是「发现」。

## 维度级证据（无合成总分）

按方法论 v3 Part3，本 pack **不出单一加权 0-100 分**。逐维给证据由写作者加权：

| 维度 | 证据（本 pack 实测 / 复用） | 读者注意 |
|---|---|---|
| XPath 全能力 | 37/37 找茬后满分（本 pack 实测） | selectolax 完全无 XPath |
| XPath vs CSS 缺口 | 7/10 目标 CSS 表达不出（本 pack 实测） | 迁移增益的量化 |
| 两套 API / 容错 | 严格/recover/宽容三档 7/7 符合（本 pack 实测） | selectolax 仅宽容一档 |
| 流式 iterparse | 30 万条峰值 RSS ~1-2MB=全载 0.3-0.4% 量级（本 pack 实测） | selectolax 无流式 |
| 命名空间 | RSS/SVG/多 NS 12/12（本 pack 实测） | 默认 NS 须绑前缀 |
| 真实脏页保真 | 11/11 解析成功，与复用 lxml 计数 11/11 一致（本 pack 实测） | 10/11 需 HTML 恢复模式 |
| 深度上限 | 默认~253 截断，huge_tree 恢复到~2045（本 pack 实测） | 二级天花板存在 |
| 读写 DOM / 序列化 | 8/8 + 5/5（含 C14N，本 pack 实测） | 完整读写树 |
| 编码 | latin-1 口音正确恢复；编码名须规范（本 pack 实测） | 对照 selectolax 静默损坏 |
| 节点生命周期 | 3 场景无硬崩溃（本 pack 子进程实测） | 与 selectolax 一样安全 |
| 纯解析速度 | 比 Lexbor 快 ~33-34%（**复用** as-of 2026-07-13） | 单平台 macOS arm64 |
| 100k CSS 吞吐 | 3.0M nodes/s，三 C 引擎最快档（**复用**） | 与 Modest 打平 |
| 内存 | 10MB RSS 128.9MB 最省（**复用**） | tracemalloc OFF 口径 |
| 线程/GIL | 4 线程 1.21x（**复用**）；GIL 释放须 per-thread parser（文档） | 共享 parser 会串行化 |
| 许可 | BSD-3 + libxml2/libxslt MIT（快照核实） | 全链宽松 |
| 维护 | 3k stars，2026-07 push，stable 6.1.1（快照核实） | 有 7.0 alpha |

## Gaps Before Final Blog Draft

- **计时全靠复用**：本 pack 自身零计时产出。所有速度/内存/线程数字都是 selectolax pack 的 lxml 行（macOS arm64 / Py 3.14 / 单平台），继承其全部 Gaps（尤其「lxml 纯解析更快」是 counter-consensus、需 Linux x86_64 复核）。
- **per-thread parser 的线程加速**：FAQ 说 GIL 释放要 per-thread parser，但复用的 1.21x 是共享 parser 场景；per-thread parser 下的真实加速比**未测**（那需新的计时测量，本 pack 不产计时数）——留给专门的计时 pack。
- **iterparse 深度 vs 更大文档**：测了 30 万条（~15 MB）的内存有界性；未测 GB 级真实 XML、未测 `iterparse` 在 HTML（vs XML）上的行为、未做多小时 soak。
- **XSLT / schema 校验 / EXSLT**：lxml 的 XSLT 1.0、RelaxNG/XMLSchema/DTD 校验、EXSLT 扩展**完全未测**（这些是 lxml 相对 selectolax 的又一大能力面，但超出「抓取解析」核心，留给后续）。
- **huge_tree 二级天花板的确切值**：观测到 5000 深时 huge_tree 只到 2045，但未定位 libxml2 的确切递归上限常量。
- **7.0.0 alpha**：只测了 stable 6.1.1；7.0.x alpha 行为未测。
- **Windows / 源码构建 / free-threaded 3.14t**：均未测。
- **XPath 变量 / 自定义扩展函数 / `XPath` 预编译对象复用**：矩阵测了内建函数，未测 `etree.XPath(expr)` 预编译复用、`XPathEvaluator` 变量传参、Python 自定义 XPath 扩展函数。

## Raw Artifact Index

Scripts（`tests/`）：
- XPath 特性矩阵（预注册 + 找茬）：[xpath_matrix.py](tests/xpath_matrix.py)
- 两套 API 行为：[two_api_behavior.py](tests/two_api_behavior.py)
- iterparse 流式内存：[iterparse_streaming.py](tests/iterparse_streaming.py)
- 命名空间：[namespaces.py](tests/namespaces.py)
- XPath vs CSS 能力缺口：[xpath_vs_css.py](tests/xpath_vs_css.py)
- 真实脏页 lxml.html + 交叉核对：[real_world_lxml.py](tests/real_world_lxml.py)
- API/序列化/编码/生命周期：[api_capabilities.py](tests/api_capabilities.py)
- 深度上限 + huge_tree：[depth_limit.py](tests/depth_limit.py)
- 汇总生成器（从 raw 计算，不手写）：[build_summary.py](tests/build_summary.py)
- 全跑 runner：[run_all.py](tests/run_all.py)

Raw results（`artifacts/raw/`）：[xpath_matrix.json](artifacts/raw/xpath_matrix.json)、[two_api_behavior.json](artifacts/raw/two_api_behavior.json)、[iterparse_streaming.json](artifacts/raw/iterparse_streaming.json)、[namespaces.json](artifacts/raw/namespaces.json)、[xpath_vs_css.json](artifacts/raw/xpath_vs_css.json)、[real_world_lxml.json](artifacts/raw/real_world_lxml.json)、[api_capabilities.json](artifacts/raw/api_capabilities.json)、[depth_limit.json](artifacts/raw/depth_limit.json)，生成的 [lxml-test-summary.json](artifacts/raw/lxml-test-summary.json)。元数据：[github_repo_snapshot_2026-07-14.json](artifacts/raw/github_repo_snapshot_2026-07-14.json)。

Logs（`artifacts/logs/`）：[run_all.log](artifacts/logs/run_all.log)、[environment.log](artifacts/logs/environment.log)、[install-note.log](artifacts/logs/install-note.log)，及各脚本单跑 log。

Fixtures：`artifacts/fixtures/big_records.xml`（iterparse 用，由脚本生成）。**复用**的真实脏页：`../selectolax/fixtures/real/*.html`（11 个，as-of 2026-07-10，只读引用未改）。

复用来源（只读，本 pack 未重跑）：`../selectolax/results/`（bench_isolate / bench_parse / bench_memory_import / etree_crosscheck / production_dims / real_world / encoding_probe .json）。

Public reproducible copy（计划）：`github.com/thunderbit-operations/scraper-benchmark` → `tools/lxml/`（唯一 repo；本 pack 未自行 push，改动留工作区待主会话统一提交）。

## Complete Source Index

- [lxml GitHub repository](https://github.com/lxml/lxml) — Tier 1（源码、许可、版本）
- [lxml.de 官网 / 文档](https://lxml.de/) — Tier 1
- [lxml XPath and XSLT](https://lxml.de/xpathxslt.html) — Tier 1（XPath 1.0、默认 NS 须绑前缀、命名空间映射）
- [lxml parsing 文档](https://lxml.de/parsing.html) — Tier 1（recover、iterparse、huge_tree）
- [lxml.html 文档](https://lxml.de/lxmlhtml.html) — Tier 1（宽容 HTML、drop_tree）
- [lxml FAQ — threading / GIL](https://lxml.de/FAQ.html) — Tier 1（GIL 释放条件、per-thread parser）
- [Stefan Behnel — faster XML stream processing](http://blog.behnel.de/posts/faster-xml-stream-processing/) — Tier 1（iterparse fast_iter，作者本人）
- [lxml launchpad #613302 — unicode strings with declared encoding](https://bugs.launchpad.net/lxml/+bug/613302) — Tier 1（编码声明处理）
- [lxml launchpad #1703810 — encoding edge](https://bugs.launchpad.net/lxml/+bug/1703810) — Tier 1
- [lxml launchpad #65510 — XML_PARSE_HUGE / 深度上限](https://answers.launchpad.net/lxml/+question/65510) — Tier 1（huge_tree / DoS 上限）
- [libxml2](https://gitlab.gnome.org/GNOME/libxml2) — Tier 1（底层引擎，MIT）
- selectolax pack 复用来源（同 repo `tools/selectolax/`，as-of 2026-07-13）：bench_isolate / bench_parse / bench_memory_import / etree_crosscheck / production_dims / real_world / encoding_probe .json，及 fixtures/real/。
