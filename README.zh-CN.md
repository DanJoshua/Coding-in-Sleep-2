# 🌙 sleepcode

<p align="center">
  <b>基于树搜索的受限非交互式编码代理会话编排工具。</b>
</p>

<p align="center">
  让代理在你睡觉时写代码。醒来即可查看精选报告。
</p>

<p align="center">
  <a href="README.md">🇬🇧 English</a>
  ·
  <a href="#-特性">特性</a>
  ·
  <a href="#-快速开始">快速开始</a>
  ·
  <a href="#-使用说明">使用说明</a>
  ·
  <a href="#-架构">架构</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## ✨ 特性

- 🌲 **树状搜索** — 通过 Builder、Fixer 和 Rebuilder 构建搜索树，并行探索多条解决方案路径。
- 🔒 **隔离工作区** — 每个候选方案在独立的 Git worktree 中运行；原始仓库始终不受干扰。
- 🤖 **多代理协作** — 编排 Codex、Kimi 等多种代理。Worker、Reviewer 和 Voter 可以由不同代理担任。
- 📝 **丰富报告** — 生成面向人类的最终报告、结构化 JSON 摘要以及每个节点的详细产物。
- ⏱️ **适合夜间运行** — 专为后台长时间运行设计。启动后安心睡觉，早上查看结果。
- 🧪 **可插拔验证** — 支持自定义测试命令、自动发现单元测试，或仅编译的冒烟检查。

## 🚀 快速开始

```bash
# 安装
pip install -e .

# 运行
sleepcode run \
  --repo /path/to/repo \
  --task-file /path/to/task.md \
  --guidelines-file /path/to/guideline.md

# 恢复之前的运行
sleepcode resume --run-dir runs/<run-id>
```

默认情况下，产物会写入 `runs/<run-id>/` 目录。从这里开始查看：

```bash
less runs/<run-id>/final_report.md
```

## 📖 使用说明

### 基础用法

运行开始前，目标仓库必须是一个干净的 Git 仓库。

传递给 `--repo`、`--task-file`、`--guidelines-file` 和 `--out` 的路径，除非使用绝对路径，否则均相对于你运行 `sleepcode` 时的 shell 目录解析。

**示例（相对路径）：**

```bash
cd /home/woden/CS2

sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

**使用绝对路径的相同命令：**

```bash
sleepcode run \
  --repo /home/woden/CS2/OmegaWiki \
  --task-file /home/woden/CS2/task.md \
  --guidelines-file /home/woden/CS2/guideline-for-cs.md
```

### 产物说明

| 文件 / 目录 | 说明 |
| :--- | :--- |
| `final_report.md` | 面向人类的晨间报告，包含推荐节点 |
| `final_report.json` | 结构化运行摘要 |
| `expostulation.md` | 本次运行共享的可复用实现证据 |
| `sleepcode.sqlite3` | 持久的编排状态与检查点 |
| `nodes/node-NNN/` | 提示词、报告、diff、验证日志、原始代理日志 |
| `worktrees/node-NNN/` | 可直接查看的候选仓库 |

### 搜索参数

默认值是为夜间运行而设，比较保守：

```bash
--max-nodes 16
--max-depth 3
--jobs 2
--builder-fanout 3
--fixer-fanout 2
--rebuilder-fanout 1
```

| 参数 | 说明 |
| :--- | :--- |
| `--max-nodes` | 总预算，包含根节点。默认 `16` 表示根节点 + 最多 15 个候选节点。 |
| `--day-mode` | 白天快速运行。如果没有同时显式指定 `--max-nodes`，则将其覆盖为 `8`。 |
| `--builder-fanout` | 从干净基线出发的独立首次尝试数量。对于有多种可行设计的任务可以增大。 |
| `--fixer-fanout` | 每个父节点的修复尝试上限。限制单个候选在整个运行中可获得的修复次数。 |
| `--rebuilder-fanout` | 每个父节点的重建尝试上限。基于候选的意图和报告，从基线重新开始。 |
| `--max-depth` | 树根以下的最大深度。Builder 位于深度 1；Fixer 和 Rebuilder 位于更深层。 |
| `--jobs` | 仅控制并发度。不会减少总预算或分支数。 |

### 推荐配置

**小型、低成本运行：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --max-nodes 4 \
  --max-depth 2 \
  --builder-fanout 2 \
  --fixer-fanout 1 \
  --rebuilder-fanout 0 \
  --jobs 1
```

**默认夜间运行：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md
```

**白天运行（更少节点）：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --day-mode
```

