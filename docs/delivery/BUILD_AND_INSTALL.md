# 从交付文件到可用产品

本章给出直接安装与源码编译两条完整路径。希望体验产品时使用路径A；希望审核实现并重建安装包时使用路径B。两条路径最终都得到同一个PIXIU桌面入口。

## 环境与依赖

| 项目 | 要求 |
|---|---|
| 原生运行与编译系统 | 银河麒麟桌面操作系统V11，amd64，桌面用户会话和systemd用户服务 |
| Python | 系统python3必须为3.12，Runtime锁文件固定cp312；不能以3.14替换 |
| 系统AI | 安装并启用Embedding、Vector Engine与麒灵模型服务，在系统AI模块管理中完成授权 |
| 网络 | 首次下载系统软件包、Python wheels及使用云模型时联网；已有本地记忆可离线读写 |
| 权限 | 普通桌面用户运行软件，sudo只用于安装依赖与DEB以及构建隔离 |
| 构建工具 | CMake、Ninja、g++、pkg-config、patch、tar、Python开发头文件、Qt5与KylinSDK开发包 |

检查系统与解释器：

~~~bash
cat /etc/os-release
dpkg --print-architecture
python3 --version
~~~

应确认V11、amd64与Python 3.12。其他系统可使用Debian兼容构建，但不代表麒麟原生SDK结果。本章原生命令不要在非V11系统强制运行。

## 路径A：直接安装使用

打开项目0.1.12发行页并下载以下两项，放在同一个空目录：

https://github.com/PlutoKeating/Project.PIXIU/releases/tag/v0.1.12

- pixiu_0.1.12-1_amd64.deb
- pixiu_0.1.12-1_amd64.deb.sha256

在下载目录打开终端，依次执行：

~~~bash
sha256sum -c pixiu_0.1.12-1_amd64.deb.sha256
sudo apt update
sudo apt install ./pixiu_0.1.12-1_amd64.deb
pixiu
~~~

校验应显示OK，安装应正常结束，随后出现PIXIU主窗口。发行页不可访问时，可按路径B使用提交的源码生成同名DEB。SHA-256用于确认下载完整性，软件内更新另有Ed25519签名校验。

安装包包含桌面、记忆服务、Agent Runtime、文档解码与Python依赖。系统仓库仍需能提供原生SDK运行库；如果APT提示缺失依赖，应配置V11官方软件源与AI模块，不能强行忽略依赖。

### 首次模型设置

在PIXIU“设置”的模型页面选择麒麟系统模型。先在系统“AI模块管理”中完成模型授权，然后发送一句普通问候，确认可以收到回答。使用其他支持的模型服务时，在同一设置页填写该服务的API地址、模型与密钥并测试连接。图片和扫描PDF还要求所选模型支持图像输入。

服务状态应显示当前版本0.1.12、记忆服务就绪以及系统Embedding和Vector Engine可用。程序要以当前桌面用户启动，不要执行sudo pixiu。

### 五分钟操作验证

1. 新建会话，输入“请记住：九月家庭电费210元、水费68.50元、燃气费156元”。
2. 等待助手确认保存后，新建另一个会话，询问“九月水电燃气共花了多少钱，请列明细并给出来源”。应得到434.50元，并可点击来源核对记录。
3. 在“设置 → 采集与隐私”添加一个资料目录，启用自动采集和目录文件变化并保存设置。把一份包含日期、地点、预算的TXT活动通知直接放入该目录，等待后台处理完成。
4. 新会话询问通知内容；再放入改期通知。打开待审批计划，核对新旧内容并批准，随后查询应使用更新后的安排。
5. 需要跨设备验证时，在另一台V11电脑独立安装。两端打开设备页完成配对并选择同一共享空间；在写入端明确将一条约定保存到该共享空间，另一端新会话查询并核对来源。目录自动整理默认私人范围，不会自动变成共享记录。

## 路径B：由最小源码包编译

源码包已包含固定版本的宿主和Runtime源代码、PIXIU补丁、系统SDK头文件、许可证及构建配置。无需Git仓库、git clone或git submodule；SOURCE-MANIFEST.json代替Git记录版本、上游提交和文件摘要。文档解码库Kreuzberg按固定wheel安装，因此不附其网站、测试与Rust开发仓库。

### 1. 解压与核对

把源代码目录中的PIXIU源代码.tar.gz放到一个空工作目录，在该目录执行：

~~~bash
tar -xzf 'PIXIU源代码.tar.gz'
cd PIXIU
python3 verify-source.py
~~~

