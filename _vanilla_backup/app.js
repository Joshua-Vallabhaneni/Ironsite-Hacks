/* ============================================
   JARVIS – Personal AI Site Analysis
   Application Logic
   ============================================ */

(function () {
  'use strict';

  // ── DOM References ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const pageUpload = $('#page-upload');
  const pageDashboard = $('#page-dashboard');
  const dropZone = $('#drop-zone');
  const fileInput = $('#file-input');
  const fileInfo = $('#file-info');
  const btnAnalyze = $('#btn-analyze');
  const progressBar = $('#progress-bar');

  // ── Initialize Waveform Bars ──
  function createWaveformBars(container, count = 40) {
    for (let i = 0; i < count; i++) {
      const bar = document.createElement('div');
      bar.classList.add('bar');
      // Random max heights for wave variety
      const maxH = 8 + Math.random() * 24;
      bar.style.setProperty('--wave-h', maxH + 'px');
      bar.style.animationDelay = (Math.random() * 0.6) + 's';
      container.appendChild(bar);
    }
  }

  // Create waveforms on both pages
  createWaveformBars($('#upload-waveform'));
  createWaveformBars($('#dashboard-waveform'));

  // ── Waveform Randomizer ──
  // Periodically change the waveform bar heights for a more organic feel
  function randomizeWaveform(container) {
    const bars = container.querySelectorAll('.bar');
    bars.forEach(bar => {
      const maxH = 6 + Math.random() * 28;
      bar.style.setProperty('--wave-h', maxH + 'px');
    });
  }

  setInterval(() => {
    const wf1 = $('#upload-waveform');
    const wf2 = $('#dashboard-waveform');
    if (wf1 && wf1.classList.contains('active')) randomizeWaveform(wf1);
    if (wf2 && wf2.classList.contains('active')) randomizeWaveform(wf2);
  }, 800);

  // ── JARVIS State Manager ──
  function setJarvisState(page, state) {
    const orbId = page === 'upload' ? '#upload-orb' : '#dashboard-orb';
    const wfId = page === 'upload' ? '#upload-waveform' : '#dashboard-waveform';
    const statusId = page === 'upload' ? '#upload-status' : '#dashboard-status';

    const orb = $(orbId);
    const wf = $(wfId);
    const status = $(statusId);

    // Remove all states
    orb.classList.remove('speaking', 'listening', 'idle');
    wf.classList.remove('active', 'listening');
    status.classList.remove('speaking', 'listening', 'standby');

    if (state === 'speaking') {
      orb.classList.add('speaking');
      wf.classList.add('active');
      status.classList.add('speaking');
      status.innerHTML = '<span class="pulse-dot"></span> JARVIS IS SPEAKING...';
    } else if (state === 'listening') {
      orb.classList.add('listening');
      wf.classList.add('listening');
      status.classList.add('listening');
      status.innerHTML = '<span class="pulse-dot"></span> LISTENING...';
    } else {
      orb.classList.add('idle');
      status.classList.add('standby');
      status.innerHTML = '<span class="pulse-dot"></span> STANDBY';
    }
  }

  // ── Transcript Manager ──
  function addTranscript(containerId, text, sender = 'jarvis') {
    const container = $(containerId);
    const bubble = document.createElement('div');
    bubble.classList.add('transcript-bubble', sender);
    bubble.textContent = text;
    container.appendChild(bubble);

    // Keep only last 6 bubbles
    const bubbles = container.querySelectorAll('.transcript-bubble');
    if (bubbles.length > 6) {
      bubbles[0].remove();
    }

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
  }

  // ── Drop Zone Events ──
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFile(e.dataTransfer.files[0]);
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });

  function handleFile(file) {
    if (!file) return;

    // Show file info
    const name = file.name || 'headcam_2026-02-21.mp4';
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    $('#file-name').textContent = name;
    $('#file-size').textContent = sizeMB + ' MB';

    fileInfo.classList.add('visible');
    btnAnalyze.classList.add('visible');
    dropZone.style.display = 'none';

    addTranscript('#upload-transcript', 'File received: ' + name + '. Click "Begin Analysis" when ready.', 'jarvis');

    // Flash the orb
    setJarvisState('upload', 'speaking');
    setTimeout(() => setJarvisState('upload', 'idle'), 2000);
  }

  // ── Begin Analysis ──
  btnAnalyze.addEventListener('click', startProcessing);

  function startProcessing() {
    btnAnalyze.style.display = 'none';
    progressBar.classList.add('visible');
    setJarvisState('upload', 'speaking');

    const steps = [
      { step: 'upload', msg: 'Uploading footage... complete.', delay: 1200 },
      { step: 'process', msg: 'Running spatial depth analysis...', delay: 2000 },
      { step: 'analyze', msg: 'Tracking hand and tool interactions...', delay: 2500 },
      { step: 'report', msg: 'Generating your performance report...', delay: 2000 },
    ];

    let cumulative = 0;

    steps.forEach((s, i) => {
      cumulative += s.delay;
      setTimeout(() => {
        // Mark previous as done
        if (i > 0) {
          const prev = document.querySelector(`.progress-step[data-step="${steps[i - 1].step}"]`);
          prev.classList.remove('active');
          prev.classList.add('done');
          prev.querySelector('.step-dot').textContent = '✓';
        }
        // Mark current as active
        const current = document.querySelector(`.progress-step[data-step="${s.step}"]`);
        current.classList.add('active');

        addTranscript('#upload-transcript', s.msg, 'jarvis');
      }, cumulative);
    });

    // After all steps complete — transition to dashboard
    cumulative += 2000;
    setTimeout(() => {
      // Mark last step as done
      const last = document.querySelector(`.progress-step[data-step="report"]`);
      last.classList.remove('active');
      last.classList.add('done');
      last.querySelector('.step-dot').textContent = '✓';

      addTranscript('#upload-transcript', 'Analysis complete. Transitioning to your dashboard...', 'jarvis');

      setTimeout(() => {
        showDashboard();
      }, 1200);
    }, cumulative);
  }

  // ── Also allow entering dashboard without upload (for demo) ──
  // Double-click the JARVIS title to skip to dashboard
  document.querySelector('.upload-title')?.addEventListener('dblclick', () => {
    showDashboard();
  });

  function showDashboard() {
    pageUpload.style.display = 'none';
    pageDashboard.classList.add('active');
    setJarvisState('dashboard', 'speaking');

    // After 4 seconds, go to idle
    setTimeout(() => {
      setJarvisState('dashboard', 'idle');
    }, 4000);
  }

  // ── Tab Navigation ──
  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Deactivate all
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      $$('.tab-content').forEach(c => c.classList.remove('active'));

      // Activate clicked
      btn.classList.add('active');
      const tabId = 'tab-' + btn.dataset.tab;
      $(`#${tabId}`).classList.add('active');
    });
  });

  // ── Clickable Data Points → JARVIS Speaks ──
  function setupJarvisClickables() {
    const clickables = document.querySelectorAll('[data-jarvis]');
    clickables.forEach(el => {
      el.addEventListener('click', () => {
        const text = el.dataset.jarvis;
        if (!text) return;

        setJarvisState('dashboard', 'speaking');
        addTranscript('#dashboard-transcript', text, 'jarvis');

        // Return to idle after a delay proportional to text length
        const readTime = Math.max(3000, text.length * 30);
        setTimeout(() => {
          setJarvisState('dashboard', 'idle');
        }, readTime);
      });
    });
  }

  setupJarvisClickables();

  // ── Mic Button ──
  const micBtn = $('#mic-btn');
  if (micBtn) {
    let holding = false;

    micBtn.addEventListener('mousedown', () => {
      holding = true;
      micBtn.classList.add('active');
      setJarvisState('dashboard', 'listening');
    });

    micBtn.addEventListener('mouseup', () => {
      if (holding) {
        holding = false;
        micBtn.classList.remove('active');

        // Simulate user spoke
        addTranscript('#dashboard-transcript', 'Can you tell me more about the safety events?', 'user');

        setTimeout(() => {
          setJarvisState('dashboard', 'speaking');
          addTranscript('#dashboard-transcript',
            "Of course. Today I detected 2 near-miss events in the cutting zone. Both occurred when the blade guard wasn't properly positioned. I'd recommend a toolbox talk on guard protocols before tomorrow's shift.",
            'jarvis'
          );
          setTimeout(() => setJarvisState('dashboard', 'idle'), 5000);
        }, 1000);
      }
    });

    micBtn.addEventListener('mouseleave', () => {
      if (holding) {
        holding = false;
        micBtn.classList.remove('active');
        setJarvisState('dashboard', 'idle');
      }
    });
  }

  // ── Initial State: Speaking on upload page ──
  setJarvisState('upload', 'speaking');
  setTimeout(() => {
    setJarvisState('upload', 'idle');
  }, 5000);

})();
