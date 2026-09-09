"""Read-only kontrola konkrétního runtime; nevypisuje jiné env ani tajemství."""
import json
import sys

import psutil

process = psutil.Process(int(sys.argv[1]))
print(json.dumps({"pid": process.pid, "cwd": process.cwd(), "exe": process.exe(), "createTime": process.create_time(), "config": {key: value for key, value in process.environ().items() if key in {"OPORA_CANVAS_DATA", "OPORA_CANVAS_PORT"}}}, indent=2))
