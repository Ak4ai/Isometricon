"""Helper client to communicate with Blender MCP server over TCP socket."""
import json
import socket
import sys

def send_blender_command(command_dict, host="127.0.0.1", port=9876, timeout=60.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    
    payload = json.dumps(command_dict).encode("utf-8")
    s.sendall(payload)
    
    chunks = []
    while True:
        try:
            chunk = s.recv(16384)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                full_data = b"".join(chunks).decode("utf-8")
                res = json.loads(full_data)
                s.close()
                return res
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        except socket.timeout:
            break
            
    s.close()
    full_data = b"".join(chunks).decode("utf-8", errors="replace")
    return json.loads(full_data) if full_data else {"status": "error", "message": "No data received"}

def execute_blender_code(code_str, host="127.0.0.1", port=9876, timeout=60.0):
    cmd = {
        "type": "execute_code",
        "params": {
            "code": code_str
        }
    }
    return send_blender_command(cmd, host=host, port=port, timeout=timeout)

def execute_blender_script_file(filepath, host="127.0.0.1", port=9876, timeout=60.0):
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    return execute_blender_code(code, host=host, port=port, timeout=timeout)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "ping":
            print(send_blender_command({"type": "ping"}))
        elif arg == "info":
            print(send_blender_command({"type": "get_scene_info"}))
        elif arg == "run" and len(sys.argv) > 2:
            res = execute_blender_script_file(sys.argv[2])
            print("RUN RESULT:", res)
