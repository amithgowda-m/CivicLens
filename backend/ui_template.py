def get_ui_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CivicLens — Civic Document Analysis</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #131b2e;
      --card-border: #1e293b;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 32px 16px;
    }
    .container { max-width: 1080px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--card-border);
    }
    .logo-area h1 { font-size: 24px; font-weight: 700; color: #fff; letter-spacing: -0.5px; }
    .logo-area p { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 9999px;
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
      border: 1px solid rgba(59, 130, 246, 0.3);
    }
    .upload-card {
      background: var(--card-bg);
      border: 2px dashed #334155;
      border-radius: 14px;
      padding: 36px 24px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-bottom: 28px;
    }
    .upload-card:hover, .upload-card.dragover {
      border-color: var(--accent);
      background: rgba(59, 130, 246, 0.05);
    }
    .upload-icon {
      font-size: 40px;
      margin-bottom: 12px;
    }
    .upload-card h3 { font-size: 17px; font-weight: 600; margin-bottom: 6px; }
    .upload-card p { font-size: 13px; color: var(--text-muted); }
    .file-input { display: none; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      background: var(--accent);
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn:hover { background: var(--accent-hover); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .sample-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 14px;
      justify-content: center;
      font-size: 13px;
      color: var(--text-muted);
    }
    .sample-btn {
      background: #1e293b;
      color: #cbd5e1;
      border: 1px solid #334155;
      padding: 4px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.15s;
    }
    .sample-btn:hover { background: #334155; color: #fff; }
    .loading-state {
      display: none;
      text-align: center;
      padding: 40px 20px;
    }
    .spinner {
      width: 38px;
      height: 38px;
      border: 3px solid rgba(255,255,255,0.1);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 16px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .results-area { display: none; }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 18px 20px;
      border-radius: 10px;
    }
    .stat-card .label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-card .value { font-size: 24px; font-weight: 700; margin-top: 6px; color: #fff; }
    .tabs {
      display: flex;
      gap: 10px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 20px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 10px 16px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      position: relative;
    }
    .tab-btn.active {
      color: var(--accent);
    }
    .tab-btn.active::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--accent);
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .clause-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 18px 20px;
      margin-bottom: 14px;
      transition: border 0.15s;
    }
    .clause-card:hover { border-color: #334155; }
    .clause-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .clause-badges { display: flex; gap: 8px; align-items: center; }
    .pill {
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
    }
    .pill-admitted { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .pill-pending { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .pill-rejected { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .pill-tag { background: #1e293b; color: #94a3b8; }
    .clause-text {
      font-size: 14px;
      line-height: 1.6;
      color: #e2e8f0;
      margin-bottom: 12px;
      padding: 10px 12px;
      background: #090d16;
      border-radius: 6px;
      border-left: 3px solid var(--accent);
      font-family: 'Inter', sans-serif;
    }
    .offset-meta {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #64748b;
    }
    .report-box {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 20px;
    }
    .report-box h3 { font-size: 16px; margin-bottom: 10px; color: #fff; }
    .report-box p { font-size: 14px; color: #cbd5e1; line-height: 1.6; }
    .impact-list { list-style: none; margin-top: 8px; }
    .impact-list li {
      position: relative;
      padding-left: 20px;
      font-size: 14px;
      color: #cbd5e1;
      margin-bottom: 8px;
      line-height: 1.5;
    }
    .impact-list li::before {
      content: '•';
      position: absolute;
      left: 6px;
      color: var(--accent);
      font-weight: bold;
    }
    .code-block {
      background: #090d16;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #38bdf8;
      overflow-x: auto;
      max-height: 500px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <h1>CivicLens</h1>
        <p>Municipal Document Ingestion & Zero-Hallucination Verification</p>
      </div>
      <div>
        <a href="/docs" target="_blank" class="badge" style="text-decoration:none; margin-right:8px;">FastAPI Swagger Docs &rarr;</a>
        <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3);">Pipeline Ready</span>
      </div>
    </header>

    <div class="upload-card" id="dropZone">
      <div class="upload-icon">&#128196;</div>
      <h3>Drag & Drop Municipal PDF Here</h3>
      <p>Or click to select a local PDF file to extract verbatim operative clauses and verify claims</p>
      <input type="file" id="fileInput" class="file-input" accept=".pdf">
      <div class="sample-bar">
        <span>Or analyze sample in repository:</span>
        <button class="sample-btn" onclick="analyzeSample('Act36of2025KA.pdf')">Act36of2025KA.pdf (GBGA 2024, 144p)</button>
        <button class="sample-btn" onclick="analyzeSample('sample_municipal_notice.pdf')">sample_municipal_notice.pdf (Ward 150)</button>
      </div>
    </div>

    <div class="loading-state" id="loadingState">
      <div class="spinner"></div>
      <h3 style="font-size: 16px; margin-bottom: 6px;">Analyzing Document...</h3>
      <p id="loadingMsg" style="font-size: 13px; color: var(--text-muted);">Parsing PDF pages, extracting verbatim clauses & running ensemble verification...</p>
    </div>

    <div class="results-area" id="resultsArea">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="label">Document File</div>
          <div class="value" id="resFilename" style="font-size: 18px; font-weight: 600; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">-</div>
        </div>
        <div class="stat-card">
          <div class="label">Pages Ingested</div>
          <div class="value" id="resPages">0</div>
        </div>
        <div class="stat-card">
          <div class="label">Operative Clauses</div>
          <div class="value" id="resClauses">0</div>
        </div>
        <div class="stat-card">
          <div class="label">Verified Claims</div>
          <div class="value" id="resVerified" style="color: #34d399;">0</div>
        </div>
      </div>

      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('tabClauses')">Verbatim Clauses & Verification</button>
        <button class="tab-btn" onclick="switchTab('tabReport')">Civic Impact Summary</button>
        <button class="tab-btn" onclick="switchTab('tabJson')">Raw Verification JSON</button>
      </div>

      <div class="tab-content active" id="tabClauses">
        <div id="clausesContainer"></div>
      </div>

      <div class="tab-content" id="tabReport">
        <div class="report-box">
          <h3>Policy Summary</h3>
          <p id="reportSummary">-</p>
        </div>
        <div class="report-box">
          <h3>Overall Policy Verdict</h3>
          <p id="reportVerdict" style="font-weight: 700; font-size: 16px;">-</p>
        </div>
        <div class="report-box">
          <h3>Stakeholders Impacted</h3>
          <ul class="impact-list" id="reportStakeholders"></ul>
        </div>
        <div class="report-box">
          <h3>Positive Impacts</h3>
          <ul class="impact-list" id="reportPositives"></ul>
        </div>
        <div class="report-box">
          <h3>Negative / Restrictive Impacts</h3>
          <ul class="impact-list" id="reportNegatives"></ul>
        </div>
        <div class="report-box">
          <h3>Identified Risk Flags</h3>
          <ul class="impact-list" id="reportRisks"></ul>
        </div>
      </div>

      <div class="tab-content" id="tabJson">
        <pre class="code-block" id="rawJson"></pre>
      </div>
    </div>
  </div>

  <script>
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const loadingState = document.getElementById('loadingState');
    const resultsArea = document.getElementById('resultsArea');

    dropZone.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      fileInput.click();
    });

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files.length) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) {
        uploadFile(e.target.files[0]);
      }
    });

    async function uploadFile(file) {
      const formData = new FormData();
      formData.append('file', file);
      runAnalysis('/api/documents/upload?analyze=true', formData);
    }

    async function analyzeSample(sampleName) {
      const formData = new FormData();
      formData.append('sample_name', sampleName);
      runAnalysis('/api/documents/upload?analyze=true', formData);
    }

    async function runAnalysis(url, formData) {
      loadingState.style.display = 'block';
      resultsArea.style.display = 'none';

      try {
        const res = await fetch(url, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Failed to analyze document: ' + res.statusText);
        const data = await res.json();
        renderResults(data);
      } catch (err) {
        alert('Error: ' + err.message);
      } finally {
        loadingState.style.display = 'none';
      }
    }

    function renderResults(data) {
      resultsArea.style.display = 'block';
      document.getElementById('resFilename').textContent = data.filename || 'Uploaded Document';
      document.getElementById('resPages').textContent = data.pages_count || 1;
      document.getElementById('resClauses').textContent = (data.raw_clauses || []).length;
      document.getElementById('resVerified').textContent = (data.verified_claims || []).length;

      // Render clauses
      const container = document.getElementById('clausesContainer');
      container.innerHTML = '';

      (data.verified_claims || []).forEach((item, idx) => {
        const clause = item.clause || {};
        const status = item.status || 'ADMITTED';
        const pillClass = status === 'ADMITTED' ? 'pill-admitted' : (status === 'PENDING_AUDIT' ? 'pill-pending' : 'pill-rejected');

        const card = document.createElement('div');
        card.className = 'clause-card';
        card.innerHTML = `
          <div class="clause-header">
            <div class="clause-badges">
              <span class="pill ${pillClass}">[${idx+1}] ${status}</span>
              <span class="pill pill-tag">Typology: ${clause.typology || 'Unclassified'}</span>
              ${clause.ward ? `<span class="pill pill-tag">Ward: ${clause.ward}</span>` : ''}
            </div>
            <div class="offset-meta">Page ${clause.page} | Offsets [${clause.char_start}:${clause.char_end}]</div>
          </div>
          <div class="clause-text">"${clause.text}"</div>
          <div class="offset-meta" style="color: #94a3b8;">
            Ensemble Gate: NLI Entailment = <strong>${item.nli_score ?? 'N/A'}</strong> | LLM-Judge = <strong>${item.llm_judge_verdict || 'yes'} (${item.llm_judge_score ?? 'N/A'})</strong>
          </div>
        `;
        container.appendChild(card);
      });

      // Render Report
      const rep = data.report || {};
      document.getElementById('reportSummary').textContent = rep.policy_summary || 'No policy summary available.';
      document.getElementById('reportVerdict').textContent = (rep.overall_verdict || 'MIXED').toUpperCase();

      renderList('reportStakeholders', rep.stakeholders_impacted || []);
      renderList('reportPositives', rep.positive_impacts || []);
      renderList('reportNegatives', rep.negative_impacts || []);
      renderList('reportRisks', rep.risk_flags || []);

      // Raw JSON
      document.getElementById('rawJson').textContent = JSON.stringify(data, null, 2);
    }

    function renderList(elementId, items) {
      const el = document.getElementById(elementId);
      el.innerHTML = '';
      if (!items || !items.length) {
        el.innerHTML = '<li style="color: #64748b;">None specified.</li>';
        return;
      }
      items.forEach(it => {
        const li = document.createElement('li');
        li.textContent = it;
        el.appendChild(li);
      });
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.target.classList.add('active');
    }
  </script>
</body>
</html>
"""
