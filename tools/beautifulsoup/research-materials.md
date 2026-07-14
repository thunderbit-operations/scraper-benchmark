# BeautifulSoup 评测研究材料

日期: 2026-07-14 (计时/内存/GIL 分布数据复用 selectolax 同实验台 bench, as-of 2026-07-13; bs4 特有能力/保真/容错测试于本日实跑)

状态: 未来某篇 Thunderbit 博客文章的**素材**。这**不是**成稿, 不得原样发布。

## 材料边界

本 pack 是对 **BeautifulSoup** (`beautifulsoup4`, 亦称 bs4) 的单工具评测证据库。bs4 是 Python 生态里最广为人知的 HTML/XML 解析封装库 —— 它本身**不解析**, 而是把多个底层解析器 (`html.parser` 内置 / `lxml` / `html5lib`) 包在一套统一、极友好的树导航与检索 API 之下。

**这是一份「视角评测」, 不是重测。** BeautifulSoup 已在 **selectolax pack 里作为对照库被完整测过** —— 计时 (`bs4_htmlparser` / `bs4_lxml` 跨 5 页尺寸 3-run 分布)、内存 (RSS / tracemalloc 分进程)、CSS (soupsieve 41 例矩阵)、鲁棒、编码、GIL 信号都已有数据。本 pack 的立场:

1. **复用**那批 bs4 数据, **绝不重跑任何计时 benchmark** (避免 CPU 争抢污染 + 重复劳动)。所有计时/内存/GIL 结论都引用 `tools/selectolax/results/*.json` 的具体字段, 标注「同实验台 selectolax bench 复用, as-of 2026-07-13」。**本 pack 自己不产任何计时数字。**
2. **主角化 bs4**: selectolax pack 里 bs4 是被比较的慢对照; 这里 bs4 是主角。bs4 的核心权衡是**「最友好 API + 最强容错 vs 最慢」**—— 用复用的 selectolax 分布数据把「慢」量化 (比 C 解析器慢 ~10–17x), 诚实呈现权衡, 不回避。
3. **补 bs4 特有维度** (非计时的能力/保真度测试, 于本 pack 的 `.venv` 实跑, 纯 Python 秒级): 三后端畸形 HTML 修复矩阵、API 易用性能力矩阵、UnicodeDammit 编码嗅探、引用环 GC 行为、soupsieve 扩展覆盖、三后端真实页一致性。

所有 bs4 特有测试在一台机器上跑 (macOS arm64 / Python 3.14.2), 可从 `tests/` 脚本复现。失败按失败记录。未测项进 **Gaps**。`artifacts/raw/*.json` 里每个结果字段都由运行算出, 非手写 (闸门 3); 汇总由 [build_summary.py](tests/build_summary.py) 从原始 JSON 派生。

### 如何读 findings

findings 编号 `FINDING-NN`, 带两个 tag:

- **置信** tag —— `[triple-run]` (复用 selectolax 的 3-run 分布数据 / 或被 ≥2 处独立检查佐证)、`[single-observation]` (本 pack 单次测得)、`[hypothesis]` (提出机制但未做归因实验); 以及
- **novelty** tag (来自预注册搜索, 见 §Novelty 核验) —— `[EXCLUSIVE]`、`[KNOWN-ISSUE: 链接]`、`[DOCUMENTED]`。

本文档不用自评形容词修饰任何 finding; novelty 由搜索表决定, 不由形容词决定。**预告结论: 本 pack 零 EXCLUSIVE。** bs4 是 20 年老库, 所测行为要么官方文档明载, 要么社区公开记录 —— 这很正常, 核心叙事是量化的权衡, 不是独家发现。

## Source Snapshot

BeautifulSoup 由其作者定位为一个 *"screen-scraping library"* —— 从 HTML/XML 里提取数据的容错解析封装。它的招牌是「面对烂到浏览器都皱眉的 HTML 也能把你要的数据捞出来」。

点位元数据 (从 PyPI 于 **2026-07-14** 拉取; 快照 [pypi_snapshot_2026-07-14.json](artifacts/raw/pypi_snapshot_2026-07-14.json)):

