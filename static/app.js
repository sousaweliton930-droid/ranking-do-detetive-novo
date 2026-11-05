'use strict';
const canvas = document.getElementById('performance');
if (canvas) {
  const values = JSON.parse(document.getElementById('chart-data').textContent);
  const draw = () => {
    const width = canvas.clientWidth, height = 220, ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    let total = 0; const points = [0, ...values.map(v => total += v)];
    const min = Math.min(...points), max = Math.max(...points), range = max - min || 1;
    const y = v => 190 - (v - min) / range * 160;
    ctx.strokeStyle = '#2c2d2e'; ctx.lineWidth = 1;
    for (let i=0; i<4; i++) { const h = 30+i*53; ctx.beginPath(); ctx.moveTo(48,h); ctx.lineTo(width-12,h); ctx.stroke(); }
    ctx.fillStyle = '#97999d'; ctx.font = '11px Arial';
    ctx.fillText(max.toFixed(2)+' u',0,25); ctx.fillText(min.toFixed(2)+' u',0,205);
    ctx.strokeStyle = '#c39a6b'; ctx.lineWidth = 2; ctx.beginPath();
    points.forEach((v,i) => { const x=48+i/(points.length-1)*(width-60); if(i)ctx.lineTo(x,y(v));else ctx.moveTo(x,y(v)); }); ctx.stroke();
  };
  new ResizeObserver(draw).observe(canvas);
}
