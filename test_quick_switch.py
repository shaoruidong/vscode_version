#!/usr/bin/env python3
"""
测试快速切换功能
"""

from main import VSCodeDetector
from version_switcher_simple import SimpleVersionSwitcher

def main():
    print("=" * 70)
    print("测试快速切换功能")
    print("=" * 70)
    print()
    
    # 1. 创建检测器和切换器
    detector = VSCodeDetector()
    switcher = SimpleVersionSwitcher(detector)
    
    # 2. 获取当前版本
    print("【步骤1】获取当前版本")
    print("-" * 70)
    current_version, install_dir = switcher.get_current_version()
    
    if current_version:
        print(f"✓ 当前版本: {current_version}")
        print(f"  安装目录: {install_dir}")
    else:
        print("✗ 未检测到VSCode")
        return
    
    print()
    
    # 3. 查看缓存信息
    print("【步骤2】查看缓存信息")
    print("-" * 70)
    cache_info = switcher.get_cache_info()
    
    print(f"已缓存版本数: {cache_info['count']}")
    print(f"缓存总大小: {cache_info['total_size_mb']:.1f} MB")
    
    if cache_info['versions']:
        print("\n缓存的版本:")
        for v in cache_info['versions']:
            size_mb = v['size'] / (1024 * 1024)
            print(f"  • 版本 {v['version']} - {size_mb:.1f} MB")
    else:
        print("暂无缓存")
    
    print()
    
    # 4. 说明
    print("【使用说明】")
    print("-" * 70)
    print("1. 打开GUI: python main.py")
    print("2. 点击'加载版本列表'")
    print("3. 选择目标版本")
    print("4. 点击'快速切换（智能缓存）'按钮")
    print()
    print("【功能特点】")
    print("• 第一次切换某个版本：下载并缓存（2-3分钟）")
    print("• 再次切换到该版本：从缓存读取（秒切）")
    print("• 配置和插件自动保留")
    print("• 可以管理缓存（查看、清空）")
    
    print()
    print("=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
