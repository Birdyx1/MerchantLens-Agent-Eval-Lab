# 2.5 官方 MCP SDK 接入

状态：已通过；[2.5a](lesson05a.md)～[2.5h 三工具 stdio 配置](lesson05h.md) 均已通过，部分由教师代写。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

官方 MCP Python SDK 已安装，当前项目使用 `mcp==2.3.0`。MCP 服务向客户端暴露工具；模型通过客户端调用工具。SDK 从函数签名和文档生成工具描述。[官方入门文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

## 实践任务

先将已有 SQL 查询包装为 MCP 工具，随后再做客户端发现与调用、Python 工具及搜索工具接入。

## 验收标准

各小课单独验收；当前要求见 2.5a。

## 面试考点与踩坑

区分服务端工具、客户端调用与 Agent 编排；不要让模型传入数据库文件路径。

## 提交与评审记录

- 2026-11-01：安装官方 SDK 并开课，等待 2.5a 提交。
