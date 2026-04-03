# Goby Skills

这是一个为 AI 编程助手（如 Claude Code、Codex 等）设计的 skill 集合，用于通过自然语言指令操控 [Goby](https://gobies.org/) 安全扫描工具，实现扫描编排、资产查询、漏洞检索、POC 管理等功能。

## 包含的 Skills

| Skill | 说明 |
|---|---|
| [goby-scan-orchestrator](skills/goby-scan-orchestrator/SKILL.md) | 操控 Goby 进行扫描编排、资产搜索、漏洞查询、POC 管理、激活与环境配置 |

## 功能说明

`goby-scan-orchestrator` 的核心能力包括：

- 维护 Goby 服务状态
- 支持高级 Goby 版本的激活
- 发起扫描任务，并支持暂停与恢复任务
- 执行 POC 更新
- 整理和输出扫描报告

在使用方式上，skill 还具备以下特性：

- 启动 Goby 时，如果本机当前没有正在使用中的 Goby 实例，skill 会询问用户提供 Goby 的安装目录。出于安全考虑，skill 不会在本机执行全盘搜索来定位 Goby。
- 在用户首次提供 Goby 安装目录后，skill 会记住该路径，后续不会重复主动询问；只有在用户明确需要修改时，才会重新更新该配置。
- 如果本机已经启动了 Goby，且客户端处于可正常使用状态，skill 可以选择接管当前 Goby 实例，相当于同时提供前端界面和 AI 指令两套操作入口。
- 该能力仅适用于红队版本及以上版本的 Goby。

## 警示说明

- 基于合法合规与安全边界的明确要求，本 skill 不可用于扫描未经授权的公网目标。

## 安装

如果你是首次使用，可以将以下指令复制给你的 AI 编程助手，它会自动将 skill 下载并安装到当前项目的对应目录：

> 请从 https://github.com/gobysec/Goby-skills 下载 `skills/goby-scan-orchestrator` 目录，安装到当前项目下你（AI 编程助手）存放自定义 skill 的目录中。

如果你已经安装过旧版本，建议使用更新指令覆盖本地已有版本，确保 skill 内容与仓库保持一致：

> 请从 https://github.com/gobysec/Goby-skills 拉取最新的 `skills/goby-scan-orchestrator` 目录，并覆盖更新当前项目中你（AI 编程助手）已安装的同名 skill，保留用户已有的本地配置。

## 操作示例

<video src="https://github.com/gobysec/Goby-skills/releases/download/v0.1/goby.mp4" controls width="100%"></video>
