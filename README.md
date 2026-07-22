# Agent Project Bootstrap

一套面向 ChatGPT Work、Codex、Claude Code 和人工开发者的轻量项目协作规范。它把“谁在做什么、先做什么、怎样验收”从聊天记录中移出，放到 GitHub Issues/Projects、Pull Requests、仓库说明和 CI 中。

它不是新的项目管理平台，也不是多 agent 调度器。它提供的是：

- 一个可安装的 Codex/ChatGPT Skill；
- 新项目和存量项目的交互式初始化流程；
- Issue、PR、CI、分支保护和 worktree 隔离的实践规范；
- macOS、Linux 和 Windows 安装器；
- 一个可选的 GitHub Issues/PR 本地只读快照。

## 一分钟安装

### macOS / Linux

只安装 Skill：

```sh
curl -fsSL https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.sh | sh
```

安装 Skill，并在全局 `AGENTS.md` 中加入“首次进入仓库时检查是否需要初始化”的规则：

```sh
curl -fsSL https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.sh | sh -s -- --with-global-rule
```

### Windows PowerShell

只安装 Skill：

```powershell
irm https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.ps1 | iex
```

安装 Skill和全局检查规则：

```powershell
$installer = irm https://raw.githubusercontent.com/futouyiba/agent-project-bootstrap/main/install.ps1; & ([scriptblock]::Create($installer)) -WithGlobalRule
```

安装器默认写入 `$CODEX_HOME/skills`，未设置 `CODEX_HOME` 时写入 `~/.codex/skills`。如果已经安装旧版本，旧目录会先被重命名为带时间戳的备份。

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

安装 GitHub 插件只是提供操作能力，不代表 agent 会自动把 GitHub 当作任务系统。仓库 `AGENTS.md` 和当前请求仍要明确：“使用 GitHub Issues/Projects 作为任务事实来源”。

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

因此需求通常先创建 Issue，然后进入 Project 的 Backlog：

```text
需求想法 → Issue + Backlog
信息补齐并排定 → Ready
有人开始做 → In progress
受依赖阻塞 → Blocked
进入 PR → In review
合并且验收完成 → Done
```

并非所有 Issue 都必须进入 backlog，例如紧急故障可能直接进入 In progress；不是所有 backlog 条目都必须立即实现，它可以长期等待排序或被关闭。

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

