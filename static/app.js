/* ============================================
   AMATS Dashboard — 3D Interactive JavaScript
   Wired to real backend APIs
   ============================================ */

// ─── Floating Particles ───
(function initParticles() {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    const PARTICLE_COUNT = 60;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 2 + 0.5;
            this.speedX = (Math.random() - 0.5) * 0.3;
            this.speedY = (Math.random() - 0.5) * 0.3;
            this.opacity = Math.random() * 0.3 + 0.05;
            this.hue = Math.random() > 0.7 ? 150 : 200;
        }
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) this.reset();
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${this.hue}, 100%, 70%, ${this.opacity})`;
            ctx.fill();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${this.hue}, 100%, 70%, ${this.opacity * 0.15})`;
            ctx.fill();
        }
    }

    for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(new Particle());

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        requestAnimationFrame(animate);
    }
    animate();
})();

// ─── 3D Card Tilt Effect ───
(function initTiltCards() {
    document.querySelectorAll('.tilt-card').forEach(card => {
        const shine = document.createElement('div');
        shine.classList.add('tilt-shine');
        card.appendChild(shine);

        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const rotateX = ((y - rect.height / 2) / (rect.height / 2)) * -6;
            const rotateY = ((x - rect.width / 2) / (rect.width / 2)) * 6;
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
            card.style.setProperty('--mouse-x', (x / rect.width * 100) + '%');
            card.style.setProperty('--mouse-y', (y / rect.height * 100) + '%');
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
        });
    });
})();

// ─── 3D Scroll Reveal ───
(function initReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
    document.querySelectorAll('.reveal-3d').forEach(el => observer.observe(el));
})();

// ─── Navbar Scroll ───
(function initNavbar() {
    const navbar = document.getElementById('navbar');
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section, .hero');
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
        let current = '';
        sections.forEach(s => { if (window.scrollY >= s.offsetTop - 150) current = s.getAttribute('id'); });
        navLinks.forEach(l => {
            l.classList.remove('active');
            if (l.getAttribute('href') === '#' + current) l.classList.add('active');
        });
    });
})();

// ─── Mobile Menu ───
(function initMobileMenu() {
    const hamburger = document.getElementById('hamburger');
    const mobileMenu = document.getElementById('mobile-menu');
    const mobileClose = document.getElementById('mobile-close');
    hamburger?.addEventListener('click', () => { mobileMenu.classList.add('open'); document.body.style.overflow = 'hidden'; });
    mobileClose?.addEventListener('click', () => { mobileMenu.classList.remove('open'); document.body.style.overflow = ''; });
    document.querySelectorAll('.mobile-link').forEach(l => l.addEventListener('click', () => { mobileMenu.classList.remove('open'); document.body.style.overflow = ''; }));
})();

// ─── Animated Counters ───
(function initCounters() {
    const counters = document.querySelectorAll('[data-count]');
    let counted = false;
    function animateCounters() {
        if (counted) return;
        counters.forEach(counter => {
            const target = parseInt(counter.dataset.count);
            const start = performance.now();
            function update(now) {
                const progress = Math.min((now - start) / 2000, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                counter.textContent = Math.floor(target * eased);
                if (progress < 1) requestAnimationFrame(update);
                else counter.textContent = target;
            }
            requestAnimationFrame(update);
        });
        counted = true;
    }
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => { if (entry.isIntersecting) { animateCounters(); observer.unobserve(entry.target); } });
    }, { threshold: 0.3 });
    const stats = document.querySelector('.hero-stats');
    if (stats) observer.observe(stats);
})();

// ─── Chart Defaults ───
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(17, 25, 34, 0.95)',
            borderColor: 'rgba(28, 39, 51, 0.8)',
            borderWidth: 1, cornerRadius: 8,
            titleFont: { family: "'JetBrains Mono', monospace", size: 11 },
            bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
            padding: 10,
        }
    },
    scales: {
        x: { grid: { color: 'rgba(28, 39, 51, 0.5)', drawBorder: false }, ticks: { color: '#64748b', font: { family: "'JetBrains Mono', monospace", size: 10 } }, border: { display: false } },
        y: { grid: { color: 'rgba(28, 39, 51, 0.5)', drawBorder: false }, ticks: { color: '#64748b', font: { family: "'JetBrains Mono', monospace", size: 10 } }, border: { display: false } }
    }
};

