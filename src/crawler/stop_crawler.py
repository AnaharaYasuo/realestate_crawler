import os
import signal
import sys

def stop_crawler():
    print("Creating stop.flag to signal crawler shutdown...")
    try:
        with open("stop.flag", "w") as f:
            f.write("STOP")
        print("stop.flag created. Crawlers checking this flag should exit shortly.")
    except Exception as e:
        print(f"Failed to create stop.flag: {e}")

    # Fallback: Robust killing for hanging processes
    print("\nSearching for hanging crawler processes to force kill...")
    myself = os.getpid()
    count = 0
    
    if not os.path.exists('/proc'):
        print("Not on a Linux system with /proc. Skipping force kill.")
        return

    # Iterate over pids in /proc (works in Debian-based Docker containers)
    for pid_str in os.listdir('/proc'):
        if not pid_str.isdigit():
            continue
            
        pid = int(pid_str)
        if pid == myself:
            continue
            
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                cmdline = f.read().decode('utf-8').replace('\0', ' ')
                
            # Target python processes running the crawler or reproduction scripts
            # We look for "main.py" or script names that imply crawler activity
            if 'python' in cmdline and ('src/crawler/main.py' in cmdline or 'reproduce' in cmdline):
                print(f"Force killing PID {pid}: {cmdline[:80]}...")
                os.kill(pid, signal.SIGKILL)
                count += 1
        except (ProcessLookupError, FileNotFoundError, PermissionError):
            continue
            
    if count > 0:
        print(f"Successfully killed {count} hanging processes.")
    else:
        print("No hanging crawler processes found.")

if __name__ == "__main__":
    stop_crawler()