| 字段 | 值 |
|---|---|
| 包名 | `beautifulsoup4` |
| 测试版本 | **4.15.0** (上传 **2026-06-07**) |
| PyPI Python 要求 | **`>=3.7.0`** |
| License | **MIT** |
| 规范 home | [crummy.com/software/BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/) |
| 源码 / bug tracker | Launchpad ([git.launchpad.net/beautifulsoup](https://git.launchpad.net/beautifulsoup), [bugs.launchpad.net/beautifulsoup](https://bugs.launchpad.net/beautifulsoup)) —— **非 GitHub** |
| 维护状态 | 活跃 (4.15.0 于 2026-06 发布, 近一年 6 个版本) |

> **元数据口径注**: bs4 与本系列其它工具不同, 它的规范托管不在 GitHub 而在 crummy.com + Launchpad。因此 stars/forks 这类 GitHub 指标对 bs4 无意义, 不列; 维护活跃度以 PyPI 发布频率佐证。

### License / 依赖分层值得一提

bs4 **封装本身**是 MIT。但它的容错能力取决于底层后端, 而后端 License 各异: `html.parser` 是 Python 标准库 (PSF License, 零额外依赖); `lxml` 是 BSD, 但底层 libxml2/libxslt 是 MIT, 且是**外部 C 依赖** (需编译或预编译 wheel); `html5lib` 是 MIT 纯 Python。对合规敏感的读者: "用 bs4" 到底引入什么 License 取决于你装了哪个后端 —— 只装内置 `html.parser` 时依赖面最干净。

## Novelty 核验 (预注册搜索)

任何 finding 写下前, 每个候选都搜了三处: 上游 bug tracker (bs4 的 Launchpad + bs4 官方文档自身即最权威规范)、官方文档相关页、SERP 前 ~20。分类 `EXCLUSIVE` (三处零命中)、`KNOWN-ISSUE` (公开记录, 给链接)、`DOCUMENTED` (文档明载)。完整搜索证据: [novelty_search_2026-07-14.json](artifacts/raw/novelty_search_2026-07-14.json)。

| 候选 finding | 判定 | 先行记录 |
|---|---|---|
| html.parser 不实现 optional-end-tag: 未闭合 `<td>`/`<li>` 被嵌套而非闭合, 文本渗漏 | **DOCUMENTED** | bs4 文档 "Differences between parsers" 明列 html.parser "less lenient than html5lib" + `<a></p>` 三后端示例; [lxml.de/elementsoup](https://lxml.de/elementsoup.html) 述 lxml 更宽容。本 pack 贡献 = 预注册畸形矩阵量化到具体 case |
| 重复属性: html.parser 保留后者, lxml/html5lib 保留前者 | **KNOWN-ISSUE (半载)** | bs4 自 4.9.1 起 `on_duplicate_attribute` 文档化 html.parser 侧行为 (REPLACE=保留后者); 文档**未**并列 lxml/html5lib 侧; HTML5 规范规定保留前者。故非独家, 判半载 |
| UnicodeDammit 短 latin-1/cp1252 样本误判 (cp720/cp862); 跟随错误声明 | **DOCUMENTED** | bs4 文档 Encoding 节给出几乎同款示例 (短 ISO-8859-8 被误判 ISO-8859-7) + "越多数据猜得越准"; DOS-box-drawing 与 Latin-1 代码点重叠是公开难题 |
| bs4 树是父子引用环, GC 关时 del 不回收, 需 GC/decompose | **DOCUMENTED** | bs4 文档明述 "objects are very densely interconnected, exactly the sort ... a garbage collector would have trouble with"; decompose 文档述 "break circular references"。selectolax pack 方法论段亦点名 |
| 三后端良构真实页抽取一致; 三后端均 flatten `<template>` (MDN 508) | **DOCUMENTED (复用 FINDING-14 镜像)** | selectolax pack `template_repro.json` 已记录 bs4 两后端 + lxml + Modest 均得 508, 仅 Lexbor 得 497 |
| `get_text(strip=True)` 逐节点拼接丢空格 | **DOCUMENTED** | bs4 文档 get_text 节; selectolax pack 记录同款 strip-space 跨库共性 |
| soupsieve 支持 `:lang`/`:-soup-contains`/`:is`/`:where`/`:has(>a)` | **DOCUMENTED** | soupsieve 官方文档逐条列出; selectolax pack 已记录 soupsieve 41/41 |

**统计: EXCLUSIVE 0 / KNOWN-ISSUE 1 / DOCUMENTED 6。** 对写作的意义: bs4 pack 的价值**不在**独家发现, 而在 (a) 把「慢」用同实验台分布数据量化成可信倍数, (b) 用预注册畸形矩阵把「三后端容错差异」从文档的定性描述做成可判定的量化结果, (c) 用校准过的仪器量化引用环 GC 规模。任何把 bs4 行为写成「独家/无人提及」的措辞都是错的。

## 官方能力声明待核验

来自 bs4 文档 (Tier 1):

1. 三后端可选 (`html.parser` / `lxml` / `html5lib`), 宽容度递增、速度递减, "different parsers will create different parse trees from the same document"。
2. `find` / `find_all` / `select` (CSS via soupsieve) / tree 导航 (`.parent` / `.next_sibling` / `.children` / `.strings`) / `.get_text()` 全套友好 API。
3. `UnicodeDammit` 自动嗅探编码并转 Unicode。
4. `decompose()` / `extract()` 拆解引用环以释放内存。

四条都在下文核验 (§1 三后端矩阵 / §2 API / §3 编码 / §4 GC)。

## 测试环境

| 项 | 值 |
|---|---|
| 机器 | macOS arm64 (Apple Silicon), macOS 26.5 |
| Python | **3.14.2** (与 selectolax pack 同一实验台) |
| beautifulsoup4 | **4.15.0** |
| 后端 | `html.parser` (标准库) / `lxml` **6.1.1** / `html5lib` **1.1** |
| CSS 引擎 | soupsieve **2.8.4** |
| 编码检测 | chardet **7.4.3** (可用; UnicodeDammit 会用它) |
| 安装 | 本 pack 独立 venv (`tools/beautifulsoup/.venv`) + `pip install beautifulsoup4==4.15.0 lxml==6.1.1 html5lib soupsieve==2.8.4 chardet` |
| 安装结果 | 干净; 全预编译 wheel (含 lxml cp314), 无需编译。安装日志 [pip-install.log](artifacts/logs/pip-install.log) |
| bs4 特有测试脚本 | `tests/` (见 Raw Artifact Index) |
| 复用的计时/内存数据来源 | `tools/selectolax/results/` (只读引用, 同实验台, as-of 2026-07-13) |

安装注:

- bs4 是**纯封装库**: 无浏览器下载、无 setup/doctor。三后端里 `html.parser` 零额外依赖 (标准库自带), 装 bs4 即可用; `lxml`/`html5lib` 是可选后端。
- **`bs4.__version__` 存在, 返回 `'4.15.0'`** (对照 selectolax pack 的 `__version__` 探针; [api_surface.json](artifacts/raw/api_surface.json) → `has_version_attr: true`)。

## 复用方法论 (数字从哪来)

本 pack **不产任何计时数字**。§1 的所有速度/内存/GIL 结论都从 selectolax pack 的原始 JSON 派生, 该 pack 的计时纪律 (3 独立进程 run + 跨 run 方差、parity 内容哈希断言、RSS 与 tracemalloc 分进程、GC 全程开、已知泄漏校准) 见其 research-materials.md。本 pack 只做**纯 Python 秒级、无 CPU 争抢**的能力/保真/容错测试 (§2–§6), 无需进程隔离计时。

- **复用来源精确到字段**: bs4 计时 = `bench_parse.json → results.{size}.{bs4_htmlparser,bs4_lxml}.p50_ms.median_across_runs`; 内存 = `bench_memory_import.json → memory_rss.page_10mb.html.{...}.rss_delta_mb.median_across_runs`; GIL = `production_dims.json → thread_scaling.bs4_lxml`; soupsieve 基础矩阵 = `css_coverage.json → cases[].soupsieve`。派生倍数 (bs4 相对 C 解析器慢多少) 由 [build_summary.py](tests/build_summary.py) 计算, 见 [beautifulsoup-test-summary.json](artifacts/raw/beautifulsoup-test-summary.json)。

---

## 1. 速度与内存 —— bs4 的代价, 用同实验台分布数据量化 (全部复用)

> 本节零本地测量。所有数字复用 `tools/selectolax` 的 3-run 分布 (as-of 2026-07-13), 见上「复用方法论」。

### 1a. 解析+抽取全任务 (parse the string, 抽全部 `<h3 class="title">` + 全部 `<a href>`)

p50 中位延迟 (ms), median across 3 runs。来源 `bench_parse.json`; 派生倍数见 `beautifulsoup-test-summary.json → sections.reused_parse_extract_p50_ms`。

| 页 | bs4_htmlparser | bs4_lxml | selectolax_lexbor | lxml | bs4_hp 慢于 lexbor | bs4_lxml 慢于 lexbor |
|---|---:|---:|---:|---:|---:|---:|
| **1 KB** | 0.323 | 0.281 | 0.027 | 0.036 | 12.0x | 10.5x |
| **10 KB** | 2.049 | 1.705 | 0.160 | 0.166 | 12.8x | 10.7x |
| **100 KB** | 20.599 | 16.540 | 1.464 | 1.423 | 14.1x | 11.3x |
| **1 MB** | 232.558 | 181.855 | 14.901 | 14.177 | 15.6x | 12.2x |
| **10 MB** | 2788.746 | 2261.557 | 159.935 | 172.933 | 17.4x | 14.1x |

**FINDING-01 [triple-run] [DOCUMENTED-folklore]:** BeautifulSoup 是这组解析器里**最慢的**, 且慢得可量化。在真实的 parse+extract 任务上, **`bs4(html.parser)` 比 C 后端 selectolax-Lexbor 慢 ~12–17x** (随页面增大而拉大), **`bs4(lxml)` 慢 ~10.5–14x**。换用 `lxml` 后端能把 bs4 提速 ~1.2x, 但**仍慢一个数量级** —— 因为无论哪个后端, bs4 都要为每个节点建一个完整的 Python 对象 (Tag / NavigableString), 这层 Python 对象化开销是 C 解析器不付的。倍数随页面增大**单调上升** (1 KB 12.0x → 10 MB 17.4x), 说明这不是固定常数开销, 而是随节点数线性放大的每节点税。这一点与 selectolax pack FINDING-01 是同一枚硬币的两面 (那里以 selectolax 为主角说「快 12–17x」, 这里以 bs4 为主角说「慢 12–17x」), 数字同源。范围: macOS arm64 / Python 3.14。

> **诚实呈现权衡, 不回避「慢」**: bs4 慢是设计取舍的**必然结果**, 不是缺陷 —— 它换来的是下文 §2 的 API 友好度和 §3–§5 的容错。文章不应把「慢」藏起来; 应把「慢一个数量级」和「省下的开发时间/容错省心」并排放, 让读者按任务权衡。对绝大多数「抓几十到几千个页面、每页几百 KB」的脚本, 232 ms vs 15 ms 的绝对差 (1 MB 页) 往往无感; 对「百万页流水线」则致命。

### 1b. 100k 节点批量 CSS 查询吞吐 (复用)

来源 `bench_isolate.json → throughput_100k`。选出 10 万个 `<a>` 并读 href, 树预建。

| 解析器 | query p50 | nodes/sec |
|---|---:|---:|
| lxml | 33.30 ms | 3,002,646 |
| selectolax_modest | 34.19 ms | 2,924,550 |
| selectolax_lexbor | 39.46 ms | 2,534,027 |
| **bs4_lxml** | **250.56 ms** | **399,111** |

**FINDING-02 [triple-run] [DOCUMENTED]:** 在 10 万节点批量 CSS 选择上, **`bs4(lxml)` 吞吐 ~39.9 万 nodes/s, 比三个 C 引擎慢 ~6.3–7.5x** (lxml 300 万 / Modest 292 万 / Lexbor 253 万 nodes/s)。即使 bs4 底层用的就是 lxml, 走 soupsieve→bs4-Tag 这条路也比 lxml 原生 cssselect 慢一个数量级 —— 每个命中节点都要包成 Python Tag。所以「给 bs4 换 lxml 后端就和 lxml 一样快」是错的: 后端只加速**建树**, 查询/遍历仍付 bs4 的 Python 对象税。范围: 同上。

### 1c. 内存 + import 冷启动 (复用)

来源 `bench_memory_import.json` (10 MB 页, tracemalloc **OFF**; RSS 才是内存判据)。

| 解析器 | RSS delta (tracemalloc OFF) |
|---|---:|
| lxml | 128.9 MB |
| selectolax_lexbor | 144.6 MB |
| **bs4_lxml** | **218.4 MB** |
| **bs4_htmlparser** | **225.6 MB** |

**FINDING-03 [triple-run] [DOCUMENTED]:** **BeautifulSoup 用 ~1.5–1.75x 于 selectolax/lxml 的 RSS** (10 MB 文档): `bs4_lxml` 218.4 MB = selectolax-Lexbor 的 1.51x; `bs4_htmlparser` 225.6 MB = lxml 的 1.75x。这是 selectolax pack FINDING-05 的复用结论, 并**继承了那次校准**: 更早的「~3x」是 tracemalloc 开着测出的污染值, 关掉后真实倍数是 ~1.5–1.75x。bs4 仍是最重的, 只是没到 3x。机制同 §1a: 每节点一个 Python 对象。

**import 冷启动** (来源同): `bs4` **33.4 ms** vs `lxml.html` 14.1 ms —— **bs4 import 慢 ~2.36x**。对 CLI 工具 / serverless 冷启动是个小但真实的项 (来源 `beautifulsoup-test-summary.json → sections.reused_memory_import.bs4_import_over_lxml`)。

### 1d. GIL / 线程扩展信号 (复用, 单次观测)

来源 `production_dims.json → thread_scaling` (单次观测, 经验墙钟信号, 非源码断言)。1 MB 页解析 48 次, 单线程 vs 4 线程。

| 解析器 | 单线程 (s) | 4 线程 (s) | speedup | 信号 |
|---|---:|---:|---:|---|
| selectolax_lexbor | 0.563 | 0.159 | 3.54 | likely-releases-GIL |
| lxml | 0.459 | 0.378 | 1.21 | inconclusive |
| **bs4_lxml** | **6.945** | **26.842** | **0.26** | **likely-holds-GIL** |

**FINDING-04 [single-observation] [hypothesis on mechanism] [DOCUMENTED]:** **`bs4(lxml)` 多线程不但没加速, 反而变慢 (speedup 0.26, 即 4 线程比单线程慢 ~3.9x)** —— 经验信号 "likely holds GIL": bs4 的树构建是纯 Python, 在 GIL 下串行化, 再叠加线程调度开销, 越加线程越慢。对比 selectolax 两引擎跨 4 线程 ~3.5–3.9x 加速。**对自由线程 (free-threading) 时代的实务读法**: bs4 解析**不能靠多线程并行**, 要并行只能上多进程 (`ProcessPoolExecutor`); selectolax/lxml 才有线程并行空间。这是单线程数 (4) / 单页 (1 MB) 的墙钟信号, 机制 (哪段代码持 GIL) 是假说, 未经插桩验证。复用 selectolax pack FINDING-15 的 bs4 行。

---

## 2. API 易用性 / 树导航 / 检索能力矩阵 (本 pack 实跑) —— bs4 的卖点

> 本节起为本 pack **实跑**的非计时能力/保真测试。脚本 [api_surface.py](tests/api_surface.py) → [api_surface.json](artifacts/raw/api_surface.json)。29 个探针, 每个 `ok` 字段由运行时把实际返回与预期比对算出 (闸门 3)。

bs4 最被称道的是「上手即用、读起来像英语」的 API。本矩阵把它主打的 `find`/`find_all`/`select`/tree 导航/`get_text`/修改序列化逐个跑一遍, 用固定 fixture 验证返回。

**结果: 29/29 探针全过。** 覆盖:

- **检索**: `find(tag)` / `find_all(class_=)` / `find(id=)` / `find(attrs={...})` / `find_all(limit=)` / **`find(lambda t: ...)` 函数谓词** (bs4 特色, C 解析器无) —— 全部命中。
- **CSS via soupsieve**: `select("p.lead")` / 后代 `div#main a` / 子组合 `ul > li` / 属性 `a[href='/link1']` / `:nth-child(2)` / `select_one(".missing") → None` —— 全部正确。
- **tree 导航** (bs4 核心卖点): `.parent` / `.find_next_sibling` / `.find_all` 子元素 / `.descendants` / `.stripped_strings` / `.find_parent` 链式回溯 —— 全部正确。
- **`get_text` 变体**: 默认拼接 / `separator="|"` —— 正确。
- **修改 / 序列化** (bs4 是可读写 DOM): `decompose()` (删 `<b>` → `<p>Hello </p>`) / `new_tag()+append` / `unwrap()` —— 全部正确。

**FINDING-05 [single-observation] [DOCUMENTED]:** bs4 的检索/导航/修改 API 在 29 个探针上零意外, 包括 C 解析器**没有**的两个人体工学优势: (a) **`find`/`find_all` 接受任意函数谓词** (`soup.find(lambda t: t.name=="a" and "btn" in t.get("class",[]))`), 把复杂条件写成一行 Python, 无需先 select 再过滤; (b) **命名清晰的双向 tree 导航** (`.parent` / `.next_sibling` / `.find_parent` / `.stripped_strings`) 覆盖 selectolax 需要多步或不提供的遍历。这是 bs4 「换慢求省心」里「省心」那一半的实测支撑。

**两个陷阱 (与 selectolax 对照)**:

- **布尔属性口径不同**: `<input disabled>` 的 `disabled` 在 bs4 里回 **空串 `""`** (selectolax 回 `None`)。两者都 falsy, 所以 `if node.get("disabled")` 都会漏判存在的布尔属性; 稳妥判法一致: `"disabled" in tag.attrs`。([api_surface.json](artifacts/raw/api_surface.json) → `bool_attr_present_value: ""`)
- **`get_text(strip=True)` 丢词界**: 逐节点 strip 后无分隔拼接, `"...with "` + `"link1"` → `"withlink1"` (探针 `find_by_attr` 实测)。与 selectolax 的同款 strip-space 陷阱一致 (跨库共性, 非 bs4 独有)。要词界用 `separator=" "`。

---

## 3. 三后端畸形 HTML 修复矩阵 (本 pack 实跑, 预注册反偏向) —— bs4 的定位

> 脚本 [malformed_matrix.py](tests/malformed_matrix.py) → [malformed_matrix.json](artifacts/raw/malformed_matrix.json)。**方法论 v3 Part 3 §9 反偏向**: 15 条畸形样本先**写死一个后端无关的结构断言** (`expect` 谓词, 表达「修复后应满足什么」), 再跑三后端; 谁满足谁不满足由运行时算出 (`meets_expectation` 非手写常量)。断言在源码里预注册, 不预判赢家。

bs4 的招牌定位就是「宽容」。但**三个后端宽容程度不同** —— 这正是 bs4 用户最容易踩的坑: 默认 `html.parser` 和换 `lxml`/`html5lib` 会从同一段烂 HTML 建出**不同的树**。

**结果 (15 条预注册畸形样本, 各后端满足预期数)**:

| 后端 | 满足预期 / 15 |
|---|---:|
| **lxml** | **15** |
| **html5lib** | **15** |
| html.parser | 12 |

三条 divergent case (三后端不一致, id 由运行时算出): `broken_table` / `bare_li` / `dup_attr`。

**FINDING-06 [single-observation] [DOCUMENTED]:** 在预注册畸形矩阵上, **`lxml` 与 `html5lib` 各满足 15/15, 内置 `html.parser` 只满足 12/15** —— 且失分的三条都是**同一个根因**: html.parser **不实现 HTML5 的「隐式结束标签 (optional end tag)」规则**, 因此:

- **未闭合 `<td>` / `<li>` 被嵌套而非闭合**: `<table><tr><td>a<td>b<tr><td>c<td>d</table>` 在 html.parser 下抽出的单元格文本是 **`['abcd','bcd','cd','d']`** (每个 td 吞掉后面全部), 而 lxml/html5lib 正确得 `['a','b','c','d']`。裸 `<li>a<li>b<li>c` 同理: html.parser 得嵌套的 `['abc','bc','c']`, lxml/html5lib 得 `['a','b','c']`。([malformed_matrix.json](artifacts/raw/malformed_matrix.json) 的 `broken_table`/`bare_li`)
- **重复属性口径相反**: `<div id="first" id="second">` 在 **html.parser 保留后者 `"second"`**, lxml/html5lib 保留前者 `"first"` (HTML5 规范规定保留前者)。

**实务后果**: 一个「随手 `BeautifulSoup(html)` 用默认后端」的爬虫, 遇到**未闭合表格/列表**(旧站、手写 HTML、模板漏闭合极常见) 会把相邻单元格的文本**渗漏拼接**在一起, 抽出脏数据且**不报错**。换 `lxml` 或 `html5lib` 后端即修复。**这是 bs4 用户第一优先要知道的事**: 默认 `html.parser` 图零依赖, 但容错弱于另两个后端; 抓不规范 HTML 时应显式 `BeautifulSoup(html, "lxml")` 或 `"html5lib"`。此行为 bs4 文档 "Differences between parsers" 已定性明载 (html.parser "less lenient"), 本 pack 贡献是量化到具体 case。

**其余 12 条畸形样本三后端一致通过** (交叉错误嵌套 `<b><i></b></i>`、缺 html/body 骨架、未加引号属性、孤立闭合标签、script 内裸 `<`/`>`、未闭合注释、嵌套 form、大小写混合、残缺实体、块级嵌 inline、属性裸引号) —— 说明 bs4 的容错**整体确实强** (三后端都不崩、内容都可达), 分歧只集中在 optional-end-tag 这一类。

> **找茬 pass 已内建**: 矩阵里的 `broken_table`/`bare_li`/`dup_attr` 本身就是主动挑来暴露后端差异的敌意样本 (optional-end-tag 是 HTML5 里最容易被简易解析器跳过的规则); html.parser 的 12/15 是找茬之后的分数, 不是构造满分。

---

## 4. 引用环 / GC 行为 (本 pack 实跑, 仪器先校准) —— bs4 生产维度

> 脚本 [gc_refcycles.py](tests/gc_refcycles.py) → [gc_refcycles.json](artifacts/raw/gc_refcycles.json)。**方法论 v3 Part 6 §3 仪器先校准**: 用已知信号验证仪器测得出来, 再下结论。这是 selectolax pack 方法论段点名的 bs4 特有维度 (「bs4 循环引用树需 GC 回收」)。

bs4 的每个 `Tag` 同时持有对 parent 和对 children 的引用, 构成**引用环**。CPython 的引用计数**无法**立刻回收环, 必须靠分代 GC。本探针分三步, 每步结论字段运行时算出:

1. **校准环存在**: 直接验证 `child.parent` 指回父、`parent.contents` 含子 → `is_reference_cycle: true`。
2. **关 GC 循环建/删 300 次**, 数存活 Tag 对象。
3. **开 GC 重跑** + **无环对照组** (纯 list of str, 已知无环) 跑同样循环。

**结果 (对象计数, 仪器 = `gc.get_objects()` 里的 bs4 Tag 数)**:

| 场景 | del 后 (未 collect) 的 Tag 数 |
|---|---:|
| **GC 关** | **120,900** (300 次 × ~403 tags/树, **一个没回收**) |
| GC 开 | 26,598 (分代 GC 循环中已触发过, 峰值被压下) |
| 强制 `gc.collect()` 后 | **0** (全部回收) |
| **无环对照组** (list of str, GC 关) | **delta 0** (证明堆积来自 bs4 环, 非仪器噪声) |

**FINDING-07 [single-observation] [DOCUMENTED]:** bs4 解析树**确实是父子双向引用环** (校准确认), 后果实测:

- **GC 关闭时, `del soup` 完全不回收**: 300 次建/删循环后 **120,900 个 Tag 对象全部滞留** —— 引用环让引用计数失效。
- **`gc.collect()` 后归零**: 分代 GC 能回收环, 一次 collect 清空全部。
- **无环对照组 delta 0**: 证明上面的堆积是 bs4 的环造成的, 不是测量噪声 (仪器被证明既灵敏又不虚报)。

**实务后果**: 在**长跑循环里逐个解析大量页面**时, 若代码 (或某些高吞吐场景) 关了 GC 或 GC 触发不够频繁, bs4 树会因引用环滞留、内存持续涨; **每页用完显式 `soup.decompose()`** (bs4 文档专为此提供) 主动断环回收, 是 bs4 长跑流水线的推荐做法。selectolax/lxml 的 C 树无此问题。此行为 bs4 文档明载 ("densely interconnected ... a garbage collector would have trouble with"), 本 pack 贡献是用校准仪器量化滞留规模 (120,900 对象) 并证明 collect 后归零。

> 与 selectolax pack 对照: 那里对 selectolax/lxml 做了 2000 iters 的 RSS 泄漏检查, 结论「无单调增长 (bounded)」, 并用 +198 MB 已知泄漏校准仪器。bs4 未进那个 RSS 泄漏检查 (本 pack 不重跑计时), 但引用环 GC 是 bs4 特有、且是对象计数级 (非 RSS 级) 的确定性行为, 故本 pack 用对象计数仪器专测。RSS 级的 bs4 长跑软化曲线进 Gaps。

---

## 5. soupsieve CSS 扩展覆盖 (本 pack 实跑, 补 selectolax 矩阵之外)

> 脚本 [soupsieve_extended.py](tests/soupsieve_extended.py) → [soupsieve_extended.json](artifacts/raw/soupsieve_extended.json)。**不重跑** selectolax pack 已测的 41 例基础矩阵 (那里记录 **soupsieve 41/41 全过**, 是全组 CSS 引擎里唯一满分, 见下「复用」), 只补 bs4/soupsieve 文档主打、但基础矩阵未覆盖的 20 例扩展用法。用 lxml 后端建良构树 (避免 §3 的 html.parser 未闭合陷阱污染 CSS 判定)。

**结果: 20/20 全过。** 覆盖 selectolax-Lexbor **不支持**的、以及 soupsieve 独有的用法:

- **selectolax-Lexbor 报 UNSUPPORTED 的**: `:lang(en)` (本 pack `lang_pseudo` PASS) —— selectolax pack 记录 Lexbor 在 `:lang`/`:dir` 上 UNSUPPORTED, soupsieve 支持。
- **soupsieve 独有拼写**: `:-soup-contains('featured')` 文本匹配 (两例 PASS) —— 类似 Lexbor 的 `:lexbor-contains` 但 soupsieve 侧。
- **选择器组 / 复杂 `:not`**: `:is(h2,span)` / `:where(h2,span)` / `p:not(.featured):not(:has(a))` / `p:is(.body):not(.featured)` —— 全 PASS。
- **`:has` 变体**: `p:has(a)` 后代 + `p:has(> a)` 直接子 —— 全 PASS。
- **兄弟组合器**: `~` 通用兄弟 + `+` 相邻 —— PASS。
- **结构伪类**: `:nth-of-type` / `:first-child` / `:last-child` / `:only-child` / `:empty` / `:disabled` / `:enabled` —— 全 PASS。

**FINDING-08 [triple-run] [DOCUMENTED]:** soupsieve (bs4 的 CSS 引擎) 是本系列对照里**最完整的 CSS 实现** —— 复用 selectolax pack: 在含找茬 pass 的 41 例基础矩阵上 **soupsieve 41/41, 高于 selectolax-Lexbor 的 39/41 和 cssselect (lxml/parsel) 的 37/41**; 本 pack 再补 20 例扩展, soupsieve 仍 20/20, 包含 Lexbor 不支持的 `:lang`。所以「选 bs4 会牺牲 CSS 能力」是错的: **CSS 能力上 bs4/soupsieve 反而领先** —— bs4 的代价在**速度** (§1), 不在 CSS 覆盖。范围: 单实验台。`[triple-run]` 因基础 41 例来自 selectolax 3-run 数据 (虽 CSS 判定是确定性布尔, 非计时)。

> **未支持项 (对照)**: soupsieve 是 CSS-only, **不支持 XPath**、不支持 parsel 的 `::text`/`::attr()` 伪元素扩展 (那是 Scrapy 扩展)。XPath 用户从 lxml/parsel 迁 bs4 会撞墙 —— 与 selectolax 同样的迁移限制。

---

## 6. 三后端在真实脏 HTML 上的一致性 (本 pack 实跑, 复用 selectolax 真实 fixture)

> 脚本 [real_backend_divergence.py](tests/real_backend_divergence.py) → [real_backend_divergence.json](artifacts/raw/real_backend_divergence.json)。**只读**引用 `tools/selectolax/fixtures/real/` 的 11 个真实站点抓取 (fetched 2026-07-10, 已过 selectolax pack 的准入门 —— 剔除了 eBay 反爬拦截页)。对每页用三后端各跑相同抽取 (全部 `<a href>` / h1–h6 / `<img src>` 计数), `agree` 字段运行时算出。**不测速度** (计时复用 §1)。

§3 的畸形矩阵显示三后端在**故意畸形**输入上会分歧。那真实世界呢? 本节回答 bs4 用户的实际问题:「我用默认 html.parser 和换 lxml/html5lib, 从真实页抽出的东西一样吗?」

**结果: 11/11 页三后端 link/heading/img 计数完全一致。** 零 divergent page。含 **MDN `<template>` 页, 三后端均得 508 链接**。

**FINDING-09 [single-observation] [DOCUMENTED]:** 在 11 个真实站点 (BBC / Wikipedia / Craigslist / MDN / old.reddit / Python docs / Hacker News / Books to Scrape / webscraper.io / whitehouse.gov / quotes.js) 上, **bs4 三后端抽取结果完全一致** —— 说明 §3 的后端分歧**只在故意畸形的 HTML 上显现**; 现代生产网站 (即便"脏") 结构够规范时, 换后端不改变抽取结果。**实务读法**: 抓主流规范站, `html.parser` 够用 (省依赖); 只有抓**明显不规范/手写/古早 HTML** 时, 后端选择才会改变结果 (见 §3), 此时上 `lxml`/`html5lib`。

**`<template>` 附带观测**: MDN 页三后端均得 508 链接 —— **bs4 全部后端把 `<template>` 内容 flatten 进主树**。这是 selectolax pack FINDING-14 的**镜像验证**: 那里仅 selectolax-Lexbor 严格遵循 HTML5 (template = inert DocumentFragment) 得 497、漏掉 `<template>` 内的 11 个链接, 而 lxml/bs4-两后端/Modest 都得 508。所以 **bs4 在 `<template>` 上和 lxml 同侧** (捞得到 template 内数据, 但也可能捞到浏览器不渲染的「幻影」数据); selectolax-Lexbor 是唯一严格 spec-correct 但会静默漏数据的。复用 `template_repro.json` 的对照事实。

---

## 给写作者的关键 findings

1. **FINDING-01 / 02 / 03** — **bs4 是最慢、最占内存的**, 且可量化: parse+extract 比 selectolax-Lexbor 慢 **12–17x** (html.parser) / **10.5–14x** (lxml 后端), 100k 节点 CSS 查询慢 **6–7.5x**, RSS **1.5–1.75x**, import 慢 **2.36x**。全部复用 selectolax 同实验台 3-run 数据 (as-of 2026-07-13)。这是 bs4「换慢求省心」权衡里「慢」那一半, 不回避。(§1)
2. **FINDING-04** — **bs4 解析不能靠多线程并行** (bs4_lxml 4 线程 speedup 0.26 = 反而慢 3.9x, likely-holds-GIL); 要并行只能多进程。selectolax/lxml 才有线程空间。free-threading 时代的实务差异。(§1d)
3. **FINDING-06 (第一优先)** — **默认 `html.parser` 容错弱于 `lxml`/`html5lib`**: 不实现 optional-end-tag, **未闭合 `<td>`/`<li>` 会把相邻文本渗漏拼接** (`['abcd','bcd','cd','d']`)、重复属性保留后者 —— 抽脏数据且不报错。抓不规范 HTML 应显式 `BeautifulSoup(html, "lxml")`。预注册畸形矩阵量化 (html.parser 12/15, lxml/html5lib 15/15)。文档已定性明载。(§3)
4. **FINDING-05 / 08** — **bs4 的「省心」是真的**: API 29/29 探针零意外 (含函数谓词 find、清晰双向 tree 导航), CSS 上 **soupsieve 反而最强** (基础 41/41 + 扩展 20/20, 高于 Lexbor 39/41 和 cssselect 37/41, 且支持 Lexbor 不支持的 `:lang`)。选 bs4 牺牲的是速度, **不是** API 或 CSS 覆盖。(§2, §5)
5. **FINDING-07** — bs4 树是**引用环**, GC 关时 `del` 不回收 (实测 300 次滞留 120,900 对象, collect 后归零, 无环对照组 delta 0 佐证)。长跑流水线**每页 `decompose()`** 主动断环。文档明载, 本 pack 量化。(§4)
6. **FINDING-09** — 真实规范站上**三后端抽取一致** (11/11); 后端分歧只在故意畸形 HTML 显现。bs4 全后端 flatten `<template>` (MDN 508), 与 selectolax-Lexbor (497, 严格 spec) 相反 —— 复用 FINDING-14 镜像。(§6)
7. **UnicodeDammit** (§见下 Gaps 引导的独立小节) — bs4 独有的编码嗅探, 8 例矩阵恢复 5 例: UTF-8/UTF-16 BOM/GBK/Shift-JIS/错标 latin-1 都对, 但**短 latin-1/cp1252 样本误判** (cp720/cp862)、**跟随错误 charset 声明**。文档明载「越短越不准」。这是 bs4 相对 selectolax「非 UTF-8 静默损坏」的**反向优势**: bs4 至少尝试嗅探恢复。
8. **novelty**: 本 pack **零 EXCLUSIVE** (1 KNOWN-ISSUE + 6 DOCUMENTED)。bs4 是 20 年老库, 独家极少是正常的; 叙事核心是量化权衡, 不是独家。(§Novelty)
9. **License / 依赖**: bs4 封装 MIT, 但引入什么取决于后端 —— `html.parser` 零依赖 (PSF), `lxml` 是外部 C 依赖 (BSD + libxml2), `html5lib` 纯 Python (MIT)。(Source Snapshot)

## UnicodeDammit 编码嗅探 (本 pack 实跑) —— bs4 独有

> 脚本 [unicode_dammit.py](tests/unicode_dammit.py) → [unicode_dammit.json](artifacts/raw/unicode_dammit.json)。selectolax **无对应组件**; selectolax pack §ENC 显示传非 UTF-8 bytes 给 selectolax 会静默损坏 (`.text()` 出 U+FFFD 或丢字节) 或抛错。bs4 走相反路线: 内置 `UnicodeDammit` 自动嗅探编码。8 例「声明 vs 实际」字符集矩阵, `recovered` 字段运行时比对目标串算出。

| case | 真实编码 | UnicodeDammit 猜到 | 恢复正确? |
|---|---|---|---|
| utf8_no_decl | utf-8 | utf-8 | ✅ |
| utf16_bom | utf-16 | utf-16le | ✅ |
| gbk_chinese | gbk | gb18030 | ✅ (gb18030 是 gbk 超集) |
| shiftjis | shift_jis | cp932 | ✅ (cp932 是 shift_jis 超集) |
| latin1_declared_utf8 | latin-1 (声明 utf-8) | iso-8859-1 | ✅ (无视错误声明) |
| latin1_no_decl | latin-1 | **cp720** (阿拉伯 DOS) | ❌ |
| cp1252_no_decl | cp1252 | **cp862** (希伯来 DOS) | ❌ |
| utf8_declared_latin1 | utf-8 (声明 latin-1) | iso-8859-1 | ❌ (**跟随错误声明**) |

**FINDING-10 [single-observation] [DOCUMENTED]:** UnicodeDammit 恢复 **5/8**: 对 UTF-8、UTF-16 BOM、GBK、Shift-JIS、以及**错标 charset 的 latin-1** 都能正确还原 (chardet 可用时), 且 GBK→gb18030、Shift-JIS→cp932 这类「猜成超集」仍正确解码。但两类失败: (a) **短 latin-1/cp1252 字节样本被误判成 DOS 代码页** (cp720/cp862) —— chardet 的统计检测在短样本上不可靠, 且 DOS box-drawing 字符与 Latin-1 重叠; (b) **`<meta charset>` 声明错误时 UnicodeDammit 信任声明** (utf8_declared_latin1 跟随谎言)。bs4 文档明载这两点 ("so short that Unicode, Dammit can't get a lock on it" + "越多数据越准")。**对照 selectolax 的实务意义**: 面对非 UTF-8 页, selectolax 静默损坏、需你自己先 decode; bs4 至少**主动嗅探并常常恢复成功** —— 这是 bs4 容错叙事的一部分, 但**短样本/错声明**时仍会猜错, 生产上对已知编码应显式 `BeautifulSoup(bytes, from_encoding="...")` 而非依赖嗅探。

## 维度级证据 (不合成总分)

按方法论 v3 Part 3, 本 pack **不**发布单一加权 0–100 总分。逐维度给证据供写作者加权:

| 维度 | 证据 (测得) | 读者 caveat |
|---|---|---|
| 安装 / 首次运行 | 纯封装, 无浏览器/setup; html.parser 零依赖即用; 全预编译 wheel | 后端 lxml 需 C 依赖 |
| 速度 vs C 解析器 | **慢 12–17x (html.parser) / 10.5–14x (lxml 后端)**, 全尺寸, 复用 3-run | 单实验台; 复用 selectolax |
| CSS 查询吞吐 | 10 万节点慢 6–7.5x; 换 lxml 后端也不救 (付 Python Tag 税) | 复用 |
| 内存 | **1.5–1.75x 于 selectolax/lxml**; 最重 | 复用; 按 RSS 非 tracemalloc |
| import 冷启动 | 慢 2.36x (33.4 vs 14.1 ms) | 复用; 小项 |
| 线程扩展 | **bs4_lxml 4 线程反慢 3.9x (holds GIL)**; 需多进程并行 | 单次观测; 复用 |
| API 易用性 | 29/29 探针; 函数谓词 find + 清晰双向 tree 导航 (C 解析器无) | bool-attr 空串陷阱、strip 丢词界 |
| CSS 覆盖 | **soupsieve 最强**: 基础 41/41 + 扩展 20/20; 支持 Lexbor 不支持的 `:lang` | 无 XPath、无 `::text` |
| 三后端容错 | lxml/html5lib 15/15; **html.parser 12/15** (未闭合 td/li 渗漏、重复属性保留后者) | 分歧只在畸形 HTML |
| 真实页一致性 | 三后端 11/11 一致; 全后端 flatten `<template>` (508) | 规范站后端无差 |
| 引用环 GC | 树是环; GC 关时 300 次滞留 120,900 对象, collect 归零; 无环对照 delta 0 | 长跑需 decompose() |
| 编码 (UnicodeDammit) | 8 例恢复 5; UTF-8/16/GBK/SJIS/错标 latin-1 对; **短 latin-1/cp1252 误判、跟随错声明** | 单次观测 |
| 维护 | 活跃 (4.15.0, 2026-06); MIT | home 在 crummy/Launchpad 非 GitHub |

## Gaps (成稿前)

- **跨平台**: 全部 macOS arm64 / Python 3.14 / 预编译 wheel。复用的计时倍数继承 selectolax pack 的单平台限制; Linux x86_64 / 源码编译 lxml 未测。
- **bs4 RSS 级长跑软化**: 本 pack 只做了对象计数级引用环 GC 测试 (确定性), **未**对 bs4 做 selectolax 那样的 2000-iters RSS 泄漏软化曲线 (因不重跑计时)。「decompose() vs 依赖 GC」在多小时 soak 下的 RSS 差异未量化。
- **on_duplicate_attribute 参数矩阵**: 只测了三后端默认重复属性行为 (html.parser 保留后者); 未系统测 `on_duplicate_attribute` 的 REPLACE/IGNORE/其它取值 × 三后端。
- **UnicodeDammit 深度**: 8 例矩阵; 未测 `exclude_encodings`、cchardet (C 版) vs chardet 的检测差异、更长文档的收敛行为、BOM 优先级细节。
- **html5lib 的 treebuilder 选项**: 只用 bs4 默认接线的 html5lib; 未测 html5lib 独立 treebuilder 差异 (etree vs dom vs lxml)。
- **超大真实页 / 流式**: bs4 一次性解析整串; 未测 >1 MB 真实页的后端分歧、无增量/流式解析路径。
- **`SoupStrainer` 部分解析**: bs4 提供 `SoupStrainer` 只解析文档一部分 (省内存), 本 pack 未测其正确性/省内存幅度。
- **XML 模式**: 只测 HTML 解析; bs4 的 `features="xml"` (lxml-xml) 路径未测。
- **与 selectolax / trafilatura / scrapling 的正面横比**: 本 pack 以复用为主对比 selectolax; 与其它 pack 的横比留待各 pack 齐备后在**正确的层级**做 (bs4 是通用解析封装, selectolax 是快解析器, trafilatura 是正文抽取 —— 层级不同)。

## Raw Artifact Index

脚本 (`tests/`, 本 pack 实跑, 均纯 Python 秒级、无计时):
- 三后端畸形矩阵 (预注册反偏向): [malformed_matrix.py](tests/malformed_matrix.py)
- API 易用性能力矩阵: [api_surface.py](tests/api_surface.py)
- UnicodeDammit 编码嗅探: [unicode_dammit.py](tests/unicode_dammit.py)
- 引用环 GC 行为 (仪器先校准 + 无环对照): [gc_refcycles.py](tests/gc_refcycles.py)
- soupsieve CSS 扩展覆盖: [soupsieve_extended.py](tests/soupsieve_extended.py)
- 三后端真实页一致性 (复用 selectolax fixture): [real_backend_divergence.py](tests/real_backend_divergence.py)
- **汇总生成器 (从原始 JSON 派生, 无手写数字; 含复用 selectolax 字段的计算)**: [build_summary.py](tests/build_summary.py)
- 全套编排: [run_all.py](tests/run_all.py)

原始结果 (`artifacts/raw/`, 本 pack 实跑): [malformed_matrix.json](artifacts/raw/malformed_matrix.json), [api_surface.json](artifacts/raw/api_surface.json), [unicode_dammit.json](artifacts/raw/unicode_dammit.json), [gc_refcycles.json](artifacts/raw/gc_refcycles.json), [soupsieve_extended.json](artifacts/raw/soupsieve_extended.json), [real_backend_divergence.json](artifacts/raw/real_backend_divergence.json), 以及**生成的** [beautifulsoup-test-summary.json](artifacts/raw/beautifulsoup-test-summary.json)。元数据: [pypi_snapshot_2026-07-14.json](artifacts/raw/pypi_snapshot_2026-07-14.json)。Novelty 搜索证据: [novelty_search_2026-07-14.json](artifacts/raw/novelty_search_2026-07-14.json)。

日志 (`artifacts/logs/`): [pip-install.log](artifacts/logs/pip-install.log)。

**复用的 selectolax 原始数据 (只读引用, 同实验台, as-of 2026-07-13)**:
- 计时: `tools/selectolax/results/bench_parse.json` (results.{size}.bs4_htmlparser/bs4_lxml.p50_ms.median_across_runs), `bench_isolate.json` (throughput_100k.bs4_lxml, parse_only)
- 内存/import: `tools/selectolax/results/bench_memory_import.json` (memory_rss.page_10mb.html, import_cold)
- GIL: `tools/selectolax/results/production_dims.json` (thread_scaling.bs4_lxml)
- CSS 基础矩阵: `tools/selectolax/results/css_coverage.json` (cases[].soupsieve → 41/41)
- `<template>` 对照: `tools/selectolax/results/template_repro.json`
- 真实 fixture: `tools/selectolax/fixtures/real/` (11 站, 只读)

公开可复现副本: 待 (随本系列推入 `github.com/thunderbit-operations/scraper-benchmark` → `tools/beautifulsoup/`; 本 pack 未自建 repo, 改动留工作区待主会话统一提交)。

## 完整 Source Index

- [BeautifulSoup 官方文档](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — Tier 1 (parser 差异、encoding、GC/decompose、get_text、on_duplicate_attribute)
- [beautifulsoup4 on PyPI](https://pypi.org/project/beautifulsoup4/) — Tier 1 (4.15.0, MIT, Python >=3.7)
- [BeautifulSoup Launchpad (源码 + bug tracker)](https://bugs.launchpad.net/beautifulsoup) — Tier 1 (bs4 的规范 tracker, 非 GitHub)
- [soupsieve 官方文档 (CSS 选择器覆盖)](https://facelessuser.github.io/soupsieve/selectors/) — Tier 1
- [lxml.de/elementsoup — lxml 作为 bs4 后端](https://lxml.de/elementsoup.html) — Tier 1 (lxml 比 html.parser 更快更宽容)
- [html5lib](https://github.com/html5lib/html5lib-python) — Tier 1 (最宽容后端, MIT)
- selectolax pack (同项目, 只读复用): `tools/selectolax/research-materials.md` 及其 `artifacts/` — bs4 计时/内存/GIL/CSS/`<template>` 数据来源
- 真实 fixture 来源 (复用 selectolax, fetched 2026-07-10): BBC News, Hacker News, Books to Scrape, webscraper.io, Python docs, MDN, old.reddit, Wikipedia, whitehouse.gov, quotes.toscrape/js, Craigslist — 公开页, HTML 本地捕获。