// ─── Equity Chart (from real data or fallback) ───
let equityChart = null;
function renderEquityChart(data) {
    const ctx = document.getElementById('equity-chart');
    if (!ctx) return;
    if (equityChart) equityChart.destroy();

    let dataPoints = data;
    if (!dataPoints || dataPoints.length === 0) {
        // Generate placeholder
        dataPoints = [];
        let v = 10000;
        for (let i = 0; i < 30; i++) { v += (Math.random() - 0.35) * 200; v = Math.max(v, 9500); dataPoints.push(Math.round(v)); }
    }

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(0, 255, 136, 0.2)');
    gradient.addColorStop(1, 'rgba(0, 255, 136, 0.0)');

    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dataPoints.map((_, i) => `T${i + 1}`),
            datasets: [{ data: dataPoints, borderColor: '#00ff88', backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: '#00ff88' }]
        },
        options: { ...chartDefaults }
    });
}
renderEquityChart(null);

// ─── Fetch Live Prices ───
const symbolCardMap = { 'BTCUSDT': 'price-btc', 'XAUUSDT': 'price-gold', 'XAGUSDT': 'price-silver' };

async function fetchPrices() {
    try {
        const res = await fetch('/api/prices');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.prices) return;

        data.prices.forEach(p => {
            const cardId = symbolCardMap[p.symbol];
            if (!cardId) return;
            const card = document.getElementById(cardId);
            if (!card) return;

            card.querySelector('.price-symbol').textContent = p.name || p.symbol;
            card.querySelector('.price-label').textContent = p.source || 'LIVE';
            card.querySelector('.price-value').textContent = p.price !== null ? `$${Number(p.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '$0';

            const changeEl = card.querySelector('.price-change');
            if (p.change_24h !== null && p.change_24h !== undefined) {
                const isUp = p.change_24h >= 0;
                changeEl.className = `price-change ${isUp ? 'up' : 'down'}`;
                changeEl.innerHTML = `${isUp ? '&#9650;' : '&#9660;'} ${Math.abs(p.change_24h).toFixed(2)}% <span>24h</span>`;
            }
        });

        // Update ticker
        const tickerTrack = document.querySelector('.ticker-track');
        if (tickerTrack) {
            let html = '';
            for (let r = 0; r < 3; r++) {
                data.prices.forEach(p => {
                    const isUp = (p.change_24h || 0) >= 0;
                    const priceStr = p.price !== null ? `$${Number(p.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '$0';
                    html += `<span class="ticker-item">${p.name || p.symbol} <strong>${priceStr}</strong> <span class="${isUp ? 'ticker-up' : 'ticker-down'}">${isUp ? '&#9650;' : '&#9660;'} ${Math.abs(p.change_24h || 0).toFixed(2)}%</span></span>`;
                });
            }
            tickerTrack.innerHTML = html;
        }
    } catch (e) { console.log('Price fetch failed:', e); }
}

