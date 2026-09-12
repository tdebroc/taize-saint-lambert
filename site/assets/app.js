// Scroll-reveal animations + subtle parallax halo
(function () {
  const reveals = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window && reveals.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    reveals.forEach((el, i) => {
      if (!el.style.getPropertyValue('--d')) {
        el.style.setProperty('--d', (i % 6) * 70 + 'ms');
      }
      io.observe(el);
    });
  } else {
    reveals.forEach((el) => el.classList.add('in'));
  }

  // Gentle parallax on the hero halo
  const halo = document.querySelector('.halo');
  if (halo && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.addEventListener('scroll', () => {
      const y = window.scrollY * 0.15;
      halo.style.transform = `translateX(-50%) translateY(${y}px)`;
    }, { passive: true });
  }

  // ---- Floating candlelight embers (canvas) ----
  const canvas = document.querySelector('.fx .embers');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (canvas && canvas.getContext && !reduce) {
    const ctx = canvas.getContext('2d');
    let W, H, DPR, particles;
    const COLORS = ['255,214,140', '255,176,84', '255,138,61', '255,238,200'];

    function resize() {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.width = Math.floor(innerWidth * DPR);
      H = canvas.height = Math.floor(innerHeight * DPR);
      canvas.style.width = innerWidth + 'px';
      canvas.style.height = innerHeight + 'px';
      const count = Math.round((innerWidth * innerHeight) / 26000);
      particles = Array.from({ length: Math.max(26, Math.min(70, count)) }, spawn);
    }
    function spawn() {
      return {
        x: Math.random() * W,
        y: Math.random() * H,
        r: (Math.random() * 2.4 + 0.8) * DPR,
        vy: -(Math.random() * 0.25 + 0.05) * DPR,
        vx: (Math.random() - 0.5) * 0.12 * DPR,
        c: COLORS[(Math.random() * COLORS.length) | 0],
        base: Math.random() * 0.4 + 0.25,
        ph: Math.random() * Math.PI * 2,
        sp: Math.random() * 0.03 + 0.012
      };
    }
    function frame(t) {
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter';
      for (const p of particles) {
        p.ph += p.sp;
        p.y += p.vy;
        p.x += p.vx + Math.sin(p.ph) * 0.15 * DPR;
        if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
        if (p.x < -10) p.x = W + 10; else if (p.x > W + 10) p.x = -10;
        const a = p.base * (0.55 + 0.45 * Math.sin(p.ph)); // twinkle
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
        g.addColorStop(0, `rgba(${p.c},${a})`);
        g.addColorStop(1, `rgba(${p.c},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
      requestAnimationFrame(frame);
    }
    addEventListener('resize', resize, { passive: true });
    resize();
    requestAnimationFrame(frame);
  }
})();
