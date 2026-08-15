/* ============================================================
   ResumeAI — script.js
   Complete front-end interaction layer for the AI Resume
   Screening & Job Recommendation System landing page.
   No jQuery. Modern ES6+. Vanilla JavaScript only.
   ============================================================ */

   (() => {
    'use strict';
  
    /* ============================================================
       0. GLOBAL STATE & CONSTANTS
       ============================================================ */
  
    const STATE = {
      isMobile: window.matchMedia('(max-width: 768px)').matches,
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      theme: localStorage.getItem('resumeai-theme') || 'dark',
      countersAnimated: false,
      dashboardAnimated: false,
      lastScrollY: 0,
      ticking: false,
    };
  
    const SELECTORS = {
      navbar: '#mainNavbar',
      navLinks: '.navbar-nav .nav-link',
      navbarCollapse: '#navbarNav',
      navbarToggler: '.navbar-toggler',
      heroHeading: '.hero-heading',
      heroButtons: '.hero-cta a.btn, .newsletter-btn, .contact-form button[type="submit"], .pricing-card a.btn',
      allButtons: '.btn-modern',
      statNumbers: '.stat-number',
      statsSection: '#statistics',
      featureCards: '.feature-card',
      dashboardStats: '.dashboard-stat',
      dashboardSection: '#dashboard-preview',
      dropZone: '#dropZone',
      fileInput: '#resumeFileInput',
      browseBtn: '#browseBtn',
      uploadProgress: '#uploadProgress',
      contactForm: '#contactForm',
      newsletterForm: '#newsletterForm',
      faqButtons: '.accordion-button',
      sections: 'section[id]',
      revealTargets: '.feature-card, .stat-card, .pricing-card, .testimonial-card, .dashboard-stat, .why-item, .step-item, .company-logo',
    };
  
    /* ============================================================
       1. UTILITIES
       ============================================================ */
  
    const qs = (sel, ctx = document) => ctx.querySelector(sel);
    const qsa = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
    const clamp = (num, min, max) => Math.min(Math.max(num, min), max);
    const debounce = (fn, delay = 150) => {
      let timer = null;
      return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
      };
    };
    const throttleRAF = (fn) => {
      let requested = false;
      return (...args) => {
        if (requested) return;
        requested = true;
        requestAnimationFrame(() => {
          fn(...args);
          requested = false;
        });
      };
    };
    const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
    const easeOutQuad = (t) => t * (2 - t);
    const randomBetween = (min, max) => Math.random() * (max - min) + min;
  
    const safeRun = (fn, label = 'script') => {
      try {
        fn();
      } catch (err) {
        console.error(`[ResumeAI] Error in ${label}:`, err);
      }
    };
  
    /* ============================================================
       2. DYNAMIC STYLE INJECTION
       For elements created purely in JS (loading screen, particles,
       cursor glow/trail, toast stack, back-to-top, scroll progress,
       theme toggle) that have no markup/CSS counterpart yet.
       ============================================================ */
  
    const injectDynamicStyles = () => {
      const style = document.createElement('style');
      style.id = 'resumeai-dynamic-styles';
      style.textContent = `
        #loadingScreen {
          position: fixed; inset: 0; z-index: 99999;
          display: flex; align-items: center; justify-content: center;
          background: var(--bg-primary, #050816);
          transition: opacity 0.6s ease, visibility 0.6s ease;
        }
        #loadingScreen.loaded { opacity: 0; visibility: hidden; pointer-events: none; }
        .loader-brain {
          width: 64px; height: 64px; border-radius: 50%;
          border: 3px solid rgba(99, 102, 241, 0.2);
          border-top-color: var(--color-primary-light, #6366F1);
          animation: resumeai-spin 0.9s linear infinite;
          position: relative;
        }
        .loader-brain::after {
          content: '\\f5dc'; font-family: 'Font Awesome 6 Free'; font-weight: 900;
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          font-size: 22px; color: var(--color-primary-light, #6366F1);
          animation: resumeai-pulse 1.2s ease-in-out infinite;
        }
        @keyframes resumeai-spin { to { transform: rotate(360deg); } }
        @keyframes resumeai-pulse { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }
  
        #particlesCanvas {
          position: fixed; inset: 0; width: 100%; height: 100%;
          z-index: 0; pointer-events: none; opacity: 0.6;
        }
        #cursorGlow {
          position: fixed; top: 0; left: 0; width: 380px; height: 380px;
          border-radius: 50%; pointer-events: none; z-index: 1;
          background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.06) 40%, transparent 70%);
          transform: translate(-50%, -50%);
          transition: opacity 0.3s ease;
          will-change: transform;
        }
        .cursor-trail-dot {
          position: fixed; top: 0; left: 0; width: 6px; height: 6px;
          border-radius: 50%; background: var(--color-secondary-light, #22D3EE);
          pointer-events: none; z-index: 2; opacity: 0.7;
          transform: translate(-50%, -50%);
          will-change: transform, opacity;
        }
  
        #scrollProgressBar {
          position: fixed; top: 0; left: 0; height: 3px; width: 0%;
          background: var(--gradient-primary, linear-gradient(135deg,#4F46E5,#8B5CF6,#06B6D4));
          z-index: 10001; transition: width 0.1s ease-out;
        }
  
        #backToTopBtn {
          position: fixed; bottom: 28px; right: 28px; width: 48px; height: 48px;
          border-radius: 50%; border: none; cursor: pointer; z-index: 9998;
          background: var(--gradient-primary, linear-gradient(135deg,#4F46E5,#8B5CF6,#06B6D4));
          color: #fff; font-size: 18px; box-shadow: var(--shadow-lg, 0 8px 40px rgba(0,0,0,0.35));
          display: flex; align-items: center; justify-content: center;
          opacity: 0; visibility: hidden; transform: translateY(16px);
          transition: opacity 0.3s ease, transform 0.3s ease, visibility 0.3s ease;
        }
        #backToTopBtn.show { opacity: 1; visibility: visible; transform: translateY(0); }
        #backToTopBtn:hover { transform: translateY(-4px) scale(1.05); }
        #backToTopBtn:focus-visible { outline: 2px solid var(--color-secondary-light, #22D3EE); outline-offset: 3px; }
  
        #themeToggleBtn {
          position: fixed; bottom: 28px; right: 86px; width: 48px; height: 48px;
          border-radius: 50%; border: 1px solid rgba(255,255,255,0.12); cursor: pointer; z-index: 9998;
          background: var(--bg-card, rgba(15,23,42,0.6)); backdrop-filter: blur(10px);
          color: #fff; font-size: 17px; box-shadow: var(--shadow-md, 0 4px 20px rgba(0,0,0,0.25));
          display: flex; align-items: center; justify-content: center;
          transition: transform 0.3s ease, background 0.3s ease;
        }
        #themeToggleBtn:hover { transform: translateY(-4px) scale(1.05); }
        #themeToggleBtn:focus-visible { outline: 2px solid var(--color-secondary-light, #22D3EE); outline-offset: 3px; }
  
        body.light-mode {
          --bg-primary: #F5F7FB; --bg-secondary: #FFFFFF; --bg-tertiary: #EEF1F8;
          --bg-card: rgba(255,255,255,0.75); --bg-card-hover: rgba(255,255,255,0.92);
          --color-white: #101223; --color-gray: #47506B; --color-gray-light: #2A3150;
          --color-muted: #5B6480;
        }
        body.light-mode { background: var(--bg-primary) !important; color: #101223 !important; }
  
        #toastStack {
          position: fixed; top: 90px; right: 20px; z-index: 10002;
          display: flex; flex-direction: column; gap: 12px; max-width: 340px;
        }
        .resumeai-toast {
          display: flex; align-items: flex-start; gap: 12px;
          background: var(--bg-card, rgba(15,23,42,0.85)); backdrop-filter: blur(14px);
          border: 1px solid rgba(255,255,255,0.1); border-left: 4px solid var(--color-primary-light, #6366F1);
          border-radius: 12px; padding: 14px 16px; box-shadow: var(--shadow-lg, 0 8px 40px rgba(0,0,0,0.35));
          color: #fff; font-size: 0.9rem; transform: translateX(120%); opacity: 0;
          transition: transform 0.4s cubic-bezier(0.34,1.56,0.64,1), opacity 0.4s ease;
        }
        .resumeai-toast.show { transform: translateX(0); opacity: 1; }
        .resumeai-toast.success { border-left-color: var(--color-success, #10B981); }
        .resumeai-toast.error { border-left-color: var(--color-danger, #EF4444); }
        .resumeai-toast.info { border-left-color: var(--color-secondary, #06B6D4); }
        .resumeai-toast i.toast-icon { font-size: 1.1rem; margin-top: 2px; }
        .resumeai-toast.success i.toast-icon { color: var(--color-success, #10B981); }
        .resumeai-toast.error i.toast-icon { color: var(--color-danger, #EF4444); }
        .resumeai-toast.info i.toast-icon { color: var(--color-secondary, #06B6D4); }
        .resumeai-toast .toast-body { flex: 1; }
        .resumeai-toast .toast-title { font-weight: 600; margin-bottom: 2px; display: block; }
        .resumeai-toast .toast-close {
          background: none; border: none; color: rgba(255,255,255,0.5); cursor: pointer;
          font-size: 0.85rem; padding: 0; line-height: 1;
        }
        .resumeai-toast .toast-close:hover { color: #fff; }
  
        .ripple-effect {
          position: absolute; border-radius: 50%; pointer-events: none;
          background: rgba(255,255,255,0.5); transform: scale(0);
          animation: resumeai-ripple 0.6s linear;
        }
        @keyframes resumeai-ripple { to { transform: scale(3); opacity: 0; } }
        .btn-modern { position: relative; overflow: hidden; }
  
        .reveal-on-scroll {
          opacity: 0; transform: translateY(36px);
          transition: opacity 0.7s ease, transform 0.7s ease;
        }
        .reveal-on-scroll.revealed { opacity: 1; transform: translateY(0); }
  
        .feature-card.tilt-active { transition: transform 0.1s ease-out; will-change: transform; }
  
        .hero-typed-cursor {
          display: inline-block; width: 3px; margin-left: 2px;
          background: var(--color-secondary-light, #22D3EE);
          animation: resumeai-blink 0.8s step-end infinite;
        }
        @keyframes resumeai-blink { 50% { opacity: 0; } }
  
        .field-invalid { border-color: var(--color-danger, #EF4444) !important; box-shadow: 0 0 0 3px rgba(239,68,68,0.15) !important; }
        .field-error-msg { color: var(--color-danger, #EF4444); font-size: 0.8rem; margin-top: 4px; display: block; }
        .field-valid { border-color: var(--color-success, #10B981) !important; }
  
        .upload-zone.drag-over { border-color: var(--color-secondary-light, #22D3EE) !important; background: rgba(34,211,238,0.06) !important; transform: scale(1.01); }
        .upload-filename-chip {
          display: inline-flex; align-items: center; gap: 8px; margin-top: 14px;
          background: var(--bg-glass-strong, rgba(255,255,255,0.08)); padding: 8px 14px;
          border-radius: var(--radius-full, 9999px); font-size: 0.85rem;
        }
  
        .dashboard-stat h5, .stat-number { font-variant-numeric: tabular-nums; }
  
        @media (prefers-reduced-motion: reduce) {
          .reveal-on-scroll { transition: none !important; }
          #particlesCanvas, #cursorGlow, .cursor-trail-dot { display: none !important; }
        }
      `;
      document.head.appendChild(style);
    };
  
    /* ============================================================
       3. LOADING SCREEN
       ============================================================ */
  
    const initLoadingScreen = () => {
      const loader = document.createElement('div');
      loader.id = 'loadingScreen';
      loader.innerHTML = '<div class="loader-brain" aria-hidden="true"></div>';
      loader.setAttribute('role', 'status');
      loader.setAttribute('aria-label', 'Loading ResumeAI');
      document.body.prepend(loader);
  
      const hideLoader = () => {
        loader.classList.add('loaded');
        document.body.classList.add('page-ready');
        setTimeout(() => loader.remove(), 700);
      };
  
      if (document.readyState === 'complete') {
        setTimeout(hideLoader, 300);
      } else {
        window.addEventListener('load', () => setTimeout(hideLoader, 300));
        // Safety net in case 'load' never fires (broken external asset)
        setTimeout(hideLoader, 4000);
      }
    };
  
    /* ============================================================
       4. NAVBAR — sticky, scroll bg, active link, smooth scroll,
          mobile auto-close
       ============================================================ */
  
    const initNavbar = () => {
      const navbar = qs(SELECTORS.navbar);
      if (!navbar) return;
  
      const onScroll = throttleRAF(() => {
        if (window.scrollY > 40) {
          navbar.classList.add('scrolled');
        } else {
          navbar.classList.remove('scrolled');
        }
      });
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
  
      // Smooth scroll for in-page anchor links
      qsa('a[href^="#"]').forEach((link) => {
        link.addEventListener('click', (e) => {
          const targetId = link.getAttribute('href');
          if (!targetId || targetId === '#') return;
          const target = qs(targetId);
          if (!target) return;
          e.preventDefault();
          const offset = navbar.offsetHeight + 10;
          const top = target.getBoundingClientRect().top + window.scrollY - offset;
          window.scrollTo({ top, behavior: STATE.reducedMotion ? 'auto' : 'smooth' });
          history.pushState(null, '', targetId);
  
          // Auto-close mobile navbar collapse after clicking a link
          const collapseEl = qs(SELECTORS.navbarCollapse);
          if (collapseEl && collapseEl.classList.contains('show')) {
            if (window.bootstrap && window.bootstrap.Collapse) {
              window.bootstrap.Collapse.getOrCreateInstance(collapseEl).hide();
            } else {
              collapseEl.classList.remove('show');
            }
          }
        });
      });
  
      initActiveNavHighlight();
    };
  
    const initActiveNavHighlight = () => {
      const navLinks = qsa(SELECTORS.navLinks);
      const sections = qsa(SELECTORS.sections);
      if (!navLinks.length || !sections.length) return;
  
      const linkMap = new Map();
      navLinks.forEach((link) => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) linkMap.set(href.slice(1), link);
      });
  
      const setActive = (id) => {
        navLinks.forEach((l) => l.classList.remove('active'));
        const activeLink = linkMap.get(id);
        if (activeLink) activeLink.classList.add('active');
      };
  
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && linkMap.has(entry.target.id)) {
              setActive(entry.target.id);
            }
          });
        },
        { rootMargin: '-45% 0px -50% 0px', threshold: 0 }
      );
  
      sections.forEach((section) => {
        if (linkMap.has(section.id)) observer.observe(section);
      });
    };
  
    /* ============================================================
       5. HERO — typing animation, rotating words, ripple buttons
       ============================================================ */
  
    const initHeroTyping = () => {
      const heading = qs(SELECTORS.heroHeading);
      if (!heading) return;
  
      const gradientSpan = qs('.text-gradient', heading);
      if (!gradientSpan) return;
  
      const rotatingWords = [
        'Job Recommendations',
        'Candidate Matching',
        'Talent Discovery',
        'Hiring Decisions',
      ];
  
      const staticPrefixNode = heading.firstChild;
      const staticPrefix = staticPrefixNode ? staticPrefixNode.textContent : '';
  
      if (STATE.reducedMotion) {
        gradientSpan.textContent = rotatingWords[0];
        return;
      }
  
      let wordIndex = 0;
      let charIndex = 0;
      let isDeleting = false;
      const typeSpeed = 65;
      const deleteSpeed = 35;
      const holdDelay = 1800;
  
      gradientSpan.textContent = '';
      const cursor = document.createElement('span');
      cursor.className = 'hero-typed-cursor';
      cursor.style.height = '1em';
      gradientSpan.after(cursor);
  
      const tick = () => {
        const currentWord = rotatingWords[wordIndex];
  
        if (!isDeleting) {
          charIndex++;
          gradientSpan.textContent = currentWord.slice(0, charIndex);
          if (charIndex === currentWord.length) {
            isDeleting = true;
            setTimeout(tick, holdDelay);
            return;
          }
          setTimeout(tick, typeSpeed);
        } else {
          charIndex--;
          gradientSpan.textContent = currentWord.slice(0, charIndex);
          if (charIndex === 0) {
            isDeleting = false;
            wordIndex = (wordIndex + 1) % rotatingWords.length;
            setTimeout(tick, 400);
            return;
          }
          setTimeout(tick, deleteSpeed);
        }
      };
  
      setTimeout(tick, 600);
    };
  
    const initRippleButtons = () => {
      qsa(SELECTORS.allButtons).forEach((btn) => {
        btn.addEventListener('click', function (e) {
          const rect = this.getBoundingClientRect();
          const ripple = document.createElement('span');
          const size = Math.max(rect.width, rect.height);
          ripple.className = 'ripple-effect';
          ripple.style.width = ripple.style.height = `${size}px`;
          ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
          ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
          this.appendChild(ripple);
          setTimeout(() => ripple.remove(), 650);
        });
  
        // Click "press" animation
        btn.addEventListener('mousedown', function () {
          this.style.transform = 'scale(0.97)';
        });
        ['mouseup', 'mouseleave'].forEach((evt) => {
          btn.addEventListener(evt, function () {
            this.style.transform = '';
          });
        });
      });
    };
  
    /* ============================================================
       6. BACKGROUND EFFECTS — particles, cursor glow/trail,
          parallax, animated gradient
       ============================================================ */
  
    const initParticles = () => {
      if (STATE.reducedMotion) return;
  
      const canvas = document.createElement('canvas');
      canvas.id = 'particlesCanvas';
      document.body.prepend(canvas);
      const ctx = canvas.getContext('2d');
  
      let particles = [];
      const particleCount = STATE.isMobile ? 30 : 65;
  
      const resize = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
      };
  
      const colors = ['rgba(99,102,241,', 'rgba(139,92,246,', 'rgba(34,211,238,'];
  
      const createParticles = () => {
        particles = Array.from({ length: particleCount }, () => ({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          r: randomBetween(0.6, 2.2),
          vx: randomBetween(-0.15, 0.15),
          vy: randomBetween(-0.25, -0.05),
          alpha: randomBetween(0.2, 0.7),
          color: colors[Math.floor(Math.random() * colors.length)],
        }));
      };
  
      resize();
      createParticles();
      window.addEventListener('resize', debounce(() => {
        resize();
        createParticles();
      }, 250));
  
      const render = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach((p) => {
          p.x += p.vx;
          p.y += p.vy;
          if (p.y < -10) p.y = canvas.height + 10;
          if (p.x < -10) p.x = canvas.width + 10;
          if (p.x > canvas.width + 10) p.x = -10;
  
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = `${p.color}${p.alpha})`;
          ctx.fill();
        });
        requestAnimationFrame(render);
      };
      requestAnimationFrame(render);
    };
  
    const initCursorEffects = () => {
      if (STATE.reducedMotion || STATE.isMobile) return;
  
      const glow = document.createElement('div');
      glow.id = 'cursorGlow';
      document.body.appendChild(glow);
  
      let glowX = window.innerWidth / 2;
      let glowY = window.innerHeight / 2;
      let targetX = glowX;
      let targetY = glowY;
  
      const trailDots = [];
      const trailLength = 8;
      for (let i = 0; i < trailLength; i++) {
        const dot = document.createElement('div');
        dot.className = 'cursor-trail-dot';
        dot.style.opacity = `${1 - i / trailLength}`;
        document.body.appendChild(dot);
        trailDots.push({ el: dot, x: targetX, y: targetY });
      }
  
      window.addEventListener('mousemove', (e) => {
        targetX = e.clientX;
        targetY = e.clientY;
      }, { passive: true });
  
      const animate = () => {
        glowX += (targetX - glowX) * 0.12;
        glowY += (targetY - glowY) * 0.12;
        glow.style.transform = `translate(${glowX}px, ${glowY}px) translate(-50%,-50%)`;
  
        let prevX = targetX;
        let prevY = targetY;
        trailDots.forEach((dot, i) => {
          dot.x += (prevX - dot.x) * 0.35;
          dot.y += (prevY - dot.y) * 0.35;
          dot.el.style.transform = `translate(${dot.x}px, ${dot.y}px) translate(-50%,-50%)`;
          prevX = dot.x;
          prevY = dot.y;
        });
  
        requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
  
      window.addEventListener('mouseleave', () => (glow.style.opacity = '0'));
      window.addEventListener('mouseenter', () => (glow.style.opacity = '1'));
    };
  
    const initParallax = () => {
      if (STATE.reducedMotion) return;
  
      const heroIllustration = qs('.hero-illustration-wrapper');
      const heroGradientBg = qs('.hero-bg-gradient');
      const floatingCards = qsa('.floating-card');
  
      const onScroll = throttleRAF(() => {
        const scrollY = window.scrollY;
        if (heroGradientBg) {
          heroGradientBg.style.transform = `translateY(${scrollY * 0.25}px)`;
        }
        if (heroIllustration && scrollY < window.innerHeight) {
          heroIllustration.style.transform = `translateY(${scrollY * 0.1}px)`;
        }
      });
      window.addEventListener('scroll', onScroll, { passive: true });
  
      // Mouse-driven parallax on hero + floating cards
      const heroSection = qs('.hero-section');
      if (heroSection && !STATE.isMobile) {
        heroSection.addEventListener('mousemove', (e) => {
          const { innerWidth, innerHeight } = window;
          const xRatio = (e.clientX - innerWidth / 2) / innerWidth;
          const yRatio = (e.clientY - innerHeight / 2) / innerHeight;
  
          if (heroIllustration) {
            heroIllustration.style.transform = `translate(${xRatio * 12}px, ${yRatio * 12}px)`;
          }
          floatingCards.forEach((card, i) => {
            const depth = (i + 1) * 6;
            card.style.transform = `translate(${xRatio * depth}px, ${yRatio * depth}px)`;
          });
        });
      }
    };
  
    /* ============================================================
       7. COUNTERS — animate stats when visible
       ============================================================ */
  
    const animateCounter = (el, duration = 2000) => {
      const target = parseInt(el.dataset.count || el.textContent, 10) || 0;
      const start = performance.now();
  
      const step = (now) => {
        const progress = clamp((now - start) / duration, 0, 1);
        const eased = easeOutCubic(progress);
        const value = Math.floor(eased * target);
        el.textContent = value.toLocaleString();
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          el.textContent = target.toLocaleString();
        }
      };
      requestAnimationFrame(step);
    };
  
    const initCounters = () => {
      const statsSection = qs(SELECTORS.statsSection);
      const numbers = qsa(SELECTORS.statNumbers);
      if (!statsSection || !numbers.length) return;
  
      const observer = new IntersectionObserver(
        (entries, obs) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && !STATE.countersAnimated) {
              STATE.countersAnimated = true;
              numbers.forEach((num) => animateCounter(num));
              obs.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.35 }
      );
      observer.observe(statsSection);
    };
  
    /* ============================================================
       8. FEATURE CARDS — tilt, glow, fade-in
       ============================================================ */
  
    const initFeatureCards = () => {
      const cards = qsa(SELECTORS.featureCards);
      if (!cards.length) return;
  
      cards.forEach((card) => {
        card.classList.add('reveal-on-scroll');
  
        if (STATE.reducedMotion || STATE.isMobile) return;
  
        card.classList.add('tilt-active');
  
        card.addEventListener('mousemove', (e) => {
          const rect = card.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;
          const rotateX = clamp(((y - rect.height / 2) / rect.height) * -8, -8, 8);
          const rotateY = clamp(((x - rect.width / 2) / rect.width) * 8, -8, 8);
          card.style.transform = `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px)`;
  
          card.style.setProperty('--glow-x', `${(x / rect.width) * 100}%`);
          card.style.setProperty('--glow-y', `${(y / rect.height) * 100}%`);
          card.style.background = `radial-gradient(circle at ${(x / rect.width) * 100}% ${(y / rect.height) * 100}%, rgba(99,102,241,0.16), var(--bg-card, rgba(15,23,42,0.6)) 60%)`;
        });
  
        card.addEventListener('mouseleave', () => {
          card.style.transform = 'perspective(900px) rotateX(0) rotateY(0) translateY(0)';
          card.style.background = '';
        });
      });
    };
  
    /* ============================================================
       9. REVEAL ON SCROLL / LAZY LOAD ANIMATIONS
       ============================================================ */
  
    const initScrollReveal = () => {
      const targets = qsa(SELECTORS.revealTargets);
      if (!targets.length) return;
  
      targets.forEach((el) => el.classList.add('reveal-on-scroll'));
  
      const observer = new IntersectionObserver(
        (entries, obs) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('revealed');
              obs.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15, rootMargin: '0px 0px -60px 0px' }
      );
      targets.forEach((el) => observer.observe(el));
  
      // Lazy-load any images marked with data-src
      const lazyImages = qsa('img[data-src]');
      if (lazyImages.length) {
        const imgObserver = new IntersectionObserver((entries, obs) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              const img = entry.target;
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
              obs.unobserve(img);
            }
          });
        }, { rootMargin: '150px' });
        lazyImages.forEach((img) => imgObserver.observe(img));
      }
    };
  
    /* ============================================================
       10. UPLOAD SECTION — Real fetch upload & Results rendering
       ============================================================ */
  
    // ---------------------------------------------------------------
    // Result persistence (survives an unexpected page reload)
    // ---------------------------------------------------------------
    // Some dev setups (e.g. VS Code Live Server) auto-reload the browser
    // whenever a file changes anywhere in the watched project folder --
    // including the resume file Flask just saved into uploads/. That
    // reload is triggered outside this page's own JS and can't be
    // prevented from here, so instead we make the result durable: save
    // it the instant it arrives, and re-display it automatically if the
    // page reloads right after a successful upload.
    const RESULT_STORAGE_KEY = 'resumeai_last_result';
  
    const saveLastResult = (data) => {
      try {
        sessionStorage.setItem(RESULT_STORAGE_KEY, JSON.stringify(data));
      } catch (err) {
        console.warn('[ResumeAI] Could not persist result to sessionStorage:', err);
      }
    };
  
    const loadLastResult = () => {
      try {
        const raw = sessionStorage.getItem(RESULT_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (err) {
        console.warn('[ResumeAI] Could not read persisted result:', err);
        return null;
      }
    };
  
    const renderResults = (data) => {
      const resultsSection = qs('#resultsSection');
      if (!resultsSection) return;
  
      // --- Extract details, matching the ACTUAL Flask /upload response shape ---
      // app.py returns applicant details nested under "applicant": { full_name, email, phone, ... }
      // and "feedback" as an OBJECT { strengths, weaknesses, suggestions }, not a flat array.
      // The fallbacks below keep this working even if the backend schema changes later.
      const applicantData = (data && typeof data.applicant === 'object' && data.applicant) || {};
  
      const name = applicantData.full_name || data.name || data.applicant_name || data.candidate_name || 'Candidate';
      const role = data.role || data.title || data.target_role || 'Job Applicant';
      const email = applicantData.email || data.email || 'N/A';
      const phone = applicantData.phone || data.phone || data.mobile || 'N/A';
      const experience = data.experience || data.total_experience || 'N/A';
  
      const score = data.ats_score ?? data.score ?? 0;
      const grade = data.grade || (score >= 80 ? 'A+' : score >= 70 ? 'B' : score >= 50 ? 'C' : 'D');
  
      const skills = Array.isArray(data.extracted_skills)
        ? data.extracted_skills
        : Array.isArray(data.skills)
        ? data.skills
        : [];
  
      // app.py's "feedback" is { strengths: [...], weaknesses: [...], suggestions: [...] }.
      // Flatten it into one bullet list, most actionable first, while still supporting a
      // plain array (older/alternate backend shape) or a top-level "suggestions" key.
      const feedbackObj = (data && typeof data.feedback === 'object' && !Array.isArray(data.feedback))
        ? data.feedback
        : {};
      const feedback = Array.isArray(data.feedback)
        ? data.feedback
        : [
            ...(Array.isArray(feedbackObj.suggestions) ? feedbackObj.suggestions : []),
            ...(Array.isArray(feedbackObj.weaknesses) ? feedbackObj.weaknesses : []),
            ...(Array.isArray(feedbackObj.strengths) ? feedbackObj.strengths : []),
            ...(Array.isArray(data.suggestions) ? data.suggestions : []),
          ];
  
      const jobs = Array.isArray(data.recommended_jobs)
        ? data.recommended_jobs
        : Array.isArray(data.jobs)
        ? data.jobs
        : [];
  
      // Update Applicant Profile UI
      const nameEl = qs('#applicantName');
      const roleEl = qs('#applicantRole');
      const emailEl = qs('#applicantEmail');
      const phoneEl = qs('#applicantPhone');
      const expEl = qs('#applicantExperience');
  
      if (nameEl) nameEl.textContent = name;
      if (roleEl) roleEl.textContent = role;
      if (emailEl) emailEl.textContent = email;
      if (phoneEl) phoneEl.textContent = phone;
      if (expEl) expEl.textContent = experience;
  
      // Update ATS Score UI
      const scoreEl = qs('#atsScoreValue');
      const progressBar = qs('#atsProgressBar');
      const badgeEl = qs('#atsGradeBadge');
  
      if (scoreEl) scoreEl.textContent = `${score}%`;
      if (badgeEl) badgeEl.textContent = `Grade: ${grade}`;
      if (progressBar) {
        progressBar.style.width = `${clamp(score, 0, 100)}%`;
        progressBar.setAttribute('aria-valuenow', String(score));
      }
  
      // Populate Skills
      const skillsContainer = qs('#skillsContainer');
      if (skillsContainer) {
        skillsContainer.innerHTML = '';
        if (skills.length > 0) {
          skills.forEach((skill) => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary bg-opacity-25 text-white border border-primary border-opacity-25 px-3 py-2 rounded-pill fs-6';
            badge.textContent = skill;
            skillsContainer.appendChild(badge);
          });
        } else {
          skillsContainer.innerHTML = '<span class="text-muted small">No skills extracted.</span>';
        }
      }
  
      // Populate Feedback
      const feedbackContainer = qs('#feedbackContainer');
      if (feedbackContainer) {
        feedbackContainer.innerHTML = '';
        if (feedback.length > 0) {
          feedback.forEach((item) => {
            const li = document.createElement('li');
            li.className = 'd-flex align-items-start gap-2 mb-2 text-muted';
            li.innerHTML = `<i class="fas fa-check-circle text-success mt-1"></i> <span>${item}</span>`;
            feedbackContainer.appendChild(li);
          });
        } else {
          feedbackContainer.innerHTML = '<li class="text-muted small">No feedback available.</li>';
        }
      }
  
      // Populate Recommended Jobs
      const jobsContainer = qs('#recommendedJobsContainer');
      if (jobsContainer) {
        jobsContainer.innerHTML = '';
        if (jobs.length > 0) {
          jobs.forEach((job) => {
            const jobTitle = typeof job === 'string' ? job : job.job_title || job.title || job.role || 'Position';
            const company = job.company || 'Top Employer';
            const location = job.location || 'Remote / Hybrid';
            const matchScore = job.match_score || job.match || score;
  
            const col = document.createElement('div');
            col.className = 'col-md-6 col-lg-4';
            col.innerHTML = `
              <div class="hover-card p-4 h-100 d-flex flex-column justify-content-between">
                <div>
                  <div class="d-flex justify-content-between align-items-start mb-2">
                    <h5 class="fw-semibold mb-0">${jobTitle}</h5>
                    <span class="badge bg-success bg-opacity-25 text-white border border-success border-opacity-25 rounded-pill">${matchScore}% Match</span>
                  </div>
                  <p class="text-muted small mb-3"><i class="fas fa-building me-1"></i>${company} &bull; <i class="fas fa-map-marker-alt me-1"></i>${location}</p>
                </div>
                <button class="btn btn-outline-primary btn-sm btn-modern w-100 mt-2">
                  <i class="fas fa-paper-plane me-2"></i>Apply Now
                </button>
              </div>
            `;
            jobsContainer.appendChild(col);
          });
        } else {
          jobsContainer.innerHTML = '<div class="col-12 text-muted small">No matching job recommendations found.</div>';
        }
      }
  
      // Unhide section & smooth scroll into view
      resultsSection.classList.remove('d-none');
      const offset = 80;
      const top = resultsSection.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: STATE.reducedMotion ? 'auto' : 'smooth' });
  
      // Re-trigger AOS animations for dynamically exposed cards
      if (window.AOS && typeof window.AOS.refresh === 'function') {
        window.AOS.refresh();
      }
    };
  
    const uploadFileToServer = async (file) => {
      const uploadProgress = qs(SELECTORS.uploadProgress);
      const progressBar = uploadProgress ? qs('.progress-bar', uploadProgress) : null;
      const statusText = uploadProgress ? qs('.upload-status', uploadProgress) : null;
  
      // --- Auth guard (Plan B: token-based auth, shared localStorage key with auth.js) ---
      // Resume upload is a protected endpoint on the backend (token_required).
      // Read the token directly from localStorage rather than depending on auth.js
      // having loaded first, so this check works regardless of script order.
      const authToken = localStorage.getItem('resumeai_token');
      if (!authToken) {
        showToast('error', 'Sign In Required', 'Please sign in to upload and analyze your resume.');
        setTimeout(() => {
          window.location.href = 'login.html';
        }, 1200);
        return;
      }
  
      if (uploadProgress) uploadProgress.classList.remove('d-none');
      if (progressBar) {
        progressBar.style.width = '30%';
        progressBar.setAttribute('aria-valuenow', '30');
      }
      if (statusText) statusText.textContent = 'Uploading resume...';
  
      const formData = new FormData();
      formData.append('file', file);
  
      try {
        if (progressBar) {
          progressBar.style.width = '60%';
          progressBar.setAttribute('aria-valuenow', '60');
        }
        if (statusText) statusText.textContent = 'Analyzing resume with AI...';
  
        const response = await fetch('http://127.0.0.1:5000/upload', {
          method: 'POST',
          headers: {
            // Token-based auth: no cookies/sessions involved, just this header.
            'Authorization': `Bearer ${authToken}`
          },
          body: formData,
        });
  
        if (response.status === 401) {
          // Token missing/expired/invalid server-side -- force a clean re-login
          // instead of showing a confusing generic error.
          localStorage.removeItem('resumeai_token');
          localStorage.removeItem('resumeai_user');
          if (uploadProgress) uploadProgress.classList.add('d-none');
          showToast('error', 'Session Expired', 'Please sign in again to continue.');
          setTimeout(() => {
            window.location.href = 'login.html';
          }, 1200);
          return;
        }
  
        // Always try to read the JSON body -- Flask's error handlers (400/404/413/500)
        // all return a JSON { success: false, message: '...' } payload, so we can show
        // the server's actual explanation instead of a generic status-code message.
        let data = null;
        try {
          data = await response.json();
        } catch (parseErr) {
          console.error('[ResumeAI] Response was not valid JSON:', parseErr);
        }
  
        if (!response.ok) {
          const serverMessage = data && data.message;
          const statusMessages = {
            400: 'The uploaded file could not be processed. Please check the format and try again.',
            404: 'The upload endpoint could not be found. Please contact support.',
            413: 'File is too large. Maximum allowed size is 10MB.',
            500: 'A server error occurred while analyzing your resume. Please try again shortly.',
          };
          throw new Error(
            serverMessage || statusMessages[response.status] || `Server returned status ${response.status}: ${response.statusText}`
          );
        }
  
        if (!data || data.success !== true) {
          throw new Error((data && data.message) || 'The server did not confirm the upload was successful.');
        }
  
        // Persist immediately -- BEFORE the render delay below -- so the result
        // survives even if something outside this page (e.g. a dev-server
        // live-reload watching the uploads/ folder) reloads the browser in
        // the next moment. See loadLastResult() in initUpload(), which
        // re-displays this automatically after such a reload.
        saveLastResult(data);
  
        if (progressBar) {
          progressBar.style.width = '100%';
          progressBar.setAttribute('aria-valuenow', '100');
        }
        if (statusText) statusText.textContent = 'Analysis complete!';
  
        showToast('success', 'Upload Successful', `${file.name} was analyzed successfully.`);
        
        if (uploadProgress) uploadProgress.classList.add('d-none');
        try {
          renderResults(data);
        } catch (renderErr) {
          // Never let a rendering bug silently leave the results section hidden --
          // surface it so it's obvious something needs fixing instead of looking
          // like the upload did nothing at all.
          console.error('[ResumeAI] Failed to render results:', renderErr);
          showToast('error', 'Display Error', 'Your resume was analyzed, but the results could not be displayed. Please refresh and try again.');
        }
  
      } catch (err) {
        console.error('[ResumeAI] Upload error:', err);
        if (uploadProgress) uploadProgress.classList.add('d-none');
        showToast('error', 'Upload Failed', err.message || 'Unable to connect to http://127.0.0.1:5000/upload.');
      }
    };
  
    const initUpload = () => {
      const dropZone = qs(SELECTORS.dropZone);
      const fileInput = qs(SELECTORS.fileInput);
      const browseBtn = qs(SELECTORS.browseBtn);
      if (!dropZone || !fileInput) return;
  
      const zoneInner = qs('.upload-zone-inner', dropZone);
  
      const ALLOWED_TYPES = ['.pdf', '.doc', '.docx', '.txt'];
      const ALLOWED_MIME = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
      ];
      const MAX_SIZE = 10 * 1024 * 1024; // 10MB
  
      const getExtension = (name) => {
        const idx = name.lastIndexOf('.');
        return idx >= 0 ? name.slice(idx).toLowerCase() : '';
      };
  
      const validateFile = (file) => {
        const ext = getExtension(file.name);
        if (!ALLOWED_TYPES.includes(ext) && !ALLOWED_MIME.includes(file.type)) {
          return { valid: false, reason: `Unsupported file type "${ext || 'unknown'}". Please upload PDF, DOC, DOCX, or TXT.` };
        }
        if (file.size > MAX_SIZE) {
          return { valid: false, reason: `File is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum size is 10MB.` };
        }
        return { valid: true };
      };
  
      const showFilenameChip = (file) => {
        let chip = qs('.upload-filename-chip', dropZone);
        if (!chip) {
          chip = document.createElement('div');
          chip.className = 'upload-filename-chip';
          zoneInner?.appendChild(chip);
        }
        const sizeKB = (file.size / 1024).toFixed(0);
        chip.innerHTML = `<i class="fas fa-file-alt"></i> <span>${file.name} · ${sizeKB} KB</span>`;
      };
  
      const handleFile = (file) => {
        if (!file) return;
        const result = validateFile(file);
        if (!result.valid) {
          showToast('error', 'Upload Failed', result.reason);
          dropZone.classList.add('drag-over');
          setTimeout(() => dropZone.classList.remove('drag-over'), 400);
          return;
        }
        showFilenameChip(file);
        uploadFileToServer(file);
      };
  
      browseBtn?.addEventListener('click', () => fileInput.click());
      dropZone.addEventListener('click', (e) => {
        if (e.target === browseBtn || browseBtn?.contains(e.target)) return;
        if (e.target.closest('.upload-filename-chip')) return;
        fileInput.click();
      });
  
      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) handleFile(fileInput.files[0]);
      });
  
      ['dragenter', 'dragover'].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropZone.classList.add('drag-over');
        });
      });
  
      ['dragleave', 'drop'].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (evt === 'dragleave' && e.target !== dropZone) return;
          dropZone.classList.remove('drag-over');
        });
      });
  
      dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer?.files?.[0];
        if (file) handleFile(file);
      });
  
      // Keyboard accessibility: Enter/Space triggers browse
      dropZone.setAttribute('tabindex', '0');
      dropZone.setAttribute('role', 'button');
      dropZone.setAttribute('aria-label', 'Upload your resume file');
      dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          fileInput.click();
        }
      });
    };
  
    /* ============================================================
       11. DASHBOARD PREVIEW — animate numbers & fade-in
       ============================================================ */
  
    const initDashboard = () => {
      const dashboardSection = qs(SELECTORS.dashboardSection);
      const statCards = qsa(SELECTORS.dashboardStats);
      if (!dashboardSection || !statCards.length) return;
  
      statCards.forEach((card) => card.classList.add('reveal-on-scroll'));
  
      const animateStatValue = (heading) => {
        const rawText = heading.textContent.trim();
        const match = rawText.match(/^([\d.]+)(.*)$/);
        if (!match) return;
  
        const targetValue = parseFloat(match[1]);
        const suffix = match[2] || '';
        const decimals = match[1].includes('.') ? match[1].split('.')[1].length : 0;
        const duration = 1500;
        const start = performance.now();
  
        const step = (now) => {
          const progress = clamp((now - start) / duration, 0, 1);
          const eased = easeOutQuad(progress);
          const value = (eased * targetValue).toFixed(decimals);
          heading.textContent = `${value}${suffix}`;
          if (progress < 1) requestAnimationFrame(step);
          else heading.textContent = `${targetValue.toFixed(decimals)}${suffix}`;
        };
        requestAnimationFrame(step);
      };
  
      // Simulated progress bars for each dashboard stat (visual flourish)
      const buildProgressBars = () => {
        statCards.forEach((card, i) => {
          if (qs('.dashboard-stat-progress', card)) return;
          const bar = document.createElement('div');
          bar.className = 'dashboard-stat-progress progress mt-2';
          bar.style.height = '4px';
          bar.style.background = 'rgba(255,255,255,0.08)';
          bar.style.borderRadius = '999px';
          bar.style.overflow = 'hidden';
          const fill = document.createElement('div');
          fill.style.height = '100%';
          fill.style.width = '0%';
          fill.style.background = 'var(--gradient-primary, linear-gradient(135deg,#4F46E5,#8B5CF6,#06B6D4))';
          fill.style.transition = 'width 1.4s ease-out';
          bar.appendChild(fill);
          const textWrap = qs('div:last-child', card);
          (textWrap || card).appendChild(bar);
          requestAnimationFrame(() => {
            setTimeout(() => {
              fill.style.width = `${70 + i * 10 > 100 ? 95 : 70 + i * 10}%`;
            }, 150);
          });
        });
      };
  
      const observer = new IntersectionObserver(
        (entries, obs) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && !STATE.dashboardAnimated) {
              STATE.dashboardAnimated = true;
              qsa('h5.fw-bold', dashboardSection).forEach(animateStatValue);
              buildProgressBars();
              obs.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.3 }
      );
      observer.observe(dashboardSection);
    };
  
    /* ============================================================
       12. FAQ ACCORDION — smooth rotation of icon
          (Bootstrap handles expand/collapse; we enhance the icon)
       ============================================================ */
  
    const initFaqAccordion = () => {
      const buttons = qsa(SELECTORS.faqButtons);
      if (!buttons.length) return;
  
      buttons.forEach((btn) => {
        btn.style.transition = 'color 0.3s ease';
        const icon = document.createElement('i');
        icon.className = 'fas fa-plus faq-toggle-icon';
        icon.style.marginLeft = 'auto';
        icon.style.transition = 'transform 0.35s ease';
        icon.style.flexShrink = '0';
        btn.style.display = 'flex';
        btn.style.alignItems = 'center';
        btn.style.gap = '12px';
  
        const textSpan = document.createElement('span');
        textSpan.textContent = btn.textContent.trim();
        textSpan.style.flex = '1';
        btn.textContent = '';
        btn.appendChild(textSpan);
        btn.appendChild(icon);
  
        const isExpanded = btn.getAttribute('aria-expanded') === 'true';
        icon.style.transform = isExpanded ? 'rotate(45deg)' : 'rotate(0deg)';
        if (isExpanded) icon.classList.replace('fa-plus', 'fa-minus');
  
        btn.addEventListener('click', () => {
          // Wait a tick for Bootstrap to toggle aria-expanded
          setTimeout(() => {
            const expanded = btn.getAttribute('aria-expanded') === 'true';
            icon.style.transform = expanded ? 'rotate(45deg)' : 'rotate(0deg)';
            icon.classList.toggle('fa-plus', !expanded);
            icon.classList.toggle('fa-minus', expanded);
          }, 10);
        });
      });
    };
  
    /* ============================================================
       13. CONTACT FORM — validation
       ============================================================ */
  
    const initContactForm = () => {
      const form = qs(SELECTORS.contactForm);
      if (!form) return;
  
      const nameInput = qs('#contactName', form);
      const emailInput = qs('#contactEmail', form);
      const phoneInput = qs('#contactPhone', form);
      const subjectInput = qs('#contactSubject', form);
      const messageInput = qs('#contactMessage', form);
  
      const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      const PHONE_RE = /^[+]?[\d\s()-]{7,20}$/;
  
      const setFieldState = (input, valid, message) => {
        let errorEl = input.parentElement.querySelector('.field-error-msg');
        if (!valid) {
          input.classList.add('field-invalid');
          input.classList.remove('field-valid');
          if (!errorEl) {
            errorEl = document.createElement('span');
            errorEl.className = 'field-error-msg';
            input.parentElement.appendChild(errorEl);
          }
          errorEl.textContent = message;
        } else {
          input.classList.remove('field-invalid');
          input.classList.add('field-valid');
          if (errorEl) errorEl.remove();
        }
      };
  
      const validateField = (input) => {
        if (!input) return true;
        const value = input.value.trim();
  
        if (input === nameInput) {
          const valid = value.length >= 2;
          setFieldState(input, valid, 'Please enter your full name (min. 2 characters).');
          return valid;
        }
        if (input === emailInput) {
          const valid = EMAIL_RE.test(value);
          setFieldState(input, valid, 'Please enter a valid email address.');
          return valid;
        }
        if (input === phoneInput) {
          if (value === '') {
            setFieldState(input, true, '');
            return true;
          }
          const valid = PHONE_RE.test(value);
          setFieldState(input, valid, 'Please enter a valid phone number.');
          return valid;
        }
        if (input === subjectInput) {
          const valid = value !== '';
          setFieldState(input, valid, 'Please select a subject.');
          return valid;
        }
        if (input === messageInput) {
          const valid = value.length >= 10;
          setFieldState(input, valid, 'Message should be at least 10 characters.');
          return valid;
        }
        return true;
      };
  
      [nameInput, emailInput, phoneInput, subjectInput, messageInput].forEach((input) => {
        if (!input) return;
        input.addEventListener('blur', () => validateField(input));
        input.addEventListener('input', () => {
          if (input.classList.contains('field-invalid')) validateField(input);
        });
      });
  
      form.addEventListener('submit', (e) => {
        e.preventDefault();
  
        const validations = [nameInput, emailInput, phoneInput, subjectInput, messageInput].map(validateField);
        const allValid = validations.every(Boolean);
  
        if (!allValid) {
          showToast('error', 'Form Incomplete', 'Please correct the highlighted fields and try again.');
          const firstInvalid = form.querySelector('.field-invalid');
          firstInvalid?.focus();
          return;
        }
  
        const submitBtn = qs('button[type="submit"]', form);
        const originalHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Sending...';
        }
  
        setTimeout(() => {
          showToast('success', 'Message Sent', "Thanks for reaching out — we'll get back to you within 24 hours.");
          form.reset();
          [nameInput, emailInput, phoneInput, subjectInput, messageInput].forEach((input) => {
            input?.classList.remove('field-valid', 'field-invalid');
          });
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
          }
        }, 1000);
      });
    };
  
    /* ============================================================
       14. NEWSLETTER FORM
       ============================================================ */
  
    const initNewsletterForm = () => {
      const form = qs(SELECTORS.newsletterForm);
      if (!form) return;
  
      const emailInput = qs('.newsletter-input', form);
      const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const value = emailInput ? emailInput.value.trim() : '';
  
        if (!EMAIL_RE.test(value)) {
          emailInput?.classList.add('field-invalid');
          showToast('error', 'Invalid Email', 'Please enter a valid email address to subscribe.');
          emailInput?.focus();
          return;
        }
  
        emailInput?.classList.remove('field-invalid');
        const submitBtn = qs('button[type="submit"]', form);
        const originalHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Subscribing...';
        }
  
        setTimeout(() => {
          showToast('success', 'Subscribed!', "You're on the list — welcome to the ResumeAI newsletter.");
          form.reset();
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
          }
        }, 800);
      });
    };
  
    /* ============================================================
       15. SCROLL — back to top, progress bar
       ============================================================ */
  
    const initScrollProgress = () => {
      const bar = document.createElement('div');
      bar.id = 'scrollProgressBar';
      document.body.appendChild(bar);
  
      const update = throttleRAF(() => {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const percent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        bar.style.width = `${clamp(percent, 0, 100)}%`;
      });
  
      window.addEventListener('scroll', update, { passive: true });
      window.addEventListener('resize', update, { passive: true });
      update();
    };
  
    const initBackToTop = () => {
      const btn = document.createElement('button');
      btn.id = 'backToTopBtn';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Back to top');
      btn.innerHTML = '<i class="fas fa-arrow-up" aria-hidden="true"></i>';
      document.body.appendChild(btn);
  
      const toggleVisibility = throttleRAF(() => {
        if (window.scrollY > 480) btn.classList.add('show');
        else btn.classList.remove('show');
      });
      window.addEventListener('scroll', toggleVisibility, { passive: true });
  
      btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: STATE.reducedMotion ? 'auto' : 'smooth' });
      });
  
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          btn.click();
        }
      });
    };
  
    /* ============================================================
       16. THEME TOGGLE — dark/light with localStorage
       ============================================================ */
  
    const initThemeToggle = () => {
      const btn = document.createElement('button');
      btn.id = 'themeToggleBtn';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Toggle dark and light mode');
  
      const applyTheme = (theme) => {
        document.body.classList.toggle('light-mode', theme === 'light');
        btn.innerHTML = theme === 'light'
          ? '<i class="fas fa-moon" aria-hidden="true"></i>'
          : '<i class="fas fa-sun" aria-hidden="true"></i>';
        btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
      };
  
      applyTheme(STATE.theme);
      document.body.appendChild(btn);
  
      btn.addEventListener('click', () => {
        STATE.theme = STATE.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('resumeai-theme', STATE.theme);
        applyTheme(STATE.theme);
        showToast('info', 'Theme Updated', `Switched to ${STATE.theme} mode.`);
      });
  
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          btn.click();
        }
      });
    };
  
    /* ============================================================
       17. TOAST NOTIFICATIONS
       ============================================================ */
  
    let toastStack = null;
  
    const getToastStack = () => {
      if (!toastStack) {
        toastStack = document.createElement('div');
        toastStack.id = 'toastStack';
        toastStack.setAttribute('aria-live', 'polite');
        document.body.appendChild(toastStack);
      }
      return toastStack;
    };
  
    const ICONS = {
      success: 'fa-circle-check',
      error: 'fa-circle-exclamation',
      info: 'fa-circle-info',
    };
  
    function showToast(type = 'info', title = '', message = '', duration = 4500) {
      const stack = getToastStack();
      const toast = document.createElement('div');
      toast.className = `resumeai-toast ${type}`;
      toast.setAttribute('role', 'alert');
      toast.innerHTML = `
        <i class="fas ${ICONS[type] || ICONS.info} toast-icon" aria-hidden="true"></i>
        <div class="toast-body">
          <span class="toast-title">${title}</span>
          <span class="toast-message">${message}</span>
        </div>
        <button type="button" class="toast-close" aria-label="Dismiss notification">
          <i class="fas fa-xmark"></i>
        </button>
      `;
      stack.appendChild(toast);
  
      requestAnimationFrame(() => toast.classList.add('show'));
  
      const remove = () => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
      };
  
      const timer = setTimeout(remove, duration);
      qs('.toast-close', toast).addEventListener('click', () => {
        clearTimeout(timer);
        remove();
      });
    }
  
    /* ============================================================
       18. FLOATING AI CARDS & FLOATING BACKGROUND ICONS
       ============================================================ */
  
    const initFloatingCards = () => {
      if (STATE.reducedMotion) return;
      const cards = qsa('.floating-card');
      cards.forEach((card, i) => {
        card.style.animation = `resumeai-float-${(i % 3) + 1} ${4 + i}s ease-in-out infinite`;
      });
  
      const floatKeyframes = document.createElement('style');
      floatKeyframes.textContent = `
        @keyframes resumeai-float-1 { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-14px); } }
        @keyframes resumeai-float-2 { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px) translateX(4px); } }
        @keyframes resumeai-float-3 { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-18px) translateX(-4px); } }
      `;
      document.head.appendChild(floatKeyframes);
    };
  
    const initFloatingBackgroundIcons = () => {
      if (STATE.reducedMotion || STATE.isMobile) return;
  
      const container = document.createElement('div');
      container.id = 'floatingIconsLayer';
      container.style.position = 'absolute';
      container.style.inset = '0';
      container.style.overflow = 'hidden';
      container.style.pointerEvents = 'none';
      container.style.zIndex = '0';
  
      const hero = qs('.hero-section');
      if (!hero) return;
      hero.style.position = hero.style.position || 'relative';
      hero.prepend(container);
  
      const icons = ['fa-file-alt', 'fa-briefcase', 'fa-user-tie', 'fa-chart-line', 'fa-brain', 'fa-magnifying-glass'];
      const count = 8;
  
      for (let i = 0; i < count; i++) {
        const icon = document.createElement('i');
        icon.className = `fas ${icons[i % icons.length]}`;
        icon.style.position = 'absolute';
        icon.style.left = `${randomBetween(5, 95)}%`;
        icon.style.top = `${randomBetween(5, 95)}%`;
        icon.style.fontSize = `${randomBetween(14, 28)}px`;
        icon.style.color = 'rgba(255,255,255,0.06)';
        icon.style.animation = `resumeai-float-${(i % 3) + 1} ${6 + i}s ease-in-out infinite`;
        icon.style.animationDelay = `${i * 0.4}s`;
        container.appendChild(icon);
      }
    };
  
    /* ============================================================
       19. KEYBOARD ACCESSIBILITY ENHANCEMENTS
       ============================================================ */
  
    const initAccessibility = () => {
      // Visible focus outline only for keyboard users
      let usingKeyboard = false;
      window.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          usingKeyboard = true;
          document.body.classList.add('user-is-tabbing');
        }
      });
      window.addEventListener('mousedown', () => {
        usingKeyboard = false;
        document.body.classList.remove('user-is-tabbing');
      });
  
      const kbdStyle = document.createElement('style');
      kbdStyle.textContent = `
        body:not(.user-is-tabbing) a:focus,
        body:not(.user-is-tabbing) button:focus,
        body:not(.user-is-tabbing) input:focus,
        body:not(.user-is-tabbing) textarea:focus,
        body:not(.user-is-tabbing) select:focus {
          outline: none;
        }
        body.user-is-tabbing a:focus,
        body.user-is-tabbing button:focus,
        body.user-is-tabbing input:focus,
        body.user-is-tabbing textarea:focus,
        body.user-is-tabbing select:focus {
          outline: 2px solid var(--color-secondary-light, #22D3EE) !important;
          outline-offset: 3px;
        }
      `;
      document.head.appendChild(kbdStyle);
  
      // Escape key closes mobile nav
      document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        const collapseEl = qs(SELECTORS.navbarCollapse);
        if (collapseEl && collapseEl.classList.contains('show')) {
          if (window.bootstrap && window.bootstrap.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(collapseEl).hide();
          } else {
            collapseEl.classList.remove('show');
          }
        }
      });
    };
  
    /* ============================================================
       20. GLOBAL ERROR HANDLING
       ============================================================ */
  
    const initErrorHandling = () => {
      window.addEventListener('error', (e) => {
        console.error('[ResumeAI] Uncaught error:', e.message, e.filename, e.lineno);
      });
      window.addEventListener('unhandledrejection', (e) => {
        console.error('[ResumeAI] Unhandled promise rejection:', e.reason);
      });
    };
  
    /* ============================================================
       21. PAGE TRANSITION (smooth fade on internal navigation)
       ============================================================ */
  
    const initPageTransition = () => {
      document.body.style.transition = STATE.reducedMotion ? 'none' : 'opacity 0.4s ease';
      document.body.style.opacity = '1';
    };
  
    /* ============================================================
       22. INIT — DOMContentLoaded entry point
       ============================================================ */
  
    const init = () => {
      safeRun(injectDynamicStyles, 'injectDynamicStyles');
      safeRun(initErrorHandling, 'initErrorHandling');
      safeRun(initLoadingScreen, 'initLoadingScreen');
      safeRun(initPageTransition, 'initPageTransition');
      safeRun(initNavbar, 'initNavbar');
      safeRun(initHeroTyping, 'initHeroTyping');
      safeRun(initRippleButtons, 'initRippleButtons');
      safeRun(initParticles, 'initParticles');
      safeRun(initCursorEffects, 'initCursorEffects');
      safeRun(initParallax, 'initParallax');
      safeRun(initCounters, 'initCounters');
      safeRun(initFeatureCards, 'initFeatureCards');
      safeRun(initScrollReveal, 'initScrollReveal');
      safeRun(initUpload, 'initUpload');
      safeRun(initDashboard, 'initDashboard');
      safeRun(initFaqAccordion, 'initFaqAccordion');
      safeRun(initContactForm, 'initContactForm');
      safeRun(initNewsletterForm, 'initNewsletterForm');
      safeRun(initScrollProgress, 'initScrollProgress');
      safeRun(initBackToTop, 'initBackToTop');
      safeRun(initThemeToggle, 'initThemeToggle');
      safeRun(initFloatingCards, 'initFloatingCards');
      safeRun(initFloatingBackgroundIcons, 'initFloatingBackgroundIcons');
      safeRun(initAccessibility, 'initAccessibility');
  
      // Re-init AOS if the library is present (loaded via CDN in index.html)
      if (window.AOS && typeof window.AOS.init === 'function') {
        window.AOS.init({ once: true, duration: 900, easing: 'ease-out-cubic' });
      }
    };
  
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  })();