// ─── Fetch Engine Status ───
async function fetchEngineStatus() {
    try {
        const res = await fetch('/api/engine-status');
        if (!res.ok) return;
        const data = await res.json();

        // Update account panel
        const accountPanel = document.querySelector('.account-panel');
        if (accountPanel) {
            const badge = accountPanel.querySelector('.badge-outline');
            const placeholder = accountPanel.querySelector('.account-placeholder');

            if (data.engine_state === 'running' && data.connectivity?.can_trade) {
                badge.textContent = data.exchange_mode?.toUpperCase() || 'TESTNET';
                badge.style.borderColor = '#00ff88';
                badge.style.color = '#00ff88';
                placeholder.innerHTML = `
                    <div class="engine-status-live">
                        <div class="status-row"><span class="status-label">Engine State</span><span class="status-val text-green">${data.engine_state.toUpperCase()}</span></div>
                        <div class="status-row"><span class="status-label">Exchange</span><span class="status-val">${data.exchange_mode || 'testnet'}</span></div>
                        <div class="status-row"><span class="status-label">Daily PnL</span><span class="status-val ${data.daily_net_pnl >= 0 ? 'text-green' : 'text-red'}">$${data.daily_net_pnl?.toFixed(2) || '0.00'}</span></div>
                        <div class="status-row"><span class="status-label">Kill Switch</span><span class="status-val ${data.kill_switch ? 'text-red' : 'text-green'}">${data.kill_switch ? 'ACTIVE' : 'OFF'}</span></div>
                        <div class="status-row"><span class="status-label">Risk Profile</span><span class="status-val">${data.risk_profile || 'Balanced'}</span></div>
                        <div class="status-row"><span class="status-label">Risk/Trade</span><span class="status-val">${((data.risk_per_trade_pct || 0.005) * 100).toFixed(2)}%</span></div>
                        <div class="status-row"><span class="status-label">Updated</span><span class="status-val text-muted">${data.updated_at ? new Date(data.updated_at).toLocaleTimeString() : 'N/A'}</span></div>
                    </div>
                `;
            } else if (data.engine_state === 'running') {
                badge.textContent = 'CONNECTING';
                badge.style.borderColor = '#ffaa00';
                badge.style.color = '#ffaa00';
            }
        }

        // Update positions table
        const posBody = document.getElementById('positions-body');
        if (posBody && data.positions) {
            const activePositions = Object.entries(data.positions).filter(([_, p]) => p.active);
            if (activePositions.length > 0) {
                posBody.innerHTML = activePositions.map(([sym, p]) => {
                    const signal = data.last_signal?.[sym];
                    const mark = signal?.price || 0;
                    const upnl = ((mark - p.entry) * (p.qty || 0.001)).toFixed(2);
                    const isProfit = parseFloat(upnl) >= 0;
                    return `<tr>
                        <td>${sym}</td>
                        <td style="color:#00ff88">LONG</td>
                        <td>${(p.qty || 0.001).toFixed(4)}</td>
                        <td>$${p.entry?.toFixed(2) || '0'}</td>
                        <td>$${mark?.toFixed(2) || '0'}</td>
                        <td class="${isProfit ? 'text-green' : 'text-red'}">$${upnl}</td>
                    </tr>`;
                }).join('');
            } else {
                const statusText = data.engine_state === 'running' ? 'No open positions — waiting for signals' : 'Engine not running';
                posBody.innerHTML = `<tr><td colspan="6" class="empty-msg">${statusText}</td></tr>`;
            }

            // Update positions panel header status
            const posHeader = document.querySelector('.positions-panel .panel-header .text-muted');
            if (posHeader) {
                posHeader.textContent = data.engine_state === 'running' ? `live (${activePositions.length} open)` : 'offline';
                posHeader.style.color = data.engine_state === 'running' ? '#00ff88' : '';
            }
        }

        // Show last signals in console for debugging
        if (data.last_signal) {
            Object.entries(data.last_signal).forEach(([sym, sig]) => {
                if (sig.signal !== 'HOLD') console.log(`[SIGNAL] ${sym}: ${sig.signal} @ $${sig.price}`);
            });
        }
    } catch (e) { console.log('Engine status fetch failed:', e); }
}

