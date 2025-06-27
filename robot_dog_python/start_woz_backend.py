#!/usr/bin/env python3
"""
WOZ系统后端启动脚本
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ.setdefault('PYTHONPATH', str(project_root))

def main():
    """启动WOZ系统后端"""
    try:
        from woz_system_backend.main import run_server
        print("Starting WOZ System Backend...")
        print(f"Project root: {project_root}")
        print("Backend will be available at: http://0.0.0.0:8995")
        print("API documentation: http://0.0.0.0:8995/docs")
        print("Press Ctrl+C to stop the server")
        
        run_server()
        
    except KeyboardInterrupt:
        print("\nShutting down WOZ System Backend...")
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please ensure all dependencies are installed:")
        print("pip install fastapi uvicorn python-multipart")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to start WOZ System Backend: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
