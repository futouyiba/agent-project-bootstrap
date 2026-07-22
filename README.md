# Agent Project Bootstrap

一套面向 ChatGPT Work、Codex、Claude Code 和人工开发者的轻量项目协作规范。它把“谁在做什么、先做什么、怎样验收”从聊天记录中移出，放到 GitHub Issues/Projects、Pull Requests、仓库说明和 CI 中。

它不是新的项目管理平台，也不伪装成常驻 GitHub webhook 服务。它提供的是：

- 一个可安装的 Codex/ChatGPT Skill；
- 新项目和存量项目的交互式初始化流程；
- 不要求记住 Issue 编号的自然语言日常工作流；
- 一个有边界的“托管”模式，让同一个主管任务自动接续 PR、评审和 CI；
- 一个可选的 GitHub Agentic Workflows 事件驱动层，让 GitHub 自己唤醒调度、实现、审查和合并就绪检查；
- 全局“合并收尾”意图，以及 Codex CLI/IDE 的 `/prompts:integrate` 快捷入口；
- Issue、PR、CI、分支保护和 worktree 隔离的实践规范；
- macOS、Linux 和 Windows 安装器；
- 一个可选的 GitHub Issues/PR 本地只读快照。

## 一分钟安装

### macOS / Linux

安装全局 Skill 和 CLI/IDE 快捷入口：

```sh
curl -fsSL https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.sh | sh
```

安装 Skill，并在全局 `AGENTS.md` 中加入“首次检查初始化 + 自然语言日常工作流”的规则：

```sh
curl -fsSL https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.sh | sh -s -- --with-global-rule
```

### Windows PowerShell

安装全局 Skill 和 CLI/IDE 快捷入口：

```powershell
irm https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.ps1 | iex
```

安装 Skill 和全局工作流规则：

```powershell
$installer = irm https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.ps1; & ([scriptblock]::Create($installer)) -WithGlobalRule
```

安装器默认把 Skill 写入 `$CODEX_HOME/skills`，把快捷 Prompt 写入 `$CODEX_HOME/prompts/integrate.md`；未设置 `CODEX_HOME` 时使用 `~/.codex`。如果已经安装旧版 Skill，旧目录会先被重命名为带时间戳的备份；不同内容的同名 Prompt 也会先备份。再次使用 `--with-global-rule` 会升级这个项目自己管理的规则块，不会覆盖其他全局说明。

也可以先克隆仓库，再离线安装：

```sh
git clone https://github.com/futouyiba/agent-project-bootstrap.git
cd agent-project-bootstrap
./install.sh --source . --with-global-rule
```

Windows 对应命令：

```powershell
git clone https://github.com/futouyiba/agent-project-bootstrap.git
Set-Location agent-project-bootstrap
./install.ps1 -Source . -WithGlobalRule
```

安装后如果 Skill 没有立刻出现，重启 ChatGPT/Codex。

## 第一次初始化项目

1. 确保当前目录已经是 Git 仓库。这个 Skill 不会未经允许替你初始化 Git。
2. 在 ChatGPT Work 中输入 `@agent-project-bootstrap`，或在 Codex 中输入 `$agent-project-bootstrap`。
3. Skill 先执行只读审计，然后让你选择：
   - **Coordination**：Issue、Project 和 Issue/PR 模板；
   - **Delivery**：再加入 CI 与分支保护清单，推荐默认选择；
   - **Worktree**：再加入 Codex worktree、本地环境、端口、数据库和 Docker 隔离。
4. 审核它准备创建或修改的文件。
5. 在 GitHub 完成 Project、Actions 权限和默认分支规则等网页端设置。
6. 创建第一个满足验收标准的 Issue，从分支和 PR 开始交付。

安装 GitHub 插件只是提供操作能力；安装 Skill 只是让 agent 理解流程。第一次对每个仓库执行 bootstrap，才会写入仓库规则、模板和检测标记。GitHub Project 的字段与自动化也需要针对该 Project 单独配置。

## 一个 Skill，两种模式

这里有意只使用一个 `agent-project-bootstrap` Skill，而不是让用户区分“初始化 Skill”和“日常管理 Skill”：

- **Bootstrap 模式**：第一次进入新仓库，或把存量项目迁移进来；
- **Daily flow 模式**：以后用自然语言查找 Issue、开始任务、创建 PR、记录验证并更新状态。

