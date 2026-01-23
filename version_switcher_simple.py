#!/usr/bin/env python3
"""
简单的VSCode版本切换器（带智能缓存）
可以升级或降级到任意指定版本，配置和插件自动保留
第一次下载后缓存，之后秒切
"""

import os
import tempfile
import shutil
import zipfile
import requests
import psutil
import json
from typing import Optional, Callable, Tuple, List
from datetime import datetime
import appdirs


class VersionCache:
    """版本缓存管理器"""
    
    def __init__(self):
        # 缓存目录
        self.cache_dir = os.path.join(
            appdirs.user_cache_dir("VSCodeSwitcher"),
            "versions"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 缓存索引文件
        self.index_file = os.path.join(self.cache_dir, "cache_index.json")
        self.index = self._load_index()
    
    def _load_index(self) -> dict:
        """加载缓存索引"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_index(self):
        """保存缓存索引"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存索引失败: {e}")
    
    def get_cached_version(self, version: str) -> Optional[str]:
        """
        获取缓存的版本
        
        Args:
            version: 版本号
            
        Returns:
            缓存的zip文件路径，如果不存在返回None
        """
        if version in self.index:
            zip_file = self.index[version]['path']
            if os.path.exists(zip_file):
                print(f"✓ 从缓存读取版本 {version}")
                return zip_file
            else:
                # 文件不存在，从索引中删除
                del self.index[version]
                self._save_index()
        return None
    
    def add_to_cache(self, version: str, zip_file: str) -> str:
        """
        添加版本到缓存
        
        Args:
            version: 版本号
            zip_file: 下载的zip文件路径
            
        Returns:
            缓存的文件路径
        """
        try:
            # 目标缓存文件
            cache_file = os.path.join(self.cache_dir, f"vscode-{version}.zip")
            
            # 复制到缓存目录
            if zip_file != cache_file:
                shutil.copy2(zip_file, cache_file)
            
            # 更新索引
            file_size = os.path.getsize(cache_file)
            self.index[version] = {
                'path': cache_file,
                'size': file_size,
                'cached_at': datetime.now().isoformat()
            }
            self._save_index()
            
            print(f"✓ 版本 {version} 已添加到缓存")
            return cache_file
            
        except Exception as e:
            print(f"添加到缓存失败: {e}")
            return zip_file
    
    def get_cached_versions(self) -> List[dict]:
        """获取所有缓存的版本"""
        versions = []
        for version, info in self.index.items():
            if os.path.exists(info['path']):
                versions.append({
                    'version': version,
                    'size': info['size'],
                    'cached_at': info['cached_at']
                })
        return versions
    
    def remove_from_cache(self, version: str) -> bool:
        """从缓存中删除版本"""
        if version in self.index:
            try:
                zip_file = self.index[version]['path']
                if os.path.exists(zip_file):
                    os.remove(zip_file)
                del self.index[version]
                self._save_index()
                print(f"✓ 已从缓存删除版本 {version}")
                return True
            except Exception as e:
                print(f"删除缓存失败: {e}")
                return False
        return False
    
    def clear_cache(self):
        """清空所有缓存"""
        try:
            for version in list(self.index.keys()):
                self.remove_from_cache(version)
            print("✓ 缓存已清空")
        except Exception as e:
            print(f"清空缓存失败: {e}")
    
    def get_cache_size(self) -> int:
        """获取缓存总大小（字节）"""
        total = 0
        for info in self.index.values():
            if os.path.exists(info['path']):
                total += info['size']
        return total


