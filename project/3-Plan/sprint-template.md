# Sprint M<major>-<nn> <标题>

> **For agentic workers:** Execute this plan in the current session without launching subagents. Follow the applicable `AGENTS.md` and track execution with checkbox (`- [ ]`) items.

**Goal:** <用一两句话说明本 Sprint 要交付的结果。>

**Architecture:** <说明本 Sprint 的架构边界、不会改动的层级，以及应遵守的包边界。>

**Tech Stack:** TypeScript, pnpm monorepo, Vitest, <其他相关技术>

---

## 1. Sprint 目标

本 Sprint 用于 <说明本次迭代的业务或工程目标>。

核心目标：

- <核心目标 1>
- <核心目标 2>
- <核心目标 3>

## 2. 前置依赖

- <依赖的 FR、设计文档、confirm 文档或前序 sprint。>
- <依赖的现有代码能力、DTO/schema、prompt 资产或 runtime 约定。>
- <需要先确认的配置、环境或索引状态。>

## 3. 边界

本 Sprint 包含：

- <纳入范围 1>
- <纳入范围 2>
- <纳入范围 3>

本 Sprint 不包含：

- <明确不做的事项 1>
- <明确不做的事项 2>
- <明确不做的事项 3>

## 4. 文件结构与职责

| 文件 / 目录 | 操作 | 职责 |
|---|---|---|
| `<path>` | Create/Modify/Move/Delete | <职责说明> |
| `<path>` | Create/Modify/Move/Delete | <职责说明> |
| `tests/<test-file>.test.ts` | Create/Modify | <测试覆盖职责> |

## 5. 工作范围

### 5.1 工作包：<名称>

目标：

- <该工作包的目标 1>
- <该工作包的目标 2>

实现任务清单：

- [ ] 先新增或更新测试，覆盖 <关键行为>，运行相关测试并确认预期失败。
- [ ] 修改 <目标文件或模块>，实现 <核心行为>。
- [ ] 保持包边界：<例如 `apps/web` 只依赖 `packages/shared`，workflow 不依赖 apps>。
- [ ] 运行相关测试，确认从失败转为通过。
- [ ] 必要时重构，保持行为不变，并重新运行相关测试。

验收标准：

- [ ] <可验证验收标准 1>
- [ ] <可验证验收标准 2>
- [ ] <可验证验收标准 3>

### 5.2 工作包：<名称>

目标：

- <该工作包的目标 1>
- <该工作包的目标 2>

实现任务清单：

- [ ] 先新增或更新测试，覆盖 <关键行为>，运行相关测试并确认预期失败。
- [ ] 修改 <目标文件或模块>，实现 <核心行为>。
- [ ] 核对相关文档、配置、prompt 或 runtime 写入位置是否符合 AGENTS.md。
- [ ] 运行相关测试，确认从失败转为通过。

验收标准：

- [ ] <可验证验收标准 1>
- [ ] <可验证验收标准 2>
- [ ] <可验证验收标准 3>

### 5.3 工作包：<名称>

目标：

- <该工作包的目标 1>
- <该工作包的目标 2>

实现任务清单：

- [ ] 先新增或更新测试，覆盖 <关键行为>，运行相关测试并确认预期失败。
- [ ] 修改 <目标文件或模块>，实现 <核心行为>。
- [ ] 补齐必要的错误处理、降级、日志或 artifact 记录。
- [ ] 运行相关测试，确认从失败转为通过。

验收标准：

- [ ] <可验证验收标准 1>
- [ ] <可验证验收标准 2>
- [ ] <可验证验收标准 3>

## 6. TDD 与测试计划

- [ ] 每个核心行为先写失败测试，再写实现，再重构。
- [ ] 修复类任务必须增加可复现的回归用例。
- [ ] 新增或修改测试文件：`tests/<test-file>.test.ts`
- [ ] 覆盖成功路径、失败路径、边界输入和回归场景。
- [ ] 如没有现成测试入口，先建立最小可执行测试骨架。

## 7. 验证命令

优先运行受影响包和相关测试：

```bash
pnpm test -- <相关测试文件>
pnpm typecheck
pnpm build
pnpm lint
```

完整默认验证：

```bash
pnpm test
pnpm typecheck
pnpm build
pnpm lint
```

## 8. 风险与回滚

风险：

- <风险 1>
- <风险 2>

控制方式：

- <测试、边界约束、feature flag、配置隔离或文档说明。>
- <避免写入源码树的 runtime 数据；运行数据统一写入 `runtime/`。>

回滚方式：

- <说明如果失败，如何撤回本 Sprint 的文件、配置或行为变更。>

## 9. 交付物

- [ ] 代码变更：<模块或包>
- [ ] 测试变更：<测试文件>
- [ ] 文档变更：<文档文件>
- [ ] runtime/config 变更：<如无则写“无”>

## 10. 完成判定

- [ ] 所有工作包验收标准通过。
- [ ] 相关测试已通过，且必要的默认验证命令已运行或明确说明无法运行的原因。
- [ ] 未违反 `apps/*`、`packages/*`、`runtime/`、prompt 外置和 V1 reference 边界。
- [ ] 如涉及 FR 完成态，相关 FR 文档、review-confirm 和 release 验收记录已按流程更新。

## 11. 备注

- <补充说明、待确认问题、后续 sprint 建议或 review traceability。>
