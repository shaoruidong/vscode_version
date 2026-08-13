# VSCode版本切换工具

> Cross-platform VSCode version manager & switcher — detect installed versions, download & install new versions, switch / upgrade / downgrade with configs and plugins preserved.

跨平台的 VSCode 版本管理工具：**检测已安装版本、从官方源下载并安装新版本、一键切换 / 升级 / 降级**，全程保留配置和插件。首次下载后本地缓存，之后秒级切换；无需重新下载安装包即可在不同版本之间自由来回。

支持本地源码运行，也支持一键打包成免 Python 环境的 EXE。

## 最近更新 (2026-08-13)

- ✅ **检测增强**：支持 D 盘等任意路径安装的 VSCode —— 注册表 `DisplayIcon` 兜底 + 从 PATH 解析 + 深度受限递归扫描；C/D 盘多版本可同时列出
- ✅ **切换优化**：目标版本未安装时不再提示"以后才支持下载"，改为询问是否下载，确认后自动下载、缓存并切换
- ✅ **修复**：GBK 控制台中文输出崩溃；过时的"下载功能将在后续版本提供"提示文案
- ✅ **打包支持**：加入 `build_config.spec` / `build.bat` / `run.bat` / `.gitignore`，可一键构建 EXE
- ✅ **缓存即切换**：在"缓存管理"中选择任一已缓存的版本即可直接快速切换，无需再次下载

## 功能特性

### 已实现功能 ✅

1. **版本检测（增强版）**
   - 自动检测本地已安装的VSCode版本
   - **无干扰检测**：不会启动VSCode窗口，静默后台检测
   - 支持预定义路径快速检测
   - **全局搜索**：注册表（`DisplayIcon` / `InstallLocation` 双兜底）+ PATH 解析 + 深度受限递归扫描，支持任意盘符和路径（如 `D:\Program Files\VS Code\`）
   - **智能版本读取**：直接从 `package.json` 文件读取版本号
   - 显示版本号、安装路径、版本类型等详细信息
   - 支持稳定版和 Insiders 版
   - **性能优化**：常规检测速度 < 0.5 秒

2. **版本管理**
   - 从VSCode官方API获取最新版本列表
   - 版本列表本地缓存（24小时有效期）
   - 一键更新版本列表
   - 版本演变图谱可视化

3. **版本切换（含下载安装）**
   - 在已安装的版本之间快速切换
   - **未安装的版本**：询问后自动下载安装并切换（快速切换模式）
   - **智能缓存**：下载过的新版本自动缓存；快速切换前会先查缓存，命中即秒切、无需再次下载
   - 保留用户配置和插件设置
   - 版本切换结果反馈

4. **配置管理**
   - 配置文件备份
   - 插件兼容性分析
   - 变更报告生成

5. **用户界面**
   - 现代化的 PyQt5 桌面应用
   - 响应式 Web 界面（HTML版本）
   - 清晰的操作反馈

### 核心组件

- **RemoteVersionRepository**: 从VSCode官方API获取版本信息
- **LocalVersionRepository**: 管理本地安装的VSCode版本
- **CacheManager**: 版本信息缓存管理
- **VSCodeVersionManager**: 版本管理核心逻辑
- **ConfigMigrationManager**: 配置迁移管理
- **SimpleVersionSwitcher**: 快速切换器（下载 + 缓存 + 替换文件）

## 快速开始（本地运行）

### 环境要求

- Python 3.7+
- Conda 环境（推荐）
- Windows / macOS / Linux

### 安装步骤

1. 克隆或下载项目到本地

2. 创建并激活 conda 环境：
```bash
conda create -n vs python=3.9
conda activate vs
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

### 运行应用（本地使用）

#### Windows 用户
双击运行 `run.bat`（脚本会自动 `conda activate vs` 并启动 GUI）

#### 命令行运行
```bash
conda activate vs
python main.py
```

#### Web 版本
在浏览器中直接打开 `index.html` 文件

## 构建成 EXE（Windows）

项目内置 PyInstaller 打包配置，可构建成**免 Python 环境的单文件桌面程序**，直接发给其他用户使用。

### 方法一：一键打包（推荐）

双击运行 `build.bat`，脚本会自动打包并生成：

```
dist\VSCode版本切换工具.exe
```

### 方法二：命令行打包

```bash
conda activate vs
pip install -r requirements.txt pyinstaller
python -m PyInstaller build_config.spec --noconfirm --clean
```

### 验证与说明

- 双击 `dist\VSCode版本切换工具.exe` 启动测试
- 打包产物是单文件、无控制台窗口
- 修改 `main.py` / `version_switcher_simple.py` 后，重新执行打包命令即可更新
- `build_config.spec` 已包含 PyQt5 / requests / yaml / packaging / psutil 等依赖的 `hiddenimports`
- 打包时自动把 `version_switcher_simple.py` 作为数据文件一并打入
- 可通过修改 spec 中的 `name` 字段自定义 exe 名称

## 使用说明

### 主界面功能

1. **当前版本信息**
   - 显示当前活动的 VSCode 版本
   - 点击"刷新信息"重新检测

2. **版本选择**
   - 点击"加载可用版本"从缓存或 API 获取版本列表
   - 点击"更新版本列表"强制从官方 API 获取最新版本
   - 从下拉框选择目标版本

