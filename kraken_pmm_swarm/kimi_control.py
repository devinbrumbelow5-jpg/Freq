from database import FreqDB
import json
import os

class KimiControl:
    def __init__(self):
        self.db = FreqDB()
        self.config_path = "kraken_pmm_swarm/kimi_config.json"

    def load_config(self):
        if not os.path.exists(self.config_path):
            default = {"pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT"], "risk_level": 1.0, "max_drawdown": 5.0}
            with open(self.config_path, "w") as f:
                json.dump(default, f, indent=2)
        with open(self.config_path) as f:
            return json.load(f)

    def save_config(self, config):
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
        print("✅ Kimi config updated - swarm will respect new settings on next cycle")

    def get_status(self):
        positions = self.db.get_active_positions()
        total_pnl = sum(p['unrealized_pnl'] or 0 for p in positions)
        return {
            "active_bots": len(positions),
            "total_unrealized_pnl": round(total_pnl, 4),
            "positions": positions
        }
