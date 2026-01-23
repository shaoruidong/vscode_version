#!/usr/bin/env python3
"""
测试下载速度优化效果
"""

import time
from version_switcher_simple import SimpleVersionSwitcher, VersionCache
from main import VSCodeDetector

def test_download_speed():
    """测试下载速度"""
    print("=" * 60)
    print("VSCode 下载速度测试")
    print("=" * 60)
    
    # 初始化
    detector = VSCodeDetector()
    switcher = SimpleVersionSwitcher(detector)
    
    # 测试版本
    test_version = "1.98.2"
    
    print(f"\n测试版本: {test_version}")
    print(f"当前系统: {detector.system}")
    
    # 进度回调
    start_time = time.time()
    last_progress_time = start_time
    
    def progress_callback(downloaded, total, speed):
        nonlocal last_progress_time
        
        # 每秒更新一次
        now = time.time()
        if now - last_progress_time < 1.0:
            return
        last_progress_time = now
        
        percent = (downloaded / total * 100) if total > 0 else 0
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        
        elapsed = now - start_time
        
        print(f"\r进度: {percent:.1f}% | "
              f"{downloaded_mb:.1f}/{total_mb:.1f} MB | "
              f"速度: {speed_mb:.2f} MB/s | "
              f"已用时: {elapsed:.0f}秒", end="")
    
    # 检查缓存
    cached = switcher.cache.get_cached_version(test_version)
    if cached:
        print(f"\n✓ 版本 {test_version} 已在缓存中")
        print(f"  缓存文件: {cached}")
        
        # 测试从缓存切换的速度
        print(f"\n测试从缓存切换...")
        start = time.time()
        success, msg = switcher.switch_version(test_version)
        elapsed = time.time() - start
        
        if success:
            print(f"\n✓ 从缓存切换成功！")
            print(f"  耗时: {elapsed:.1f} 秒")
        else:
            print(f"\n✗ 切换失败: {msg}")
    else:
        print(f"\n版本 {test_version} 不在缓存中，开始下载测试...")
        print(f"注意：这将下载约 140MB 的文件\n")
        
        # 下载测试
        success, msg = switcher.switch_version(test_version, progress_callback)
        
        elapsed = time.time() - start_time
        
        print(f"\n")
        print("=" * 60)
        if success:
            print(f"✓ 下载并切换成功！")
            print(f"  总耗时: {elapsed:.1f} 秒")
            print(f"  平均速度: {140 / elapsed:.2f} MB/s")
        else:
            print(f"✗ 失败: {msg}")
        print("=" * 60)
    
    # 显示缓存信息
    print(f"\n缓存信息:")
    cache_info = switcher.get_cache_info()
    print(f"  已缓存版本数: {cache_info['count']}")
    print(f"  总缓存大小: {cache_info['total_size_mb']:.1f} MB")
    
    if cache_info['versions']:
        print(f"\n  缓存的版本:")
        for v in cache_info['versions']:
            size_mb = v['size'] / (1024 * 1024)
            print(f"    - {v['version']}: {size_mb:.1f} MB")

if __name__ == "__main__":
    test_download_speed()
