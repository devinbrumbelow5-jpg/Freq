#!/usr/bin/env python3
import time
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

GREEN = '\033[92m'
RED = '\033[91m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'
CLEAR = '\033[2J\033[H'

TAKER_FEE = 0.0026
SLIPPAGE = 0.0005
SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

STARTING_BALANCE = 1000.0

def get_db_conn():
    """Connect to PostgreSQL database"""
    return psycopg2.connect(
        host="localhost",
        database="freqdb",
        user="frequser",
        password="freqpass"
    )

def color_pnl(value):
    return f"{GREEN}+${value:.4f}{RESET}" if value >= 0 else f"{RED}-${abs(value):.4f}{RESET}"

def color_balance(value, starting):
    if value >= starting:
        return f"{GREEN}${value:,.2f}{RESET}"
    else:
        return f"{RED}${value:,.2f}{RESET}"

def format_price(pair, price):
    if 'BTC' in pair:
        return f"${price:,.0f}"
    elif 'ETH' in pair:
        return f"${price:,.2f}"
    return f"${price:.4f}"

def get_data(spinner_idx):
    """Get data from PostgreSQL database"""
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get PnL from trades table
        cur.execute("SELECT COALESCE(SUM(pnl), 0) as total_pnl FROM trades")
        row = cur.fetchone()
        total_realized_pnl = float(row['total_pnl'] or 0)
        
        # Get PnL today only
        cur.execute("""
            SELECT COALESCE(SUM(pnl), 0) as today_pnl 
            FROM trades 
            WHERE timestamp >= CURRENT_DATE
        """)
        row = cur.fetchone()
        realized_today = float(row['today_pnl'] or 0)
        
        # Get active positions
        cur.execute("""
            SELECT bot_id, pair, side, qty, entry_price, current_price, unrealized_pnl
            FROM positions
            WHERE qty != 0
            ORDER BY ABS(qty * current_price) DESC
        """)
        
        positions = []
        total_position_value = 0.0
        total_unrealized = 0.0
        
        for row in cur.fetchall():
            bot_id = row['bot_id']
            pair = row['pair']
            side = row['side']
            qty = float(row['qty'] or 0)
            entry = float(row['entry_price'] or 0)
            current = float(row['current_price'] or 0)
            unrealized = float(row['unrealized_pnl'] or 0)
            
            positions.append({
                'bot_id': bot_id,
                'pair': pair,
                'side': side,
                'qty': qty,
                'entry': entry,
                'current': current,
                'unrealized': unrealized,
                'market_value': qty * current
            })
            
            total_position_value += qty * current
            total_unrealized += unrealized
        
        # Get trade count
        cur.execute("SELECT COUNT(*) as count FROM trades")
        total_fills = cur.fetchone()['count'] or 0
        
        cur.close()
        conn.close()
        
        # Calculate balance
        cash_balance = STARTING_BALANCE + total_realized_pnl
        total_equity = cash_balance + total_unrealized
        
        return {
            'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'spinner': SPINNER[spinner_idx % len(SPINNER)],
            'starting_balance': STARTING_BALANCE,
            'cash_balance': cash_balance,
            'total_equity': total_equity,
            'total_realized_pnl': total_realized_pnl,
            'active_bots': len(positions),
            'positions': positions,
            'total_position_market_value': total_position_value,
            'total_unrealized': total_unrealized,
            'realized_today': realized_today,
            'overall_today': realized_today + total_unrealized,
            'total_fills': total_fills
        }
    except Exception as e:
        import traceback
        return {
            'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'spinner': SPINNER[0],
            'starting_balance': STARTING_BALANCE,
            'cash_balance': STARTING_BALANCE,
            'total_equity': STARTING_BALANCE,
            'total_realized_pnl': 0,
            'active_bots': 0,
            'positions': [],
            'total_position_market_value': 0,
            'total_unrealized': 0,
            'realized_today': 0,
            'overall_today': 0,
            'total_fills': 0,
            'error': str(e) + "\n" + traceback.format_exc()
        }

