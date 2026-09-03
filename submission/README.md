# PIXIU 赛事正式交付区

本目录用于生成和存放华南理工大学 PIXIU 团队的最终赛事交付文件。它不是日常构建
输出目录，也不得放入未脱敏日志、开发机信息、密钥、临时数据库或未经审核的证据。

## 权威口径

交付清单同时执行两份只读官方材料：

- `docs/OriginProblemDescription.md` 第五、八节；
- `docs/完整赛题要求.pptx` 第 21 页。

官方核心作品为项目报告 PPT、技术方案及测试结果 Word/PDF、源代码及规范；PPT 细则
另要求部署文档及不超过 7 分钟的 `.avi`、`.mp4` 或 `.wmv` 功能演示视频。平台文字
方案要求技术文档/用户手册覆盖需求、架构、算法、实现、部署、操作、数据集、对比
实验和量化指标，并提供记忆流转说明、至少一个实际案例及 V11 适配测试报告。经报名
系统审核通过的盖章报名表须同步报送，但它不是由代码仓库自动生成的作品文件。

最终外层名称严格采用：

`华南理工大学－OSAgent记忆优化及高效应用研究－PIXIU`

## 目录约定

- `submission-plan.json`：唯一的机器可读交付清单、来源和就绪门；
- `build_submission.py`：校验官方原件、release commit、Git 洁净度和全部文件，生成
  `SHA256SUMS` 与最终 ZIP；
- `final/`：最终文件生成位置，构建产物不进入 Git，避免源码包递归包含自身；
- `human-input/`：说明必须由团队负责人提供的 PPT、视频和盖章报名表。

当前 `release_ready=false` 是有意的。只有 H-01～H-03、Agent 闭环、最终 V11 指标、
三设备同步、安装/升级和 D-01～D-10 全部以同一 commit 通过并审核后，才可填写最终
commit、把各门设置为 `passed`，并运行：

```bash
python3 submission/build_submission.py --check
python3 submission/build_submission.py --package
```

`--package` 在任何门未通过、文件缺失、命名/格式错误、官方原件哈希改变或工作区不
洁净时都会失败。视频和 PPT 只校验，不由自动化生成；其他文档及源码包必须在最终
候选完成后由仓库维护源生成并经人工审核，禁止以当前工作稿占位提交。
