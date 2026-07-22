# Agent Project Bootstrap

一套面向 ChatGPT Work、Codex、Claude Code 和人工开发者的轻量项目协作规范。它把“谁在做什么、先做什么、怎样验收”从聊天记录中移出，放到 GitHub Issues/Projects、Pull Requests、仓库说明和 CI 中。

它不是新的项目管理平台，也不是多 agent 调度器。它提供的是：

- 一个可安装的 Codex/ChatGPT Skill；
- 新项目和存量项目的交互式初始化流程；
- 不要求记住 Issue 编号的自然语言日常工作流；
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
| Skill | 理解初始化和日常流程 | 是 |
| 全局 Prompt | 在 CLI/IDE 提供 `/prompts:integrate` | 是，但属于 deprecated 兼容入口 |
| 全局 `AGENTS.md` | 记住个人通用偏好：不要求 Issue 编号、识别短语、遇到歧义再问 | 仅使用 `--with-global-rule` 时 |
| 仓库 `AGENTS.md` | 保存 Project 地址、精确状态名、测试命令和常规授权边界 | 每个仓库 bootstrap 时 |
| GitHub Project workflows | 自动加入 Project、默认 Backlog、关闭或合并后 Done | 每个 Project 单独配置 |

因此，bootstrap 完成后，Agent 才能依据仓库规则自动执行已选任务内的常规动作；它不会因为 Skill 存在就擅自合并、部署、删除或扩大需求范围。执行工具本身如果出现平台授权提示，仍需用户批准。

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