def draw(data):
    lines = []
    lines.append(f"{CYAN}{BOLD}🚀 KRAKEN PMM SWARM — LIVE TERMINAL DASHBOARD{RESET}")
    lines.append(f"{CYAN}══════════════════════════════════════════════════════════════════════════{RESET}")
    lines.append(f"{CYAN}Press Ctrl+C to stop{RESET}")
    lines.append("")
    lines.append(f"{YELLOW}🕒 {data['spinner']} LIVE @ {data['now']} CDT{RESET}")
    lines.append("")
    
    # Account Overview
    lines.append(f"{CYAN}╔══════════════════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{CYAN}║{BOLD} ACCOUNT OVERVIEW{RESET}{' ' * 58}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"{CYAN}║{RESET}  Starting Balance:           {YELLOW}${data['starting_balance']:>14,.2f} USDC{RESET}{' ' * 18}{CYAN}║{RESET}")
    
    realized_str = color_pnl(data['total_realized_pnl'])
    lines.append(f"{CYAN}║{RESET}  Realized PnL:             {realized_str:>35}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Cash Available:             {YELLOW}${data['cash_balance']:>14,.2f} USDC{RESET}{' ' * 18}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════╣{RESET}")
    
    equity_str = color_balance(data['total_equity'], data['starting_balance'])
    lines.append(f"{CYAN}║{BOLD}{RESET}  TOTAL EQUITY:             {BOLD}{equity_str:>35}{RESET}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Active Positions:            {YELLOW}{data['active_bots']:>14}{RESET}{' ' * 22}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Total Trades:                {YELLOW}{data['total_fills']:>14,}{RESET}{' ' * 22}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")
    
    # P&L Overview
    lines.append(f"{CYAN}╔══════════════════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{CYAN}║{BOLD} P&L BREAKDOWN{RESET}{' ' * 52}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"{CYAN}║{RESET}  Realized Today:            {color_pnl(data['realized_today']):>35}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Unrealized PnL:           {color_pnl(data['total_unrealized']):>35}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Overall PnL Today:         {color_pnl(data['overall_today']):>35}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}║{RESET}  Total Realized (all):      {color_pnl(data['total_realized_pnl']):>35}{' ' * 6}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")
    
    # Positions Table
    pos_count = len(data['positions'])
    lines.append(f"{CYAN}╔══════════════════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{CYAN}║{BOLD} OPEN POSITIONS ({pos_count}){RESET}{' ' * (54 - len(str(pos_count)))}{CYAN}║{RESET}")
    lines.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"{CYAN}║{RESET} {'Symbol':<10} {'Side':<6} {'Qty':<12} {'Entry':<13} {'Current':<13} {'Unreal PnL':<15} {CYAN}║{RESET}")
    lines.append(f"{CYAN}╠══════════════════════════════════════════════════════════════════════════╣{RESET}")
    if data['positions']:
        for p in data['positions']:
            symbol = p['pair'][:9]
            side = p['side'][:5] if p['side'] else 'N/A'
            qty_str = f"{p['qty']:.5f}"
            entry_str = format_price(p['pair'], p['entry'])
            current_str = format_price(p['pair'], p['current'])
            unreal_str = color_pnl(p['unrealized'])
            lines.append(f"{CYAN}║{RESET} {symbol:<10} {side:<6} {qty_str:<12} {entry_str:<13} {current_str:<13} {unreal_str:<24} {CYAN}║{RESET}")
    else:
        lines.append(f"{CYAN}║{RESET}  (No open positions){' ' * 56}{CYAN}║{RESET}")
    
    rows_printed = len(data['positions']) if data['positions'] else 1
    for _ in range(6 - rows_printed):
        lines.append(f"{CYAN}║{RESET}{' ' * 76}{CYAN}║{RESET}")
    
    lines.append(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")
    lines.append(f"{YELLOW}💰 Fees: Taker {TAKER_FEE*100:.2f}% + Slippage {SLIPPAGE*100:.2f}% = 0.31% per leg{RESET}")
    lines.append(f"{YELLOW}⏱️  Next update in 2 seconds... (Press Ctrl+C to stop){RESET}")
    
    if 'error' in data:
        lines.append(f"{RED}⚠️  Error: {data['error'][:100]}{RESET}")
    
    return '\n'.join(lines)

def main():
    spinner_idx = 0
    try:
        while True:
            data = get_data(spinner_idx)
            output = draw(data)
            sys.stdout.write(CLEAR + output)
            sys.stdout.flush()
            spinner_idx += 1
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n\n{CYAN}{BOLD}👋 Dashboard stopped. Swarm continues running in background.{RESET}")
        print(f"{CYAN}══════════════════════════════════════════════════════════════════════════{RESET}\n")

if __name__ == "__main__":
    main()