**更广泛的设计搜索：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --max-nodes 24 \
  --builder-fanout 4 \
  --fixer-fanout 2 \
  --rebuilder-fanout 2 \
  --jobs 3
```

**仅使用 Codex：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --agents codex
```

## 🤖 代理

默认：`--agents codex,kimi`

- **Worker** 优先使用 Codex：`Codex xhigh → Codex high → Kimi → 循环`。
- **Review** 尽可能使用与 Worker 不同的代理。
- **Voting** 采用多代理视角，要求为 `fix`、`rebuild` 或 `drop` 提供具体证据。

| 参数 | 说明 |
| :--- | :--- |
| `--agents codex` | 更快或更简单的运行 |
| `--agents kimi` | 由 Kimi 处理所有角色 |
| `--model <name>` | 为支持的代理指定模型 |

## 🧪 验证

默认情况下，sleepcode 假设目标仓库没有测试。

验证顺序：

1. 如果提供了 `--test-cmd`，则运行该命令。
2. 否则，如果候选创建了 `.sleepcode/tests/test*.py`，则运行：
   ```bash
   python -m unittest discover -s .sleepcode/tests
   ```
3. 否则，对于 Python 仓库，运行仅编译的冒烟检查（报告为 `smoke`，而非完整通过）。
4. 否则，将验证报告为 `unknown`。

**自定义测试命令：**

```bash
sleepcode run \
  --repo OmegaWiki \
  --task-file task.md \
  --guidelines-file guideline-for-cs.md \
  --test-cmd "python -m pytest"
```

## 📋 运行结束后

Sleepcode **不会**合并、提交或推送任何内容。它将候选变更留在独立的工作区中，并将补丁写入运行产物。最终仍由人工决定接受哪些变更。

### 检查推荐的候选

```bash
# 从最终报告开始
less runs/<run-id>/final_report.md

# 检查推荐的节点，例如 node-008
less runs/<run-id>/nodes/node-008/worker_report.md
less runs/<run-id>/nodes/node-008/review_report.md
less runs/<run-id>/nodes/node-008/validation.log
git -C runs/<run-id>/worktrees/node-008 diff HEAD
```

### 应用补丁

基于 sleepcode 使用的相同基线引用创建一个新分支：

```bash
cd /path/to/target-repo
git switch -c accept-sleepcode-node-008

# 验证补丁可以干净地应用
git apply --check runs/<run-id>/nodes/node-008/diff.patch

# 应用并暂存
git apply --index runs/<run-id>/nodes/node-008/diff.patch
```

如果目标仓库在 sleepcode 启动后发生了变化，尝试三路合并：

```bash
git apply --3way runs/<run-id>/nodes/node-008/diff.patch
```

然后像处理普通 Git 冲突一样解决冲突，并运行你自己的检查。

### 清理

```bash
# 不再需要时删除运行产物
rm -rf runs/<run-id>
```

如果你使用 `--cleanup-worktrees` 启动运行，sleepcode 会在结束时删除候选工作区，但报告和节点产物仍会保留。

## ⚙️ 超时与工作区

| 参数 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `--agent-timeout` | `3600` | 单次代理回合的最大挂钟时间（秒） |
| `--agent-startup-timeout` | `120` | 终止没有初始输出的回合 |
| `--agent-idle-timeout` | `300` | Codex 在无输出后终止 |
| `--kimi-idle-timeout` | `0` | 禁用 Kimi 空闲超时（Kimi 可能会静默运行子代理很长时间） |
| `--allow-network` | `false` | 允许 Codex 代理访问外部网络（用于测试需要调用外部 API 的场景） |

候选工作区默认保留（`--keep-worktrees`）。如果你只想要报告和产物，请使用 `--cleanup-worktrees`。

## 🏗️ 架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   任务与    │────▶│   根节点    │────▶│   Builders  │
│   指南文件  │     │             │     │  (深度 1)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────┐
                    ▼                          ▼          ▼
              ┌─────────┐               ┌──────────┐ ┌──────────┐
              │ Fixers  │               │ Rebuild  │ │  Vote /  │
              │(修复)   │               │(重建)    │ │  Drop    │
              └─────────┘               └──────────┘ └──────────┘
                    │
                    ▼
            ┌───────────────┐
            │  最终报告     │
            │ (面向人类)    │
            └───────────────┘
```

调度器优先展开 Builder 种子，然后使用代理投票决定每个候选应该被修复、重建还是丢弃。

## 📄 许可证

MIT