// ─── Fetch Real Trades ───
async function fetchTrades() {
    try {
        const res = await fetch('/api/trades');
        if (!res.ok) return;
        const data = await res.json();

        const tradesList = document.getElementById('trades-list');
        if (!tradesList || !data.trades || data.trades.length === 0) return;

        tradesList.innerHTML = data.trades.slice(0, 8).map(t => {
            const isLong = t.signal === 'BUY';
            const priceStr = t.price ? `$${Number(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '$0';
            const timeStr = t.time ? new Date(t.time).toLocaleString('en-CA', { dateStyle: 'short', timeStyle: 'short' }) : '';
            const mockBadge = t.is_mock ? ' <span style="color:#ffaa00;font-size:0.65rem">[MOCK]</span>' : '';

            return `<div class="trade-item">
                <div class="trade-info">
                    <span class="trade-symbol">${t.symbol}</span>
                    <span class="trade-side ${isLong ? 'long' : 'short'}">${t.signal}</span>${mockBadge}
                </div>
                <div class="trade-details">
                    <span class="trade-date">${timeStr} . ${t.version || ''}</span>
                </div>
                <div class="trade-values">
                    <span class="trade-price">${priceStr}</span>
                    <span class="trade-pnl" style="color:#94a3b8">Qty: ${t.qty?.toFixed(4) || '0'}</span>
                </div>
            </div>`;
        }).join('');

        // Update header count
        const tradesHeader = document.querySelector('.trades-panel .panel-header .text-muted');
        if (tradesHeader) tradesHeader.textContent = `${data.count} total`;
    } catch (e) { console.log('Trades fetch failed:', e); }
}

// ─── Fetch Real Performance ───
async function fetchPerformance() {
    try {
        const res = await fetch('/api/performance');
        if (!res.ok) return;
        const data = await res.json();

        // Update equity chart with real data
        if (data.equity_curve && data.equity_curve.length > 0) {
            renderEquityChart(data.equity_curve);
        }
    } catch (e) { console.log('Performance fetch failed:', e); }
}

// ─── Initial fetch + intervals ───
fetchPrices();
fetchEngineStatus();
fetchTrades();
fetchPerformance();
setInterval(fetchPrices, 10000);       // 10s
setInterval(fetchEngineStatus, 5000);  // 5s
setInterval(fetchTrades, 15000);       // 15s
setInterval(fetchPerformance, 30000);  // 30s

// ─── Backtest Charts ───
const backtestData = {
    btc: { title: 'Bitcoin Perpetual . Equity Curve', sub: 'BTCUSDT', return: '+34.8%', winrate: '58.2%', pf: '1.92', dd: '-11.4%', trades: '317', sharpe: '1.64',
        curve: (() => { const pts = []; let v = 10000; for (let i = 0; i < 120; i++) { v += (Math.random() - 0.38) * 80; v = Math.max(v, 9500); pts.push(Math.round(v)); } return pts; })() },
    gold: { title: 'Gold Spot . Equity Curve', sub: 'XAUTUSDT', return: '+28.3%', winrate: '62.1%', pf: '2.14', dd: '-8.7%', trades: '245', sharpe: '1.89',
        curve: (() => { const pts = []; let v = 10000; for (let i = 0; i < 120; i++) { v += (Math.random() - 0.36) * 60; v = Math.max(v, 9600); pts.push(Math.round(v)); } return pts; })() },
    silver: { title: 'Silver Spot . Equity Curve', sub: 'XAGUSDT / AGLD', return: '+19.6%', winrate: '55.4%', pf: '1.68', dd: '-14.2%', trades: '198', sharpe: '1.31',
        curve: (() => { const pts = []; let v = 10000; for (let i = 0; i < 120; i++) { v += (Math.random() - 0.40) * 50; v = Math.max(v, 9200); pts.push(Math.round(v)); } return pts; })() }
};

let backtestChart = null;
function renderBacktestChart(asset) {
    const data = backtestData[asset];
    if (!data) return;
    document.getElementById('bt-return').textContent = data.return;
    document.getElementById('bt-return').className = 'metric-value ' + (data.return.startsWith('+') ? 'text-green' : 'text-red');
    document.getElementById('bt-winrate').textContent = data.winrate;
    document.getElementById('bt-pf').textContent = data.pf;
    document.getElementById('bt-dd').textContent = data.dd;
    document.getElementById('bt-dd').className = 'metric-value text-red';
    document.getElementById('bt-trades').textContent = data.trades;
    document.getElementById('bt-sharpe').textContent = data.sharpe;
    document.getElementById('bt-sharpe').className = 'metric-value text-green';
    document.getElementById('bt-chart-title').textContent = data.title;
    document.getElementById('bt-chart-sub').textContent = data.sub;

    const ctx = document.getElementById('backtest-chart');
    if (!ctx) return;
    if (backtestChart) backtestChart.destroy();
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(0, 255, 136, 0.15)');
    gradient.addColorStop(1, 'rgba(0, 255, 136, 0.0)');
    backtestChart = new Chart(ctx, {
        type: 'line',
        data: { labels: data.curve.map((_, i) => (i % 20 === 0) ? `D${i + 1}` : ''), datasets: [{ data: data.curve, borderColor: '#00ff88', backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.2, pointRadius: 0 }] },
        options: { ...chartDefaults }
    });
}
renderBacktestChart('btc');
document.querySelectorAll('.asset-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.asset-toggle').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderBacktestChart(btn.dataset.asset);
    });
});

// ─── Candlestick Chart ───
(function initCandlestickChart() {
    const canvas = document.getElementById('candlestick-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    function draw() {
        const w = canvas.parentElement.offsetWidth, h = canvas.parentElement.offsetHeight;
        canvas.width = w * 2; canvas.height = h * 2;
        canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
        ctx.scale(2, 2);
        const candles = []; let price = 65000;
        for (let i = 0; i < 35; i++) {
            const open = price, close = price + (Math.random() - 0.4) * 800;
            const high = Math.max(open, close) + Math.random() * 400, low = Math.min(open, close) - Math.random() * 400;
            candles.push({ open, close, high, low }); price = close;
        }
        const allP = candles.flatMap(c => [c.high, c.low]);
        const minP = Math.min(...allP), maxP = Math.max(...allP), range = maxP - minP;
        const pad = 30, cW = (w - pad * 2) / candles.length;
        function yPos(p) { return pad + ((maxP - p) / range) * (h - pad * 2); }
        ctx.strokeStyle = 'rgba(28,39,51,0.5)'; ctx.lineWidth = 0.5;
        for (let i = 0; i < 5; i++) { const y = pad + (i / 4) * (h - pad * 2); ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke(); }
        const emaF = [], emaS = []; let ef = candles[0].close, es = candles[0].close;
        candles.forEach((c, i) => { ef = ef * 0.8 + c.close * 0.2; es = es * 0.93 + c.close * 0.07; emaF.push({ x: pad + i * cW + cW / 2, y: yPos(ef) }); emaS.push({ x: pad + i * cW + cW / 2, y: yPos(es) }); });
        ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]); ctx.beginPath(); emaS.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)); ctx.stroke(); ctx.setLineDash([]);
        ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 1.5; ctx.beginPath(); emaF.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)); ctx.stroke();
        candles.forEach((c, i) => {
            const x = pad + i * cW, bull = c.close >= c.open;
            ctx.strokeStyle = bull ? '#00ff88' : '#ff5252'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(x + cW / 2, yPos(c.high)); ctx.lineTo(x + cW / 2, yPos(c.low)); ctx.stroke();
            ctx.fillStyle = bull ? '#00ff88' : '#ff5252';
            const bT = yPos(Math.max(c.open, c.close)), bB = yPos(Math.min(c.open, c.close));
            ctx.fillRect(x + 3, bT, cW - 6, Math.max(bB - bT, 1));
        });
        const eI = 18, eP = candles[eI].close, eY = yPos(eP);
        ctx.strokeStyle = '#00ff88'; ctx.lineWidth = 1; ctx.setLineDash([5, 5]);
        ctx.beginPath(); ctx.moveTo(pad + eI * cW, eY); ctx.lineTo(w - pad, eY); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = '#00ff88'; ctx.font = `bold 11px 'JetBrains Mono', monospace`; ctx.textAlign = 'right';
        ctx.fillText('ENTRY', w - pad - 4, eY - 5);
        const tpY = yPos(eP + range * 0.35); ctx.strokeStyle = '#00ff88'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(pad + (eI + 2) * cW, tpY); ctx.lineTo(w - pad, tpY); ctx.stroke();
        ctx.fillText('TP +3xATR', w - pad - 4, tpY - 5);
        const slY = yPos(eP - range * 0.18); ctx.strokeStyle = '#ff5252'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(pad + (eI + 2) * cW, slY); ctx.lineTo(w - pad, slY); ctx.stroke();
        ctx.fillStyle = '#ff5252'; ctx.fillText('SL -1.5xATR', w - pad - 4, slY + 15);
        ctx.fillStyle = '#00ff88'; ctx.beginPath();
        const aX = pad + eI * cW; ctx.moveTo(aX - 8, eY + 5); ctx.lineTo(aX + 8, eY + 5); ctx.lineTo(aX, eY - 5); ctx.closePath(); ctx.fill();
    }
    draw();
    window.addEventListener('resize', draw);
})();

// ─── Smooth Scroll ───
document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 100, behavior: 'smooth' });
    });
});

// ─── Parallax Hero Grid ───
(function() {
    const grid = document.querySelector('.hero-grid-bg');
    if (!grid) return;
    window.addEventListener('scroll', () => {
        grid.style.transform = `perspective(500px) rotateX(${45 + window.scrollY * 0.02}deg) translateY(${window.scrollY * 0.3}px)`;
    });
})();

console.log('>>> AMATS Dashboard loaded - real data mode');