安装时选择 `--with-global-rule` 后，Agent 会把下列短语识别为工作流意图；仓库 `AGENTS.md` 再提供该项目的具体授权和状态名称：

```text
记一下：以后也许要支持离线导出
收需求：把刚才确认的三个事项整理进去
开始做：修复首次登录时偶发的白屏
收尾
合并收尾
托管
托管：当前版本
```

你不需要知道 Issue 编号，也不用复述“读取验收标准、建分支、开 PR、更新 In review、不要合并”等长提示。Agent 应先用描述查找：只有一个明显结果就直接采用；多个相近结果只列出最可能的两三个供确认；没有结果时再按仓库授权创建或提出 Issue。

`收尾` 只检查和整理，不授权合并。`合并收尾` 是当前这一次任务的明确合并授权：Agent 重新读取 GitHub，按依赖顺序逐个处理已批准 PR；每次合并后刷新剩余项目；CI、冲突、评审线程或验收条件不满足的项目会被跳过。该授权不包含部署、发布或扩大范围。

Codex CLI 和 IDE 扩展还可以输入：

```text
/prompts:integrate
/prompts:integrate 本周迭代
```

自定义 Slash Prompt 是 Codex 当前保留的兼容机制，官方已标记为 deprecated，并且只适用于 CLI 和 IDE 扩展。因此它只是快捷外壳：真正的全局、跨客户端工作流仍由 Skill 和“合并收尾”自然语言意图承担；ChatGPT 桌面端直接输入“合并收尾”即可。

### 三层配置分别负责什么

| 层级 | 作用 | 是否安装后自动完成 |
|---|---|---|
| Skill | 理解初始化、日常流程和可选 `gh-aw` 安装流程 | 是 |
| 全局 Prompt | 在 CLI/IDE 提供 `/prompts:integrate` | 是，但属于 deprecated 兼容入口 |
| 全局 `AGENTS.md` | 记住个人通用偏好：不要求 Issue 编号、识别短语、遇到歧义再问 | 仅使用 `--with-global-rule` 时 |
| 仓库 `AGENTS.md` | 保存 Project 地址、精确状态名、测试命令和常规授权边界 | 每个仓库 bootstrap 时 |
| GitHub Project workflows | 自动加入 Project、默认 Backlog、关闭或合并后 Done | 每个 Project 单独配置 |
| GitHub Agentic Workflows | 事件/定时唤醒并在 agent 角色之间自动交接 | 否；每仓库显式安装，默认 staged |

因此，bootstrap 完成后，Agent 才能依据仓库规则自动执行已选任务内的常规动作；它不会因为 Skill 存在就擅自合并、部署、删除或扩大需求范围。执行工具本身如果出现平台授权提示，仍需用户批准。

## 托管模式：不再让人在对话之间传话

托管模式不是继续增加“实现对话”、“评审对话”和“合并对话”，而是使用一个持久的项目主管任务。GitHub 是所有人可见的信箱和事实来源；主管每次被唤醒后直接读取 Issue、PR、review thread 和 CI，自己判断下一步，不再让用户复制消息。

在已 bootstrap 的仓库中，直接输入：

```text
托管
```

它默认表示“托管当前仓库和当前明确目标、活跃 Issue 或 PR”。只有需要限定范围时才多打几个字，例如 `托管：登录模块`。“托管这个项目”或其他自然说法仍然有效。当当前上下文真的对应多个范围时，Agent 才问一个简短问题。

Agent 会一次性确认或记录：

- 托管的 Goal 或 Issue 范围；
- 心跳时间，活跃开发默认可从 15–30 分钟开始；
- 修复—评审—CI 的最大重试次数，默认 3 次；
- Codex GitHub 自动评审是否已启用；
- 合并是继续每次授权，还是允许满足全部门禁的低风险 PR 使用 Auto-merge；
- 必须叫用户的产品、安全、数据、费用、发布和连续失败边界。

之后同一个主管会按下列顺序循环：

```text
刷新 GitHub → 继续活跃 PR → 处理评审/CI → 重新验证 → 复审 → 合格后合并 → 继续依赖任务
```

