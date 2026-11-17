"""公开目录采集演示。"""
import json
from .capture import read_catalog

def main():
    print(json.dumps(read_catalog('http://127.0.0.1:8765/'), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
