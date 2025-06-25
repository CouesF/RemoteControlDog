"""
WOZ系统后端启动脚本
"""
import sys
import os
import logging

# 添加项目路径到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def main():
    """启动WOZ系统后端"""
    try:
        print("Starting WOZ System Backend...")
        print("=" * 50)
        
        # 导入并运行服务器
        from woz_system_backend import run_server, API_HOST, API_PORT
        
        print(f"Server will start on http://{API_HOST}:{API_PORT}")
        print(f"API documentation available at http://{API_HOST}:{API_PORT}/docs")
        print("Press Ctrl+C to stop the server")
        print("=" * 50)
        
        run_server()
        
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Failed to start server: {e}")
        logging.exception("Server startup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
