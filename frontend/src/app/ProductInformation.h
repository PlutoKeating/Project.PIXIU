#pragma once

#include <QCoreApplication>
#include <QString>

// Shared factual descriptions; neither a new license nor a guarantee of erasure.
class ProductInformation
{
    Q_DECLARE_TR_FUNCTIONS(ProductInformation)
public:
    static QString about(const QString &version)
    {
        return tr("PIXIU %1\n\n"
                  "面向银河麒麟 V11 与 Debian 系发行版的记忆工作台。"
                  "唯一桌面宿主基于 openKylin Agent，PIXIU 提供记忆、来源、偏好、"
                  "冲突、遗忘、采集及可信设备同步管理。\n\n"
                  "管理功能直接访问记忆服务，不要求先配置云模型。"
                  "Agent 会话与模型调用、工具执行由集成的 Agent 运行时处理。")
            .arg(version);
    }
    static QString dataUse()
    {
        return tr("默认部署将记忆服务与数据库放在本机；更改后端地址会改变数据发送目标。\n\n"
                  "可信设备同步只处理 shared:* 共享范围，user:* 个人范围不经该同步链路传出。"
                  "这不等于所有内容永不联网：会话输入、召回的记忆上下文和工具结果可能发送到"
                  "所选模型服务；麒灵系统云模型及官方直连模型不是离线推理。\n\n"
                  "自动采集由“采集与隐私”中的已保存配置控制。关闭采集不会删除已有记忆。"
                  "敏感识别有能力边界，不能保证识别所有私人信息。\n\n"
                  "遗忘采用预览与人工确认。当前知识隐藏、向量删除和共享墓碑不等于证据、"
                  "会话、日志、备份及所有副本均已物理擦除。共享送达状态需另行核对。");
    }
    static QString licenses()
    {
        return tr("PIXIU 为参赛作品，集成 openKylin Agent、Agent Runtime 与其他第三方组件。"
                  "项目贡献与上游组件应分别识别；本说明不授予新的许可，也不替代实际许可证。\n\n"
                  "安装包中的第三方声明、组件清单和对应许可证位于：\n"
                  "/usr/share/doc/pixiu/agent/NOTICE.agent.txt\n"
                  "/usr/share/doc/pixiu/agent/agent-components.spdx.json\n"
                  "/usr/share/doc/pixiu/agent/LICENSE.kylin-agent\n"
                  "/usr/share/doc/pixiu/agent/LICENSE.kylin-agent-runtime\n"
                  "/usr/share/doc/pixiu/agent/message-renderer/\n\n"
                  "请以对应安装包内实际文件为准；开发环境未安装软件时这些路径可能不存在。");
    }
};