3. **操作选项**
   - 备份当前配置：切换前备份配置文件
   - 迁移配置和插件：保留用户设置
   - 分析插件兼容性：检查插件兼容性

4. **版本操作**
   - **切换到选中版本**：目标版本已安装时直接切换（修改 PATH）；**未安装时询问是否下载并安装**，确认后自动下载切换
   - **快速切换（智能缓存）**：先检查缓存，目标版本已缓存则直接秒切；未缓存才下载，下载后自动缓存，下次即秒切
   - 回滚到上一个版本：恢复到之前的版本

### 版本演变图谱

显示：
- 当前活动版本
- 推荐版本（比当前版本新的 3 个版本和旧的 2 个版本）
- 可用版本总数
- 最近的 10 个版本

### 版本缓存机制

- 通过工具下载的新版本会**自动缓存**，之后切到同一版本时**直接秒切**（先查缓存，命中即用，无需再次下载）
- 缓存**无数量上限**，会保留所有下载过的版本
- 缓存位置：系统用户缓存目录（appdirs 下的 `VSCodeSwitcher`）
- 在"缓存管理"对话框中可查看已缓存版本列表、缓存总大小，**选择任一缓存版本即可直接秒切**（无需再次下载），也可一键清空

### 插件兼容性分析

点击"分析兼容性"按钮，系统会：
- 扫描已安装的插件
- 分析与目标版本的兼容性
- 显示兼容、不兼容和未知状态的插件

### 变更报告

每次版本切换后，系统会生成详细的变更报告，包括：
- 操作类型和时间
- 源版本和目标版本
- 备份路径
- 插件兼容性分析结果
- 警告信息和建议

## 测试

仓库包含以下测试脚本（在 `vs` 环境下运行）：

```bash
conda activate vs
python test_download_speed.py   # 下载速度 / 镜像源测试
python test_quick_switch.py     # 快速切换流程测试
```

## 项目结构

```
vscode_version/
├── main.py                     # 主程序（PyQt5 GUI）
├── version_switcher_simple.py  # 快速切换器（下载 + 缓存 + 替换文件）
├── index.html                  # Web 版本界面
├── build_config.spec           # PyInstaller 打包配置
├── run.bat                     # Windows 启动脚本
├── build.bat                   # Windows 一键打包脚本
├── test_download_speed.py      # 下载速度测试
├── test_quick_switch.py        # 快速切换测试
├── requirements.txt            # Python 依赖
├── README.md                   # 项目文档
├── .gitignore                  # Git 忽略规则
└── VSCode版本切换工具.exe       # 已构建的桌面程序（可直接运行）
```

## 技术栈

- **GUI 框架**: PyQt5
- **HTTP 请求**: requests
- **版本解析**: packaging
- **配置管理**: pyyaml, jsonschema
- **测试框架**: hypothesis
- **打包工具**: PyInstaller
- **跨平台支持**: appdirs, psutil

## 注意事项

1. **网络连接**：首次使用需要网络连接以获取版本列表 / 下载版本
2. **权限要求**：修改 PATH 环境变量等操作可能需要管理员权限
3. **备份建议**：切换版本前建议备份重要数据
4. **缓存有效期**：版本列表缓存 24 小时后自动失效
5. **下载缓存**：通过工具下载的新版本都会自动缓存（无数量上限），保存在系统缓存目录（appdirs），可在"缓存管理"中查看或一键清空

## 开发状态

### 已完成 ✅
- 核心数据模型
- 远程版本仓库
- 本地版本仓库
- 缓存管理器
- 版本管理器
- 快速切换器（下载 + 缓存 + 自动切换）
- 增强版版本检测（注册表 / PATH / 递归扫描）
- GUI 界面更新

### 待实现 🚧
- VSCode Server 管理器
- 配置管理器增强
- 错误处理机制完善
- 平台兼容性测试

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 更新日志

### v0.3.0 (2026-08-13) - 检测增强与快速切换优化
- ✅ 版本检测增强：注册表 `DisplayIcon` 兜底、PATH 解析、深度受限递归扫描，支持 D 盘等任意路径安装
- ✅ 扫描合并修复：C/D 盘多版本安装可同时列出
- ✅ 切换优化：目标版本未安装时询问是否下载，确认后走快速切换（下载 + 缓存 + 自动切换）
- ✅ 修复 GBK 控制台中文输出崩溃
- ✅ 修正过时的"下载功能将在后续版本提供"提示
- ✅ 加入完整打包配置（`build_config.spec` / `build.bat` / `run.bat` / `.gitignore`）

### v0.2.1 (2024-01-21) - 检测增强
- ✅ 增强版本检测功能
- ✅ 全局搜索 VSCode 安装（支持多驱动器）
- ✅ Windows 注册表搜索
- ✅ 智能版本读取（从 package.json）
- ✅ 支持自定义安装路径
- ✅ 详细的检测日志输出

### v0.2.0 (2024-01-21)
- ✅ 实现 RemoteVersionRepository
- ✅ 实现 LocalVersionRepository
- ✅ 实现 CacheManager
- ✅ 增强 VSCodeVersionManager
- ✅ 添加"更新版本列表"功能
- ✅ 完整的属性测试套件

### v0.1.0 (初始版本)
- ✅ 基础版本检测
- ✅ 版本演变图谱
- ✅ 配置备份
- ✅ 插件兼容性分析
- ✅ PyQt5 GUI 界面
- ✅ Web 界面