默认不托管部署、发布、删除、密钥、计费、破坏性数据迁移、需求扩张和高风险合并。这些动作只在仓库政策明确单独授权时才能执行。

Codex Automation 目前主要是定时心跳，不是 GitHub webhook；本地执行时还可能依赖电脑和客户端保持可用。如果需要真正的事件驱动，可选官方 [`openai/codex-action`](https://github.com/openai/codex-action)，但它需要 API Key、GitHub Secret、权限和 prompt-injection 威胁模型，本项目默认不启用可写的事件自动化。

### 可选：基于 `gh-aw` 的事件驱动托管

如果目标是不再由人把“实现完成—请审查—还要修改—CI 已通过”粘贴到不同对话，可以为单个仓库启用 [GitHub Agentic Workflows (`gh-aw`)](https://github.com/github/gh-aw) profile。它在 GitHub Actions 中启动独立的无界面 agent run，不会给桌面端任务发送 Steer，也不会打断 ChatGPT/Codex 当前对话。

本项目提供四个角色，但仍然只有一个调度者：

```text
GitHub 事件/30 分钟兜底心跳
             ↓
      agent-supervisor
       ↙      ↓      ↘
 实现/返工   独立审查   合并就绪核验
    ↓          ↓           ↓
 Issue、PR、Review、CI（共同事实来源）
```

- `agent-supervisor`：只路由带 `agent:managed` 的事项；
- `agent-implement`：创建 Issue 关联 PR，或在同一 PR 分支修复；
- `agent-review`：独立审查，留下 `VERDICT: MERGE_READY` 或阻塞意见；
- `agent-integrate`：重新核对当前 head、CI、依赖和评论，但**不执行合并**。

它不是安装全局 Skill 后自动开启的。每个仓库都要先做只读计划：

```sh
python3 ~/.codex/skills/agent-project-bootstrap/scripts/configure_agentic_workflows.py /path/to/repository --engine codex
```

确认后只安装预演版：

```sh
python3 ~/.codex/skills/agent-project-bootstrap/scripts/configure_agentic_workflows.py /path/to/repository --engine codex --apply
gh aw compile --strict
```

Windows PowerShell 对应使用：

```powershell
python "$HOME/.codex/skills/agent-project-bootstrap/scripts/configure_agentic_workflows.py" C:\path\to\repository --engine codex --apply
gh aw compile --strict
```

模板目前使用官方 `gh-aw v0.82.14` 做过严格编译验证。首次编译会把新增的 engine secrets 和 Actions 列为 safe-update 安全审查项；逐项检查并在 PR 中记录理由后，再执行 `gh aw compile --strict --approve`。安装脚本不会替你静默批准。CI 完成事件默认匹配所有 PR head 分支，但只接受由 `pull_request` 触发的目标 CI；可以用 `--ci-branch-pattern` 收紧分支 glob，用 `--ci-workflow` 指定准确的 workflow 名称。

第一次生成的 workflow 强制使用 `staged: true`：即使同时传入 `--live --apply`，工具也会拒绝首次安装。它会在 Actions Summary 展示拟评论、拟打标签、拟创建 PR 和拟派发的 worker，但不真正写入 GitHub。必须在真实 Issue、PR、review 和 CI 上验证过路由、权限、费用和 prompt-injection 边界，才能另开一次变更使用 `--live`；只有四个现有文件与工具生成的 staged 版本逐字一致时，升级才会受控执行，任何人工修改都会作为冲突保留。

安装器还会拒绝 `.github`、`.github/workflows` 或目标 workflow 文件中的符号链接，防止仓库内路径把写入重定向到仓库外部。

Codex engine 需要把 `OPENAI_API_KEY` 配置为 GitHub Actions secret；ChatGPT 订阅不能替代 API Key。还需要创建 `agent:managed`、`agent:needs-review`、`agent:needs-rework`、`agent:merge-ready` 和 `needs:human` 五个机器路由标签。它们不是 Project 状态的第二份副本。每次返工会在 PR 记录 `AGENT-CYCLE:` 证据；同一阻塞条件累计三次失败后停止自动派发并升级给人。

Worker 不依赖提示词判断托管范围：AI 启动前会由 pre-activation job 查询精确的 Issue/PR 编号、类型和 `agent:managed` 标签；AI 结束后、任何 safe output 写入前还会再次检查。所有 worker 写入固定到传入编号，支持标签门禁的 handler 同时配置 `required-labels: [agent:managed]`。因此仓库正文或评论中的 prompt injection 不能自行把未托管事项加入执行范围。

将 `.github/workflows/*.md`、编译生成的 `*.lock.yml` 和 `.github/aw/actions-lock.json` 一起提交。`gh-aw` 升级也要通过 PR 重新编译和审查。本 profile 默认完全不提供 merge safe output；需要合并时继续使用 `合并收尾`，或在仓库规则成熟后单独配置 GitHub Auto-merge/merge queue。

如果由 Actions 默认 `GITHUB_TOKEN` 创建 PR 或评论，GitHub 为防止递归通常不会由它继续触发所有下游 workflow；因此 supervisor 还有定时兜底。想实现近实时递归链路，需要单独评审 GitHub App/PAT 的权限和成本，不能把更强 token 当默认值。

可复用的主管指令位于 [`skill/assets/codex-managed-supervisor.md`](skill/assets/codex-managed-supervisor.md)，安装 Skill 时会一起安装。

## Agent 与 GitHub 自动化怎样配合

Agent 负责需要语义判断的工作：理解自然语言、搜索和消歧 Issue、判断需求是否明确、实现与总结。GitHub Project 的内置 workflow 负责确定性动作：匹配的 Issue 自动进入 Project、Issue 或 draft intake 默认进入 `Backlog`、Issue 关闭后进入 `Done`。PR 默认只作为 Issue 的关联交付记录，不作为第二个 Project 条目。

推荐在每个 Project 的 **Workflows** 页面配置：

1. `Auto-add to project`：只筛选目标仓库的 Issues；
2. `Item added to project`：只把 Issue/draft intake 的 Status 设为 `Backlog`；
3. `Issue closed`：Status 设为 `Done`；
4. 如果团队明确选择同时追踪 PR，PR 加入时直接设为 `In review`，合并后再设为 `Done`。

GitHub 套餐、Project 类型和权限会影响可用 workflow。Bootstrap 会先检测；能通过已连接工具可靠配置时才执行，否则输出准确的网页操作清单并把状态记为 pending，不会假装已经配置好。

## 它怎样工作

每一种信息只保留一个权威位置：

| 内容 | 权威位置 |
|---|---|
| 需求、任务、依赖、负责人 | GitHub Issue |
| Backlog、状态、优先级、路线图 | GitHub Project |
| 稳定的 agent 与工程规则 | 仓库 `AGENTS.md` |
| 代码改动、讨论和审批 | Branch + Pull Request |
| 可重复的自动验证 | CI / GitHub Actions |
| Codex 新 worktree 所需的忽略文件 | 仓库 `.worktreeinclude` |
| 可丢弃的远端只读缓存 | `.codex/cache/github-snapshot.json` |

核心原则是：不要再维护一份可编辑的 `tasks.md` 或 `tasks.json` 与 GitHub 双向同步。双写最终一定会产生冲突。可以缓存或生成摘要，但缓存不能反向成为任务数据库。

## 在已经运行一段时间的项目中引入

不要一次性重写所有流程。推荐渐进迁移：

1. **只读盘点**：识别现有任务文档、分支方式、CI、Issue/PR 模板和发布流程。
2. **确定切换点**：旧任务表改为只读归档；从某个日期起，所有新增或仍未完成的工作进入 GitHub Issues。
3. **小范围试点**：选择一个模块或 3–10 个真实任务，建立 Issue、依赖、分支和 PR。
4. **补 CI**：先让现有本地测试在 GitHub Actions 稳定运行，不急着开启强制规则。
5. **开启保护**：CI 至少成功运行一次后，再要求 PR、CI 和审批。
6. **清理重复状态**：README 或旧看板只保留入口链接，不再复制进行中状态。
7. **再开托管**：先让真实 PR 稳定跑通 CI 和评审，然后再启用主管心跳与低风险 Auto-merge，不要在迁移第一天就全权自动化。

完整说明见 [存量项目迁移](docs/adopting-existing-project.md)。

在当前机器的其他项目中不需要重复安装 Skill。进入那个仓库，调用 `@agent-project-bootstrap` 或 `$agent-project-bootstrap` 即可。每个仓库仍需单独初始化，因为技术栈、测试命令、忽略文件和分支策略都不同。

## Issues/PR 能否保存在本地

部分可以，但不是通过 `.github/` 自动完成。

- `.git/` 保存提交、分支、标签和上次 fetch 得到的远端分支引用。
- `.github/` 保存 Issue 模板、PR 模板、Actions workflow、CODEOWNERS 等仓库配置。
- Issue、PR 的标题、状态、评论、审批和 Project 字段保存在 GitHub 数据库中，不会随 `git clone` 或 `git pull` 下载。

本项目提供可选快照：

```sh
python3 ~/.codex/skills/agent-project-bootstrap/scripts/snapshot_github.py refresh
python3 ~/.codex/skills/agent-project-bootstrap/scripts/snapshot_github.py status
```

它把常用 Issue/PR 元数据写到被 Git 忽略的 `.codex/cache/github-snapshot.json`。Agent 可以在只读分析时先读取新鲜缓存；在创建、关闭、合并或需要最新状态前仍必须访问 GitHub。详见 [本地缓存](docs/local-cache-and-offline.md)。

## 新手概念

### PR 解决什么问题

Pull Request 不是“另一种 Git 合并算法”，而是给一次合并增加一个协作和治理界面：

- 展示两个分支的差异；
- 关联 Issue；
- 进行逐行评论、评审和批准；
- 运行 CI；
- 执行权限和分支保护规则；
- 保存“为什么这样改、谁同意了、验证是否通过”的记录。

直接在本地执行 `git merge` 也能产生相似的最终代码，但通常绕过了这些讨论、审计和自动门禁。个人实验分支可以直接合并；共享主分支更适合通过 PR 集成。

### 什么是 backlog

Backlog 是“尚未承诺立即执行的候选工作集合”，不是另一种 GitHub 数据类型。Issue 是一个具体工作对象；Backlog 通常是这些 Issue 在 GitHub Project 中的一种状态或视图。

清晰、可讨论和可验收的需求通常创建为 Issue，再进入 Project 的 Backlog；尚不确定的想法也可以先作为 Project draft item，而不必立刻成为 Issue：

```text
不确定想法 → Project draft + Backlog
明确事项 → Issue + Backlog
信息补齐并排定 → Ready
有人开始做 → In progress
受依赖阻塞 → Blocked
进入 PR → In review
合并且验收完成 → Done
```

并非所有 Issue 都必须进入 backlog，例如紧急故障可能直接进入 In progress；不是所有 backlog 条目都是 Issue，也不代表高优先级。Backlog 只是尚未承诺立即执行的候选集合，可以长期等待排序、转成 Issue 或被移除。

更多解释见 [PR、Issue、Backlog 与 CI](docs/concepts.md)。

## CI 在哪里运行

默认情况下，GitHub Actions CI 在 GitHub 托管的远端 runner 上运行：

```text
本地或 agent 推送提交
        ↓
GitHub 收到 push / PR 事件
        ↓
GitHub runner 拉取代码并执行 .github/workflows/*.yml
        ↓
结果成为 PR 的 status check
        ↓
分支保护决定是否允许合并
```

它不在 Codex 内部运行，也不由本地 Git 客户端运行。也可以自行配置 self-hosted runner，让 Actions 在自己的机器或服务器上执行，但控制和结果仍由 GitHub Actions 管理。

## Codex GitHub Review 能补足什么

Codex GitHub Review 可以承担独立代码评审角色，尤其适合所有产品讨论和实现都在 ChatGPT Work 中完成的流程。它能从 PR 角度检查改动并给出评论，但不能完全替代：

- 产品与架构决策记录；
- 单元测试、集成测试和 CI；
- 高风险改动的人类审批；
- 分支保护和权限控制。

比较稳妥的组合是：Work 负责讨论和实施，GitHub Issue/PR 保存事实状态，Codex Review 提供独立评审，Actions/CI 负责确定性检查。

## 开发和验证

```sh
python3 -m unittest discover -s tests -v
./install.sh --source . --codex-home /tmp/agent-project-bootstrap-test --with-global-rule
```

GitHub Actions 会在 Linux、macOS 和 Windows 上分别验证对应安装器。

## License

[MIT](LICENSE)