应显示源码文件摘要全部通过。以下命令均在这个PIXIU目录执行。不要复用含旧构建结果的目录。

### 2. 准备系统软件

~~~bash
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-native-x86_64 --with-build-deps
sudo apt install patch tar gzip file util-linux sudo
python3 -m venv /tmp/pixiu-python-check
/tmp/pixiu-python-check/bin/python --version
~~~

预置脚本从V11官方软件源安装Qt5、WebEngine、WebSockets、Multimedia、pybind11以及KylinSDK开发和运行库。应无“找不到软件包”或未满足依赖的错误。Python检查必须输出3.12。

核心原生开发包为libkylin-coreai-embedding-dev、libkysdk-vector-engine-client-dev、libkysdk-genai-nlp-dev，以及libkysdk-shortcut-dev、libkysdk-notification-dev、libkysdk-qtwidgets-dev、libkysdk-waylandhelper-dev。完整软件包参数随源码位于build/release/profiles/kylin-v11-native-x86_64.env，执行预置命令即可，无需自行拼接依赖。

### 3. 构建宿主与Runtime

~~~bash
sudo -v
export PIXIU_KYSDK=ON
export CMAKE_BUILD_PARALLEL_LEVEL=2
bash build/release/scripts/prepare-agent-supply-chain.sh
~~~

此步骤先在隔离网络中编译宿主，再联网下载锁定的构建工具和Runtime依赖，随后离线安装验证。sudo用于建立网络命名空间，实际构建仍以当前普通用户运行。

成功结果是末尾供应链检查报告ready=true。日志、宿主二进制、Runtime wheelhouse与许可证记录保存在build/release/evidence/agent-supply-chain/。该目录为现场生成内容，不随最小源码包交付。

### 4. 生成完整安装包

~~~bash
export PIXIU_PROFILE=kylin-v11-native-x86_64
export PIXIU_KYSDK=ON
export PIXIU_INSTALL_STRICT=1
export PIXIU_PYTHON=python3
export PIXIU_PYTHON_VERSION=312
export PIXIU_SKIP_TESTS=1
make -C build/release build-deb
~~~

最小源码包及Runtime构建均剔除上游历史备份、使用状态和开发测试，Runtime wheel摘要已随构建锁同步。

最小源码包不含开发回归测试，PIXIU_SKIP_TESTS=1跳过回归专用前端工程；正式宿主在上一步已经编译和冒烟检查，版本一致性、供应链、原生扩展和依赖检查仍执行。

安装包输出到build/release/out/pixiu_0.1.12-1_amd64.deb。成功时脚本正常退出，目录内存在非空DEB文件。本地重建包不带官方发布私钥签名，也不宣称与发布资产逐字节相同。

~~~bash
dpkg-deb --info build/release/out/pixiu_0.1.12-1_amd64.deb
sudo apt install ./build/release/out/pixiu_0.1.12-1_amd64.deb
pixiu
~~~

然后按路径A的首次设置与五分钟操作验证使用产品。

## 故障定位与恢复

| 现象 | 处理方法 |
|---|---|
| Python版本不是3.12 | 使用V11提供的3.12解释器，不修改哈希锁冒充其他ABI |
| 找不到KylinSDK包或库 | 检查V11官方源、AI模块及开发包，重新预置依赖；不要关闭原生检查 |
| Runtime wheel与锁文件不一致 | 停止打包，核对源码摘要、Python3.12、amd64与依赖下载；不要手工改锁 |
| 已存在供应链evidence目录 | 保留日志后换一个全新解压目录重建，不混用旧结果 |
| sudo -n或unshare权限失败 | 当前终端执行sudo -v，使用允许网络命名空间的本机V11环境 |
| 记忆服务未就绪 | 执行下方服务与日志命令，检查系统AI组件和当前用户会话 |
| 会话不能生成回答 | 检查模型授权、地址、密钥和网络；记忆就绪不等于模型连接正常 |
| 目录文件未处理 | 确认目录授权已保存、自动采集开启，文件为直接子文件且不超过30MiB |
| 配对后查不到记录 | 确认两端在线、同一共享范围，记录确实写入共享空间 |

~~~bash
systemctl --user status pixiu-backend.service
journalctl --user -u pixiu-backend.service -n 50 --no-pager
systemctl --user restart pixiu-backend.service
~~~

软件更新在设置中完成。配置、记忆与设备身份位于当前用户目录，升级保留数据。卸载程序使用sudo apt remove pixiu；删除用户数据是另一个操作，卸载前先保留需要的资料。
