from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>BTC Automation Control Center</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
    tailwind.config = {
        darkMode: "class",
        theme: {
            extend: {
                colors: {
                    "surface-tint": "#00e38b", "inverse-on-surface": "#303033", "tertiary-container": "#ffd8b7", "on-error": "#690005", "primary-fixed": "#56ffa8", "surface-container-high": "#292a2c", "outline-variant": "#3b4a3f", "on-primary-fixed-variant": "#00522f", "tertiary": "#fffaff", "on-surface": "#e3e2e5", "on-primary-fixed": "#002110", "surface-container-lowest": "#0d0e10", "on-primary": "#00391f", "outline": "#849587", "error": "#ffb4ab", "primary-fixed-dim": "#00e38b", "error-container": "#93000a", "inverse-surface": "#e3e2e5", "inverse-primary": "#006d40", "secondary-container": "#fe6b00", "tertiary-fixed": "#ffdcbf", "on-tertiary-fixed-variant": "#6b3b00", "secondary-fixed-dim": "#ffb693", "on-secondary-fixed-variant": "#7a3000", "on-secondary-fixed": "#351000", "on-background": "#e3e2e5", "surface-dim": "#121315", "surface": "#121315", "on-primary-container": "#007143", "surface-bright": "#38393b", "on-tertiary": "#4b2800", "on-tertiary-fixed": "#2d1600", "background": "#121315", "secondary-fixed": "#ffdbcc", "surface-variant": "#343537", "on-secondary-container": "#572000", "on-surface-variant": "#b9cbbc", "surface-container-low": "#1b1c1e", "secondary": "#ffb693", "on-error-container": "#ffdad6", "surface-container-highest": "#343537", "on-tertiary-container": "#925300", "primary": "#f4fff3", "on-secondary": "#561f00", "primary-container": "#00ff9d", "tertiary-fixed-dim": "#ffb874", "surface-container": "#1f2022"
                },
                borderRadius: { "DEFAULT": "0.125rem", "lg": "0.25rem", "xl": "0.5rem", "full": "0.75rem" },
                spacing: { "sm": "8px", "gutter": "16px", "md": "16px", "margin": "24px", "xs": "4px", "unit": "4px", "xl": "40px", "lg": "24px" },
                fontFamily: { "label-caps": ["Inter"], "data-sm": ["JetBrains Mono"], "body-sm": ["Inter"], "headline-lg-mobile": ["Inter"], "body-lg": ["Inter"], "headline-md": ["Inter"], "data-lg": ["JetBrains Mono"], "headline-lg": ["Inter"] },
                fontSize: { "label-caps": ["11px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "700" }], "data-sm": ["12px", { "lineHeight": "16px", "fontWeight": "400" }], "body-sm": ["14px", { "lineHeight": "20px", "fontWeight": "400" }], "headline-lg-mobile": ["24px", { "lineHeight": "30px", "fontWeight": "700" }], "body-lg": ["16px", { "lineHeight": "24px", "fontWeight": "400" }], "headline-md": ["24px", { "lineHeight": "32px", "fontWeight": "600" }], "data-lg": ["18px", { "lineHeight": "24px", "fontWeight": "500" }], "headline-lg": ["32px", { "lineHeight": "40px", "letterSpacing": "-0.02em", "fontWeight": "700" }] }
            }
        }
    }
</script>
<style>
    .glass-card { background: rgba(27, 28, 30, 0.6); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.05), transparent); }
    .glow-active { box-shadow: 0 0 15px rgba(0, 255, 157, 0.2); }
    .pulse-dot { animation: pulse 2s infinite; }
    @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 157, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(0, 255, 157, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 157, 0); } }
    .terminal-bg { background-color: #000000; }
    .blink-cursor { animation: blink 1s step-end infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .profit-text { color: #00ff9d; }
    .loss-text { color: #ff4d4d; }
</style>
<script>setTimeout(function(){ location.reload(); }, 15000);</script> </head>
<body class="bg-background text-on-background min-h-screen flex flex-col font-body-sm selection:bg-primary-container selection:text-on-primary-container">
<header class="bg-surface/80 backdrop-blur-xl border-b border-white/10 shadow-sm flex justify-between items-center px-margin h-16 z-50 fixed top-0 w-full">
<div class="flex items-center gap-xs">
<span class="font-headline-md text-headline-md font-bold text-primary-container tracking-tight">BTC Automation Control Center</span>
</div>
<div class="flex items-center gap-md">
<div class="flex items-center gap-xs bg-surface-container-low px-sm py-xs rounded-full border border-white/5">
<div class="w-2 h-2 rounded-full bg-primary-container pulse-dot"></div>
<span class="font-label-caps text-label-caps text-on-surface-variant">Bot Status: 7/24 Active</span>
</div>
</div>
</header>
<div class="flex flex-1 pt-16">
<nav class="bg-surface-container-low/60 backdrop-blur-xl border-r border-white/10 flex flex-col pt-20 pb-8 px-4 fixed left-0 top-0 h-full w-64 hidden md:flex z-40">
<div class="mb-lg px-4">
<h2 class="font-body-lg text-body-lg text-on-surface font-semibold">Control Center</h2>
<p class="font-data-sm text-data-sm text-on-surface-variant">V3.0 - alpaca-py</p>
</div>
<ul class="flex flex-col gap-xs flex-1">
<li><a class="bg-primary-container/20 text-primary-container border-r-2 border-primary-container flex items-center gap-md px-4 py-sm rounded-l-lg" href="#"><span class="material-symbols-outlined">dashboard</span><span class="font-body-sm text-body-sm font-medium">Dashboard</span></a></li>
</ul>
</nav>
<main class="flex-1 p-margin md:ml-64 w-full md:w-auto overflow-y-auto pb-24 md:pb-margin">

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-margin">
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-32 glow-active relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-xl">account_balance_wallet</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Alpaca Balance</span></div>
    <div class="font-data-lg text-headline-lg-mobile md:text-headline-lg text-primary-container font-bold z-10">{{ status.balance }}</div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-32 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-xl">currency_bitcoin</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Live BTC Price</span></div>
    <div class="font-data-lg text-headline-lg-mobile md:text-headline-lg text-on-surface font-bold z-10">{{ status.btc_price }}</div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-32 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-xl">stacked_line_chart</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Current RSI (14)</span></div>
    <div class="font-data-lg text-headline-lg-mobile md:text-headline-lg text-cyan-400 font-bold z-10">{{ status.rsi }}</div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-32 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-xl">memory</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Bot State</span></div>
    <div class="font-data-lg text-headline-lg-mobile md:text-headline-lg text-secondary-container font-bold z-10 uppercase">{{ status.status }}</div>
    </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-margin">
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-24 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-sm">trending_up</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Total P&amp;L</span></div>
    <div class="font-data-lg text-headline-md font-bold z-10 {% if status.total_pnl.startswith('+') or status.total_pnl.startswith('$0') %}profit-text{% else %}loss-text{% endif %}">{{ status.total_pnl }}</div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-24 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-sm">checklist</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Win Rate</span></div>
    <div class="font-data-lg text-headline-md font-bold text-primary-container z-10">{{ status.win_rate }}</div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-24 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-sm">swap_horiz</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Total Trades</span></div>
    <div class="font-data-lg text-headline-md font-bold text-on-surface z-10">{{ status.total_trades }} <span class="font-body-sm text-on-surface-variant">({{ status.wins }}W / {{ status.losses }}L)</span></div>
    </div>
    <div class="glass-card rounded-xl p-md flex flex-col justify-between h-24 relative overflow-hidden group">
    <div class="flex items-center gap-sm text-on-surface-variant z-10"><span class="material-symbols-outlined text-sm">signal_cellular_alt</span><span class="font-label-caps text-label-caps uppercase tracking-wider">Last Signal</span></div>
    <div class="font-data-lg text-headline-md font-bold z-10 {% if status.last_signal == 'BUY' %}profit-text{% elif status.last_signal == 'SELL' %}loss-text{% else %}text-on-surface{% endif %}">{{ status.last_signal }}</div>
    </div>
</div>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-gutter mb-margin">
    <div class="glass-card rounded-xl border border-white/10 flex flex-col h-96">
    <div class="border-b border-white/10 px-md py-sm flex items-center justify-between bg-surface-container-low/50 rounded-t-xl">
    <div class="flex items-center gap-sm text-on-surface"><span class="material-symbols-outlined text-sm">terminal</span><span class="font-body-sm text-body-sm font-semibold">Recent Activities &amp; Logs</span></div>
    </div>
    <div class="flex-1 terminal-bg p-md overflow-y-auto font-data-sm text-data-sm rounded-b-xl border-t border-black">
    <div class="text-outline mb-xs">[SYS] Alpaca-py motoru baslatildi.</div>
    <div class="text-outline mb-xs">[DATA] BTC/USD 15m mumlari cekiliyor...</div>
    <div class="text-primary-container mb-xs">[CALC] RSI(14) + Bollinger + EMA + MACD hesaplandi.</div>
    <div class="{% if 'ALIM' in status.last_trade.reason or 'BUY' in status.last_trade.side %}text-primary-container{% elif 'SATIS' in status.last_trade.reason or 'SELL' in status.last_trade.side %}text-cyan-400{% else %}text-cyan-400{% endif %} mb-xs">&gt;&gt; {{ status.last_trade.time }} | {{ status.last_trade.side }} @ {{ status.last_trade.price }} | {{ status.last_trade.reason }}</div>
    {% for trade in status.trade_log[-8:-1] %}
    <div class="{% if trade.side == 'BUY' %}text-primary-container{% else %}text-cyan-400{% endif %} mb-xs opacity-70">[LOG] {{ trade.time }} | {{ trade.side }} @ {{ trade.price }} | {{ trade.reason }}</div>
    {% endfor %}
    <div class="text-outline mt-sm flex items-center"><span class="text-primary-container mr-sm">bot@control:~#</span><span class="text-on-surface">awaiting next tick<span class="inline-block w-2 h-4 bg-primary-container ml-xs blink-cursor align-middle"></span></span></div>
    </div>
    </div>

    <div class="glass-card rounded-xl border border-white/10 flex flex-col h-96">
    <div class="border-b border-white/10 px-md py-sm flex items-center justify-between bg-surface-container-low/50 rounded-t-xl">
    <div class="flex items-center gap-sm text-on-surface"><span class="material-symbols-outlined text-sm">info</span><span class="font-body-sm text-body-sm font-semibold">System Info &amp; Risk Status</span></div>
    </div>
    <div class="flex-1 p-md overflow-y-auto font-body-sm text-body-sm rounded-b-xl space-y-3">
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Connection</span>
            <span class="text-primary-container font-semibold">Alpaca API ✓</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">In Position</span>
            <span class="{% if status.in_position %}text-secondary-container{% else %}text-outline{% endif %} font-semibold">{{ status.in_position|string }}</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Entry Price</span>
            <span class="text-on-surface font-semibold">{{ status.entry_price }}</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Consecutive Losses</span>
            <span class="{% if status.consecutive_losses >= 2 %}loss-text{% else %}text-on-surface{% endif %} font-semibold">{{ status.consecutive_losses }}</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Cooldown Active</span>
            <span class="text-on-surface font-semibold">{{ status.cooldown }}</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Bot Running</span>
            <span class="{% if status.is_running %}text-primary-container{% else %}loss-text{% endif %} font-semibold">{{ status.is_running|string }}</span>
        </div>
        {% if status.last_error %}
        <div class="flex justify-between items-center py-2 border-b border-white/5">
            <span class="text-on-surface-variant">Last Error</span>
            <span class="loss-text font-semibold text-xs">{{ status.last_error }}</span>
        </div>
        {% endif %}
    </div>
    </div>
</div>

</main>
</div>
</body></html>"""


def create_app(engine):
    @app.route("/")
    def home():
        status = engine.get_status()
        return render_template_string(HTML_TEMPLATE, status=status)

    return app
