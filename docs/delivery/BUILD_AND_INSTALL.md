# 安装、编译与首次使用

直接体验产品请按“路径A”安装随附软件包；审核源码并重建安装包请按“路径B”操作。本章依次说明环境要求、安装与编译命令、首次配置和故障处理。终端框中的 $ 和 > 是提示符，输入命令时请省略；反斜杠表示命令续行。

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

原生安装和编译要求银河麒麟 V11、amd64 架构和 Python 3.12。请先核对以上输出，再执行本章命令。Debian 系统的兼容构建步骤见“其他平台：从源码编译安装”。

## 路径A：直接安装使用

作品提交包的“源代码”目录提供以下 x64 安装包和校验文件：

1. pixiu_0.1.12-1_amd64.deb
2. pixiu_0.1.12-1_amd64.deb.sha256

在“源代码”目录打开终端，依次执行：

~~~bash
sha256sum -c pixiu_0.1.12-1_amd64.deb.sha256
sudo apt update
sudo apt install ./pixiu_0.1.12-1_amd64.deb
pixiu
~~~

校验显示 OK 后继续安装，安装完成后运行 pixiu 打开主窗口。SHA-256 摘要用于核对安装文件完整性；软件内更新还会验证 Ed25519 签名。需要从源码重建安装包时，按“路径B”操作。

安装包包含桌面程序、记忆服务、Agent Runtime、文档解码组件和 Python 依赖。原生 SDK 运行库由 V11 系统软件源提供。APT 如提示缺少依赖，请先配置官方软件源和 AI 模块，再重新安装。

### 首次模型设置

在PIXIU“设置”的模型页面选择麒麟系统模型。先在系统“AI模块管理”中完成模型授权，然后发送一句普通问候，确认可以收到回答。使用其他支持的模型服务时，在同一设置页填写该服务的API地址、模型与密钥并测试连接。图片和扫描PDF还要求所选模型支持图像输入。

以当前桌面用户运行 pixiu。服务状态应显示版本 0.1.12、记忆服务就绪，以及系统 Embedding 和 Vector Engine 可用。

### 五分钟操作验证

1. 新建会话，输入“请记住：九月家庭电费210元、水费68.50元、燃气费156元”。
2. 等待助手确认保存后，新建另一个会话，询问“九月水电燃气共花了多少钱，请列明细并给出来源”。应得到434.50元，并可点击来源核对记录。
3. 在“设置 → 采集与隐私”添加一个资料目录，启用自动采集和目录文件变化并保存设置。把一份包含日期、地点、预算的TXT活动通知直接放入该目录，等待后台处理完成。
4. 新会话询问通知内容；再放入改期通知。打开待审批计划，核对新旧内容并批准，随后查询应使用更新后的安排。
5. 跨设备验证时，在另一台 V11 电脑安装 PIXIU。两端在设备页完成配对，选择同一共享空间。将一条约定保存到该空间后，在另一端新会话中查询并核对来源。目录自动整理的资料默认保存在本机私人范围；跨设备使用需要明确设置共享内容和空间。

## 路径B：由最小源码包编译

源码包包含固定版本的宿主、Runtime、PIXIU 补丁、系统 SDK 头文件、许可证和构建配置。SOURCE-MANIFEST.json 记录版本、上游提交和文件摘要，构建脚本可直接读取。文档解码组件 Kreuzberg 按依赖锁安装预编译包。

### 1. 解压与核对

把源代码目录中的PIXIU源代码.tar.gz放到一个空工作目录，在该目录执行：

~~~bash
tar -xzf 'PIXIU源代码.tar.gz'
cd PIXIU
python3 verify-source.py
~~~

确认所有源码摘要核对通过后，在解压得到的 PIXIU 目录中执行后续命令。每次复现使用全新解压目录，避免旧构建结果影响检查。

### 2. 准备系统软件

~~~bash
sudo bash build/release/scripts/provision-target.sh \
  kylin-v11-native-x86_64 --with-build-deps
sudo apt install patch tar gzip file util-linux sudo
python3 -m venv /tmp/pixiu-python-check
/tmp/pixiu-python-check/bin/python --version
~~~

预置脚本从V11官方软件源安装Qt5、WebEngine、WebSockets、Multimedia、pybind11以及KylinSDK开发和运行库。应无“找不到软件包”或未满足依赖的错误。Python检查必须输出3.12。

原生开发包包括 libkylin-coreai-embedding-dev、libkysdk-vector-engine-client-dev、libkysdk-genai-nlp-dev，以及快捷键、通知、Qt 扩展和 Wayland 适配包。预置脚本按 build/release/profiles/kylin-v11-native-x86_64.env 安装完整依赖。

### 3. 构建宿主与Runtime

~~~bash
sudo -v
export PIXIU_KYSDK=ON
export CMAKE_BUILD_PARALLEL_LEVEL=2
bash build/release/scripts/prepare-agent-supply-chain.sh
~~~

脚本先在隔离网络中编译桌面宿主，再联网下载锁定版本的构建工具和 Runtime 依赖，最后执行离线安装验证。sudo 用于建立网络隔离环境，实际编译以当前普通用户执行。

末尾检查报告显示 ready=true 表示本步骤成功。构建日志、宿主程序、Runtime 依赖包和许可证记录写入 build/release/evidence/agent-supply-chain/，可用于排查构建失败。

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

最小源码包保留产品构建需要的文件，Runtime 依赖按版本和文件摘要锁定。

PIXIU_SKIP_TESTS=1 用于跳过源码包未附带的前端回归测试工程。上一步已完成宿主编译和启动检查，本步骤继续检查组件版本、构建来源、原生扩展和依赖。

成功后，build/release/out/pixiu_0.1.12-1_amd64.deb 应为非空文件，构建脚本正常退出。该文件是本地重建产物，发布签名和文件摘要以正式发布包为准。

~~~bash
dpkg-deb --info build/release/out/pixiu_0.1.12-1_amd64.deb
sudo apt install ./build/release/out/pixiu_0.1.12-1_amd64.deb
pixiu
~~~

安装完成后，按“路径A”完成首次模型设置和操作验证。

## 其他平台：从源码编译安装

随附 DEB 适用于银河麒麟 V11 x64。其他平台请解压 PIXIU源代码.tar.gz，在目标系统上配置依赖、编译并安装。

Debian 系 x64 环境需要 Python 3.12，可从 generic-ubuntu 构建配置开始适配。预置依赖时使用该配置；准备构建环境前设置 PIXIU_KYSDK=OFF；生成安装包时设置 PIXIU_PROFILE=generic-ubuntu 和 PIXIU_INSTALL_STRICT=0。其余步骤按“路径B”执行，并核对目标发行版的软件包名称。此配置使用可移植实现。

ARM64 等架构需要在目标机编译宿主，按目标 CPU 和 Python 接口版本重建 Runtime 依赖及哈希锁，再添加 build/release/profiles 构建配置并调整 amd64 校验。完成依赖检查、打包和安装验证后，才能确认该架构可用。目前已验证的整包平台为 V11 amd64。

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