class SimpleVersionSwitcher:
    """简单的版本切换器 - 核心功能类（带缓存）"""
    
    def __init__(self, detector):
        """
        初始化
        
        Args:
            detector: VSCodeDetector实例
        """
        self.detector = detector
        self.cache = VersionCache()
    
    def get_current_version(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取当前版本
        
        Returns:
            (版本号, 安装路径) 或 (None, None)
        """
        version, edition = self.detector.detect_current_version()
        
        if not version:
            return None, None
        
        # 获取安装路径
        paths = self.detector.get_vscode_paths()
        for path in paths.get(edition, []):
            if os.path.exists(path):
                install_dir = os.path.dirname(path)
                return version, install_dir
        
        # 尝试全局搜索
        installations = self.detector.search_vscode_globally()
        if installations:
            path, _ = installations[0]
            install_dir = os.path.dirname(path)
            return version, install_dir
        
        return version, None
    
    def switch_version(
        self,
        target_version: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> Tuple[bool, str]:
        """
        切换到指定版本（智能缓存）
        
        Args:
            target_version: 目标版本号
            progress_callback: 进度回调 (downloaded, total, speed)
            
        Returns:
            (是否成功, 消息)
        """
        try:
            # 1. 获取当前安装目录
            current_version, install_dir = self.get_current_version()
            
            if not install_dir:
                return False, "无法找到VSCode安装目录"
            
            # 2. 检查是否是相同版本
            if current_version == target_version:
                return False, f"已经是版本 {target_version}"
            
            # 3. 检查VSCode是否运行
            if self._is_vscode_running():
                return False, "请先关闭VSCode"
            
            # 4. 检查缓存
            zip_file = self.cache.get_cached_version(target_version)
            
            if zip_file:
                # 从缓存读取，秒切
                print(f"使用缓存的版本 {target_version}")
            else:
                # 下载新版本
                print(f"下载版本 {target_version}...")
                zip_file = self._download_version(target_version, progress_callback)
                if not zip_file:
                    return False, "下载失败"
                
                # 添加到缓存
                zip_file = self.cache.add_to_cache(target_version, zip_file)
            
            # 5. 替换文件
            success = self._replace_files(zip_file, install_dir)
            
            if success:
                return True, f"成功切换到版本 {target_version}"
            else:
                return False, "替换文件失败"
                
        except Exception as e:
            return False, f"切换失败: {str(e)}"
    
    def get_cached_versions(self) -> List[dict]:
        """获取所有缓存的版本"""
        return self.cache.get_cached_versions()
    
    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        versions = self.cache.get_cached_versions()
        total_size = self.cache.get_cache_size()
        
        return {
            'count': len(versions),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'versions': versions
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear_cache()
    
    def remove_cached_version(self, version: str) -> bool:
        """删除指定版本的缓存"""
        return self.cache.remove_from_cache(version)
    
    def _is_vscode_running(self) -> bool:
        """检查VSCode是否正在运行"""
        try:
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if 'code.exe' in name or 'code' == name:
                    return True
            return False
        except:
            return False
    
    def _download_version(
        self,
        version: str,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        下载指定版本（优化版：更大的chunk、更好的镜像源）
        
        Args:
            version: 版本号
            progress_callback: 进度回调
            
        Returns:
            下载的zip文件路径，失败返回None
        """
        try:
            # 构建下载URL（尝试多个镜像源）
            urls = []
            
            if self.detector.system == "Windows":
                # 官方源
                urls.append(f"https://update.code.visualstudio.com/{version}/win32-x64-archive/stable")
                # 备用：vscode.cdn.azure.cn（中国镜像）
                urls.append(f"https://vscode.cdn.azure.cn/stable/{version}/VSCode-win32-x64-{version}.zip")
            elif self.detector.system == "Darwin":
                urls.append(f"https://update.code.visualstudio.com/{version}/darwin/stable")
            else:
                urls.append(f"https://update.code.visualstudio.com/{version}/linux-x64/stable")
            
            # 创建临时目录
            temp_dir = tempfile.gettempdir()
            zip_file = os.path.join(temp_dir, f"vscode-{version}.zip")
            
            # 如果文件已存在，删除
            if os.path.exists(zip_file):
                os.remove(zip_file)
            
            print(f"开始下载 VSCode {version}")
            
            # 尝试每个URL
            last_error = None
            for idx, url in enumerate(urls):
                try:
                    print(f"尝试下载源 {idx + 1}/{len(urls)}: {url}")
                    
                    # 下载文件（增大chunk_size到1MB，提升速度）
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    last_time = datetime.now()
                    last_downloaded = 0
                    
                    with open(zip_file, 'wb') as f:
                        # 使用1MB的chunk_size，大幅提升下载速度
                        for chunk in response.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # 更新进度
                                now = datetime.now()
                                time_diff = (now - last_time).total_seconds()
                                
                                if time_diff >= 0.5 and progress_callback:
                                    speed = (downloaded - last_downloaded) / time_diff
                                    progress_callback(downloaded, total_size, speed)
                                    last_time = now
                                    last_downloaded = downloaded
                    
                    # 最后一次进度更新
                    if progress_callback:
                        now = datetime.now()
                        time_diff = (now - last_time).total_seconds()
                        if time_diff > 0:
                            speed = (downloaded - last_downloaded) / time_diff
                            progress_callback(downloaded, total_size, speed)
                    
                    print(f"下载完成: {zip_file}")
                    return zip_file
                    
                except Exception as e:
                    last_error = e
                    print(f"下载源 {idx + 1} 失败: {e}")
                    if os.path.exists(zip_file):
                        os.remove(zip_file)
                    continue
            
            # 所有源都失败
            print(f"所有下载源都失败，最后错误: {last_error}")
            return None
            
        except Exception as e:
            print(f"下载失败: {e}")
            return None
    
    def _replace_files(self, zip_file: str, install_dir: str) -> bool:
        """
        替换VSCode文件
        
        Args:
            zip_file: 下载的zip文件
            install_dir: VSCode安装目录
            
        Returns:
            是否成功
        """
        try:
            print(f"开始替换文件...")
            print(f"安装目录: {install_dir}")
            
            # 1. 删除旧文件（保留data目录）
            for item in os.listdir(install_dir):
                if item == 'data':  # 便携版的用户数据
                    continue
                
                path = os.path.join(install_dir, item)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    else:
                        shutil.rmtree(path)
                except Exception as e:
                    print(f"删除 {path} 失败: {e}")
            
            # 2. 解压新文件
            print(f"解压文件到: {install_dir}")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(install_dir)
            
            # 3. 验证
            code_exe = os.path.join(install_dir, "Code.exe")
            if not os.path.exists(code_exe):
                print(f"错误: 未找到 Code.exe")
                return False
            
            print(f"替换完成！")
            return True
            
        except Exception as e:
            print(f"替换文件失败: {e}")
            return False
