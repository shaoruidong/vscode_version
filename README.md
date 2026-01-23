# VSCode版本切换工具

一个跨平台的VSCode版本管理工具，支持版本检测、升级降级、配置迁移等功能。

## 功能特性

### 已实现功能 ✅

1. **版本检测（增强版）**
   - 自动检测本地已安装的VSCode版本
   - **无干扰检测**：不会启动VSCode窗口，静默后台检测
   - 支持预定义路径快速检测
   - **全局搜索功能**：在多个驱动器和常见位置搜索VSCode
   - **Windows注册表搜索**：从系统注册表查找VSCode安装
   - **智能版本读取**：直接从package.json文件读取版本号
   - 显示版本号、安装路径、版本类型等详细信息
   - 支持稳定版和Insiders版
   - 支持自定义安装路径（如 D:\vs\visual code\vscode\）
   - **性能优化**：检测速度 < 0.5秒

2. **版本管理**
   - 从VSCode官方API获取最新版本列表
   - 版本列表本地缓存（24小时有效期）
   - 一键更新版本列表
   - 版本演变图谱可视化

3. **版本切换**
   - 在已安装的版本之间快速切换
   - 保留用户配置和插件设置
   - 版本切换结果反馈

4. **配置管理**
   - 配置文件备份
   - 插件兼容性分析
   - 变更报告生成

5. **用户界面**
   - 现代化的PyQt5桌面应用
   - 响应式Web界面（HTML版本）
   - 清晰的操作反馈

### 核心组件

- **RemoteVersionRepository**: 从VSCode官方API获取版本信息
- **LocalVersionRepository**: 管理本地安装的VSCode版本
- **CacheManager**: 版本信息缓存管理
- **VSCodeVersionManager**: 版本管理核心逻辑
- **ConfigMigrationManager**: 配置迁移管理

## 安装和使用

### 环境要求

- Python 3.7+
- Conda环境（推荐）
- Windows/macOS/Linux

### 安装步骤

1. 克隆或下载项目到本地

2. 创建并激活conda环境：
```bash
conda create -n vs python=3.9
conda activate vs
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

### 运行应用

#### Windows用户
双击运行 `run.bat` 文件

#### 命令行运行
```bash
conda activate vs
python main.py
```

#### Web版本
在浏览器中打开 `index.html` 文件

## 使用说明

### 主界面功能

1. **当前版本信息**
   - 显示当前活动的VSCode版本
   - 点击"刷新信息"重新检测

2. **版本选择**
   - 点击"加载可用版本"从缓存或API获取版本列表
   - 点击"更新版本列表"强制从官方API获取最新版本
   - 从下拉框选择目标版本

3. **操作选项**
   - 备份当前配置：切换前备份配置文件
   - 迁移配置和插件：保留用户设置
   - 分析插件兼容性：检查插件兼容性

4. **版本操作**
   - 升级到选中版本：切换到指定版本
   - 回滚到上一个版本：恢复到之前的版本

### 版本演变图谱

显示：
- 当前活动版本
- 推荐版本（比当前版本新的3个版本和旧的2个版本）
- 可用版本总数
- 最近的10个版本

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

项目包含完整的属性测试套件，使用hypothesis库验证核心功能的正确性。

运行测试：
```bash
conda activate vs
python test_properties.py
```

测试覆盖的属性：
- 属性1: 版本检测完整性
- 属性2: 版本切换一致性
- 属性5: API数据完整性
- 属性6: 错误回退一致性
- 属性7: 版本排序正确性
- 属性9: 缓存一致性

## 项目结构

```
vscode_version/
├── main.py                 # 主程序（PyQt5 GUI）
├── index.html             # Web版本界面
├── test_properties.py     # 属性测试
├── requirements.txt       # Python依赖
├── run.bat               # Windows启动脚本
├── README.md             # 项目文档
└── .kiro/specs/          # 规格说明文档
    └── vscode-version-updater/
        ├── requirements.md  # 需求文档
        ├── design.md       # 设计文档
        └── tasks.md        # 任务列表
```

## 技术栈

- **GUI框架**: PyQt5
- **HTTP请求**: requests
- **版本解析**: packaging
- **配置管理**: pyyaml, jsonschema
- **测试框架**: hypothesis
- **跨平台支持**: appdirs, psutil

## 注意事项

1. **网络连接**: 首次使用需要网络连接以获取版本列表
2. **权限要求**: 某些操作可能需要管理员权限
3. **备份建议**: 切换版本前建议备份重要数据
4. **缓存有效期**: 版本列表缓存24小时后自动失效

## 开发状态

### 已完成 ✅
- 核心数据模型
- 远程版本仓库
- 本地版本仓库
- 缓存管理器
- 版本管理器
- GUI界面更新
- 属性测试

### 待实现 🚧
- VSCode Server管理器
- 安装管理器（下载和安装新版本）
- 配置管理器增强
- 错误处理机制完善
- 性能优化
- 平台兼容性测试

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 更新日志

### v0.2.1 (2024-01-21) - 检测增强
- ✅ 增强版本检测功能
- ✅ 全局搜索VSCode安装（支持多驱动器）
- ✅ Windows注册表搜索
- ✅ 智能版本读取（从package.json）
- ✅ 支持自定义安装路径
- ✅ 详细的检测日志输出

### v0.2.0 (2024-01-21)
- ✅ 实现RemoteVersionRepository
- ✅ 实现LocalVersionRepository
- ✅ 实现CacheManager
- ✅ 增强VSCodeVersionManager
- ✅ 添加"更新版本列表"功能
- ✅ 完整的属性测试套件

### v0.1.0 (初始版本)
- ✅ 基础版本检测
- ✅ 版本演变图谱
- ✅ 配置备份
- ✅ 插件兼容性分析
- ✅ PyQt5 GUI界面
- ✅ Web界面
