# PR、Issue、Backlog 与 CI

## Issue

Issue 是一个具体、可讨论、可关联代码的工作对象。它可以是需求、缺陷、技术债、调研或决策任务。一个实施就绪的 Issue 应说明可观察成果、范围、验收标准、验证方式和依赖。

## Backlog

Backlog 是候选工作的集合或队列。它通常由处于 Backlog 状态的 Issues 构成。Backlog 关注“还没有承诺现在做什么”；Issue 关注“这一项工作具体是什么”。

不要创建一份 Backlog 文档，再把同样的内容复制成 Issues。直接让 Issue 进入 Project 的 Backlog 状态。

## Branch

Branch 是 Git 中的一条提交线。它隔离代码变化，但本身不提供评审、评论、审批、CI 门禁或产品状态。

## Pull Request

PR 是请求把一个 branch 的变化集成到另一个 branch 的协作对象。它在 Git 分支之上增加：

- 差异浏览；
- 逐行评论；
- reviewer 与 approval；
- Issue 关联；
- CI checks；
- 合并策略与权限规则；
- 可追溯的决策记录。

PR 最终仍通过 Git 合并、rebase 或 squash 产生提交结果；它改变的是协作和治理过程，而不是 Git 的基本数据模型。

## CI 与 GitHub Actions

CI 是持续、自动验证每个候选改动的工程实践。GitHub Actions 是执行这套实践的平台之一。

默认 GitHub-hosted runner 位于 GitHub 的基础设施上。开发者或 agent 只负责推送触发事件和读取结果。本地 Git 不会执行 workflow，Codex 也不会天然执行它。

Self-hosted runner 可以把执行机器换成自己的电脑或服务器，但触发、排队、权限和 status check 仍由 GitHub Actions 协调。

