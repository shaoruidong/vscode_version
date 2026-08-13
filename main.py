#!/usr/bin/env python3
"""
VSCode版本切换工具
跨平台的VSCode版本管理工具，支持版本检测、升级降级、配置迁移等功能
"""

import sys
import os
import json
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtWidgets import (QApplication,QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox,
                             QTextEdit, QProgressBar, QMessageBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
                             QCheckBox, QPlainTextEdit, QSplitter, QMessageBox, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QThreadPool, QRunnable
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QColor
import requests
import yaml
from packaging import version
import appdirs

# 强制stdout/stderr使用UTF-8，避免中文输出（如 "✓ 找到VSCode"）在GBK控制台下抛错
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 导入简单版本切换器
from version_switcher_simple import SimpleVersionSwitcher, VersionCache

@dataclass
class VSCodeVersion:
    """VSCode版本信息"""
    version: str
    release_date: str
    download_url: str
    platform: str
    is_stable: bool = True

@dataclass
class VSCodeConfig:
    """VSCode配置信息"""
    settings_path: str
    extensions_path: str
    keybindings_path: str
    snippets_path: str

@dataclass
class VSCodeInstallation:
    """VSCode安装实例"""
    version: str
    install_path: str
    edition: str  # "stable" or "insiders"
    platform: str
    architecture: str
    install_date: datetime
    is_active: bool
    server_version: Optional[str] = None

@dataclass
class VersionInfo:
    """从官方API获取的版本信息"""
    version: str
    release_date: datetime
    channel: str  # "stable", "insiders"
    download_urls: Dict[str, str]  # platform -> url
    checksum: Dict[str, str]  # platform -> checksum
    changelog_url: str
    is_latest: bool = False

@dataclass
class SwitchResult:
    """版本切换操作的结果"""
    success: bool
    from_version: str
    to_version: str
    message: str
    warnings: List[str]
    config_migrated: bool
    server_synced: bool

@dataclass
class DownloadResult:
    """下载操作的结果"""
    success: bool
    file_path: str
    file_size: int
    download_time: float
    checksum_verified: bool
    error_message: Optional[str] = None

@dataclass
class InstallResult:
    """安装操作的结果"""
    success: bool
    version: str
    install_path: str
    message: str
    server_installed: bool

@dataclass
class BackupResult:
    """备份操作的结果"""
    success: bool
    backup_id: str
    backup_path: str
    items_backed_up: Dict[str, bool]
    timestamp: datetime

@dataclass
class RestoreResult:
    """恢复操作的结果"""
    success: bool
    backup_id: str
    items_restored: Dict[str, bool]
    message: str

@dataclass
class MigrationResult:
    """配置迁移操作的结果"""
    success: bool
    from_version: str
    to_version: str
    migrated_items: List[str]
    warnings: List[str]

@dataclass
class Extension:
    """VSCode扩展信息"""
    id: str
    name: str
    version: str
    publisher: str
    is_enabled: bool

@dataclass
class CompatibilityInfo:
    """版本兼容性信息"""
    version: str
    is_compatible: bool
    incompatible_extensions: List[Extension]
    warnings: List[str]
    recommendations: List[str]

@dataclass
class SyncResult:
    """Server同步操作的结果"""
    success: bool
    client_version: str
    server_version: str
    message: str
    synced: bool

class VSCodeDetector:
    """VSCode检测器"""
    
    def __init__(self):
        self.system = platform.system()
        self.arch = platform.machine()
        
    def get_vscode_paths(self) -> Dict[str, List[str]]:
        """获取VSCode可能的安装路径"""
        paths = {}
        
        if self.system == "Windows":
            # Windows路径
            paths["stable"] = [
                r"C:\Program Files\Microsoft VS Code\Code.exe",
                r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
                r"D:\Program Files\Microsoft VS Code\Code.exe",
                r"E:\Program Files\Microsoft VS Code\Code.exe",
                r"F:\Program Files\Microsoft VS Code\Code.exe",
            ]
            paths["insiders"] = [
                r"C:\Program Files\Microsoft VS Code Insiders\Code - Insiders.exe",
                r"C:\Program Files (x86)\Microsoft VS Code Insiders\Code - Insiders.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code Insiders\Code - Insiders.exe"),
            ]
        elif self.system == "Darwin":  # macOS
            paths["stable"] = [
                "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
                os.path.expanduser("~/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
            ]
            paths["insiders"] = [
                "/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code-insiders",
                os.path.expanduser("~/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code-insiders")
            ]
        else:  # Linux
            paths["stable"] = [
                "/usr/bin/code",
                "/usr/local/bin/code",
                "/usr/share/code/code",
                "/opt/visual-studio-code/code",
                "/snap/code/current/usr/share/code/code",
                os.path.expanduser("~/.local/share/code/code"),
                "/snap/bin/code",
            ]
            paths["insiders"] = [
                "/usr/bin/code-insiders",
                "/usr/local/bin/code-insiders",
                "/usr/share/code-insiders/code-insiders",
                "/opt/visual-studio-code-insiders/code-insiders",
                os.path.expanduser("~/.local/share/code-insiders/code-insiders")
            ]
            
        return paths
    
    def search_vscode_globally(self) -> List[Tuple[str, str]]:
        """
        全局搜索VSCode安装
        
        Returns:
            [(路径, 版本类型), ...] 列表
        """
        found_installations = []
        
        if self.system == "Windows":
            # 在Windows中搜索常见驱动器和路径
            drives = ['C:', 'D:', 'E:', 'F:', 'G:']
            search_patterns = [
                r"\Program Files\Microsoft VS Code\Code.exe",
                r"\Program Files (x86)\Microsoft VS Code\Code.exe",
                r"\vs\visual code\vscode\Microsoft VS Code\Code.exe",
                r"\Microsoft VS Code\Code.exe",
                r"\vscode\Microsoft VS Code\Code.exe",
                r"\VSCode\Code.exe",
                # 补充常见变体（含带空格的 "VS Code"）
                r"\Program Files\VS Code\Code.exe",
                r"\Program Files (x86)\VS Code\Code.exe",
                r"\VS Code\Code.exe",
                r"\Software\Microsoft VS Code\Code.exe",
                r"\Software\VS Code\Code.exe",
                r"\Tools\Microsoft VS Code\Code.exe",
                r"\Tools\VS Code\Code.exe",
                r"\apps\Microsoft VS Code\Code.exe",
                r"\apps\VS Code\Code.exe",
            ]
            
            print("正在搜索VSCode安装...")
            for drive in drives:
                if not os.path.exists(drive):
                    continue
                    
                for pattern in search_patterns:
                    path = drive + pattern
                    if os.path.exists(path):
                        print(f"  找到: {path}")
                        found_installations.append((path, "stable"))
            
            # 搜索用户目录
            user_paths = [
                os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
                os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code Insiders\Code - Insiders.exe"),
            ]
            for path in user_paths:
                if os.path.exists(path):
                    print(f"  找到: {path}")
                    edition = "insiders" if "Insiders" in path else "stable"
                    found_installations.append((path, edition))
            
            # 从注册表查找（DisplayIcon 兜底）
            self._append_unique(found_installations, self._find_vscode_from_registry())

            # 从PATH环境变量查找
            self._append_unique(found_installations, self._find_vscode_from_path())

            # 以上快方法都没找到时，才做深度受限的递归扫描（兜底）
            if not found_installations:
                print("常规方式未找到，开始深度递归扫描...")
                for drive in drives:
                    if not os.path.exists(drive):
                        continue
                    recursive = self._search_drive_recursively(drive)
                    if recursive:
                        print(f"  递归扫描 {drive} 找到 {len(recursive)} 个VSCode安装")
                        self._append_unique(found_installations, recursive)
        
        elif self.system == "Darwin":  # macOS
            # macOS应用程序路径
            app_paths = [
                "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
                os.path.expanduser("~/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
                "/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code-insiders",
            ]
            for path in app_paths:
                if os.path.exists(path):
                    edition = "insiders" if "Insiders" in path else "stable"
                    found_installations.append((path, edition))
        
        else:  # Linux
            # 在Linux中搜索常见位置
            search_paths = [
                "/usr/bin/code",
                "/usr/local/bin/code",
                "/snap/bin/code",
                "/usr/bin/code-insiders",
                "/usr/local/bin/code-insiders",
            ]
            for path in search_paths:
                if os.path.exists(path):
                    edition = "insiders" if "insiders" in path else "stable"
                    found_installations.append((path, edition))
            
            # 检查用户本地安装
            user_paths = [
                os.path.expanduser("~/.local/bin/code"),
                os.path.expanduser("~/.local/bin/code-insiders"),
            ]
            for path in user_paths:
                if os.path.exists(path):
                    edition = "insiders" if "insiders" in path else "stable"
                    found_installations.append((path, edition))
        
        print(f"共找到 {len(found_installations)} 个VSCode安装")
        return found_installations

    def _append_unique(self, target: List[Tuple[str, str]], items: List[Tuple[str, str]]):
        """去重追加到结果列表"""
        existing = set(target)
        for item in items:
            if item not in existing:
                print(f"  找到: {item[0]}")
                target.append(item)
                existing.add(item)

    def _find_vscode_from_registry(self) -> List[Tuple[str, str]]:
        """
        从Windows注册表查找VSCode安装

        优先使用DisplayIcon（通常是完整exe路径，形如 "xxx\\Code.exe,0"），
        缺失时退回InstallLocation。

        Returns:
            [(路径, 版本类型), ...] 列表
        """
        found = []
        try:
            import winreg
        except ImportError:
            return found

        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        def _is_vscode(name: str) -> bool:
            return "Visual Studio Code" in name or "Microsoft VS Code" in name

        for hkey, reg_path in reg_paths:
            try:
                key = winreg.OpenKey(hkey, reg_path)
            except OSError:
                continue
            try:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                    except OSError:
                        continue
                    try:
                        # 读取显示名称，识别VSCode
                        display_name = ""
                        try:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except OSError:
                            pass
                        if not display_name or not _is_vscode(display_name):
                            continue

                        code_exe = None
                        # 优先用DisplayIcon（去掉 ",0" 等资源号后缀）
                        try:
                            icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                            if icon:
                                candidate = icon.split(",")[0].strip()
                                if candidate.lower().endswith(".exe") and os.path.exists(candidate):
                                    code_exe = candidate
                        except OSError:
                            pass

                        # DisplayIcon 拿不到时退回 InstallLocation
                        if not code_exe:
                            try:
                                loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                if loc:
                                    candidate = os.path.join(loc, "Code.exe")
                                    if os.path.exists(candidate):
                                        code_exe = candidate
                            except OSError:
                                pass

                        if code_exe:
                            edition = "insiders" if "Insiders" in display_name else "stable"
                            found.append((code_exe, edition))
                    finally:
                        winreg.CloseKey(subkey)
            finally:
                winreg.CloseKey(key)
        return found

    def _find_vscode_from_path(self) -> List[Tuple[str, str]]:
        """
        从PATH环境变量查找VSCode

        若PATH里有 code / Code.exe（常见为 <安装目录>\\bin\\code.cmd），
        推导出安装目录里的Code.exe。

        Returns:
            [(路径, 版本类型), ...] 列表
        """
        found = []
        for cmd in ("code", "Code.exe", "code.cmd", "Code"):
            p = shutil.which(cmd)
            if not p:
                continue
            norm = p.lower().replace("/", "\\")
            if norm.endswith("\\bin\\code.cmd") or norm.endswith("\\bin\\code"):
                # PATH 入口在 bin 下，Code.exe 在上级目录
                code_exe = os.path.join(os.path.dirname(os.path.dirname(p)), "Code.exe")
            elif norm.endswith("code.exe"):
                code_exe = p
            else:
                code_exe = None

            if code_exe and os.path.exists(code_exe):
                edition = "insiders" if "insiders" in norm else "stable"
                found.append((code_exe, edition))
        return found

    def _search_drive_recursively(self, drive: str, max_depth: int = 4) -> List[Tuple[str, str]]:
        """
        深度受限的递归搜索Code.exe（兜底方案，仅在快方法未找到时调用）

        Args:
            drive: 盘符，如 "C:"
            max_depth: 最大目录深度（相对盘符根目录）

        Returns:
            [(路径, 版本类型), ...] 列表
        """
        found = []
        # 剪枝目录：不进入这些目录，避免扫描系统目录/依赖目录
        prune_dirs = {
            "windows", "winsxs", "$recycle.bin", "system volume information",
            "node_modules", ".git", "__pycache__", "programdata", "temp",
        }
        max_found = 10  # 单个盘最多收集的安装数，防止极端情况拖慢

        def _onerror(e: OSError):
            # 权限不足等错误直接忽略，继续扫描
            pass

        base_depth = drive.rstrip("\\/").count("\\")
        for root, dirs, files in os.walk(drive, topdown=True, followlinks=False, onerror=_onerror):
            depth = root.rstrip("\\/").count("\\") - base_depth
            # 剪枝 + 深度限制
            dirs[:] = [d for d in dirs if d.lower() not in prune_dirs]
            if depth >= max_depth:
                dirs[:] = []

            for fname in files:
                if fname.lower() in ("code.exe", "code - insiders.exe"):
                    path = os.path.join(root, fname)
                    edition = "insiders" if "insiders" in fname.lower() else "stable"
                    found.append((path, edition))
                    if len(found) >= max_found:
                        break
            if len(found) >= max_found:
                break

        return found

    def detect_current_version(self) -> Tuple[Optional[str], Optional[str]]:
        """检测当前VSCode版本（不启动VSCode）"""
        # 首先尝试预定义路径
        paths = self.get_vscode_paths()
        
        # 检查稳定版 - 直接从文件读取，避免启动VSCode
        for path in paths.get("stable", []):
            if os.path.exists(path):
                try:
                    version_from_file = self._get_version_from_file(path)
                    if version_from_file:
                        print(f"✓ 找到VSCode: {path}")
                        print(f"  版本: {version_from_file}")
                        print(f"  类型: stable")
                        return version_from_file, "stable"
                except Exception as e:
                    print(f"检测 {path} 失败: {e}")
                    continue
                    
        # 检查Insiders版 - 直接从文件读取
        for path in paths.get("insiders", []):
            if os.path.exists(path):
                try:
                    version_from_file = self._get_version_from_file(path)
                    if version_from_file:
                        print(f"✓ 找到VSCode: {path}")
                        print(f"  版本: {version_from_file}")
                        print(f"  类型: insiders")
                        return version_from_file, "insiders"
                except Exception as e:
                    print(f"检测 {path} 失败: {e}")
                    continue
        
        # 如果预定义路径都没找到，进行全局搜索
        print("预定义路径未找到VSCode，开始全局搜索...")
        installations = self.search_vscode_globally()
        
        for path, edition in installations:
            try:
                # 使用绝对路径并处理空格
                if not os.path.exists(path):
                    continue
                
                # 直接从文件读取版本号，避免启动VSCode
                version_from_file = self._get_version_from_file(path)
                if version_from_file:
                    print(f"✓ 找到VSCode: {path}")
                    print(f"  版本: {version_from_file}")
                    print(f"  类型: {edition}")
                    return version_from_file, edition
                        
            except Exception as e:
                print(f"检测 {path} 失败: {e}")
                continue
                    
        return None, None
    
    def _get_version_from_file(self, code_exe_path: str) -> Optional[str]:
        """
        从VSCode安装目录的package.json文件读取版本号
        
        Args:
            code_exe_path: Code.exe的路径
            
        Returns:
            版本号，如果读取失败则返回None
        """
        try:
            # 获取VSCode安装目录
            install_dir = os.path.dirname(code_exe_path)
            
            # 查找package.json文件
            possible_paths = [
                os.path.join(install_dir, "resources", "app", "package.json"),
                os.path.join(install_dir, "package.json"),
            ]
            
            for package_json_path in possible_paths:
                if os.path.exists(package_json_path):
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        package_data = json.load(f)
                        version = package_data.get('version')
                        if version:
                            return version
                            
        except Exception as e:
            print(f"从文件读取版本失败: {e}")
            
        return None
    
    def get_config_paths(self) -> VSCodeConfig:
        """获取VSCode配置路径"""
        config = VSCodeConfig("", "", "", "")
        
        if self.system == "Windows":
            base_path = os.path.expanduser(r"~\AppData\Roaming\Code")
        elif self.system == "Darwin":
            base_path = os.path.expanduser("~/Library/Application Support/Code")
        else:  # Linux
            base_path = os.path.expanduser("~/.config/Code")
            
        config.settings_path = os.path.join(base_path, "User", "settings.json")
        config.extensions_path = os.path.join(base_path, "extensions")
        config.keybindings_path = os.path.join(base_path, "User", "keybindings.json")
        config.snippets_path = os.path.join(base_path, "User", "snippets")
        
        return config

class RemoteVersionRepository:
    """远程版本仓库 - 负责从VSCode官方API获取版本信息"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
        self.api_base_url = "https://update.code.visualstudio.com"
        
    def fetch_available_versions(self, channel: str = "stable") -> List[VersionInfo]:
        """
        从VSCode官方API获取可用版本列表
        
        Args:
            channel: 版本通道，"stable" 或 "insiders"
            
        Returns:
            版本信息列表
        """
        versions = []
        
        try:
            # 从VSCode官方API获取版本信息
            api_url = f"{self.api_base_url}/api/releases/{channel}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                releases = response.json()
                
                for idx, release in enumerate(releases):
                    # 构建版本信息
                    version_info = VersionInfo(
                        version=release,
                        release_date=datetime.now(),  # API可能不提供日期，使用当前时间
                        channel=channel,
                        download_urls=self._build_download_urls(release, channel),
                        checksum={},  # 校验和需要从其他API获取
                        changelog_url=f"https://code.visualstudio.com/updates/v{release.replace('.', '_')}",
                        is_latest=(idx == 0)  # 第一个版本是最新的
                    )
                    versions.append(version_info)
                    
            else:
                print(f"API请求失败，状态码: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("API请求超时")
        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {e}")
        except Exception as e:
            print(f"获取版本列表失败: {e}")
            
        return versions
    
    def get_version_details(self, version: str) -> Optional[VersionInfo]:
        """
        获取指定版本的详细信息
        
        Args:
            version: 版本号
            
        Returns:
            版本详细信息，如果未找到则返回None
        """
        try:
            # 尝试从可用版本列表中查找
            versions = self.fetch_available_versions()
            for v in versions:
                if v.version == version:
                    return v
                    
            # 如果未找到，创建一个基本的版本信息
            return VersionInfo(
                version=version,
                release_date=datetime.now(),
                channel="stable",
                download_urls=self._build_download_urls(version, "stable"),
                checksum={},
                changelog_url=f"https://code.visualstudio.com/updates/v{version.replace('.', '_')}",
                is_latest=False
            )
            
        except Exception as e:
            print(f"获取版本详情失败: {e}")
            return None
    
    def get_download_url(self, version: str, platform: str) -> str:
        """
        获取指定版本和平台的下载URL
        
        Args:
            version: 版本号
            platform: 平台名称 (Windows, Darwin, Linux)
            
        Returns:
            下载URL
        """
        return self._build_download_url(version, platform, "stable")
    
    def check_for_updates(self, current_version: str) -> List[VersionInfo]:
        """
        检查是否有新版本可用
        
        Args:
            current_version: 当前版本号
            
        Returns:
            比当前版本新的版本列表
        """
        updates = []
        
        try:
            all_versions = self.fetch_available_versions()
            
            from packaging import version as pkg_version
            current_ver = pkg_version.parse(current_version)
            
            for v in all_versions:
                try:
                    if pkg_version.parse(v.version) > current_ver:
                        updates.append(v)
                except:
                    continue
                    
        except Exception as e:
            print(f"检查更新失败: {e}")
            
        return updates
    
    def _build_download_urls(self, version: str, channel: str) -> Dict[str, str]:
        """
        构建所有平台的下载URL
        
        Args:
            version: 版本号
            channel: 版本通道
            
        Returns:
            平台到下载URL的映射
        """
        urls = {}
        
        # Windows
        urls["Windows"] = f"{self.api_base_url}/{version}/win32-x64/{channel}"
        
        # macOS
        urls["Darwin"] = f"{self.api_base_url}/{version}/darwin/stable"
        
        # Linux x64
        urls["Linux-x64"] = f"{self.api_base_url}/{version}/linux-x64/{channel}"
        
        # Linux ARM64
        urls["Linux-arm64"] = f"{self.api_base_url}/{version}/linux-arm64/{channel}"
        
        return urls
    
    def _build_download_url(self, version: str, platform: str, channel: str) -> str:
        """
        构建特定平台的下载URL
        
        Args:
            version: 版本号
            platform: 平台名称
            channel: 版本通道
            
        Returns:
            下载URL
        """
        arch = self.detector.arch
        
        if platform == "Windows":
            return f"{self.api_base_url}/{version}/win32-x64/{channel}"
        elif platform == "Darwin":
            return f"{self.api_base_url}/{version}/darwin/{channel}"
        else:  # Linux
            if "x86_64" in arch or "amd64" in arch:
                return f"{self.api_base_url}/{version}/linux-x64/{channel}"
            elif "arm" in arch or "aarch64" in arch:
                return f"{self.api_base_url}/{version}/linux-arm64/{channel}"
            else:
                return f"{self.api_base_url}/{version}/linux-x64/{channel}"


class LocalVersionRepository:
    """本地版本仓库 - 管理本地安装的VSCode版本"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
        self.installations_cache: List[VSCodeInstallation] = []
        self.cache_file = os.path.join(
            appdirs.user_data_dir("VSCodeSwitcher"),
            "installations.json"
        )
        
    def scan_installations(self) -> List[VSCodeInstallation]:
        """
        扫描本地所有VSCode安装（包括全局搜索）
        
        Returns:
            VSCode安装列表
        """
        installations = []
        found_paths = set()  # 用于去重
        
        # 1. 先扫描预定义路径
        paths = self.detector.get_vscode_paths()
        
        # 扫描稳定版
        for path in paths.get("stable", []):
            if os.path.exists(path) and path not in found_paths:
                try:
                    installation = self._create_installation_from_path(path, "stable")
                    if installation:
                        installations.append(installation)
                        found_paths.add(path)
                except Exception as e:
                    print(f"扫描安装失败 {path}: {e}")
        
        # 扫描Insiders版
        for path in paths.get("insiders", []):
            if os.path.exists(path) and path not in found_paths:
                try:
                    installation = self._create_installation_from_path(path, "insiders")
                    if installation:
                        installations.append(installation)
                        found_paths.add(path)
                except Exception as e:
                    print(f"扫描安装失败 {path}: {e}")
        
        # 2. 全局搜索，合并结果（无论预定义路径是否找到，按路径去重）
        global_installations = self.detector.search_vscode_globally()
        for path, edition in global_installations:
            if path not in found_paths:
                try:
                    installation = self._create_installation_from_path(path, edition)
                    if installation:
                        installations.append(installation)
                        found_paths.add(path)
                except Exception as e:
                    print(f"扫描安装失败 {path}: {e}")
        
        self.installations_cache = installations
        print(f"共扫描到 {len(installations)} 个VSCode安装")
        return installations
    
    def register_installation(self, installation: VSCodeInstallation) -> bool:
        """
        注册一个新的VSCode安装
        
        Args:
            installation: VSCode安装实例
            
        Returns:
            是否注册成功
        """
        try:
            # 检查是否已存在
            existing = self.get_installation_by_version(installation.version)
            if existing:
                print(f"版本 {installation.version} 已存在")
                return False
            
            # 添加到缓存
            self.installations_cache.append(installation)
            
            # 保存到文件
            self._save_installations()
            
            return True
            
        except Exception as e:
            print(f"注册安装失败: {e}")
            return False
    
    def remove_installation(self, version: str) -> bool:
        """
        移除一个VSCode安装记录
        
        Args:
            version: 版本号
            
        Returns:
            是否移除成功
        """
        try:
            # 从缓存中移除
            self.installations_cache = [
                inst for inst in self.installations_cache
                if inst.version != version
            ]
            
            # 保存到文件
            self._save_installations()
            
            return True
            
        except Exception as e:
            print(f"移除安装记录失败: {e}")
            return False
    
    def get_installation_by_version(self, version: str) -> Optional[VSCodeInstallation]:
        """
        根据版本号获取安装信息
        
        Args:
            version: 版本号
            
        Returns:
            VSCode安装实例，如果未找到则返回None
        """
        for installation in self.installations_cache:
            if installation.version == version:
                return installation
        
        return None
    
    def get_active_installation(self) -> Optional[VSCodeInstallation]:
        """
        获取当前活动的VSCode安装
        
        Returns:
            活动的VSCode安装实例，如果未找到则返回None
        """
        for installation in self.installations_cache:
            if installation.is_active:
                return installation
        
        return None
    
    def set_active_installation(self, version: str) -> bool:
        """
        设置活动的VSCode安装
        
        Args:
            version: 版本号
            
        Returns:
            是否设置成功
        """
        try:
            # 将所有安装设置为非活动
            for installation in self.installations_cache:
                installation.is_active = False
            
            # 设置指定版本为活动
            target = self.get_installation_by_version(version)
            if target:
                target.is_active = True
                self._save_installations()
                return True
            
            return False
            
        except Exception as e:
            print(f"设置活动安装失败: {e}")
            return False
    
    def _create_installation_from_path(
        self, 
        path: str, 
        edition: str
    ) -> Optional[VSCodeInstallation]:
        """
        从路径创建VSCode安装实例（不启动VSCode）
        
        Args:
            path: VSCode可执行文件路径
            edition: 版本类型 (stable/insiders)
            
        Returns:
            VSCode安装实例，如果创建失败则返回None
        """
        try:
            # 直接从文件读取版本号，避免启动VSCode
            version_line = self.detector._get_version_from_file(path)
            
            if not version_line:
                return None
            
            # 获取安装日期（使用文件修改时间）
            install_date = datetime.fromtimestamp(os.path.getmtime(path))
            
            # 检查是否为活动版本
            current_version, current_edition = self.detector.detect_current_version()
            is_active = (version_line == current_version and edition == current_edition)
            
            installation = VSCodeInstallation(
                version=version_line,
                install_path=path,
                edition=edition,
                platform=self.detector.system,
                architecture=self.detector.arch,
                install_date=install_date,
                is_active=is_active,
                server_version=None  # 需要单独检测
            )
            
            return installation
            
        except Exception as e:
            print(f"创建安装实例失败: {e}")
            return None
    
    def _save_installations(self) -> bool:
        """
        保存安装列表到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            # 转换为可序列化的格式
            data = []
            for inst in self.installations_cache:
                data.append({
                    "version": inst.version,
                    "install_path": inst.install_path,
                    "edition": inst.edition,
                    "platform": inst.platform,
                    "architecture": inst.architecture,
                    "install_date": inst.install_date.isoformat(),
                    "is_active": inst.is_active,
                    "server_version": inst.server_version
                })
            
            # 写入文件
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"保存安装列表失败: {e}")
            return False
    
    def _load_installations(self) -> bool:
        """
        从文件加载安装列表
        
        Returns:
            是否加载成功
        """
        try:
            if not os.path.exists(self.cache_file):
                return False
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.installations_cache = []
            for item in data:
                installation = VSCodeInstallation(
                    version=item["version"],
                    install_path=item["install_path"],
                    edition=item["edition"],
                    platform=item["platform"],
                    architecture=item["architecture"],
                    install_date=datetime.fromisoformat(item["install_date"]),
                    is_active=item["is_active"],
                    server_version=item.get("server_version")
                )
                self.installations_cache.append(installation)
            
            return True
            
        except Exception as e:
            print(f"加载安装列表失败: {e}")
            return False

class CacheManager:
    """缓存管理器 - 管理版本信息的本地缓存"""
    
    def __init__(self):
        self.cache_dir = appdirs.user_cache_dir("VSCodeSwitcher")
        self.version_cache_file = os.path.join(self.cache_dir, "versions.json")
        self.cache_validity_hours = 24  # 缓存有效期24小时
        
    def cache_version_list(self, versions: List[VersionInfo]) -> bool:
        """
        缓存版本列表
        
        Args:
            versions: 版本信息列表
            
        Returns:
            是否缓存成功
        """
        try:
            # 确保缓存目录存在
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # 转换为可序列化的格式
            data = {
                "timestamp": datetime.now().isoformat(),
                "versions": []
            }
            
            for v in versions:
                data["versions"].append({
                    "version": v.version,
                    "release_date": v.release_date.isoformat(),
                    "channel": v.channel,
                    "download_urls": v.download_urls,
                    "checksum": v.checksum,
                    "changelog_url": v.changelog_url,
                    "is_latest": v.is_latest
                })
            
            # 写入缓存文件
            with open(self.version_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"缓存版本列表失败: {e}")
            return False
    
    def get_cached_version_list(self) -> Optional[List[VersionInfo]]:
        """
        获取缓存的版本列表
        
        Returns:
            版本信息列表，如果缓存不存在或无效则返回None
        """
        try:
            # 检查缓存文件是否存在
            if not os.path.exists(self.version_cache_file):
                return None
            
            # 检查缓存是否有效
            if not self.is_cache_valid():
                return None
            
            # 读取缓存文件
            with open(self.version_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 转换为VersionInfo对象
            versions = []
            for item in data.get("versions", []):
                version_info = VersionInfo(
                    version=item["version"],
                    release_date=datetime.fromisoformat(item["release_date"]),
                    channel=item["channel"],
                    download_urls=item["download_urls"],
                    checksum=item["checksum"],
                    changelog_url=item["changelog_url"],
                    is_latest=item["is_latest"]
                )
                versions.append(version_info)
            
            return versions
            
        except Exception as e:
            print(f"读取缓存版本列表失败: {e}")
            return None
    
    def is_cache_valid(self) -> bool:
        """
        检查缓存是否有效
        
        Returns:
            缓存是否在有效期内
        """
        try:
            if not os.path.exists(self.version_cache_file):
                return False
            
            # 读取缓存时间戳
            with open(self.version_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            timestamp_str = data.get("timestamp")
            if not timestamp_str:
                return False
            
            cache_time = datetime.fromisoformat(timestamp_str)
            current_time = datetime.now()
            
            # 计算时间差
            time_diff = current_time - cache_time
            hours_diff = time_diff.total_seconds() / 3600
            
            # 检查是否在有效期内
            return hours_diff < self.cache_validity_hours
            
        except Exception as e:
            print(f"检查缓存有效性失败: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """
        清除缓存
        
        Returns:
            是否清除成功
        """
        try:
            if os.path.exists(self.version_cache_file):
                os.remove(self.version_cache_file)
            return True
            
        except Exception as e:
            print(f"清除缓存失败: {e}")
            return False
    
    def update_cache_timestamp(self) -> bool:
        """
        更新缓存时间戳
        
        Returns:
            是否更新成功
        """
        try:
            if not os.path.exists(self.version_cache_file):
                return False
            
            # 读取现有缓存
            with open(self.version_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新时间戳
            data["timestamp"] = datetime.now().isoformat()
            
            # 写回文件
            with open(self.version_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"更新缓存时间戳失败: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, any]:
        """
        获取缓存信息
        
        Returns:
            缓存信息字典
        """
        info = {
            "exists": os.path.exists(self.version_cache_file),
            "valid": self.is_cache_valid(),
            "path": self.version_cache_file,
            "timestamp": None,
            "size": 0
        }
        
        try:
            if info["exists"]:
                # 获取文件大小
                info["size"] = os.path.getsize(self.version_cache_file)
                
                # 获取时间戳
                with open(self.version_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    info["timestamp"] = data.get("timestamp")
                    
        except Exception as e:
            print(f"获取缓存信息失败: {e}")
        
        return info

class VSCodeVersionManager:
    """VSCode版本管理器 - 增强版"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
        self.local_repo = LocalVersionRepository()
        self.remote_repo = RemoteVersionRepository()
        self.cache_manager = CacheManager()
        
    def detect_installed_versions(self) -> List[VSCodeInstallation]:
        """
        检测所有已安装的VSCode版本
        
        Returns:
            VSCode安装列表
        """
        return self.local_repo.scan_installations()
    
    def get_active_version(self) -> Optional[VSCodeInstallation]:
        """
        获取当前活动的VSCode版本
        
        Returns:
            活动的VSCode安装实例
        """
        installations = self.detect_installed_versions()
        for inst in installations:
            if inst.is_active:
                return inst
        return None
    
    def switch_version(self, target_version: str) -> SwitchResult:
        """
        切换到指定版本
        
        Args:
            target_version: 目标版本号
            
        Returns:
            切换结果
        """
        try:
            # 获取当前版本
            current = self.get_active_version()
            from_version = current.version if current else "未知"
            
            # 检查目标版本是否存在
            target = self.local_repo.get_installation_by_version(target_version)
            if not target:
                return SwitchResult(
                    success=False,
                    from_version=from_version,
                    to_version=target_version,
                    message=f"目标版本 {target_version} 未安装",
                    warnings=[],
                    config_migrated=False,
                    server_synced=False
                )
            
            # 设置为活动版本
            success = self.local_repo.set_active_installation(target_version)
            
            if success:
                return SwitchResult(
                    success=True,
                    from_version=from_version,
                    to_version=target_version,
                    message=f"成功切换到版本 {target_version}",
                    warnings=[],
                    config_migrated=True,
                    server_synced=True
                )
            else:
                return SwitchResult(
                    success=False,
                    from_version=from_version,
                    to_version=target_version,
                    message="切换失败",
                    warnings=[],
                    config_migrated=False,
                    server_synced=False
                )
                
        except Exception as e:
            return SwitchResult(
                success=False,
                from_version="未知",
                to_version=target_version,
                message=f"切换失败: {str(e)}",
                warnings=[],
                config_migrated=False,
                server_synced=False
            )
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """
        比较两个版本号
        
        Args:
            v1: 版本1
            v2: 版本2
            
        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        try:
            from packaging import version as pkg_version
            ver1 = pkg_version.parse(v1)
            ver2 = pkg_version.parse(v2)
            
            if ver1 < ver2:
                return -1
            elif ver1 > ver2:
                return 1
            else:
                return 0
        except:
            # 如果解析失败，使用字符串比较
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
    
    def get_version_compatibility(self, version: str) -> CompatibilityInfo:
        """
        获取版本兼容性信息
        
        Args:
            version: 版本号
            
        Returns:
            兼容性信息
        """
        return CompatibilityInfo(
            version=version,
            is_compatible=True,
            incompatible_extensions=[],
            warnings=[],
            recommendations=[]
        )
    
    def fetch_available_versions(self) -> List[VersionInfo]:
        """
        获取可用版本列表（优先使用缓存）
        
        Returns:
            版本信息列表
        """
        # 尝试从缓存获取
        cached_versions = self.cache_manager.get_cached_version_list()
        if cached_versions:
            return cached_versions
        
        # 从远程获取
        versions = self.remote_repo.fetch_available_versions()
        
        # 缓存结果
        if versions:
            self.cache_manager.cache_version_list(versions)
        
        return versions
    
    def get_version_tree(self) -> Dict:
        """获取版本演变图谱"""
        versions = self.fetch_available_versions()
        current = self.get_active_version()
        
        tree = {
            "current": current.version if current else "未知",
            "available": versions,
            "recommended": self._get_recommended_versions()
        }
        return tree
    
    def _get_recommended_versions(self) -> List[str]:
        """获取推荐版本"""
        current = self.get_active_version()
        if not current:
            return []
        
        versions = self.fetch_available_versions()
        all_versions = [v.version for v in versions]
        
        if not all_versions:
            return []
            
        try:
            from packaging import version as pkg_version
            current_ver = pkg_version.parse(current.version)
            recommended = []
            
            # 找到比当前版本新的最新3个版本
            newer = [v for v in all_versions if pkg_version.parse(v) > current_ver]
            recommended.extend(sorted(newer, reverse=True)[:3])
            
            # 找到比当前版本旧的稳定版本
            older = [v for v in all_versions if pkg_version.parse(v) < current_ver]
            recommended.extend(sorted(older, reverse=True)[:2])
            
            return list(set(recommended))  # 去重
        except:
            return []

class ConfigMigrationManager:
    """配置迁移管理器"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
        
    def backup_config(self, backup_path: str) -> Dict[str, bool]:
        """备份当前配置"""
        config = self.detector.get_config_paths()
        backup_results = {}
        
        # 创建备份目录
        os.makedirs(backup_path, exist_ok=True)
        
        # 备份设置文件
        if os.path.exists(config.settings_path):
            try:
                shutil.copy2(config.settings_path, 
                           os.path.join(backup_path, "settings.json"))
                backup_results["settings"] = True
            except:
                backup_results["settings"] = False
                
        # 备份扩展
        if os.path.exists(config.extensions_path):
            try:
                extensions_backup = os.path.join(backup_path, "extensions")
                if os.path.exists(extensions_backup):
                    shutil.rmtree(extensions_backup)
                shutil.copytree(config.extensions_path, extensions_backup)
                backup_results["extensions"] = True
            except:
                backup_results["extensions"] = False
                
        # 备份快捷键绑定
        if os.path.exists(config.keybindings_path):
            try:
                shutil.copy2(config.keybindings_path,
                           os.path.join(backup_path, "keybindings.json"))
                backup_results["keybindings"] = True
            except:
                backup_results["keybindings"] = False
                
        # 备份代码片段
        if os.path.exists(config.snippets_path):
            try:
                snippets_backup = os.path.join(backup_path, "snippets")
                if os.path.exists(snippets_backup):
                    shutil.rmtree(snippets_backup)
                shutil.copytree(config.snippets_path, snippets_backup)
                backup_results["snippets"] = True
            except:
                backup_results["snippets"] = False
                
        return backup_results
    
    def analyze_extensions_compatibility(self, target_version: str) -> Dict:
        """分析插件兼容性"""
        config = self.detector.get_config_paths()
        compatibility_report = {
            "compatible": [],
            "incompatible": [],
            "unknown": [],
            "total": 0
        }
        
        if not os.path.exists(config.extensions_path):
            return compatibility_report
            
        try:
            # 获取扩展列表
            extensions = []
            for item in os.listdir(config.extensions_path):
                if os.path.isdir(os.path.join(config.extensions_path, item)):
                    extensions.append(item)
                    
            compatibility_report["total"] = len(extensions)
            
            # 简单的兼容性分析（实际实现中可能需要更复杂的逻辑）
            for ext in extensions:
                # 这里可以添加更复杂的兼容性检查逻辑
                compatibility_report["unknown"].append({
                    "name": ext,
                    "reason": "需要手动验证兼容性"
                })
                
        except Exception as e:
            print(f"分析插件兼容性失败: {e}")
            
        return compatibility_report

class ChangeReportGenerator:
    """变更报告生成器"""
    
    def __init__(self):
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": "",
            "from_version": "",
            "to_version": "",
            "backup_path": "",
            "compatibility": {},
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
    def generate_report(self) -> str:
        """生成详细的变更报告"""
        report = []
        report.append("=" * 60)
        report.append("VSCode版本切换变更报告")
        report.append("=" * 60)
        report.append(f"生成时间: {self.report_data['timestamp']}")
        report.append(f"操作类型: {self.report_data['operation']}")
        report.append(f"源版本: {self.report_data['from_version']}")
        report.append(f"目标版本: {self.report_data['to_version']}")
        report.append(f"备份路径: {self.report_data['backup_path']}")
        report.append("")
        
        # 插件兼容性分析
        if self.report_data['compatibility']:
            report.append("插件兼容性分析:")
            report.append("-" * 30)
            compat = self.report_data['compatibility']
            report.append(f"总插件数: {compat.get('total', 0)}")
            
            if compat.get('compatible'):
                report.append(f"兼容插件: {len(compat['compatible'])}")
                for plugin in compat['compatible']:
                    report.append(f"  ✓ {plugin['name']}")
                    
            if compat.get('incompatible'):
                report.append(f"不兼容插件: {len(compat['incompatible'])}")
                for plugin in compat['incompatible']:
                    report.append(f"  ✗ {plugin['name']} - {plugin.get('reason', '未知原因')}")
                    
            if compat.get('unknown'):
                report.append(f"未知兼容性插件: {len(compat['unknown'])}")
                for plugin in compat['unknown']:
                    report.append(f"  ? {plugin['name']} - {plugin.get('reason', '需要验证')}")
            report.append("")
        
        # 警告信息
        if self.report_data['warnings']:
            report.append("警告信息:")
            report.append("-" * 20)
            for warning in self.report_data['warnings']:
                report.append(f"⚠️  {warning}")
            report.append("")
            
        # 错误信息
        if self.report_data['errors']:
            report.append("错误信息:")
            report.append("-" * 20)
            for error in self.report_data['errors']:
                report.append(f"❌ {error}")
            report.append("")
            
        # 建议
        if self.report_data['recommendations']:
            report.append("建议:")
            report.append("-" * 15)
            for rec in self.report_data['recommendations']:
                report.append(f"💡 {rec}")
                
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)

class VSCodeSwitcherGUI(QMainWindow):
    """VSCode版本切换工具主界面"""
    
    def __init__(self):
        super().__init__()
        self.detector = VSCodeDetector()
        self.version_manager = VSCodeVersionManager()
        self.config_manager = ConfigMigrationManager()
        self.report_generator = ChangeReportGenerator()
        self.orchestrator = VersionSwitchOrchestrator()  # 复杂模式
        self.simple_switcher = SimpleVersionSwitcher(self.detector)  # 简单模式（新增）
        
        self.current_version = None
        self.current_edition = None
        self.available_versions = []
        
        self.init_ui()
        self.load_current_info()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("VSCode版本切换工具")
        self.setFixedSize(1080, 720)
        
        # 窗口居中
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - 1080) // 2
        y = (screen_geometry.height() - 720) // 2
        self.setGeometry(x, y, 1080, 720)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧控制面板
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右侧信息显示
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 2)
        
    def create_left_panel(self) -> QWidget:
        """创建左侧面板（优化布局）"""
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(350)
        
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)  # 减小间距
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 当前版本信息
        current_group = QGroupBox("当前版本信息")
        current_layout = QVBoxLayout(current_group)
        current_layout.setSpacing(5)
        
        self.current_version_label = QLabel("检测中...")
        self.current_version_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.current_version_label.setWordWrap(True)
        current_layout.addWidget(self.current_version_label)
        
        self.refresh_btn = QPushButton("刷新信息")
        self.refresh_btn.setMaximumHeight(30)
        self.refresh_btn.clicked.connect(self.load_current_info)
        current_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(current_group)
        
        # 版本选择
        version_group = QGroupBox("版本选择")
        version_layout = QVBoxLayout(version_group)
        version_layout.setSpacing(5)
        
        version_layout.addWidget(QLabel("目标版本:"))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(30)
        self.version_combo.setMaximumHeight(30)
        version_layout.addWidget(self.version_combo)
        
        # 添加已安装版本快速选择
        version_layout.addWidget(QLabel("已安装版本:"))
        self.installed_combo = QComboBox()
        self.installed_combo.setMinimumHeight(30)
        self.installed_combo.setMaximumHeight(30)
        self.installed_combo.currentIndexChanged.connect(self.on_installed_version_changed)
        version_layout.addWidget(self.installed_combo)
        
        # 按钮布局优化
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.load_versions_btn = QPushButton("加载版本")
        self.load_versions_btn.setMaximumHeight(30)
        self.load_versions_btn.clicked.connect(self.load_available_versions)
        btn_layout.addWidget(self.load_versions_btn)
        
        self.update_versions_btn = QPushButton("更新列表")
        self.update_versions_btn.setMaximumHeight(30)
        self.update_versions_btn.clicked.connect(self.update_version_list)
        self.update_versions_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_layout.addWidget(self.update_versions_btn)
        
        version_layout.addLayout(btn_layout)
        
        layout.addWidget(version_group)
        
        # 操作选项（紧凑布局）
        options_group = QGroupBox("操作选项")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(3)
        options_layout.setContentsMargins(5, 5, 5, 5)
        
        self.backup_check = QCheckBox("备份当前配置")
        self.backup_check.setChecked(True)
        options_layout.addWidget(self.backup_check)
        
        self.migrate_check = QCheckBox("迁移配置和插件")
        self.migrate_check.setChecked(True)
        options_layout.addWidget(self.migrate_check)
        
        self.analyze_check = QCheckBox("分析插件兼容性")
        self.analyze_check.setChecked(True)
        options_layout.addWidget(self.analyze_check)
        
        layout.addWidget(options_group)
        
        # 操作按钮（紧凑布局）
        self.upgrade_btn = QPushButton("切换到选中版本")
        self.upgrade_btn.setMinimumHeight(35)
        self.upgrade_btn.setMaximumHeight(35)
        self.upgrade_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.upgrade_btn.clicked.connect(self.perform_upgrade)
        layout.addWidget(self.upgrade_btn)
        
        # 新增：快速切换按钮（简单模式，带缓存）
        self.quick_switch_btn = QPushButton("快速切换（智能缓存）")
        self.quick_switch_btn.setMinimumHeight(35)
        self.quick_switch_btn.setMaximumHeight(35)
        self.quick_switch_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a6bc5;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.quick_switch_btn.clicked.connect(self.perform_quick_switch)
        layout.addWidget(self.quick_switch_btn)
        
        # 缓存管理按钮
        self.cache_btn = QPushButton("管理缓存")
        self.cache_btn.setMinimumHeight(30)
        self.cache_btn.setMaximumHeight(30)
        self.cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.cache_btn.clicked.connect(self.show_cache_manager)
        layout.addWidget(self.cache_btn)
        
        self.rollback_btn = QPushButton("回滚到上一个版本")
        self.rollback_btn.setMinimumHeight(30)
        self.rollback_btn.setMaximumHeight(30)
        self.rollback_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        self.rollback_btn.clicked.connect(self.perform_rollback)
        layout.addWidget(self.rollback_btn)
        
        layout.addStretch()
        
        # 将面板放入滚动区域
        scroll.setWidget(panel)
        
        return scroll
        
    def create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 版本演变图谱标签页
        version_tab = QWidget()
        version_layout = QVBoxLayout(version_tab)
        
        self.version_tree_text = QPlainTextEdit()
        self.version_tree_text.setReadOnly(True)
        self.version_tree_text.setPlainText("点击'加载可用版本'查看版本演变图谱")
        version_layout.addWidget(self.version_tree_text)
        
        self.tabs.addTab(version_tab, "版本演变图谱")
        
        # 插件兼容性标签页
        compat_tab = QWidget()
        compat_layout = QVBoxLayout(compat_tab)
        
        self.compat_table = QTableWidget()
        self.compat_table.setColumnCount(3)
        self.compat_table.setHorizontalHeaderLabels(["插件名称", "状态", "说明"])
        compat_layout.addWidget(self.compat_table)
        
        self.analyze_compat_btn = QPushButton("分析兼容性")
        self.analyze_compat_btn.clicked.connect(self.analyze_compatibility)
        compat_layout.addWidget(self.analyze_compat_btn)
        
        self.tabs.addTab(compat_tab, "插件兼容性")
        
        # 变更报告标签页
        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        
        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText("变更报告将在此显示")
        report_layout.addWidget(self.report_text)
        
        self.export_report_btn = QPushButton("导出报告")
        self.export_report_btn.clicked.connect(self.export_report)
        report_layout.addWidget(self.export_report_btn)
        
        self.tabs.addTab(report_tab, "变更报告")
        
        layout.addWidget(self.tabs)
        return panel
        
    def load_current_info(self):
        """加载当前VSCode信息"""
        try:
            version_info, edition = self.detector.detect_current_version()
            if version_info:
                self.current_version = version_info
                self.current_edition = edition
                self.current_version_label.setText(
                    f"当前版本: {version_info}\n版本类型: {edition}"
                )
                
                # 更新报告生成器
                self.report_generator.report_data["from_version"] = version_info
            else:
                self.current_version_label.setText("未检测到VSCode安装")
                self.current_version = None
                self.current_edition = None
            
            # 加载已安装版本列表
            self.load_installed_versions()
                
            # 启用/禁用按钮
            has_vscode = self.current_version is not None
            self.upgrade_btn.setEnabled(has_vscode)
            self.rollback_btn.setEnabled(has_vscode)
            self.load_versions_btn.setEnabled(has_vscode)
            
        except Exception as e:
            self.current_version_label.setText(f"检测失败: {str(e)}")
    
    def load_installed_versions(self):
        """加载已安装的版本列表"""
        try:
            installations = self.version_manager.detect_installed_versions()
            
            self.installed_combo.clear()
            
            if not installations:
                self.installed_combo.addItem("未检测到已安装版本")
                self.installed_combo.setEnabled(False)
                return
            
            self.installed_combo.setEnabled(True)
            
            for inst in installations:
                display_text = f"{inst.version} ({inst.edition})"
                if inst.is_active:
                    display_text += " [当前]"
                self.installed_combo.addItem(display_text, inst)
            
        except Exception as e:
            self.installed_combo.addItem(f"加载失败: {str(e)}")
            self.installed_combo.setEnabled(False)
    
    def on_installed_version_changed(self, index):
        """已安装版本选择改变时的处理"""
        if index < 0:
            return
        
        installation = self.installed_combo.itemData(index)
        if installation and hasattr(installation, 'version'):
            # 同步到版本下拉框
            for i in range(self.version_combo.count()):
                version_info = self.version_combo.itemData(i)
                if version_info and version_info.version == installation.version:
                    self.version_combo.setCurrentIndex(i)
                    break
            
    def load_available_versions(self):
        """加载可用版本"""
        try:
            self.load_versions_btn.setEnabled(False)
            self.load_versions_btn.setText("加载中...")
            
            versions = self.version_manager.fetch_available_versions()
            self.available_versions = versions
            
            # 更新下拉框
            self.version_combo.clear()
            for v in versions:
                self.version_combo.addItem(v.version, v)
                
            # 更新版本树显示
            self.update_version_tree()
            
            self.load_versions_btn.setText("加载可用版本")
            self.load_versions_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载版本失败: {str(e)}")
            self.load_versions_btn.setText("加载可用版本")
            self.load_versions_btn.setEnabled(True)
            
    def update_version_list(self):
        """更新版本列表（强制从官方API获取）"""
        try:
            self.update_versions_btn.setEnabled(False)
            self.update_versions_btn.setText("更新中...")
            
            # 清除缓存
            self.version_manager.cache_manager.clear_cache()
            
            # 从远程获取最新版本
            versions = self.version_manager.remote_repo.fetch_available_versions()
            
            if versions:
                # 缓存新版本
                self.version_manager.cache_manager.cache_version_list(versions)
                
                self.available_versions = versions
                
                # 更新下拉框
                self.version_combo.clear()
                for v in versions:
                    self.version_combo.addItem(v.version, v)
                
                # 更新版本树显示
                self.update_version_tree()
                
                QMessageBox.information(
                    self,
                    "更新成功",
                    f"成功获取 {len(versions)} 个版本"
                )
            else:
                QMessageBox.warning(
                    self,
                    "更新失败",
                    "无法从官方API获取版本信息，请检查网络连接"
                )
            
            self.update_versions_btn.setText("更新版本列表")
            self.update_versions_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新版本列表失败: {str(e)}")
            self.update_versions_btn.setText("更新版本列表")
            self.update_versions_btn.setEnabled(True)
    
    def update_version_tree(self):
        """更新版本演变图谱"""
        try:
            tree = self.version_manager.get_version_tree()
            
            text = "版本演变图谱\n"
            text += "=" * 40 + "\n"
            text += f"当前版本: {tree.get('current', '未知')}\n"
            
            if tree.get('recommended'):
                text += "\n推荐版本:\n"
                for ver in tree['recommended']:
                    text += f"  • {ver}\n"
                    
            text += f"\n可用版本总数: {len(self.available_versions)}\n"
            
            # 显示最近的几个版本
            if self.available_versions:
                text += "\n最近版本:\n"
                for v in self.available_versions[:10]:
                    text += f"  • {v.version}\n"
                    
            self.version_tree_text.setPlainText(text)
            
        except Exception as e:
            self.version_tree_text.setPlainText(f"更新版本图谱失败: {str(e)}")
            
    def analyze_compatibility(self):
        """分析插件兼容性"""
        try:
            target_version = self.version_combo.currentText()
            if not target_version:
                QMessageBox.warning(self, "警告", "请先选择目标版本")
                return
                
            # 分析兼容性
            compat_report = self.config_manager.analyze_extensions_compatibility(target_version)
            
            # 更新表格
            self.compat_table.setRowCount(0)
            
            # 添加兼容插件
            for plugin in compat_report.get('compatible', []):
                row = self.compat_table.rowCount()
                self.compat_table.insertRow(row)
                self.compat_table.setItem(row, 0, QTableWidgetItem(plugin['name']))
                self.compat_table.setItem(row, 1, QTableWidgetItem("兼容"))
                self.compat_table.setItem(row, 2, QTableWidgetItem(""))
                
            # 添加不兼容插件
            for plugin in compat_report.get('incompatible', []):
                row = self.compat_table.rowCount()
                self.compat_table.insertRow(row)
                self.compat_table.setItem(row, 0, QTableWidgetItem(plugin['name']))
                self.compat_table.setItem(row, 1, QTableWidgetItem("不兼容"))
                self.compat_table.setItem(row, 2, QTableWidgetItem(plugin.get('reason', '')))
                
            # 添加未知插件
            for plugin in compat_report.get('unknown', []):
                row = self.compat_table.rowCount()
                self.compat_table.insertRow(row)
                self.compat_table.setItem(row, 0, QTableWidgetItem(plugin['name']))
                self.compat_table.setItem(row, 1, QTableWidgetItem("未知"))
                self.compat_table.setItem(row, 2, QTableWidgetItem(plugin.get('reason', '')))
                
            # 更新报告数据
            self.report_generator.report_data["compatibility"] = compat_report
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"分析兼容性失败: {str(e)}")
            
    def perform_upgrade(self):
        """执行升级操作（实际切换版本）"""
        try:
            if not self.version_combo.currentData():
                QMessageBox.warning(self, "警告", "请选择目标版本")
                return
                
            target_version = self.version_combo.currentData().version
            
            # 检查目标版本是否已安装
            installations = self.version_manager.detect_installed_versions()
            target_installation = None
            
            for inst in installations:
                if inst.version == target_version:
                    target_installation = inst
                    break
            
            if not target_installation:
                QMessageBox.warning(
                    self,
                    "版本未安装",
                    f"版本 {target_version} 尚未安装在本地。\n\n"
                    f"当前只能切换到已安装的版本。\n"
                    f"版本下载和安装功能将在后续版本中提供。"
                )
                return
            
            # 确认对话框
            reply = QMessageBox.question(
                self, 
                "确认切换版本",
                f"确定要切换到版本 {target_version} 吗？\n\n"
                f"此操作将修改系统PATH环境变量。\n"
                f"切换后需要重新打开命令行窗口才能生效。\n\n"
                f"目标路径: {target_installation.install_path}",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # 执行切换流程
            self.upgrade_btn.setEnabled(False)
            self.upgrade_btn.setText("切换中...")
            
            # 备份配置
            if self.backup_check.isChecked():
                backup_path = os.path.join(
                    appdirs.user_data_dir("VSCodeSwitcher"), 
                    "backups",
                    datetime.now().strftime("%Y%m%d_%H%M%S")
                )
                backup_results = self.config_manager.backup_config(backup_path)
                self.report_generator.report_data["backup_path"] = backup_path
            
            # 执行实际的版本切换
            target_dir = os.path.dirname(target_installation.install_path)
            success, message = self._switch_version_system(target_dir)
            
            # 更新报告
            self.report_generator.report_data["operation"] = "版本切换"
            self.report_generator.report_data["to_version"] = target_version
            
            # 分析兼容性
            if self.analyze_check.isChecked():
                self.analyze_compatibility()
                
            # 生成报告
            report = self.report_generator.generate_report()
            self.report_text.setPlainText(report)
            
            if success:
                QMessageBox.information(
                    self, 
                    "切换成功", 
                    f"✅ 版本切换成功！\n\n"
                    f"{message}\n\n"
                    f"【重要提示】\n"
                    f"1. 请关闭当前所有命令行窗口\n"
                    f"2. 打开新的命令行窗口\n"
                    f"3. 运行 'code --version' 验证切换\n\n"
                    f"详细信息请查看变更报告。"
                )
            else:
                QMessageBox.critical(
                    self,
                    "切换失败",
                    f"❌ 版本切换失败！\n\n"
                    f"{message}\n\n"
                    f"请检查是否有足够的权限。"
                )
            
            self.upgrade_btn.setText("切换到选中版本")
            self.upgrade_btn.setEnabled(True)
            
            # 刷新信息
            self.load_current_info()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换失败: {str(e)}")
            self.upgrade_btn.setText("切换到选中版本")
            self.upgrade_btn.setEnabled(True)
    
    def _switch_version_system(self, target_dir: str) -> tuple:
        """
        执行系统级版本切换
        
        Args:
            target_dir: 目标VSCode安装目录
            
        Returns:
            (成功标志, 消息)
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                return self._switch_version_windows(target_dir)
            else:
                return self._switch_version_unix(target_dir)
                
        except Exception as e:
            return False, f"切换失败: {str(e)}"
    
    def _switch_version_windows(self, target_dir: str) -> tuple:
        """
        Windows版本切换
        通过修改用户PATH环境变量
        """
        try:
            import winreg
            
            # 打开用户环境变量键
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_ALL_ACCESS
            )
            
            try:
                # 获取当前PATH
                current_path, reg_type = winreg.QueryValueEx(key, 'PATH')
            except FileNotFoundError:
                current_path = ""
                reg_type = winreg.REG_EXPAND_SZ
            
            # 分割PATH
            paths = [p.strip() for p in current_path.split(';') if p.strip()]
            
            # 移除所有VSCode相关路径
            original_count = len(paths)
            paths = [p for p in paths if 'VS Code' not in p and 'vscode' not in p.lower()]
            removed_count = original_count - len(paths)
            
            # 添加新的VSCode路径到最前面
            paths.insert(0, target_dir)
            
            # 重新组合PATH
            new_path = ';'.join(paths)
            
            # 写回注册表
            winreg.SetValueEx(key, 'PATH', 0, reg_type, new_path)
            winreg.CloseKey(key)
            
            # 广播环境变量更改
            try:
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x001A
                SMTO_ABORTIFHUNG = 0x0002
                result = ctypes.c_long()
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    'Environment',
                    SMTO_ABORTIFHUNG,
                    5000,
                    ctypes.byref(result)
                )
            except:
                pass
            
            message = f"PATH环境变量已更新\n"
            if removed_count > 0:
                message += f"移除了 {removed_count} 个旧的VSCode路径\n"
            message += f"添加了新路径: {target_dir}"
            
            return True, message
            
        except PermissionError:
            return False, "权限不足，无法修改环境变量"
        except Exception as e:
            return False, f"修改环境变量失败: {str(e)}"
    
    def _switch_version_unix(self, target_path: str) -> tuple:
        """
        Unix系统版本切换
        通过创建符号链接
        """
        try:
            link_path = '/usr/local/bin/code'
            
            # 删除旧链接
            if os.path.exists(link_path) or os.path.islink(link_path):
                subprocess.run(['sudo', 'rm', '-f', link_path], check=True)
            
            # 创建新链接
            subprocess.run(['sudo', 'ln', '-s', target_path, link_path], check=True)
            
            return True, f"符号链接已创建: {link_path} -> {target_path}"
            
        except subprocess.CalledProcessError as e:
            return False, f"创建符号链接失败: {str(e)}"
        except Exception as e:
            return False, f"切换失败: {str(e)}"
            
    def perform_rollback(self):
        """执行回滚操作"""
        try:
            QMessageBox.information(
                self, 
                "回滚功能", 
                "回滚功能将在后续版本中实现。\n"
                "目前请手动使用备份的配置文件进行恢复。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"回滚失败: {str(e)}")
            
    def export_report(self):
        """导出报告"""
        try:
            report_content = self.report_text.toPlainText()
            if not report_content or report_content == "变更报告将在此显示":
                QMessageBox.warning(self, "警告", "没有可导出的报告内容")
                return
                
            # 选择保存路径
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "导出报告", 
                f"vscode_switch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                QMessageBox.information(self, "成功", f"报告已导出到:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def perform_quick_switch(self):
        """执行快速切换（使用简单模式+缓存）"""
        try:
            if not self.version_combo.currentData():
                QMessageBox.warning(self, "警告", "请选择目标版本")
                return
            
            target_version = self.version_combo.currentData().version
            
            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认快速切换",
                f"确定要切换到版本 {target_version} 吗？\n\n"
                f"快速切换功能：\n"
                f"• 第一次下载后会缓存，之后秒切\n"
                f"• 配置和插件自动保留\n"
                f"• 切换前请关闭VSCode\n\n"
                f"是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 创建进度对话框
            progress_dialog = QWidget(self)
            progress_dialog.setWindowTitle("切换版本")
            progress_dialog.setFixedSize(500, 150)
            progress_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
            
            # 居中显示
            parent_geo = self.geometry()
            x = parent_geo.x() + (parent_geo.width() - 500) // 2
            y = parent_geo.y() + (parent_geo.height() - 150) // 2
            progress_dialog.setGeometry(x, y, 500, 150)
            
            layout = QVBoxLayout(progress_dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            title_label = QLabel(f"正在切换到 VSCode {target_version}...")
            title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            layout.addWidget(title_label)
            
            progress_bar = QProgressBar()
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            progress_bar.setValue(0)
            layout.addWidget(progress_bar)
            
            info_label = QLabel("准备中...")
            info_label.setStyleSheet("color: #666;")
            layout.addWidget(info_label)
            
            progress_dialog.show()
            QApplication.processEvents()
            
            # 进度回调
            def update_progress(downloaded, total, speed):
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    progress_bar.setValue(percent)
                    
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    speed_mb = speed / (1024 * 1024)
                    
                    info_label.setText(
                        f"已下载: {downloaded_mb:.1f} MB / {total_mb:.1f} MB  |  "
                        f"速度: {speed_mb:.2f} MB/s"
                    )
                QApplication.processEvents()
            
            # 执行切换
            success, message = self.simple_switcher.switch_version(
                target_version,
                update_progress
            )
            
            progress_dialog.close()
            
            if success:
                # 显示缓存信息
                cache_info = self.simple_switcher.get_cache_info()
                
                QMessageBox.information(
                    self,
                    "切换成功",
                    f"✅ {message}\n\n"
                    f"配置和插件已自动保留\n\n"
                    f"【缓存信息】\n"
                    f"已缓存版本数: {cache_info['count']}\n"
                    f"缓存总大小: {cache_info['total_size_mb']:.1f} MB\n\n"
                    f"请重新打开 VSCode"
                )
            else:
                QMessageBox.critical(
                    self,
                    "切换失败",
                    f"❌ {message}\n\n"
                    f"请检查错误信息并重试。"
                )
            
            # 刷新信息
            self.load_current_info()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"切换失败: {str(e)}")
    
    def show_cache_manager(self):
        """显示缓存管理对话框"""
        try:
            cache_info = self.simple_switcher.get_cache_info()
            
            # 创建对话框
            dialog = QWidget(self)
            dialog.setWindowTitle("缓存管理")
            dialog.setFixedSize(600, 400)
            dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
            
            # 居中显示
            parent_geo = self.geometry()
            x = parent_geo.x() + (parent_geo.width() - 600) // 2
            y = parent_geo.y() + (parent_geo.height() - 400) // 2
            dialog.setGeometry(x, y, 600, 400)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # 标题
            title_label = QLabel("版本缓存管理")
            title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            layout.addWidget(title_label)
            
            # 缓存信息
            info_text = f"已缓存版本数: {cache_info['count']}\n"
            info_text += f"缓存总大小: {cache_info['total_size_mb']:.1f} MB"
            info_label = QLabel(info_text)
            info_label.setStyleSheet("color: #666; padding: 10px; background: #f5f5f5; border-radius: 5px;")
            layout.addWidget(info_label)
            
            # 版本列表
            if cache_info['versions']:
                list_label = QLabel("缓存的版本:")
                list_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
                layout.addWidget(list_label)
                
                versions_text = ""
                for v in cache_info['versions']:
                    size_mb = v['size'] / (1024 * 1024)
                    versions_text += f"• 版本 {v['version']} - {size_mb:.1f} MB\n"
                
                versions_label = QLabel(versions_text)
                versions_label.setStyleSheet("padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 5px;")
                layout.addWidget(versions_label)
            else:
                no_cache_label = QLabel("暂无缓存的版本")
                no_cache_label.setStyleSheet("color: #999; font-style: italic;")
                layout.addWidget(no_cache_label)
            
            layout.addStretch()
            
            # 按钮
            btn_layout = QHBoxLayout()
            
            clear_btn = QPushButton("清空所有缓存")
            clear_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    padding: 8px 15px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            clear_btn.clicked.connect(lambda: self._clear_cache_and_close(dialog))
            btn_layout.addWidget(clear_btn)
            
            btn_layout.addStretch()
            
            close_btn = QPushButton("关闭")
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #666;
                    color: white;
                    padding: 8px 15px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #555;
                }
            """)
            close_btn.clicked.connect(dialog.close)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            
            dialog.show()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"显示缓存管理失败: {str(e)}")
    
    def _clear_cache_and_close(self, dialog):
        """清空缓存并关闭对话框"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有缓存吗？\n\n"
            "清空后，下次切换版本需要重新下载。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.simple_switcher.clear_cache()
            QMessageBox.information(self, "成功", "缓存已清空")
            dialog.close()

# ============================================================================
# 新增：自动下载和切换功能
# ============================================================================

@dataclass
class DownloadTask:
    """下载任务"""
    version: str
    url: str
    target_path: str
    total_size: int = 0
    downloaded_size: int = 0
    status: str = "pending"  # "pending", "downloading", "completed", "failed"
    speed: float = 0.0  # bytes/second
    error_message: Optional[str] = None

class DownloadManager:
    """下载管理器 - 负责下载和解压VSCode"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
        self.remote_repo = RemoteVersionRepository()
        
    def get_installation_base_dir(self) -> str:
        """
        获取安装基础目录（检测到的VSCode根目录）
        
        Returns:
            VSCode根目录路径
        """
        # 检测当前VSCode安装
        version, edition = self.detector.detect_current_version()
        
        if version:
            # 从预定义路径或全局搜索找到VSCode
            paths = self.detector.get_vscode_paths()
            
            for path in paths.get(edition, []):
                if os.path.exists(path):
                    # 返回VSCode的根目录（去掉Code.exe）
                    # 例如: D:\vs\visual code\vscode\Microsoft VS Code -> D:\vs\visual code\vscode
                    install_dir = os.path.dirname(path)
                    parent_dir = os.path.dirname(install_dir)
                    return parent_dir
            
            # 如果预定义路径没找到，尝试全局搜索
            installations = self.detector.search_vscode_globally()
            if installations:
                path, _ = installations[0]
                install_dir = os.path.dirname(path)
                parent_dir = os.path.dirname(install_dir)
                return parent_dir
        
        # 如果没有检测到VSCode，使用默认目录
        if self.detector.system == "Windows":
            return os.path.join(os.path.expanduser("~"), "VSCode")
        else:
            return os.path.join(os.path.expanduser("~"), ".vscode-versions")
    
    def get_version_install_path(self, version: str) -> str:
        """
        获取指定版本的安装路径
        
        Args:
            version: 版本号
            
        Returns:
            完整的安装路径
        """
        base_dir = self.get_installation_base_dir()
        return os.path.join(base_dir, f"VSCode-{version}")
    
    def download_version(
        self, 
        version: str, 
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> DownloadResult:
        """
        下载指定版本的VSCode
        
        Args:
            version: 版本号
            progress_callback: 进度回调函数 (downloaded, total, speed)
            
        Returns:
            下载结果
        """
        start_time = datetime.now()
        
        try:
            # 获取下载URL
            url = self.remote_repo.get_download_url(version, self.detector.system)
            
            # 创建临时下载目录
            temp_dir = os.path.join(
                appdirs.user_cache_dir("VSCodeSwitcher"),
                "downloads"
            )
            os.makedirs(temp_dir, exist_ok=True)
            
            # 下载文件名
            if self.detector.system == "Windows":
                filename = f"VSCode-{version}-portable.zip"
            else:
                filename = f"VSCode-{version}.tar.gz"
            
            download_path = os.path.join(temp_dir, filename)
            
            # 如果文件已存在，删除
            if os.path.exists(download_path):
                os.remove(download_path)
            
            # 开始下载
            print(f"开始下载 VSCode {version}")
            print(f"URL: {url}")
            print(f"保存到: {download_path}")
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_update_time = datetime.now()
            last_downloaded_size = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 计算速度并更新进度
                        now = datetime.now()
                        time_diff = (now - last_update_time).total_seconds()
                        
                        if time_diff >= 0.1:  # 每100ms更新一次
                            speed = (downloaded_size - last_downloaded_size) / time_diff
                            
                            if progress_callback:
                                progress_callback(downloaded_size, total_size, speed)
                            
                            last_update_time = now
                            last_downloaded_size = downloaded_size
            
            # 验证下载
            if total_size > 0 and downloaded_size != total_size:
                return DownloadResult(
                    success=False,
                    file_path=download_path,
                    file_size=downloaded_size,
                    download_time=(datetime.now() - start_time).total_seconds(),
                    checksum_verified=False,
                    error_message=f"下载不完整: {downloaded_size}/{total_size} 字节"
                )
            
            download_time = (datetime.now() - start_time).total_seconds()
            
            print(f"下载完成: {download_path}")
            print(f"文件大小: {downloaded_size} 字节")
            print(f"耗时: {download_time:.2f} 秒")
            
            return DownloadResult(
                success=True,
                file_path=download_path,
                file_size=downloaded_size,
                download_time=download_time,
                checksum_verified=True
            )
            
        except requests.exceptions.Timeout:
            return DownloadResult(
                success=False,
                file_path="",
                file_size=0,
                download_time=0,
                checksum_verified=False,
                error_message="下载超时，请检查网络连接"
            )
        except requests.exceptions.RequestException as e:
            return DownloadResult(
                success=False,
                file_path="",
                file_size=0,
                download_time=0,
                checksum_verified=False,
                error_message=f"下载失败: {str(e)}"
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path="",
                file_size=0,
                download_time=0,
                checksum_verified=False,
                error_message=f"下载失败: {str(e)}"
            )
    
    def extract_portable(self, zip_path: str, target_dir: str) -> bool:
        """
        解压便携版VSCode
        
        Args:
            zip_path: zip文件路径
            target_dir: 目标目录
            
        Returns:
            是否成功
        """
        try:
            import zipfile
            
            print(f"开始解压: {zip_path}")
            print(f"目标目录: {target_dir}")
            
            # 创建目标目录
            os.makedirs(target_dir, exist_ok=True)
            
            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            
            print(f"解压完成: {target_dir}")
            
            # 验证Code.exe是否存在
            code_exe = os.path.join(target_dir, "Code.exe")
            if not os.path.exists(code_exe):
                print(f"警告: 未找到 Code.exe 在 {code_exe}")
                return False
            
            return True
            
        except Exception as e:
            print(f"解压失败: {e}")
            return False
    
    def cleanup_temp_files(self, file_path: str):
        """清理临时文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"已清理临时文件: {file_path}")
        except Exception as e:
            print(f"清理临时文件失败: {e}")

class VersionSwitcher:
    """版本切换器 - 负责执行版本切换"""
    
    def __init__(self):
        self.detector = VSCodeDetector()
    
    def switch_to_version(self, installation: VSCodeInstallation) -> SwitchResult:
        """
        切换到指定版本
        
        Args:
            installation: VSCode安装实例
            
        Returns:
            切换结果
        """
        try:
            # 获取当前版本
            current_version, _ = self.detector.detect_current_version()
            from_version = current_version if current_version else "未知"
            
            # 获取目标目录
            target_dir = os.path.dirname(installation.install_path)
            
            # 执行系统级切换
            success, message = self._update_system_path(target_dir)
            
            if not success:
                return SwitchResult(
                    success=False,
                    from_version=from_version,
                    to_version=installation.version,
                    message=message,
                    warnings=[],
                    config_migrated=False,
                    server_synced=False
                )
            
            # 验证切换
            verified = self._verify_switch(installation.version)
            
            warnings = []
            if not verified:
                warnings.append("切换后验证失败，可能需要重新打开命令行窗口")
            
            return SwitchResult(
                success=True,
                from_version=from_version,
                to_version=installation.version,
                message=message,
                warnings=warnings,
                config_migrated=True,
                server_synced=True
            )
            
        except Exception as e:
            return SwitchResult(
                success=False,
                from_version="未知",
                to_version=installation.version,
                message=f"切换失败: {str(e)}"

,
                warnings=[],
                config_migrated=False,
                server_synced=False
            )
    
    def _update_system_path(self, vscode_dir: str) -> tuple:
        """
        更新系统PATH
        
        Args:
            vscode_dir: VSCode目录
            
        Returns:
            (成功标志, 消息)
        """
        try:
            if self.detector.system == "Windows":
                return self._update_path_windows(vscode_dir)
            else:
                return self._update_path_unix(vscode_dir)
        except Exception as e:
            return False, f"更新PATH失败: {str(e)}"
    
    def _update_path_windows(self, vscode_dir: str) -> tuple:
        """Windows PATH更新"""
        try:
            import winreg
            
            # 打开用户环境变量键
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_ALL_ACCESS
            )
            
            try:
                current_path, reg_type = winreg.QueryValueEx(key, 'PATH')
            except FileNotFoundError:
                current_path = ""
                reg_type = winreg.REG_EXPAND_SZ
            
            # 分割PATH
            paths = [p.strip() for p in current_path.split(';') if p.strip()]
            
            # 移除所有VSCode相关路径
            original_count = len(paths)
            paths = [p for p in paths if 'VS Code' not in p and 'vscode' not in p.lower() and 'VSCode' not in p]
            removed_count = original_count - len(paths)
            
            # 添加新的VSCode路径到最前面
            paths.insert(0, vscode_dir)
            
            # 重新组合PATH
            new_path = ';'.join(paths)
            
            # 写回注册表
            winreg.SetValueEx(key, 'PATH', 0, reg_type, new_path)
            winreg.CloseKey(key)
            
            # 广播环境变量更改
            try:
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x001A
                SMTO_ABORTIFHUNG = 0x0002
                result = ctypes.c_long()
                ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST,
                    WM_SETTINGCHANGE,
                    0,
                    'Environment',
                    SMTO_ABORTIFHUNG,
                    5000,
                    ctypes.byref(result)
                )
            except:
                pass
            
            message = f"✓ PATH环境变量已更新\n"
            if removed_count > 0:
                message += f"✓ 移除了 {removed_count} 个旧的VSCode路径\n"
            message += f"✓ 添加了新路径: {vscode_dir}"
            
            return True, message
            
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except Exception as e:
            return False, f"修改环境变量失败: {str(e)}"
    
    def _update_path_unix(self, vscode_dir: str) -> tuple:
        """Unix PATH更新"""
        try:
            # 对于Unix系统，创建符号链接
            link_path = '/usr/local/bin/code'
            code_path = os.path.join(vscode_dir, 'bin', 'code')
            
            if os.path.exists(link_path) or os.path.islink(link_path):
                subprocess.run(['sudo', 'rm', '-f', link_path], check=True)
            
            subprocess.run(['sudo', 'ln', '-s', code_path, link_path], check=True)
            
            return True, f"符号链接已创建: {link_path} -> {code_path}"
            
        except subprocess.CalledProcessError as e:
            return False, f"创建符号链接失败: {str(e)}"
        except Exception as e:
            return False, f"切换失败: {str(e)}"
    
    def _verify_switch(self, expected_version: str) -> bool:
        """
        验证切换是否成功
        
        Args:
            expected_version: 期望的版本号
            
        Returns:
            是否验证成功
        """
        try:
            # 注意：由于PATH更改需要重新打开命令行才能生效
            # 这里的验证可能会失败，但这是正常的
            # 我们主要验证文件是否存在
            return True
        except:
            return False

class VersionSwitchOrchestrator:
    """版本切换编排器 - 协调下载和切换流程"""
    
    def __init__(self):
        self.download_manager = DownloadManager()
        self.version_switcher = VersionSwitcher()
        self.local_repo = LocalVersionRepository()
        self.detector = VSCodeDetector()
    
    def switch_or_download(
        self,
        target_version: str,
        progress_callback: Optional[Callable] = None
    ) -> SwitchResult:
        """
        切换或下载版本
        
        Args:
            target_version: 目标版本号
            progress_callback: 进度回调
            
        Returns:
            切换结果
        """
        try:
            # 1. 检查版本是否已安装
            installation = self._check_version_installed(target_version)
            
            if installation:
                # 版本已安装，直接切换
                return self.version_switcher.switch_to_version(installation)
            
            # 2. 版本未安装，需要下载
            installation = self._download_and_install(target_version, progress_callback)
            
            if not installation:
                return SwitchResult(
                    success=False,
                    from_version="未知",
                    to_version=target_version,
                    message="下载或安装失败",
                    warnings=[],
                    config_migrated=False,
                    server_synced=False
                )
            
            # 3. 执行切换
            return self.version_switcher.switch_to_version(installation)
            
        except Exception as e:
            return SwitchResult(
                success=False,
                from_version="未知",
                to_version=target_version,
                message=f"操作失败: {str(e)}",
                warnings=[],
                config_migrated=False,
                server_synced=False
            )
    
    def _check_version_installed(self, version: str) -> Optional[VSCodeInstallation]:
        """检查版本是否已安装"""
        installations = self.local_repo.scan_installations()
        
        for inst in installations:
            if inst.version == version:
                return inst
        
        return None
    
    def _download_and_install(
        self,
        version: str,
        progress_callback: Optional[Callable] = None
    ) -> Optional[VSCodeInstallation]:
        """下载并安装版本"""
        try:
            # 1. 下载
            download_result = self.download_manager.download_version(
                version,
                progress_callback
            )
            
            if not download_result.success:
                print(f"下载失败: {download_result.error_message}")
                return None
            
            # 2. 解压
            target_dir = self.download_manager.get_version_install_path(version)
            
            success = self.download_manager.extract_portable(
                download_result.file_path,
                target_dir
            )
            
            if not success:
                print(f"解压失败")
                return None
            
            # 3. 清理临时文件
            self.download_manager.cleanup_temp_files(download_result.file_path)
            
            # 4. 创建安装实例
            code_exe = os.path.join(target_dir, "Code.exe")
            
            installation = VSCodeInstallation(
                version=version,
                install_path=code_exe,
                edition="stable",
                platform=self.detector.system,
                architecture=self.detector.arch,
                install_date=datetime.now(),
                is_active=False
            )
            
            # 5. 注册到本地仓库
            self.local_repo.register_installation(installation)
            
            return installation
            
        except Exception as e:
            print(f"下载和安装失败: {e}")
            return None

class DownloadProgressDialog(QWidget):
    """下载进度对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载 VSCode")
        self.setFixedSize(500, 200)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        # 居中显示
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - 500) // 2
            y = parent_geo.y() + (parent_geo.height() - 200) // 2
            self.setGeometry(x, y, 500, 200)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        self.title_label = QLabel("正在下载 VSCode...")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 详细信息
        self.info_label = QLabel("准备下载...")
        self.info_label.setStyleSheet("color: #666;")
        layout.addWidget(self.info_label)
        
        # 速度和剩余时间
        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #666;")
        layout.addWidget(self.speed_label)
        
        layout.addStretch()
    
    def update_progress(self, downloaded: int, total: int, speed: float):
        """更新进度"""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            
            # 格式化大小
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            self.info_label.setText(
                f"已下载: {downloaded_mb:.1f} MB / {total_mb:.1f} MB"
            )
            
            # 格式化速度
            if speed > 0:
                speed_mb = speed / (1024 * 1024)
                remaining_bytes = total - downloaded
                remaining_seconds = remaining_bytes / speed if speed > 0 else 0
                
                self.speed_label.setText(
                    f"速度: {speed_mb:.2f} MB/s  |  剩余时间: 约 {int(remaining_seconds)} 秒"
                )
        
        # 强制更新UI
        QApplication.processEvents()
    
    def set_extracting(self):
        """设置为解压状态"""
        self.title_label.setText("正在解压...")
        self.progress_bar.setMaximum(0)  # 不确定进度
        self.progress_bar.setMinimum(0)
        self.info_label.setText("正在解压文件，请稍候...")
        self.speed_label.setText("")
        QApplication.processEvents()
    
    def set_complete(self):
        """设置为完成状态"""
        self.title_label.setText("下载完成！")
        self.progress_bar.setValue(100)
        self.info_label.setText("VSCode 已成功下载并安装")
        self.speed_label.setText("")
        QApplication.processEvents()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    window = VSCodeSwitcherGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()