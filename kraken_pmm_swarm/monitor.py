#!/usr/bin/env python3
"""
PMM Swarm Autonomous Monitor - CENTRAL TIME (CDT/CST)
Handles stale detection, auto-restart, and health checks
All timestamps in America/Chicago (Central Time)
"""

import sqlite3
import subprocess
import time
import signal
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Force Central Time for entire process
os.environ['TZ'] = 'America/Chicago'
time.tzset()

DB_PATH = Path(__file__).parent / "coinbase_swarm.db"
LOG_DIR = Path(__file__).parent / "logs"
PID_FILE = Path(__file__).parent / "swarm.pid"

class PMMMonitor:
    def __init__(self):
        self.running = True
        self.tz = 'America/Chicago'
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
    
    def _shutdown(self, signum, frame):
        print("Monitor shutting down...")
        self.running = False
    
    def now(self):
        """Get current time in Central Time."""
        return datetime.now()
    
    def format_time(self, dt):
        """Format datetime for display in CT."""
        if dt:
            return dt.strftime('%Y-%m-%d %H:%M:%S CDT')
        return 'N/A'
    
    def get_latest_fill_time(self):
        """Get timestamp of most recent fill."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.execute("SELECT filled_at FROM fills ORDER BY filled_at DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                # Parse ISO format timestamp (stored in UTC, convert to CT)
                dt = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                return dt
            return None
        except Exception as e:
            print(f"[{self.now().strftime('%H:%M:%S CT')}] DB error: {e}")
            return None
    
    def get_process_pid(self):
        """Get current swarm PID."""
        try:
            if PID_FILE.exists():
                return int(PID_FILE.read_text().strip())
        except:
            pass
        return None
    
    def is_process_running(self, pid):
        """Check if process is alive."""
        if not pid:
            return False
        try:
            subprocess.run(['kill', '-0', str(pid)], check=True, capture_output=True)
            return True
        except:
            return False
    
    def get_fill_stats(self, minutes=5):
        """Get fill count in last N minutes."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            # Convert CT to UTC for comparison (DB stores UTC)
            since = (self.now() - timedelta(minutes=minutes)).isoformat()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM fills WHERE filled_at > ?",
                (since,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"[{self.now().strftime('%H:%M:%S CT')}] Stats error: {e}")
            return 0
    
    def backup_database(self):
        """Create timestamped backup."""
        backup_path = DB_PATH.parent / f"backups/coinbase_swarm_{self.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path.parent.mkdir(exist_ok=True)
        try:
            conn = sqlite3.connect(str(DB_PATH))
            backup_conn = sqlite3.connect(str(backup_path))
            conn.backup(backup_conn)
            backup_conn.close()
            conn.close()
            print(f"[{self.now().strftime('%H:%M:%S CT')}] Backup created: {backup_path}")
            return True
        except Exception as e:
            print(f"[{self.now().strftime('%H:%M:%S CT')}] Backup failed: {e}")
            return False
    
    def restart_swarm(self):
        """Kill existing process and restart."""
        # Find and kill existing
        try:
            subprocess.run(['pkill', '-9', '-f', 'python.*main.py'], 
                         capture_output=True, timeout=5)
            time.sleep(2)
        except:
            pass
        
        # Backup before restart
        self.backup_database()
        
        # Start new instance
        log_file = LOG_DIR / f"coinbase_swarm_{self.now().strftime('%Y%m%d_%H%M%S')}.log"
        LOG_DIR.mkdir(exist_ok=True)
        
        try:
            proc = subprocess.Popen(
                [str(Path(__file__).parent / "venv/bin/python"), "main.py"],
                cwd=str(Path(__file__).parent),
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            
            # Write PID
            PID_FILE.write_text(str(proc.pid))
            
            print(f"[{self.now().strftime('%H:%M:%S CT')}] Swarm restarted: PID {proc.pid}, log {log_file}")
            return proc.pid
        except Exception as e:
            print(f"[{self.now().strftime('%H:%M:%S CT')}] Restart failed: {e}")
            return None
    
    def run(self):
        """Main monitoring loop."""
        print(f"[{self.now().strftime('%Y-%m-%d %H:%M:%S CT')}] PMM Monitor started")
        
        # Initial check
        if not self.is_process_running(self.get_process_pid()):
            print(f"[{self.now().strftime('%H:%M:%S CT')}] No running process found, starting swarm...")
            self.restart_swarm()
        
        while self.running:
            try:
                pid = self.get_process_pid()
                
                # Check process alive
                if not self.is_process_running(pid):
                    print(f"[{self.now().strftime('%H:%M:%S CT')}] Process down, restarting...")
                    self.restart_swarm()
                    time.sleep(10)
                    continue
                
                # Check fill activity (last 5 minutes)
                recent_fills = self.get_fill_stats(minutes=5)
                
                if recent_fills == 0:
                    # Check last fill time
                    last_fill = self.get_latest_fill_time()
                    if last_fill:
                        minutes_ago = (self.now() - last_fill.replace(tzinfo=None)).total_seconds() / 60
                        if minutes_ago > 10:
                            print(f"[{self.now().strftime('%H:%M:%S CT')}] STALE: No fills in {minutes_ago:.1f} minutes, restarting...")
                            self.restart_swarm()
                            time.sleep(10)
                            continue
                
                # Status output (Central Time)
                last = self.get_latest_fill_time()
                last_str = last.strftime('%H:%M:%S') if last else 'N/A'
                print(f"[{self.now().strftime('%H:%M:%S CT')}] PID {pid} | Last fill: {last_str} CT | Recent: {recent_fills}")
                
                time.sleep(30)
                
            except Exception as e:
                print(f"[{self.now().strftime('%H:%M:%S CT')}] Monitor error: {e}")
                time.sleep(30)

if __name__ == '__main__':
    monitor = PMMMonitor()
    monitor.run()
