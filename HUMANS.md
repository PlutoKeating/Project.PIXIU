# HUMAN.md

这是写给人的协作说明。意思很简单：让 Agent 帮你干活，但最后把关的人必须是你。

---

## 1. 你要负责什么

你是这个项目的把关人。

Agent 可以改文件、写代码、写文档，也可以在本地提交。可是它不能替你决定哪些东西能发到远程，哪些东西能进测试环境，哪些东西能上线。

你要做的事：

- 说清楚要改什么，改到什么程度算完成。
- 看一眼 Agent 改了哪些文件。
- 确认没有把密码、`.env`、依赖包、构建结果、数据库、缓存、日志一起提交。
- 决定什么时候 `push`。
- 决定什么时候合并到 `staging`。
- 决定什么时候合并到 `production`。

一句话：Agent 负责干活，你负责开门。

---

## 2. 最重要的三条分支

本项目按这个顺序走：

```text
个人特性分支 -> staging 分支 -> production 分支
```

你可以把它理解成三道门：

- 个人特性分支：自己干活的地方。
- `staging`：大家一起检查的地方。
- `production`：真正给用户用的地方。

不要跳门。没有检查过的东西，不要直接进 `production`。

---

## 3. 分支到底是什么

很多新同事会误会：以为一个分支只是一小块代码。不是。

一个分支是一整套项目代码。你切到哪个分支，看到的就是那个分支上的完整项目。

区别只在于：不同分支保存的版本不一样。

可以这样理解：

- `production` 是正式店面里的完整货架。
- `staging` 是后屋里正在检查的完整货架。
- 个人特性分支是你自己正在整理的完整货架。

你不是只拿着一小块代码在改。你是在一份完整项目上改其中几处。

所以切分支前后，要看清楚自己在哪个分支。不要在错的分支上改东西。

---

## 4. 个人特性分支

每次做一个新功能、修一个问题、整理一批文档，都先开自己的分支。

推荐命名：

```text
feature/<short-name>
fix/<short-name>
docs/<short-name>
chore/<short-name>
```

常用命令：

```bash
git checkout -b feature/example
# 开发或让 Agent 修改
git add <changed-files>
git commit -m "Add example feature"
```

你要检查：

- 这次改动是不是只改了该改的地方。
- 有没有误提交 `.env`、`node_modules`、`dist`、`.venv`、数据库、缓存或日志。
- 有没有做必要的测试、构建或人工检查。
- commit 信息能不能看懂。

---

## 5. staging 分支

`staging` 是试一试的地方。

个人分支上的东西，先合进 `staging`，让大家检查。检查没问题，再考虑上线。

进 `staging` 前，至少要确认：

- 代码或文档已经看过。
- 该跑的测试或构建已经跑过。
- 没有密码、密钥、真实 `.env` 内容。
- 没有一大堆和任务无关的改动。

不要直接在 `staging` 上乱改。先在个人分支改好，再合进去。

---

## 6. production 分支

`production` 是正式给用户用的地方。

只有在 `staging` 检查通过后，才可以进 `production`。

进 `production` 前，你要能说清楚：

- 这次到底发了什么。
- 在 `staging` 有没有试过。
- 出问题怎么退回去。
- 有没有改数据库、环境变量、第三方服务或权限。
- 要不要通知其他人。

如果这些说不清，就先别进 `production`。

---

## 7. .gitignore 是什么

`.gitignore` 是一张“不要提交清单”。

项目里有些东西只适合放在你自己的电脑上，不应该交给 Git，也不应该发给别人。`.gitignore` 就是告诉 Git：这些东西别管，别提交。

常见不该提交的东西：

- `.env`：本地环境配置，里面可能有密码、密钥、服务器地址。
- `node_modules/`：前端依赖包，太大，而且别人可以自己安装。
- `dist/`、`build/`：构建出来的结果，不是手写源码。
- `.venv/`：Python 本地虚拟环境。
- `*.db`、`*.sqlite`：本地数据库。
- 日志、缓存、临时文件。

`.gitignore` 能做什么：

- 防止把密码和密钥交出去。
- 防止仓库变得很大很乱。
- 防止每个人电脑上的临时文件互相干扰。
- 让 Git 只关注真正该保存的源码和文档。

怎么用：

- 平时不要随便删 `.gitignore` 里的规则。
- 新增一种本地生成文件时，先想想它该不该提交。
- 不该提交的，就把规则加到 `.gitignore`。
- 该给大家看的配置样板，放进 `.env.example`，不要放真实 `.env`。
- 提交前看一眼 `git status`，发现奇怪文件要停下来检查。

重要提醒：如果一个文件已经被 Git 跟踪了，后来再写进 `.gitignore`，它不会自动消失。需要单独处理。新同事不确定时，先问负责人。

---

## 8. Agent 和人的分工

Agent 必须经常在本地执行：

```bash
git add <changed-files>
git commit -m "<clear local commit message>"
```

Agent 绝对不能执行：

```bash
git push
```

人的责任是远程操作：

- `git push`
- 创建 Pull Request / Merge Request
- 找人 review
- 合并到 `staging`
- 从 `staging` 合并到 `production`
- 创建 tag 或 release
- 触发正式部署

简单说：Agent 只能把东西装进本地箱子，不能自己寄出去。寄不寄、寄到哪里，由你决定。

---

## 9. 推荐做事顺序

1. 你先开个人特性分支。
2. 你告诉 Agent 要做什么。
3. Agent 改文件，并在本地 commit。
4. 你检查改动和 commit。
5. 你确认没问题后再 `git push`。
6. 你创建 PR/MR。
7. 通过检查后合进 `staging`。
8. `staging` 验证没问题后，再合进 `production`。

---

## 10. 最后记住

不要急着上线。

先在自己的分支改，再到 `staging` 检查，最后才进 `production`。这套流程看起来多一步，其实是在帮你少出事故。

---

## 11. 参考资料

- GitHub Flow: https://docs.github.com/en/get-started/using-github/github-flow
- GitLab Flow best practices: https://about.gitlab.com/topics/version-control/what-are-gitlab-flow-best-practices/
- GitLab branching strategies: https://docs.gitlab.com/user/project/repository/branches/strategies/
- Atlassian Gitflow workflow: https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow