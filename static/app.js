/**
 * OWASP ASVS 5.0 (Chapter V1 Level 1) Self-Assessment Frontend Controller (`static/app.js`)
 *
 * Security & Accessibility Guarantees (ASVS V1 L1 + WCAG 2.2 AA):
 * - Zero usage of innerHTML, outerHTML, document.write, eval, or new Function.
 * - All DOM & SVG nodes are constructed via document.createElement / createElementNS
 *   and populated strictly via textContent.
 * - Full keyboard navigation for ARIA tabs (ArrowLeft / ArrowRight / Home / End) and dialogs.
 */

(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  const state = {
    activeRunId: null,
    eventSource: null,
    currentReport: null,
    runsList: [],
    zapStatus: null,
    aiStatus: null,
    aiConfigured: false,
    currentUser: null,
    selectiveRerunBaseRunId: null,
    selectiveRerunSelectedReqs: new Set(),
    selectiveRerunVerdicts: [],
  };

  // ===========================================================================
  // Safe DOM & SVG Helper Functions
  // ===========================================================================

  function clearChildren(node) {
    if (!node) return;
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (v === null || v === undefined) return;
        if (k === "className") {
          node.className = String(v);
        } else {
          node.setAttribute(k, String(v));
        }
      });
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function svgEl(tag, attrs, text) {
    const node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (v !== null && v !== undefined) {
          node.setAttribute(k, String(v));
        }
      });
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }


  function showAlert(message, isError) {
    const banner = document.getElementById("global-alert");
    if (!banner) return;
    banner.hidden = false;
    banner.textContent = message;
    banner.style.borderLeft = isError
      ? "4px solid var(--colorPaletteRedBorderActive)"
      : "4px solid var(--colorBrandStroke1)";
  }

  function showFormFeedback(message, isError) {
    const banner = document.getElementById("form-feedback-banner");
    if (!banner) return;
    if (!message) {
      banner.style.display = "none";
      banner.textContent = "";
      return;
    }
    banner.style.display = "block";
    banner.textContent = message;
    banner.className = isError ? "form-feedback-banner error" : "form-feedback-banner info";
  }

  // Friendly labels exist only in the presentation layer; persisted/exported codes stay technical.
  const VERDICT_LABELS_PT = {
    PASS: "Aprovado",
    FAIL: "Reprovado",
    INCONCLUSIVE: "Inconclusivo",
    MANUAL_REQUIRED: "Revisão manual",
  };

  function createVerdictBadge(statusText) {
    const safeStatus = statusText || "INCONCLUSIVE";
    return el(
      "span",
      { className: "badge badge-" + safeStatus, title: safeStatus, "aria-label": (VERDICT_LABELS_PT[safeStatus] || safeStatus) + " (" + safeStatus + ")" },
      VERDICT_LABELS_PT[safeStatus] || safeStatus
    );
  }

  function buildComplianceSummary(m) {
    const total = m.total_in_scope ?? ((m.pass_count || 0) + (m.fail_count || 0) + (m.inconclusive_count || 0) + (m.manual_count || 0));
    const parts = [(m.pass_count || 0) + " de " + total + " verificações aprovadas"];
    if (m.fail_count) parts.push(m.fail_count + " reprovada(s)");
    if (m.inconclusive_count) parts.push(m.inconclusive_count + " inconclusiva(s)");
    if (m.manual_count) parts.push(m.manual_count + " com revisão manual pendente");
    let text = parts.join("; ") + ".";
    if (m.inconclusive_count || m.manual_count) {
      text += " Verificações inconclusivas ou pendentes de revisão manual não são contadas como aprovadas.";
    }
    return text;
  }

  function renderComplianceHero(report) {
    const m = report.metrics || {};
    const pct = Number(m.pass_percentage ?? 0);
    const valueEl = document.getElementById("compliance-hero-value");
    const barEl = document.getElementById("compliance-progress");
    const fillEl = document.getElementById("compliance-progress-fill");
    const sumEl = document.getElementById("compliance-hero-summary");
    const cta = document.getElementById("compliance-hero-cta");
    if (valueEl) valueEl.textContent = Math.round(pct) + "%";
    if (barEl) barEl.setAttribute("aria-valuenow", String(Math.round(pct)));
    if (fillEl) fillEl.style.width = Math.max(0, Math.min(100, pct)) + "%";
    if (sumEl) sumEl.textContent = buildComplianceSummary(m);
    if (cta) cta.hidden = true;
  }

  // ===========================================================================
  // Theme Switcher (Light / Dark Fluent 2 Tokens) & Keyboard Tab Navigation
  // ===========================================================================

  function initThemeToggle() {
    const btn = document.getElementById("theme-toggle-btn");
    const saved = localStorage.getItem("asvs_theme") || "light";
    applyTheme(saved);

    if (btn) {
      btn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
      });
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("asvs_theme", theme);
    const btn = document.getElementById("theme-toggle-btn");
    if (btn) {
      const isDark = theme === "dark";
      btn.setAttribute("aria-pressed", isDark ? "true" : "false");
      btn.textContent = isDark ? "Tema Claro" : "Tema Escuro";
    }
    if (state.currentReport) {
      renderCharts(state.currentReport);
    }
  }

  function initTabs() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    tabs.forEach((tab, idx) => {
      tab.addEventListener("click", () => activateTab(tab));
      tab.addEventListener("keydown", (ev) => {
        let targetIdx = null;
        if (ev.key === "ArrowRight") targetIdx = (idx + 1) % tabs.length;
        else if (ev.key === "ArrowLeft") targetIdx = (idx - 1 + tabs.length) % tabs.length;
        else if (ev.key === "Home") targetIdx = 0;
        else if (ev.key === "End") targetIdx = tabs.length - 1;

        if (targetIdx !== null) {
          ev.preventDefault();
          tabs[targetIdx].focus();
          activateTab(tabs[targetIdx]);
        }
      });
    });
  }

  function activateTab(selectedTab) {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    tabs.forEach((t) => {
      const isSelected = t === selectedTab;
      t.setAttribute("aria-selected", isSelected ? "true" : "false");
      t.setAttribute("tabindex", isSelected ? "0" : "-1");
      const panelId = t.getAttribute("aria-controls");
      const panel = panelId ? document.getElementById(panelId) : null;
      if (panel) {
        panel.hidden = !isSelected;
      }
      if (isSelected && panelId === "panel-users") {
        loadUsersList();
      }
    });
  }

  // ===========================================================================
  // OWASP ZAP Daemon Real-Time Connectivity Check (`GET /api/zap/status`)
  // ===========================================================================

  let zapAutoCheckInterval = null;

  async function refreshZapStatus() {
    const badge = document.getElementById("zap-status-badge");
    const textEl = document.getElementById("zap-status-text");
    if (badge && (!state.zapStatus || !state.zapStatus.online)) {
      badge.className = "badge badge-INCONCLUSIVE";
      badge.textContent = "Verificando ZAP...";
    }
    try {
      const resp = await fetch("/api/zap/status");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      state.zapStatus = data;
      if (badge) {
        if (data.online) {
          badge.className = "badge badge-PASS";
          badge.textContent = "ZAP ONLINE" + (data.version ? " (v" + data.version + ")" : "");
        } else {
          badge.className = "badge badge-INCONCLUSIVE";
          badge.textContent = "ZAP OFFLINE";
        }
      }
      if (textEl) {
        textEl.textContent = data.online
          ? "Conectado em " + data.zap_base_url
          : "Aguardando daemon ZAP (auto-verificação ativa)...";
      }
      return data;
    } catch (_err) {
      state.zapStatus = { online: false };
      if (badge) {
        badge.className = "badge badge-INCONCLUSIVE";
        badge.textContent = "ZAP OFFLINE";
      }
      if (textEl) {
        textEl.textContent = "Daemon DAST inacessível (auto-verificação ativa)";
      }
      return state.zapStatus;
    }
  }

  function scheduleZapAutoCheck() {
    refreshZapStatus();
    [3000, 6000, 12000].forEach((delayMs) => {
      window.setTimeout(() => {
        if (!state.zapStatus || !state.zapStatus.online) {
          refreshZapStatus();
        }
      }, delayMs);
    });
    if (!zapAutoCheckInterval) {
      zapAutoCheckInterval = window.setInterval(() => {
        if (!state.zapStatus || !state.zapStatus.online) {
          refreshZapStatus();
        }
      }, 10000);
    }
  }

  // ===========================================================================
  // AI Provider Configuration & Real-Time Status (`/api/ai/*`)
  // ===========================================================================

  async function refreshAIStatus() {
    const badge = document.getElementById("ai-status-badge");
    const panelBadge = document.getElementById("ai-panel-status-badge");
    const summaryText = document.getElementById("ai-status-summary-text");
    const botLabel = document.getElementById("ai-chat-bot-label");
    const introText = document.getElementById("ai-chat-intro-text");

    const providerSelect = document.getElementById("ai-provider-select");
    const azureGroup = document.getElementById("azure-config-group");
    const geminiGroup = document.getElementById("gemini-config-group");

    const resInput = document.getElementById("azure-resource-name");
    const deployInput = document.getElementById("azure-deployment-id");
    const verInput = document.getElementById("azure-api-version");
    const azureKeyInput = document.getElementById("azure-api-key");

    const geminiModelInput = document.getElementById("ai-model-name");
    const geminiKeyInput = document.getElementById("ai-api-key");

    try {
      const resp = await fetch("/api/ai/status");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      state.aiStatus = data;
      state.aiConfigured = Boolean(data && data.configured);

      const isConfigured = state.aiConfigured;
      const prov = (data.provider || "azureopenai").toLowerCase();
      const modelDisplayName = data.deployment_id || data.model_name || (prov === "azureopenai" ? "azure-gpt5" : "gemini-2.0-flash");

      if (badge) {
        if (isConfigured) {
          badge.className = "badge badge-PASS";
          badge.textContent = "Motor Conectado: " + modelDisplayName + " (" + prov + ")";
        } else {
          badge.className = "badge badge-MANUAL_REQUIRED";
          badge.textContent = "IA Não Configurada";
        }
      }

      if (panelBadge) {
        if (isConfigured) {
          panelBadge.className = "badge badge-PASS";
          panelBadge.textContent = "Conectado (" + prov + " / " + modelDisplayName + ")";
        } else {
          panelBadge.className = "badge badge-MANUAL_REQUIRED";
          panelBadge.textContent = "IA Não Configurada";
        }
      }

      if (summaryText) {
        summaryText.textContent = isConfigured
          ? "Motor cognitivo pronto em memória volátil de sessão (" + prov + " / " + modelDisplayName + ")."
          : "Configuração de credenciais (Azure OpenAI / Gemini) e chat de teste gerenciados na Guia 5.";
      }

      if (botLabel) {
        botLabel.textContent = "Assistente IA (" + modelDisplayName + ")";
      }
      if (introText && isConfigured) {
        introText.textContent = "Motor conectado com sucesso (" + modelDisplayName + "). Envie uma mensagem abaixo para testar a comunicação interativa.";
      }

      if (isConfigured) {
        if (providerSelect) {
          providerSelect.value = prov;
        }
        if (prov === "azureopenai") {
          if (azureGroup) azureGroup.style.display = "flex";
          if (geminiGroup) geminiGroup.style.display = "none";
          if (resInput && data.resource_name) resInput.value = data.resource_name;
          if (deployInput && data.deployment_id) deployInput.value = data.deployment_id;
          if (verInput && data.api_version) verInput.value = data.api_version;
          if (azureKeyInput && !azureKeyInput.value) {
            azureKeyInput.placeholder = "•••••••• (Chave salva em memória)";
          }
        } else {
          if (azureGroup) azureGroup.style.display = "none";
          if (geminiGroup) geminiGroup.style.display = "flex";
          if (geminiModelInput && data.model_name) geminiModelInput.value = data.model_name;
          if (geminiKeyInput && !geminiKeyInput.value) {
            geminiKeyInput.placeholder = "•••••••• (Chave salva em memória)";
          }
        }
      }

      return data;
    } catch (_err) {
      state.aiStatus = { configured: false };
      state.aiConfigured = false;
      if (badge) {
        badge.className = "badge badge-MANUAL_REQUIRED";
        badge.textContent = "IA Não Configurada";
      }
      if (panelBadge) {
        panelBadge.className = "badge badge-MANUAL_REQUIRED";
        panelBadge.textContent = "IA Não Configurada";
      }
      return state.aiStatus;
    }
  }

  function showAIBanner(msg, isError, isLoading) {
    const banner = document.getElementById("ai-feedback-banner");
    if (!banner) return;
    banner.style.display = "block";
    banner.textContent = msg;
    if (isLoading) {
      banner.style.background = "var(--colorNeutralBackground3)";
      banner.style.color = "var(--colorNeutralForeground1)";
      banner.style.border = "1px solid var(--colorNeutralStroke1)";
    } else if (isError) {
      banner.style.background = "var(--colorPaletteRedBackground1)";
      banner.style.color = "var(--colorPaletteRedForeground1)";
      banner.style.border = "1px solid var(--colorPaletteRedBorderActive)";
    } else {
      banner.style.background = "var(--colorPaletteGreenBackground1)";
      banner.style.color = "var(--colorPaletteGreenForeground1)";
      banner.style.border = "1px solid var(--colorPaletteGreenBorderActive)";
    }
  }

  function initAIConfiguration() {
    const goToAiBtn = document.getElementById("go-to-ai-tab-btn");
    if (goToAiBtn) {
      goToAiBtn.addEventListener("click", () => {
        const tabAi = document.getElementById("tab-ai-config");
        if (tabAi) activateTab(tabAi);
      });
    }

    const providerSelect = document.getElementById("ai-provider-select");
    const azureGroup = document.getElementById("azure-config-group");
    const geminiGroup = document.getElementById("gemini-config-group");

    if (providerSelect) {
      providerSelect.addEventListener("change", () => {
        const isAzure = providerSelect.value === "azureopenai";
        if (azureGroup) azureGroup.style.display = isAzure ? "flex" : "none";
        if (geminiGroup) geminiGroup.style.display = isAzure ? "none" : "flex";
      });
    }

    const saveBtn = document.getElementById("ai-save-config-btn");
    const testBtn = document.getElementById("ai-test-connection-btn");
    const clearBtn = document.getElementById("ai-clear-config-btn");

    const resInput = document.getElementById("azure-resource-name");
    const deployInput = document.getElementById("azure-deployment-id");
    const verInput = document.getElementById("azure-api-version");
    const azureKeyInput = document.getElementById("azure-api-key");

    if (resInput) {
      resInput.addEventListener("input", () => {
        const val = resInput.value.trim();
        if (val.includes("openai.azure.com")) {
          const mHost = val.match(/([A-Za-z0-9\-_]+)\.openai\.azure\.com/i);
          if (mHost && mHost[1]) {
            resInput.value = mHost[1];
          }
          const mDep = val.match(/\/deployments\/([^/?#]+)/i);
          if (mDep && mDep[1] && deployInput) {
            deployInput.value = mDep[1];
          }
          const mVer = val.match(/[?&]api-version=([^&#\s]+)/i);
          if (mVer && mVer[1] && verInput) {
            verInput.value = mVer[1];
          }
        }
      });
    }

    const geminiModelInput = document.getElementById("ai-model-name");
    const geminiKeyInput = document.getElementById("ai-api-key");

    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const prov = providerSelect ? providerSelect.value : "azureopenai";
        let bodyPayload = {};

        if (prov === "azureopenai") {
          const resName = resInput ? resInput.value.trim() : "";
          const deployId = deployInput ? deployInput.value.trim() : "";
          const apiVer = verInput ? verInput.value.trim() : "2024-06-01";
          const apiKey = azureKeyInput ? azureKeyInput.value.trim() : "";

          if (!resName || !deployId || (!apiKey && !state.aiConfigured)) {
            showAIBanner("Preencha resource_name, deployment_id e a chave de API antes de salvar.", true);
            return;
          }

          bodyPayload = {
            service: "azureopenai",
            service_settings: {
              resource_name: resName,
              deployment_id: deployId,
              api_version: apiVer,
              api_key: apiKey || "placeholder",
            },
          };
          if (!apiKey && state.aiConfigured) {
            delete bodyPayload.service_settings.api_key;
          }
        } else {
          const model = geminiModelInput ? geminiModelInput.value.trim() : "";
          const apiKey = geminiKeyInput ? geminiKeyInput.value.trim() : "";

          if (!model || (!apiKey && !state.aiConfigured)) {
            showAIBanner("Informe o modelo e a chave de API Gemini antes de salvar.", true);
            return;
          }

          bodyPayload = {
            provider: "gemini",
            model_name: model,
            api_key: apiKey,
          };
        }

        try {
          saveBtn.disabled = true;
          showAIBanner("Salvando credenciais em memória volátil...", false, true);
          const resp = await fetch("/api/ai/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyPayload),
          });
          const data = await resp.json();
          if (!resp.ok) {
            showAIBanner("Erro ao salvar configuração: " + (data.detail || "Falha HTTP"), true);
          } else {
            // Write-only policy: wipe plaintext key from inputs immediately
            if (azureKeyInput) {
              azureKeyInput.value = "";
              azureKeyInput.placeholder = "•••••••• (Chave salva em memória)";
            }
            if (geminiKeyInput) {
              geminiKeyInput.value = "";
              geminiKeyInput.placeholder = "•••••••• (Chave salva em memória)";
            }
            state.aiConfigured = true;
            showAIBanner("Credenciais de IA salvas em memória com sucesso (Write-Only).", false);
            showFormFeedback("", false);
            await refreshAIStatus();
          }
        } catch (err) {
          showAIBanner("Erro de rede ao salvar credenciais: " + err.message, true);
        } finally {
          saveBtn.disabled = false;
        }
      });
    }

    if (testBtn) {
      testBtn.addEventListener("click", async () => {
        const prov = providerSelect ? providerSelect.value : "azureopenai";
        showAIBanner("Testando comunicação direta com o motor de IA...", false, true);
        try {
          testBtn.disabled = true;
          let bodyPayload = { provider: prov };

          if (prov === "azureopenai") {
            const resName = resInput ? resInput.value.trim() : "";
            const deployId = deployInput ? deployInput.value.trim() : "";
            const apiVer = verInput ? verInput.value.trim() : "";
            const apiKey = azureKeyInput ? azureKeyInput.value.trim() : "";

            if (resName) bodyPayload.resource_name = resName;
            if (deployId) bodyPayload.deployment_id = deployId;
            if (apiVer) bodyPayload.api_version = apiVer;
            if (apiKey) bodyPayload.api_key = apiKey;
          } else {
            const model = geminiModelInput ? geminiModelInput.value.trim() : "";
            const apiKey = geminiKeyInput ? geminiKeyInput.value.trim() : "";
            if (model) bodyPayload.model_name = model;
            if (apiKey) bodyPayload.api_key = apiKey;
          }

          const resp = await fetch("/api/ai/test-connection", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyPayload),
          });
          const data = await resp.json();
          if (data.ok) {
            showAIBanner(data.message, false);
          } else {
            showAIBanner(data.message || "Falha ao testar conexão com IA.", true);
          }
        } catch (err) {
          showAIBanner("Erro de rede ao testar IA: " + err.message, true);
        } finally {
          testBtn.disabled = false;
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (azureKeyInput) {
          azureKeyInput.value = "";
          azureKeyInput.placeholder = "Cole sua API Key do Azure OpenAI...";
        }
        if (geminiKeyInput) {
          geminiKeyInput.value = "";
          geminiKeyInput.placeholder = "Cole sua Gemini API Key...";
        }
        showAIBanner("Campos limpos localmente.", false);
      });
    }

    initAIChatPlayground();
  }

  function initAIChatPlayground() {
    const chatInput = document.getElementById("ai-chat-input");
    const sendBtn = document.getElementById("ai-chat-send-btn");
    const chatBox = document.getElementById("chat-box");
    const latencyTag = document.getElementById("ai-chat-latency");

    if (!sendBtn || !chatInput || !chatBox) return;

    async function handleSendMessage() {
      const text = chatInput.value.trim();
      if (!text) return;

      const providerSelect = document.getElementById("ai-provider-select");
      const prov = providerSelect ? providerSelect.value : "azureopenai";

      // Append user message safely via DOM (zero innerHTML)
      const userBubble = el("div", {
        style: "align-self:flex-end; max-width:85%; background:var(--colorBrandBackground); color:var(--colorNeutralForegroundOnBrand); border-radius:var(--borderRadiusMedium); padding:10px 14px; text-align:right;"
      });
      userBubble.appendChild(el("strong", { style: "display:block; font-size:12px; margin-bottom:2px; opacity:0.9;" }, "Você"));
      userBubble.appendChild(el("div", null, text));
      chatBox.appendChild(userBubble);

      chatInput.value = "";
      chatBox.scrollTop = chatBox.scrollHeight;

      if (latencyTag) {
        latencyTag.textContent = "Aguardando resposta...";
      }
      sendBtn.disabled = true;
      chatInput.disabled = true;

      const payload = {
        message: text,
        provider: prov,
      };

      if (prov === "azureopenai") {
        const resInput = document.getElementById("azure-resource-name");
        const deployInput = document.getElementById("azure-deployment-id");
        const verInput = document.getElementById("azure-api-version");
        const keyInput = document.getElementById("azure-api-key");

        if (resInput && resInput.value.trim()) payload.resource_name = resInput.value.trim();
        if (deployInput && deployInput.value.trim()) payload.deployment_id = deployInput.value.trim();
        if (verInput && verInput.value.trim()) payload.api_version = verInput.value.trim();
        if (keyInput && keyInput.value.trim()) payload.api_key = keyInput.value.trim();
      } else {
        const geminiModelInput = document.getElementById("ai-model-name");
        const geminiKeyInput = document.getElementById("ai-api-key");

        if (geminiModelInput && geminiModelInput.value.trim()) payload.model_name = geminiModelInput.value.trim();
        if (geminiKeyInput && geminiKeyInput.value.trim()) payload.api_key = geminiKeyInput.value.trim();
      }

      try {
        const resp = await fetch("/api/ai/chat-test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();

        const aiBubble = el("div", {
          style: "align-self:flex-start; max-width:85%; background:var(--colorNeutralBackground1); border:1px solid var(--colorNeutralStroke1); border-radius:var(--borderRadiusMedium); padding:10px 14px;"
        });
        const headerLabel = (data.model_used || "Assistente IA") + " (" + (data.provider || prov) + ")";
        aiBubble.appendChild(el("strong", { style: "display:block; color:var(--colorBrandForeground1); margin-bottom:2px; font-size:12px;" }, headerLabel));
        aiBubble.appendChild(el("div", null, data.response_text));
        chatBox.appendChild(aiBubble);
        chatBox.scrollTop = chatBox.scrollHeight;

        if (latencyTag) {
          latencyTag.textContent = (data.ok ? "Latência: " : "Erro • ") + data.latency_ms + " ms";
        }
      } catch (err) {
        const errBubble = el("div", {
          style: "align-self:flex-start; max-width:85%; background:var(--colorPaletteRedBackground1); border:1px solid var(--colorPaletteRedBorderActive); color:var(--colorPaletteRedForeground1); border-radius:var(--borderRadiusMedium); padding:10px 14px;"
        });
        errBubble.appendChild(el("strong", { style: "display:block; font-size:12px; margin-bottom:2px;" }, "Erro de Comunicação"));
        errBubble.appendChild(el("div", null, err.message));
        chatBox.appendChild(errBubble);
        chatBox.scrollTop = chatBox.scrollHeight;

        if (latencyTag) {
          latencyTag.textContent = "Erro na requisição";
        }
      } finally {
        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
      }
    }

    sendBtn.addEventListener("click", handleSendMessage);
    chatInput.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        handleSendMessage();
      }
    });
  }

  // ===========================================================================
  // Assessment Form & SSE Real-Time Pipeline Stream
  // ===========================================================================

  function syncSastSourceFields() {
    const sourceSelect = document.getElementById("source-type");
    const pathGroup = document.getElementById("workspace-path-group");
    const zipGroup = document.getElementById("zip-upload-group");
    if (!sourceSelect || !pathGroup || !zipGroup) return;

    const isZip = sourceSelect.value === "zip_upload";
    pathGroup.hidden = isZip;
    pathGroup.style.display = isZip ? "none" : "flex";
    zipGroup.hidden = !isZip;
    zipGroup.style.display = isZip ? "flex" : "none";
  }

  function initAssessmentForm() {
    const sourceSelect = document.getElementById("source-type");
    const pathGroup = document.getElementById("workspace-path-group");
    const zipGroup = document.getElementById("zip-upload-group");

    syncSastSourceFields();
    if (sourceSelect && pathGroup && zipGroup) {
      sourceSelect.addEventListener("change", () => {
        syncSastSourceFields();
      });
    }

    const checkZapBtn = document.getElementById("check-zap-btn");
    if (checkZapBtn) {
      checkZapBtn.addEventListener("click", async () => {
        const st = await refreshZapStatus();
        showAlert(
          st.message || (st.online ? "OWASP ZAP ONLINE." : "OWASP ZAP OFFLINE."),
          !st.online
        );
      });
    }

    const zapAuthCheckbox = document.getElementById("zap-authorized");
    const dastAuthContainer = document.getElementById("dast-auth-container");
    if (zapAuthCheckbox && dastAuthContainer) {
      zapAuthCheckbox.addEventListener("change", () => {
        if (zapAuthCheckbox.checked) {
          dastAuthContainer.classList.remove("input-error-highlight");
          dastAuthContainer.classList.remove("has-error");
          showFormFeedback("", false);
        }
      });
    }

    const targetUrlInput = document.getElementById("target-url");
    if (targetUrlInput) {
      targetUrlInput.addEventListener("keydown", async (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          await submitAssessmentForm();
        }
      });
    }

    initAIConfiguration();

    const form = document.getElementById("new-run-form");
    if (form) {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        await submitAssessmentForm();
      });
    }

    const selfCheckBtn = document.getElementById("self-check-btn");
    if (selfCheckBtn) {
      selfCheckBtn.addEventListener("click", async () => {
        if (!state.aiConfigured) {
          const tabAi = document.getElementById("tab-ai-config");
          if (tabAi) activateTab(tabAi);
          const keyInput = document.getElementById("azure-api-key") || document.getElementById("ai-api-key");
          if (keyInput) keyInput.focus();
          showFormFeedback(
            "Pré-requisito de IA não atendido: Configure as credenciais de IA na Guia 5 antes de iniciar a autoavaliação da ferramenta.",
            true
          );
          showAlert(
            "Pré-requisito de IA não atendido: Configure a IA na Guia 5 antes de executar a autoavaliação da ferramenta.",
            true
          );
          return;
        }

        const zapSt = await refreshZapStatus();
        if (sourceSelect) sourceSelect.value = "workspace_path";
        syncSastSourceFields();
        const pathInput = document.getElementById("workspace-subpath");
        const urlInput = document.getElementById("target-url");
        const zapAuthCheckbox = document.getElementById("zap-authorized");
        const zapModeSelect = document.getElementById("zap-mode");

        if (pathInput) pathInput.value = "app";
        if (zapAuthCheckbox) zapAuthCheckbox.checked = true;
        const dastAuthContainer = document.getElementById("dast-auth-container");
        if (dastAuthContainer) {
          dastAuthContainer.classList.remove("input-error-highlight");
          dastAuthContainer.classList.remove("has-error");
        }

        if (zapSt && zapSt.online) {
          if (urlInput) {
            urlInput.value = window.location.origin || "http://localhost:8000";
          }
          if (zapModeSelect) {
            zapModeSelect.value = "active";
          }
        } else {
          if (urlInput) {
            urlInput.value = "";
          }
          showAlert(
            "Aviso: OWASP ZAP Daemon está OFFLINE. A autoavaliação executará somente SAST + IA (25.0% PASS; 6 requisitos dependentes do ZAP ficarão INCONCLUSIVE). Para cobertura completa (100.0% PASS), inicie o ZAP com: docker compose up -d zap",
            true
          );
        }
        await submitAssessmentForm();
      });
    }

    const cancelBtn = document.getElementById("cancel-run-btn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", async () => {
        if (!state.activeRunId) return;
        const resp = await fetch("/api/runs/" + encodeURIComponent(String(state.activeRunId)) + "/cancel", {
          method: "POST",
        });
        const data = await resp.json();
        showAlert(data.message || "Execução cancelada.", false);
      });
    }

    const rerunBtn = document.getElementById("rerun-btn");
    if (rerunBtn) {
      rerunBtn.addEventListener("click", async () => {
        if (!state.activeRunId) return;
        await triggerRerun(state.activeRunId);
      });
    }

    const selectiveRerunBtn = document.getElementById("selective-rerun-btn");
    if (selectiveRerunBtn) {
      selectiveRerunBtn.addEventListener("click", () => {
        if (!state.activeRunId) return;
        openSelectiveRerunModal(state.activeRunId);
      });
    }
  }

  async function submitAssessmentForm() {
    const sourceType = document.getElementById("source-type").value;
    const subpath = document.getElementById("workspace-subpath").value.trim();
    const targetUrl = document.getElementById("target-url").value.trim();
    const zapModeEl = document.getElementById("zap-mode");
    if (zapModeEl) zapModeEl.value = "active";
    const zapMode = "active";
    const zapAuthCheckbox = document.getElementById("zap-authorized");
    const dastAuthContainer = document.getElementById("dast-auth-container");
    const sastCard = document.getElementById("sast-artifact-card");
    const dastCard = document.getElementById("dast-artifact-card");
    const zapAuth = zapAuthCheckbox ? zapAuthCheckbox.checked : false;

    if (sastCard) sastCard.classList.remove("input-error-highlight");
    if (dastCard) dastCard.classList.remove("input-error-highlight");

    // 0. Validate SAST Artifact Presence
    if (sourceType === "workspace_path" && !subpath) {
      if (sastCard) sastCard.classList.add("input-error-highlight");
      const pathInput = document.getElementById("workspace-subpath");
      if (pathInput) pathInput.focus();
      showFormFeedback(
        "Artefato SAST obrigatório: Informe o Caminho Relativo no Workspace antes de iniciar a avaliação.",
        true
      );
      showAlert("Informe o Caminho Relativo no Workspace para o SAST.", true);
      return;
    }
    if (sourceType === "zip_upload") {
      const fileInput = document.getElementById("zip-file");
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (sastCard) sastCard.classList.add("input-error-highlight");
        if (fileInput) fileInput.focus();
        showFormFeedback(
          "Artefato SAST obrigatório: Selecione um pacote .ZIP válido do código-fonte antes de iniciar a avaliação.",
          true
        );
        showAlert("Selecione um arquivo .ZIP do código-fonte para iniciar a avaliação.", true);
        return;
      }
    }

    // 1. Strict Universal DAST Guardrail (US1 / Princípio IV)
    if (!zapAuth) {
      if (dastAuthContainer) {
        dastAuthContainer.classList.add("input-error-highlight");
        dastAuthContainer.classList.add("has-error");
      }
      if (zapAuthCheckbox) {
        zapAuthCheckbox.focus();
      }
      showFormFeedback(
        "Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação.",
        true
      );
      showAlert(
        "Bloqueio de Segurança: É obrigatório declarar autorização explícita marcando o checkbox de consentimento antes de iniciar qualquer avaliação.",
        true
      );
      return;
    } else {
      if (dastAuthContainer) {
        dastAuthContainer.classList.remove("input-error-highlight");
        dastAuthContainer.classList.remove("has-error");
      }
    }

    // 2. Strict AI Prerequisite Gate (US2 / Princípio IV)
    if (!state.aiConfigured) {
      const tabAi = document.getElementById("tab-ai-config");
      if (tabAi) activateTab(tabAi);
      const keyInput = document.getElementById("azure-api-key") || document.getElementById("ai-api-key");
      if (keyInput) {
        keyInput.focus();
      }
      showFormFeedback(
        "Pré-requisito de IA não atendido: O modelo de IA deve ser configurado na Guia 5 antes de iniciar a avaliação.",
        true
      );
      showAlert(
        "Pré-requisito Obrigatório: Configure o modelo de IA e salve as credenciais em memória na Guia 5 antes de iniciar a avaliação.",
        true
      );
      return;
    }

    showFormFeedback("", false);

    if (targetUrl && state.zapStatus && state.zapStatus.online === false) {
      showAlert(
        "Atenção: URL alvo informada, mas o daemon OWASP ZAP aparenta estar OFFLINE (" +
          (state.zapStatus.zap_base_url || "http://localhost:8090") +
          "). Sem o daemon ZAP em execução, os requisitos V1.2.1–V1.2.5 e V1.5.1 receberão INCONCLUSIVE.",
        true
      );
    }

    resetStepper();
    let resp;
    try {
      if (sourceType === "zip_upload") {
        const fileInput = document.getElementById("zip-file");
        if (!fileInput || !fileInput.files || !fileInput.files[0]) {
          showFormFeedback(
            "Arquivo obrigatório: Selecione um pacote .ZIP válido do código-fonte antes de iniciar a avaliação.",
            true
          );
          showAlert("Selecione um arquivo .ZIP do código-fonte para iniciar a avaliação.", true);
          return;
        }
        const formData = new FormData();
        formData.append("source_type", "zip_upload");
        formData.append("source_zip", fileInput.files[0]);
        formData.append("zip_file", fileInput.files[0]);
        if (targetUrl) formData.append("target_url", targetUrl);
        formData.append("zap_authorized", zapAuth ? "true" : "false");
        formData.append("zap_mode", zapMode);
        resp = await fetch("/api/runs/upload", { method: "POST", body: formData });
      } else {
        resp = await fetch("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_type: "workspace_path",
            workspace_subpath: subpath,
            target_url: targetUrl || null,
            zap_authorized: zapAuth,
            zap_mode: zapMode,
          }),
        });
      }

      let payload = {};
      const rawText = await resp.text();
      try {
        payload = rawText ? JSON.parse(rawText) : {};
      } catch (_parseErr) {
        payload = { detail: rawText || "Resposta inválida do servidor (HTTP " + resp.status + ")" };
      }

      if (!resp.ok) {
        const detailMsg =
          typeof payload.detail === "string"
            ? payload.detail
            : JSON.stringify(payload.detail || "Falha ao iniciar");
        showFormFeedback("Erro (" + resp.status + "): " + detailMsg, true);
        showAlert("Erro de Guardrail (" + resp.status + "): " + detailMsg, true);
        return;
      }

      state.activeRunId = payload.run_id;
      if (!targetUrl) {
        showAlert(
          "Execução #" +
            payload.run_id +
            " iniciada em modo Somente SAST (sem URL alvo DAST/OWASP ZAP). " +
            "Nota: os 6 requisitos que dependem de verificação dinâmica (V1.2.1–V1.2.5, V1.5.1) receberão INCONCLUSIVE caso não possuam achados estáticos.",
          false
        );
      } else {
        showAlert(
          "Execução #" +
            payload.run_id +
            " iniciada (SAST Semgrep + DAST OWASP ZAP em " +
            targetUrl +
            "). Acompanhando progresso via SSE...",
          false
        );
      }
      connectSSE(payload.run_id);
      await loadRunsHistory();
    } catch (err) {
      showAlert("Falha de rede ao iniciar avaliação: " + String(err), true);
    }
  }

  async function triggerRerun(runId) {
    resetStepper();
    const resp = await fetch("/api/runs/" + encodeURIComponent(String(runId)) + "/rerun", {
      method: "POST",
    });
    const payload = await resp.json();
    if (!resp.ok) {
      showAlert("Erro ao reexecutar: " + (payload.detail || "Falha"), true);
      return;
    }
    state.activeRunId = payload.run_id;
    showAlert(
      "Reexecução idempotente #" + payload.run_id + " (baseada na #" + runId + ") iniciada.",
      false
    );
    connectSSE(payload.run_id);
    await loadRunsHistory();
  }

  // ===========================================================================
  // Selective Rerun Modal & Multi-Dimensional Filters (Feature 008)
  // ===========================================================================

  const ASVS_V1_METADATA = {
    "V1.2.1": { section: "V1.2", name: "Prevenção de Injeção", title: "Consultas SQL Parametrizadas", tools: ["semgrep", "zap"] },
    "V1.2.2": { section: "V1.2", name: "Prevenção de Injeção", title: "Prevenção de Injeção de Comandos de SO", tools: ["semgrep", "zap"] },
    "V1.2.3": { section: "V1.2", name: "Prevenção de Injeção", title: "Prevenção de Injeção XPath / XML", tools: ["semgrep", "zap"] },
    "V1.2.4": { section: "V1.2", name: "Prevenção de Injeção", title: "Prevenção de Injeção LDAP", tools: ["semgrep", "zap"] },
    "V1.2.5": { section: "V1.2", name: "Prevenção de Injeção", title: "Prevenção de Injeção ORM / ODM", tools: ["semgrep", "zap"] },
    "V1.3.1": { section: "V1.3", name: "Sanitização & Entrada", title: "Sanitização Sensível ao Contexto (AI Evaluator)", tools: ["ai_evaluator"] },
    "V1.3.2": { section: "V1.3", name: "Sanitização & Entrada", title: "Validação Estrita de Entrada (RegEx / Pattern)", tools: ["semgrep"] },
    "V1.5.1": { section: "V1.5", name: "Desserialização Segura", title: "Desserialização Segura & Hardening de Parsers", tools: ["semgrep", "zap"] },
  };

  async function openSelectiveRerunModal(runId) {
    const targetRunId = runId || state.activeRunId;
    if (!targetRunId) {
      showAlert("Nenhuma avaliação selecionada para reexecução.", true);
      return;
    }

    const dialog = document.getElementById("selective-rerun-dialog");
    if (!dialog) return;

    const baseIdSpan = document.getElementById("selective-rerun-base-id");
    if (baseIdSpan) baseIdSpan.textContent = "#" + targetRunId;

    const errBox = document.getElementById("selective-rerun-error-msg");
    if (errBox) {
      errBox.style.display = "none";
      errBox.textContent = "";
    }

    state.selectiveRerunBaseRunId = targetRunId;
    state.selectiveRerunSelectedReqs = new Set();

    // Reset filters
    const filterIds = ["filter-section", "filter-id", "filter-verdict", "filter-confidence", "filter-tool"];
    filterIds.forEach((fId) => {
      const select = document.getElementById(fId);
      if (select) select.value = "";
    });

    const selectAllCheckbox = document.getElementById("check-select-all");
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    }

    // Fetch report / verdicts if needed
    let verdicts = [];
    if (state.currentReport && state.currentReport.id === targetRunId && Array.isArray(state.currentReport.verdicts)) {
      verdicts = state.currentReport.verdicts;
    } else {
      try {
        const resp = await fetch("/api/runs/" + encodeURIComponent(String(targetRunId)));
        if (resp.ok) {
          const rep = await resp.json();
          verdicts = rep.verdicts || [];
        }
      } catch (_err) {
        // fallback
      }
    }

    state.selectiveRerunVerdicts = verdicts;
    renderSelectiveRerunTable();
    updateSelectiveRerunCounter();

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function renderSelectiveRerunTable() {
    const tbody = document.getElementById("selective-rerun-tbody");
    if (!tbody) return;
    clearChildren(tbody);

    const filterSecEl = document.getElementById("filter-section");
    const filterIdEl = document.getElementById("filter-id");
    const filterVerdEl = document.getElementById("filter-verdict");
    const filterConfEl = document.getElementById("filter-confidence");
    const filterToolEl = document.getElementById("filter-tool");

    const filterSec = filterSecEl ? filterSecEl.value : "";
    const filterId = filterIdEl ? filterIdEl.value : "";
    const filterVerd = filterVerdEl ? filterVerdEl.value : "";
    const filterConf = filterConfEl ? filterConfEl.value : "";
    const filterTool = filterToolEl ? filterToolEl.value : "";

    const reqIds = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"];
    let visibleCount = 0;
    let visibleCheckedCount = 0;

    reqIds.forEach((reqId) => {
      const meta = ASVS_V1_METADATA[reqId] || { section: "", name: "", title: reqId, tools: [] };
      const v = (state.selectiveRerunVerdicts || []).find((item) => item.req_id === reqId) || {
        status: "INCONCLUSIVE",
        confidence_level: "MEDIUM",
        section_id: meta.section,
        section_name: meta.name,
      };

      const toolsList = meta.tools || [];
      const vStatus = v.status || "INCONCLUSIVE";
      const vConf = v.confidence_level || "MEDIUM";
      const vSec = v.section_id || meta.section;

      // Filtering logic
      if (filterSec && vSec !== filterSec) return;
      if (filterId && reqId !== filterId) return;
      if (filterVerd && vStatus !== filterVerd) return;
      if (filterConf && vConf !== filterConf) return;
      if (filterTool && !toolsList.includes(filterTool)) return;

      visibleCount++;
      const isChecked = state.selectiveRerunSelectedReqs.has(reqId);
      if (isChecked) visibleCheckedCount++;

      const tr = el("tr", { "data-req-id": reqId, style: "border-bottom:1px solid var(--colorNeutralStroke2);" });

      // Checkbox
      const tdCheck = el("td", { style: "padding:8px; text-align:center;" });
      const chk = el("input", {
        type: "checkbox",
        className: "selective-req-checkbox",
        "data-req-id": reqId,
        "aria-label": "Selecionar requisito " + reqId,
      });
      chk.checked = isChecked;
      chk.addEventListener("change", () => {
        if (chk.checked) {
          state.selectiveRerunSelectedReqs.add(reqId);
        } else {
          state.selectiveRerunSelectedReqs.delete(reqId);
        }
        updateSelectiveRerunCounter();
      });
      tdCheck.appendChild(chk);
      tr.appendChild(tdCheck);

      // ID
      const tdId = el("td", { style: "padding:8px; font-weight:700;" }, reqId);
      tr.appendChild(tdId);

      // Section
      const tdSec = el("td", { style: "padding:8px; font-size:12px;" }, vSec);
      tr.appendChild(tdSec);

      // Title
      const tdTitle = el("td", { style: "padding:8px;" }, meta.title);
      tr.appendChild(tdTitle);

      // Verdict
      const tdVerd = el("td", { style: "padding:8px;" });
      tdVerd.appendChild(createVerdictBadge(vStatus));
      tr.appendChild(tdVerd);

      // Confidence
      const tdConf = el("td", { style: "padding:8px; font-size:12px;" }, vConf);
      tr.appendChild(tdConf);

      // Tools
      const tdTools = el("td", { style: "padding:8px; font-size:12px; color:var(--colorNeutralForeground2);" }, toolsList.join(", "));
      tr.appendChild(tdTools);

      tbody.appendChild(tr);
    });

    if (visibleCount === 0) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7", style: "padding:16px; text-align:center; color:var(--colorNeutralForeground3);" }, "Nenhum requisito corresponde aos filtros aplicados."));
      tbody.appendChild(tr);
    }

    const selectAllCheckbox = document.getElementById("check-select-all");
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = visibleCount > 0 && visibleCheckedCount === visibleCount;
      selectAllCheckbox.indeterminate = visibleCheckedCount > 0 && visibleCheckedCount < visibleCount;
    }
  }

  function updateSelectiveRerunCounter() {
    const count = state.selectiveRerunSelectedReqs.size;
    const counterBadge = document.getElementById("selective-rerun-counter");
    if (counterBadge) {
      counterBadge.textContent = count + " de 8 selecionados";
      if (count > 0) {
        counterBadge.style.background = "var(--colorPaletteGreenBackground2)";
        counterBadge.style.color = "var(--colorPaletteGreenForeground1)";
      } else {
        counterBadge.style.background = "var(--colorBrandBackground2)";
        counterBadge.style.color = "var(--colorBrandForeground2)";
      }
    }

    const confirmBtn = document.getElementById("btn-confirm-selective-rerun");
    if (confirmBtn) {
      confirmBtn.disabled = count === 0;
    }

    // Sync master checkbox with visible rows
    const tbody = document.getElementById("selective-rerun-tbody");
    if (tbody) {
      const visibleCheckboxes = Array.from(tbody.querySelectorAll("input.selective-req-checkbox"));
      const visibleCount = visibleCheckboxes.length;
      const checkedVisibleCount = visibleCheckboxes.filter((c) => c.checked).length;
      const selectAllCheckbox = document.getElementById("check-select-all");
      if (selectAllCheckbox) {
        selectAllCheckbox.checked = visibleCount > 0 && checkedVisibleCount === visibleCount;
        selectAllCheckbox.indeterminate = checkedVisibleCount > 0 && checkedVisibleCount < visibleCount;
      }
    }
  }

  function initSelectiveRerunControls() {
    const dialog = document.getElementById("selective-rerun-dialog");
    const closeBtn = document.getElementById("close-selective-rerun-btn");
    const cancelBtn = document.getElementById("btn-cancel-selective-rerun");
    const confirmBtn = document.getElementById("btn-confirm-selective-rerun");

    function closeDialog() {
      if (!dialog) return;
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }

    if (closeBtn) closeBtn.addEventListener("click", closeDialog);
    if (cancelBtn) cancelBtn.addEventListener("click", closeDialog);

    // Filters
    const filterIds = ["filter-section", "filter-id", "filter-verdict", "filter-confidence", "filter-tool"];
    filterIds.forEach((fId) => {
      const select = document.getElementById(fId);
      if (select) {
        select.addEventListener("change", () => {
          renderSelectiveRerunTable();
          updateSelectiveRerunCounter();
        });
      }
    });

    // Master Checkbox
    const selectAllCheckbox = document.getElementById("check-select-all");
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", () => {
        const check = selectAllCheckbox.checked;
        const tbody = document.getElementById("selective-rerun-tbody");
        if (!tbody) return;
        const visibleCheckboxes = Array.from(tbody.querySelectorAll("input.selective-req-checkbox"));
        visibleCheckboxes.forEach((chk) => {
          chk.checked = check;
          const reqId = chk.getAttribute("data-req-id");
          if (reqId) {
            if (check) state.selectiveRerunSelectedReqs.add(reqId);
            else state.selectiveRerunSelectedReqs.delete(reqId);
          }
        });
        updateSelectiveRerunCounter();
      });
    }

    // Batch Actions
    const btnSelectFiltered = document.getElementById("btn-select-filtered");
    if (btnSelectFiltered) {
      btnSelectFiltered.addEventListener("click", () => {
        const tbody = document.getElementById("selective-rerun-tbody");
        if (!tbody) return;
        const visibleCheckboxes = Array.from(tbody.querySelectorAll("input.selective-req-checkbox"));
        visibleCheckboxes.forEach((chk) => {
          chk.checked = true;
          const reqId = chk.getAttribute("data-req-id");
          if (reqId) state.selectiveRerunSelectedReqs.add(reqId);
        });
        updateSelectiveRerunCounter();
      });
    }

    const btnDeselectFiltered = document.getElementById("btn-deselect-filtered");
    if (btnDeselectFiltered) {
      btnDeselectFiltered.addEventListener("click", () => {
        const tbody = document.getElementById("selective-rerun-tbody");
        if (!tbody) return;
        const visibleCheckboxes = Array.from(tbody.querySelectorAll("input.selective-req-checkbox"));
        visibleCheckboxes.forEach((chk) => {
          chk.checked = false;
          const reqId = chk.getAttribute("data-req-id");
          if (reqId) state.selectiveRerunSelectedReqs.delete(reqId);
        });
        updateSelectiveRerunCounter();
      });
    }

    const btnClearSelection = document.getElementById("btn-clear-selection");
    if (btnClearSelection) {
      btnClearSelection.addEventListener("click", () => {
        state.selectiveRerunSelectedReqs.clear();
        const tbody = document.getElementById("selective-rerun-tbody");
        if (tbody) {
          const allCheckboxes = Array.from(tbody.querySelectorAll("input.selective-req-checkbox"));
          allCheckboxes.forEach((chk) => { chk.checked = false; });
        }
        updateSelectiveRerunCounter();
      });
    }

    // Confirm Execution
    if (confirmBtn) {
      confirmBtn.addEventListener("click", async () => {
        const selectedReqs = Array.from(state.selectiveRerunSelectedReqs);
        const errBox = document.getElementById("selective-rerun-error-msg");
        if (selectedReqs.length === 0) {
          if (errBox) {
            errBox.style.display = "block";
            errBox.textContent = "Selecione ao menos 1 requisito para disparar a reexecução seletiva.";
          }
          return;
        }

        if (errBox) {
          errBox.style.display = "none";
          errBox.textContent = "";
        }

        confirmBtn.disabled = true;
        try {
          resetStepper();
          const baseRunId = state.selectiveRerunBaseRunId;
          const resp = await fetch("/api/runs/" + encodeURIComponent(String(baseRunId)) + "/rerun", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ req_ids: selectedReqs }),
          });
          const payload = await resp.json();
          if (!resp.ok) {
            if (errBox) {
              errBox.style.display = "block";
              errBox.textContent = payload.detail || "Erro ao disparar reexecução seletiva.";
            }
            return;
          }

          closeDialog();
          state.activeRunId = payload.run_id;
          showAlert(
            "Reexecução seletiva #" +
              payload.run_id +
              " (baseada na #" +
              baseRunId +
              " com " +
              selectedReqs.length +
              "/8 requisitos) iniciada. Acompanhando via SSE...",
            false
          );
          activateTab(document.getElementById("tab-execution"));
          connectSSE(payload.run_id);
          await loadRunsHistory();
        } catch (err) {
          if (errBox) {
            errBox.style.display = "block";
            errBox.textContent = "Falha de rede ao disparar reexecução: " + String(err);
          }
        } finally {
          confirmBtn.disabled = false;
        }
      });
    }
  }

  function resetStepper() {
    const nodes = document.querySelectorAll("#pipeline-stepper .step-node");
    nodes.forEach((n) => {
      n.classList.remove("active", "completed");
      const sub = n.querySelector(".step-status");
      if (sub) sub.textContent = "Pendente";
    });
    const logList = document.getElementById("sse-log-list");
    clearChildren(logList);
  }

  function appendSSELog(text) {
    const logList = document.getElementById("sse-log-list");
    if (!logList) return;
    const item = el("li", null, "[" + new Date().toLocaleTimeString() + "] " + text);
    logList.appendChild(item);
    logList.scrollTop = logList.scrollHeight;
  }

  function connectSSE(runId) {
    if (state.eventSource) {
      state.eventSource.close();
    }
    const cancelBtn = document.getElementById("cancel-run-btn");
    const rerunBtn = document.getElementById("rerun-btn");
    const selectiveRerunBtn = document.getElementById("selective-rerun-btn");
    const badge = document.getElementById("active-run-badge");
    if (cancelBtn) cancelBtn.disabled = false;
    if (rerunBtn) rerunBtn.disabled = true;
    if (selectiveRerunBtn) selectiveRerunBtn.disabled = true;
    if (badge) {
      badge.className = "badge badge-INCONCLUSIVE";
      badge.textContent = "Execução #" + runId + " • EM ANDAMENTO";
    }

    const es = new EventSource("/api/runs/" + encodeURIComponent(String(runId)) + "/events");
    state.eventSource = es;

    es.addEventListener("pipeline_update", async (ev) => {
      try {
        const data = JSON.parse(ev.data);
        updateStepperStage(data.stage, data.stage_status);
        appendSSELog("(" + data.stage + " - " + data.stage_status + ") " + data.message);

        if (
          data.status === "COMPLETED" ||
          data.status === "FAILED" ||
          data.status === "CANCELLED"
        ) {
          es.close();
          if (cancelBtn) cancelBtn.disabled = true;
          if (rerunBtn) rerunBtn.disabled = false;
          if (selectiveRerunBtn) selectiveRerunBtn.disabled = false;
          if (badge) {
            badge.className =
              data.status === "COMPLETED" ? "badge badge-PASS" : "badge badge-FAIL";
            badge.textContent = "Execução #" + runId + " • " + data.status;
          }
          await loadRunsHistory();
          await loadRunDashboard(runId);
        }
      } catch (err) {
        appendSSELog("Erro ao processar evento SSE: " + String(err));
      }
    });

    es.onerror = () => {
      es.close();
      if (cancelBtn) cancelBtn.disabled = true;
      if (rerunBtn) rerunBtn.disabled = false;
      if (selectiveRerunBtn) selectiveRerunBtn.disabled = false;
    };
  }

  function updateStepperStage(stage, stageStatus) {
    if (stage === "DONE") {
      const allNodes = document.querySelectorAll("#pipeline-stepper .step-node");
      allNodes.forEach((n) => {
        n.classList.remove("active");
        n.classList.add("completed");
      });
      return;
    }
    const node = document.querySelector('#pipeline-stepper .step-node[data-stage="' + stage + '"]');
    if (!node) return;
    const sub = node.querySelector(".step-status");
    if (stageStatus === "STARTED") {
      node.classList.add("active");
      if (sub) sub.textContent = "Em execução...";
    } else if (stageStatus === "COMPLETED" || stageStatus === "SKIPPED") {
      node.classList.remove("active");
      node.classList.add("completed");
      if (sub) sub.textContent = stageStatus === "SKIPPED" ? "Ignorado (Só SAST)" : "Concluído";
    } else if (stageStatus === "FAILED" || stageStatus === "CANCELLED") {
      node.classList.remove("active");
      if (sub) sub.textContent = stageStatus;
    }
  }

  // ===========================================================================
  // Dashboard, SVG Charts, 8-Req Table, Findings & Triage
  // ===========================================================================

  async function loadRunDashboard(runId) {
    if (!runId) return;
    state.activeRunId = runId;
    const select = document.getElementById("dashboard-run-select");
    if (select) select.value = String(runId);

    const resp = await fetch("/api/runs/" + encodeURIComponent(String(runId)));
    if (!resp.ok) return;
    const report = await resp.json();
    state.currentReport = report;

    renderMetricCards(report);
    renderCharts(report);
    renderVerdictsTable(report);
    renderFindingsTable(report);
  }

  function renderMetricCards(report) {
    const m = report.metrics || {};
    const r = report.run || report || {};
    document.getElementById("metric-pass-pct").textContent = (m.pass_percentage ?? 0) + "%";
    document.getElementById("metric-pass-count").textContent = String(m.pass_count ?? 0);
    document.getElementById("metric-fail-count").textContent = String(m.fail_count ?? 0);
    document.getElementById("metric-inc-count").textContent = String(m.inconclusive_count ?? 0);
    document.getElementById("metric-manual-count").textContent = String(m.manual_count ?? 0);
    let metaText = "Run #" + (r.id || report.id) + " • " + (r.source_path || "") + " (" + (r.status || "") + ")";
    if (r.is_selective || report.is_selective) {
      const selIds = r.selected_req_ids || report.selected_req_ids || [];
      const inhId = r.inherited_from_run_id || report.inherited_from_run_id;
      metaText =
        "Run #" +
        (r.id || report.id) +
        " (Reexecução Seletiva • " +
        selIds.length +
        "/8" +
        (inhId ? " • Base: #" + inhId : "") +
        ") • " +
        (r.source_path || "") +
        " (" +
        (r.status || "") +
        ")";
    }
    document.getElementById("metric-run-meta").textContent = metaText;
    renderComplianceHero(report);
  }

  function renderCharts(report) {
    const m = report.metrics || {};
    const styles = getComputedStyle(document.documentElement);
    const colors = {
      PASS: styles.getPropertyValue("--colorPaletteGreenForeground1").trim() || "#0e700e",
      FAIL: styles.getPropertyValue("--colorPaletteRedForeground1").trim() || "#b10e1c",
      INCONCLUSIVE: styles.getPropertyValue("--colorPaletteMarigoldForeground1").trim() || "#8a5700",
      MANUAL_REQUIRED: styles.getPropertyValue("--colorPaletteBlueForeground2").trim() || "#0f548c",
      fg: styles.getPropertyValue("--colorNeutralForeground1").trim() || "#242424",
      stroke: styles.getPropertyValue("--colorNeutralStroke2").trim() || "#e0e0e0",
    };

    // 1. Donut Chart
    const donutSvg = document.getElementById("verdict-donut-svg");
    const legendBox = document.getElementById("verdict-donut-legend");
    clearChildren(donutSvg);
    clearChildren(legendBox);

    const segments = [
      { key: "PASS", label: VERDICT_LABELS_PT.PASS, count: m.pass_count || 0, color: colors.PASS },
      { key: "FAIL", label: VERDICT_LABELS_PT.FAIL, count: m.fail_count || 0, color: colors.FAIL },
      { key: "INCONCLUSIVE", label: VERDICT_LABELS_PT.INCONCLUSIVE, count: m.inconclusive_count || 0, color: colors.INCONCLUSIVE },
      { key: "MANUAL_REQUIRED", label: VERDICT_LABELS_PT.MANUAL_REQUIRED, count: m.manual_count || 0, color: colors.MANUAL_REQUIRED },
    ];
    const total = segments.reduce((acc, s) => acc + s.count, 0) || 8;
    const radius = 64;
    const circumference = 2 * Math.PI * radius;

    donutSvg.appendChild(
      svgEl("circle", {
        cx: 90,
        cy: 90,
        r: radius,
        fill: "none",
        stroke: colors.stroke,
        "stroke-width": 22,
      })
    );

    let offset = 0;
    segments.forEach((seg) => {
      if (seg.count > 0) {
        const dash = (seg.count / total) * circumference;
        donutSvg.appendChild(
          svgEl("circle", {
            cx: 90,
            cy: 90,
            r: radius,
            fill: "none",
            stroke: seg.color,
            "stroke-width": 22,
            "stroke-dasharray": dash + " " + (circumference - dash),
            "stroke-dashoffset": -offset,
            transform: "rotate(-90 90 90)",
          })
        );
        offset += dash;
      }

      const row = el("div", { style: "display:flex; align-items:center; gap:8px;" });
      const swatch = el("span", {
        style:
          "display:inline-block; width:12px; height:12px; border-radius:3px; background:" +
          seg.color,
      });
      const lbl = el("span", null, seg.label + ": " + seg.count + " / 8");
      row.appendChild(swatch);
      row.appendChild(lbl);
      legendBox.appendChild(row);
    });

    donutSvg.appendChild(
      svgEl(
        "text",
        {
          x: 90,
          y: 95,
          "text-anchor": "middle",
          fill: colors.fg,
          "font-size": "18",
          "font-weight": "700",
        },
        (m.pass_percentage ?? 0) + "%"
      )
    );

    // 2. Section Horizontal Stacked Bar Chart (V1.2, V1.3, V1.5)
    const barsSvg = document.getElementById("section-bars-svg");
    clearChildren(barsSvg);
    const secBreakdown = report.section_breakdown || {};
    const sectionsOrder = [
      { id: "V1.2", label: "V1.2 Injection (5)", max: 5 },
      { id: "V1.3", label: "V1.3 Sanitization (2)", max: 2 },
      { id: "V1.5", label: "V1.5 Deserialization (1)", max: 1 },
    ];

    sectionsOrder.forEach((sec, idx) => {
      const y = 25 + idx * 52;
      const counts = secBreakdown[sec.id] || {};
      barsSvg.appendChild(
        svgEl(
          "text",
          { x: 10, y: y + 16, fill: colors.fg, "font-size": "12", "font-weight": "600" },
          sec.label
        )
      );

      const barXStart = 165;
      const maxBarWidth = 230;
      barsSvg.appendChild(
        svgEl("rect", {
          x: barXStart,
          y: y,
          width: maxBarWidth,
          height: 22,
          rx: 4,
          fill: colors.stroke,
        })
      );

      let curX = barXStart;
      ["PASS", "FAIL", "INCONCLUSIVE", "MANUAL_REQUIRED"].forEach((stKey) => {
        const c = counts[stKey] || 0;
        if (c > 0) {
          const w = (c / sec.max) * maxBarWidth;
          barsSvg.appendChild(
            svgEl("rect", {
              x: curX,
              y: y,
              width: w,
              height: 22,
              fill: colors[stKey],
            })
          );
          curX += w;
        }
      });
    });
  }

  // Feature 015: cache of in-scope catalog descriptions (fallback when report lacks req_description)
  const catalogDescriptions = {};
  let catalogDescriptionsLoaded = false;

  function getCatalogDescription(reqId) {
    return catalogDescriptions[reqId] || { en: "", pt: "" };
  }

  // Feature 017: never render "undefined"/"null"; derive section from req_id (e.g. V1.2.1 -> V1.2).
  function safeText(value) {
    return value === undefined || value === null || value === "undefined" || value === "null" ? "" : String(value);
  }

  function deriveSectionId(v) {
    if (safeText(v.section_id)) return String(v.section_id);
    const m = /^(V\d+\.\d+)\./.exec(safeText(v.req_id));
    return m ? m[1] : "";
  }

  // Feature 019: Descrição completa em bloco recolhível para V1.2.1 a V1.5.1.
  function appendRequirementDescription(container, v, className, isCollapsible = true) {
    const cat = getCatalogDescription(v.req_id);
    const text = safeText(v.description_pt) || cat.pt || safeText(v.req_description) || cat.en || "Descrição normativa indisponível";
    if (isCollapsible) {
      const details = el("details", { className: "req-desc-details" });
      const summary = el("summary", { className: "req-desc-summary" }, "Descrição completa");
      details.appendChild(summary);
      details.appendChild(el("div", { className: "req-description-body " + (className || ""), lang: "pt-BR" }, text));
      container.appendChild(details);
    } else {
      container.appendChild(el("div", { className: className, lang: "pt-BR" }, text));
    }
  }

  async function ensureCatalogDescriptions() {
    if (catalogDescriptionsLoaded) return;
    try {
      const resp = await fetch("/api/requirements/in-scope");
      if (!resp.ok) return;
      const data = await resp.json();
      (data.items || []).forEach((it) => {
        catalogDescriptions[it.req_id] = { en: it.req_description || "", pt: it.description_pt || "" };
      });
      catalogDescriptionsLoaded = true;
    } catch (e) {
      /* fallback is best-effort */
    }
  }

  function renderVerdictsTable(report) {
    const tbody = document.getElementById("verdicts-tbody");
    clearChildren(tbody);

    if (!catalogDescriptionsLoaded && (report.verdicts || []).some((x) => !safeText(x.description_pt) || !safeText(x.req_description))) {
      ensureCatalogDescriptions().then(() => {
        if (catalogDescriptionsLoaded && state.currentReport === report) renderVerdictsTable(report);
      });
    }

    const statusFilter = document.getElementById("filter-verdict-status").value;
    const secFilter = document.getElementById("filter-verdict-section").value;

    const verdicts = (report.verdicts || []).filter((v) => {
      if (statusFilter && v.status !== statusFilter) return false;
      if (secFilter && deriveSectionId(v) !== secFilter) return false;
      return true;
    });

    if (verdicts.length === 0) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "4" }, "Nenhuma verificação corresponde aos filtros selecionados."));
      tbody.appendChild(tr);
      return;
    }

    verdicts.forEach((v) => {
      const tr = el("tr");

      // Col 1: Req ID + Section
      const tdReq = el("td");
      tdReq.appendChild(el("strong", null, v.req_id));
      if (v.is_inherited) {
        const inhId = v.inherited_from_run_id || (report.run && report.run.inherited_from_run_id) || report.inherited_from_run_id;
        const inhBadge = el(
          "span",
          {
            className: "badge badge-INCONCLUSIVE",
            style: "margin-left:6px; font-size:10px; padding:1px 5px;",
            title: "Veredito e evidências herdados da execução #" + (inhId || "?"),
          },
          "Herdado" + (inhId ? " (#" + inhId + ")" : "")
        );
        tdReq.appendChild(inhBadge);
      }
      const reqTitle = safeText(v.friendly_title) || safeText(v.section_name);
      if (reqTitle) tdReq.appendChild(el("div", { className: "req-title" }, reqTitle));
      const reqSection = [deriveSectionId(v), safeText(v.section_name)].filter(Boolean).join(" — ");
      if (reqSection) tdReq.appendChild(el("div", { className: "req-section" }, reqSection));
      appendRequirementDescription(tdReq, v, "req-description");
      tr.appendChild(tdReq);

      // Col 2: Verdict Badge
      const tdVerdict = el("td");
      tdVerdict.appendChild(createVerdictBadge(v.status));
      tr.appendChild(tdVerdict);

      // Col 3: Technical details (collapsible; auto-open on print)
      const tdTech = el("td");
      const details = el("details", { className: "tech-details" });
      details.appendChild(el("summary", null, "Detalhes técnicos"));
      details.appendChild(el("div", null, "Confiança: " + (v.confidence_level || "N/A")));
      details.appendChild(el("div", { style: "font-weight:600;" }, (v.tools_used || []).join(", ") || "Nenhuma ferramenta"));
      details.appendChild(
        el("div", { style: "font-size:12px; color:var(--colorNeutralForeground3);" }, (v.rules_executed || []).join(", ") || "0 regras")
      );
      details.appendChild(el("div", { style: "margin-top:4px;" }, v.coverage_declared || ""));
      const posList = v.positive_evidence || [];
      if (posList.length > 0) {
        details.appendChild(
          el(
            "div",
            { style: "font-size:12px; color:var(--colorPaletteGreenForeground1); margin-top:4px;" },
            "Evidência positiva: " + posList.join(" | ")
          )
        );
      }
      details.appendChild(el("div", { style: "margin-top:4px;" }, v.rationale || ""));
      details.appendChild(
        el("div", { style: "font-size:12px; color:var(--colorNeutralForeground3); margin-top:4px;" }, "Limitações: " + (v.limitations || "N/A"))
      );
      tdTech.appendChild(details);
      tr.appendChild(tdTech);

      // Col 4: Actions
      const tdActions = el("td", { className: "no-print" });
      const detBtn = el("button", { type: "button", className: "fluent-btn" }, "Ver Detalhes");
      detBtn.addEventListener("click", () => openRequirementModal(v));
      tdActions.appendChild(detBtn);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }


  function renderFindingsTable(report) {
    const tbody = document.getElementById("findings-tbody");
    clearChildren(tbody);

    const reqFilter = document.getElementById("filter-finding-req").value;
    const toolFilter = document.getElementById("filter-finding-tool").value;

    const findings = (report.findings || []).filter((f) => {
      if (reqFilter && f.req_id !== reqFilter) return false;
      if (toolFilter && f.tool !== toolFilter) return false;
      return true;
    });

    if (findings.length === 0) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7" }, "0 achados registrados para os filtros selecionados."));
      tbody.appendChild(tr);
      return;
    }

    findings.forEach((f) => {
      const tr = el("tr");
      tr.appendChild(el("td", null, "#" + f.id));
      tr.appendChild(el("td", null, f.req_id));
      tr.appendChild(el("td", null, f.tool + " (" + f.rule_or_plugin_id + ")"));
      tr.appendChild(el("td", null, f.severity + " / " + f.confidence));

      const tdLoc = el("td");
      tdLoc.appendChild(el("code", null, f.primary_location));
      tr.appendChild(tdLoc);

      const tdStatus = el("td");
      if (f.is_false_positive) {
        tdStatus.appendChild(el("span", { className: "badge badge-MANUAL_REQUIRED" }, "Falso Positivo"));
        if (f.fp_reason) {
          tdStatus.appendChild(el("div", { style: "font-size:11px; margin-top:4px;" }, f.fp_reason));
        }
      } else {
        tdStatus.appendChild(el("span", { className: "badge badge-FAIL" }, "Ativo"));
      }
      tr.appendChild(tdStatus);

      const tdActions = el("td", { className: "no-print" });
      const btnWrap = el("div", { style: "display:flex; gap:6px; flex-wrap:wrap;" });

      const evBtn = el("button", { type: "button", className: "fluent-btn" }, "Ver Evidência");
      evBtn.addEventListener("click", () => openEvidenceModal(f.id));

      const fpBtn = el(
        "button",
        { type: "button", className: "fluent-btn" },
        f.is_false_positive ? "Reverter FP" : "Marcar FP"
      );
      fpBtn.addEventListener("click", () => openTriageModal(f));

      btnWrap.appendChild(evBtn);
      btnWrap.appendChild(fpBtn);
      tdActions.appendChild(btnWrap);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  }

  // ===========================================================================
  // Evidence Viewer Modal & False Positive Triage Modal
  // ===========================================================================

  async function openEvidenceModal(findingId) {
    const dialog = document.getElementById("evidence-dialog");
    const body = document.getElementById("evidence-dialog-body");
    const title = document.getElementById("evidence-dialog-title");
    if (!dialog || !body) return;

    clearChildren(body);
    const resp = await fetch("/api/findings/" + encodeURIComponent(String(findingId)) + "/evidence");
    if (!resp.ok) return;
    const data = await resp.json();
    const f = data.finding;

    if (title) {
      title.textContent = "Evidência Navegável — Achado #" + f.id + " (" + f.req_id + ")";
    }

    body.appendChild(
      el(
        "p",
        { style: "margin:0;" },
        "Regra/Plugin: " + f.rule_or_plugin_id + " | Localização: " + f.primary_location
      )
    );
    body.appendChild(el("p", { style: "margin:0; font-weight:600;" }, f.title));

    (data.evidences || []).forEach((ev) => {
      if (ev.code_snippet) {
        body.appendChild(
          el("div", { style: "font-weight:600;" }, "Trecho de Código (" + ev.file_path + ":" + ev.line_start + "):")
        );
        body.appendChild(el("pre", { className: "code-block" }, ev.code_snippet));
      }
      if (ev.http_request || ev.http_response) {
        body.appendChild(
          el("div", { style: "font-weight:600;" }, "Transação HTTP (" + (ev.http_method || "GET") + " " + (ev.http_url || "") + "):")
        );
        body.appendChild(
          el(
            "pre",
            { className: "code-block" },
            (ev.http_request || "") + "\n---\n" + (ev.http_response || "")
          )
        );
      }
    });

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function openRequirementModal(v) {
    const dialog = document.getElementById("evidence-dialog");
    const body = document.getElementById("evidence-dialog-body");
    const title = document.getElementById("evidence-dialog-title");
    if (!dialog || !body) return;

    clearChildren(body);
    if (title) {
      title.textContent = "Detalhes da Verificação — " + v.req_id + " (" + (safeText(v.section_name) || deriveSectionId(v)) + ")";
    }

    const headerRow = el("div", { style: "display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:8px;" });
    headerRow.appendChild(createVerdictBadge(v.status));
    headerRow.appendChild(el("span", { style: "font-weight:600;" }, "Confiança: " + v.confidence_level));
    headerRow.appendChild(
      el(
        "span",
        { style: "color:var(--colorNeutralForeground3); font-size:12px;" },
        "Ferramentas: " + ((v.tools_used || []).join(", ") || "Nenhuma")
      )
    );
    body.appendChild(headerRow);

    body.appendChild(el("div", { style: "font-weight:600; margin-top:4px;" }, "O que foi verificado:"));
    const descBox = el("div", { style: "margin:0 0 8px 0; font-size:13px;" });
    appendRequirementDescription(descBox, v, "req-description", false);
    body.appendChild(descBox);

    // AI Evaluation Special Card if ai_evaluator is used or mentioned
    const isAiUsed =
      (v.tools_used || []).includes("ai_evaluator") ||
      (v.positive_evidence || []).some((e) => e.includes("AIEvaluatorAgent") || e.includes("modelo IA")) ||
      (v.rationale || "").includes("AIEvaluatorAgent");

    if (isAiUsed) {
      const aiCard = el("div", {
        style:
          "border:1px solid var(--colorNeutralStroke1); border-left:4px solid var(--colorBrandForegroundLink); " +
          "border-radius:4px; padding:12px; background:var(--colorNeutralBackground2); margin:4px 0;",
      });
      aiCard.appendChild(
        el(
          "div",
          { style: "font-weight:600; color:var(--colorBrandForegroundLink); margin-bottom:6px;" },
          "🤖 Avaliação Assistida por IA (AIEvaluatorAgent)"
        )
      );
      aiCard.appendChild(
        el("p", { style: "margin:0 0 8px 0; font-size:13px;" }, v.rationale || "Veredito emitido com base em modelo de IA.")
      );

      const snippets = (v.positive_evidence || []).filter(
        (e) => !e.startsWith("Semgrep executou") && !e.startsWith("OWASP ZAP executou")
      );
      if (snippets.length > 0) {
        aiCard.appendChild(
          el("div", { style: "font-size:12px; font-weight:600; margin-bottom:4px;" }, "Evidências e Arquivos Inspecionados:")
        );
        const ul = el("ul", { style: "margin:0; padding-left:18px; font-size:12px;" });
        snippets.forEach((s) => ul.appendChild(el("li", null, s)));
        aiCard.appendChild(ul);
      }
      body.appendChild(aiCard);
    }

    body.appendChild(el("div", { style: "font-weight:600; margin-top:8px;" }, "Justificativa Técnica do Veredito:"));
    body.appendChild(el("p", { style: "margin:0; font-size:13px;" }, v.rationale || "Sem justificativa"));

    body.appendChild(el("div", { style: "font-weight:600; margin-top:8px;" }, "Cobertura Declarada:"));
    body.appendChild(el("p", { style: "margin:0; font-size:13px;" }, v.coverage_declared || "N/A"));

    if ((v.positive_evidence || []).length > 0) {
      body.appendChild(el("div", { style: "font-weight:600; margin-top:8px;" }, "Evidências Positivas:"));
      const evUl = el("ul", { style: "margin:0; padding-left:18px; font-size:12px;" });
      (v.positive_evidence || []).forEach((ev) => evUl.appendChild(el("li", null, ev)));
      body.appendChild(evUl);
    }

    if (v.limitations) {
      body.appendChild(el("div", { style: "font-weight:600; margin-top:8px;" }, "Limitações Conhecidas:"));
      body.appendChild(el("p", { style: "margin:0; font-size:12px; color:var(--colorNeutralForeground3);" }, v.limitations));
    }

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function openTriageModal(finding) {
    const dialog = document.getElementById("triage-dialog");
    if (!dialog) return;
    document.getElementById("triage-finding-id").value = String(finding.id);
    document.getElementById("triage-is-fp").value = finding.is_false_positive ? "false" : "true";
    document.getElementById("triage-justification").value = finding.fp_reason || "";
    document.getElementById("triage-dialog-title").textContent =
      "Triagem de Falso Positivo — Achado #" + finding.id + " (" + finding.req_id + ")";

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function initModalsAndFilters() {
    const closeEvBtn = document.getElementById("close-evidence-btn");
    const evDialog = document.getElementById("evidence-dialog");
    if (closeEvBtn && evDialog) {
      closeEvBtn.addEventListener("click", () => {
        if (typeof evDialog.close === "function") evDialog.close();
        else evDialog.removeAttribute("open");
      });
    }

    const cancelTriageBtn = document.getElementById("cancel-triage-btn");
    const triageDialog = document.getElementById("triage-dialog");
    if (cancelTriageBtn && triageDialog) {
      cancelTriageBtn.addEventListener("click", () => {
        if (typeof triageDialog.close === "function") triageDialog.close();
        else triageDialog.removeAttribute("open");
      });
    }

    const triageForm = document.getElementById("triage-form");
    if (triageForm) {
      triageForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const findingId = document.getElementById("triage-finding-id").value;
        const isFp = document.getElementById("triage-is-fp").value === "true";
        const justification = document.getElementById("triage-justification").value.trim();

        const resp = await fetch("/api/findings/" + encodeURIComponent(findingId) + "/triage", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            is_false_positive: isFp,
            justification: justification,
            actor: "avaliador_local",
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          showAlert("Erro na triagem: " + (data.detail || "Justificativa inválida"), true);
          return;
        }
        if (triageDialog) {
          if (typeof triageDialog.close === "function") triageDialog.close();
          else triageDialog.removeAttribute("open");
        }
        showAlert(
          "Achado #" +
            findingId +
            " atualizado. Novo veredito de " +
            data.req_id +
            ": " +
            data.updated_verdict.status +
            " (% PASS: " +
            data.updated_run_metrics.pass_percentage +
            "%).",
          false
        );
        if (state.activeRunId) {
          await loadRunDashboard(state.activeRunId);
          await loadRunsHistory();
        }
      });
    }

    ["filter-verdict-status", "filter-verdict-section"].forEach((id) => {
      const node = document.getElementById(id);
      if (node) {
        node.addEventListener("change", () => {
          if (state.currentReport) renderVerdictsTable(state.currentReport);
        });
      }
    });

    ["filter-finding-req", "filter-finding-tool"].forEach((id) => {
      const node = document.getElementById(id);
      if (node) {
        node.addEventListener("change", () => {
          if (state.currentReport) renderFindingsTable(state.currentReport);
        });
      }
    });

    const runSelect = document.getElementById("dashboard-run-select");
    if (runSelect) {
      runSelect.addEventListener("change", () => {
        const val = parseInt(runSelect.value, 10);
        if (val) loadRunDashboard(val);
      });
    }

    const refreshBtn = document.getElementById("refresh-dashboard-btn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        if (state.activeRunId) loadRunDashboard(state.activeRunId);
      });
    }

    const dashSelectiveRerunBtn = document.getElementById("dashboard-selective-rerun-btn");
    if (dashSelectiveRerunBtn) {
      dashSelectiveRerunBtn.addEventListener("click", () => {
        if (!state.activeRunId) {
          showAlert("Selecione uma execução no dashboard antes de abrir a reexecução seletiva.", true);
          return;
        }
        openSelectiveRerunModal(state.activeRunId);
      });
    }

    const exportJsonBtn = document.getElementById("export-json-btn");
    if (exportJsonBtn) {
      exportJsonBtn.addEventListener("click", () => triggerExport("json"));
    }
    const exportHtmlBtn = document.getElementById("export-html-btn");
    if (exportHtmlBtn) {
      exportHtmlBtn.addEventListener("click", () => triggerExport("html"));
    }
    const printPdfBtn = document.getElementById("print-pdf-btn");
    if (printPdfBtn) {
      printPdfBtn.addEventListener("click", () => window.print());
    }
  }

  function triggerExport(format) {
    if (!state.activeRunId) {
      showAlert("Selecione uma execução antes de exportar o relatório.", true);
      return;
    }
    const safeFormat = format === "html" ? "html" : "json";
    const href =
      "/api/runs/" +
      encodeURIComponent(String(state.activeRunId)) +
      "/export?format=" +
      safeFormat;
    const link = el("a", {
      href: href,
      download: "asvs_v1_run_" + state.activeRunId + "_report." + safeFormat,
    });
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // ===========================================================================
  // Run History & Side-by-Side Comparison
  // ===========================================================================

  async function loadRunsHistory() {
    const resp = await fetch("/api/runs");
    if (!resp.ok) return;
    const data = await resp.json();
    state.runsList = data.items || [];

    const dashSelect = document.getElementById("dashboard-run-select");
    const baseSelect = document.getElementById("compare-base-select");
    const targetSelect = document.getElementById("compare-target-select");
    [dashSelect, baseSelect, targetSelect].forEach((sel) => {
      if (!sel) return;
      clearChildren(sel);
      state.runsList.forEach((r) => {
        sel.appendChild(
          el(
            "option",
            { value: String(r.id) },
            "Run #" + r.id + " — " + r.source_path + " (" + r.pass_percentage + "% PASS)"
          )
        );
      });
    });

    if (!state.activeRunId && state.runsList.length > 0) {
      state.activeRunId = state.runsList[0].id;
      await loadRunDashboard(state.activeRunId);
    }

    const tbody = document.getElementById("history-tbody");
    clearChildren(tbody);
    if (state.runsList.length === 0) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7" }, "Nenhuma execução registrada até o momento."));
      tbody.appendChild(tr);
      return;
    }

    state.runsList.forEach((r) => {
      const tr = el("tr");
      const tdId = el("td", { style: "font-weight:700;" }, "#" + r.id);
      if (r.is_selective) {
        const selBadge = el(
          "span",
          {
            className: "badge badge-PASS",
            style: "margin-left:6px; font-size:10px; padding:1px 5px;",
            title: "Reexecução seletiva de requisitos",
          },
          "Seletiva"
        );
        tdId.appendChild(selBadge);
      }
      tr.appendChild(tdId);
      tr.appendChild(el("td", null, r.created_at));
      tr.appendChild(
        el(
          "td",
          null,
          r.source_path + (r.target_url ? " | DAST: " + r.target_url : " (Somente SAST)")
        )
      );
      tr.appendChild(el("td", null, r.status));
      tr.appendChild(el("td", { style: "font-weight:700;" }, r.pass_percentage + "%"));
      tr.appendChild(
        el(
          "td",
          null,
          r.pass_count +
            " PASS / " +
            r.fail_count +
            " FAIL / " +
            r.inconclusive_count +
            " INC / " +
            r.manual_count +
            " MAN"
        )
      );

      const tdAct = el("td");
      const btnWrap = el("div", { style: "display:flex; gap:6px; flex-wrap:wrap;" });
      const openBtn = el("button", { type: "button", className: "fluent-btn" }, "Abrir Dashboard");
      openBtn.addEventListener("click", async () => {
        await loadRunDashboard(r.id);
        activateTab(document.getElementById("tab-dashboard"));
      });
      btnWrap.appendChild(openBtn);

      if (r.status === "COMPLETED" || r.status === "FAILED" || r.status === "CANCELLED") {
        const selBtn = el(
          "button",
          {
            type: "button",
            className: "fluent-btn",
            title: "Reexecutar requisitos específicos da execução #" + r.id,
          },
          "Reexecução Seletiva..."
        );
        selBtn.addEventListener("click", () => {
          openSelectiveRerunModal(r.id);
        });
        btnWrap.appendChild(selBtn);
      }
      tdAct.appendChild(btnWrap);
      tr.appendChild(tdAct);
      tbody.appendChild(tr);
    });
  }

  function initComparisonControls() {
    const btn = document.getElementById("compare-runs-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const baseId = document.getElementById("compare-base-select").value;
      const targetId = document.getElementById("compare-target-select").value;
      if (!baseId || !targetId) return;

      const resp = await fetch(
        "/api/runs/compare?base_run_id=" +
          encodeURIComponent(baseId) +
          "&target_run_id=" +
          encodeURIComponent(targetId)
      );
      if (!resp.ok) return;
      const data = await resp.json();

      const summary = document.getElementById("comparison-summary");
      if (summary) {
        const dPct = data.deltas.pass_percentage;
        const sign = dPct > 0 ? "+" : "";
        summary.textContent =
          "Comparando Run #" +
          data.base_run.id +
          " (" +
          data.base_run.pass_percentage +
          "% PASS) → Run #" +
          data.target_run.id +
          " (" +
          data.target_run.pass_percentage +
          "% PASS) | Delta: " +
          sign +
          dPct +
          "% PASS";
      }

      const tbody = document.getElementById("comparison-tbody");
      clearChildren(tbody);
      (data.requirement_transitions || []).forEach((t) => {
        const tr = el("tr");
        tr.appendChild(el("td", { style: "font-weight:700;" }, t.req_id));
        const tdBase = el("td");
        tdBase.appendChild(createVerdictBadge(t.base_status));
        tr.appendChild(tdBase);
        const tdTarget = el("td");
        tdTarget.appendChild(createVerdictBadge(t.target_status));
        tr.appendChild(tdTarget);
        tr.appendChild(el("td", null, t.changed ? "Sim (Transição)" : "Inalterado"));
        tr.appendChild(
          el(
            "td",
            null,
            t.base_active_findings +
              " → " +
              t.target_active_findings +
              " (Δ " +
              t.delta_findings +
              ")"
          )
        );
        tbody.appendChild(tr);
      });
    });
  }

  // ===========================================================================
  // Authentication, Session & User Management (Feature 007 - RBAC)
  // ===========================================================================

  async function checkAuthSession() {
    try {
      const resp = await fetch("/api/auth/me");
      if (resp.status === 401) {
        showLoginModal();
        return null;
      }
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const user = await resp.json();
      state.currentUser = user;
      updateUserUI(user);

      if (user.must_change_password) {
        showChangePasswordModal();
      }
      return user;
    } catch (_err) {
      showLoginModal();
      return null;
    }
  }

  function updateUserUI(user) {
    const badge = document.getElementById("user-profile-badge");
    const nameEl = document.getElementById("user-display-name");
    const tabUsers = document.getElementById("tab-users");

    if (!user) {
      if (badge) badge.style.display = "none";
      if (tabUsers) tabUsers.style.display = "none";
      return;
    }

    if (badge) badge.style.display = "flex";
    if (nameEl) {
      nameEl.textContent = "👤 " + user.username + " (" + user.role + ")";
    }

    if (tabUsers) {
      if (user.role === "admin") {
        tabUsers.style.display = "inline-block";
      } else {
        tabUsers.style.display = "none";
      }
    }
  }

  function showLoginModal() {
    const dialog = document.getElementById("login-dialog");
    if (dialog && typeof dialog.showModal === "function") {
      const errEl = document.getElementById("login-error-msg");
      if (errEl) {
        errEl.style.display = "none";
        errEl.textContent = "";
      }
      if (!dialog.open) {
        dialog.showModal();
      }
    }
  }

  function showChangePasswordModal() {
    const dialog = document.getElementById("change-password-dialog");
    if (dialog && typeof dialog.showModal === "function") {
      const errEl = document.getElementById("change-password-error-msg");
      if (errEl) {
        errEl.style.display = "none";
        errEl.textContent = "";
      }
      if (!dialog.open) {
        dialog.showModal();
      }
    }
  }

  function initAuthControls() {
    // 1. Login Form
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
      loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const usernameInput = document.getElementById("login-username");
        const passwordInput = document.getElementById("login-password");
        const errEl = document.getElementById("login-error-msg");
        const submitBtn = document.getElementById("login-submit-btn");

        const username = usernameInput ? usernameInput.value.trim() : "";
        const password = passwordInput ? passwordInput.value : "";

        if (!username || !password) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "Por favor, preencha o usuário e a senha.";
          }
          return;
        }

        if (submitBtn) submitBtn.disabled = true;
        try {
          const resp = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username, password: password }),
          });

          const data = await resp.json();
          if (!resp.ok) {
            if (errEl) {
              errEl.style.display = "block";
              errEl.textContent = data.detail || "Usuário ou senha inválidos.";
            }
            return;
          }

          state.currentUser = {
            id: data.user_id,
            username: data.username,
            role: data.role,
            must_change_password: data.must_change_password,
          };
          updateUserUI(state.currentUser);

          const loginDialog = document.getElementById("login-dialog");
          if (loginDialog && typeof loginDialog.close === "function") {
            loginDialog.close();
          }

          if (usernameInput) usernameInput.value = "";
          if (passwordInput) passwordInput.value = "";

          if (data.must_change_password) {
            showChangePasswordModal();
          } else {
            showAlert("Autenticado com sucesso como " + data.username + ".", false);
            scheduleZapAutoCheck();
            await refreshAIStatus();
            await loadRunsHistory();
            if (data.role === "admin") {
              await loadUsersList();
            }
          }
        } catch (_err) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "Erro de conexão ao autenticar.";
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // 2. Change Password Form
    const cpForm = document.getElementById("change-password-form");
    if (cpForm) {
      cpForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const curPassInput = document.getElementById("cp-current-password");
        const newPassInput = document.getElementById("cp-new-password");
        const confPassInput = document.getElementById("cp-confirm-password");
        const errEl = document.getElementById("change-password-error-msg");
        const submitBtn = document.getElementById("change-password-submit-btn");

        const curPass = curPassInput ? curPassInput.value : "";
        const newPass = newPassInput ? newPassInput.value : "";
        const confPass = confPassInput ? confPassInput.value : "";

        if (!curPass || !newPass || !confPass) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "Preencha todos os campos.";
          }
          return;
        }

        if (newPass !== confPass) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "A nova senha e a confirmação não coincidem.";
          }
          return;
        }

        if (newPass.length < 8) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "A nova senha deve possuir no mínimo 8 caracteres.";
          }
          return;
        }

        if (submitBtn) submitBtn.disabled = true;
        try {
          const resp = await fetch("/api/auth/change-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ current_password: curPass, new_password: newPass }),
          });

          const data = await resp.json();
          if (!resp.ok) {
            if (errEl) {
              errEl.style.display = "block";
              errEl.textContent = data.detail || "Falha ao alterar senha.";
            }
            return;
          }

          if (state.currentUser) {
            state.currentUser.must_change_password = false;
          }

          const cpDialog = document.getElementById("change-password-dialog");
          if (cpDialog && typeof cpDialog.close === "function") {
            cpDialog.close();
          }

          if (curPassInput) curPassInput.value = "";
          if (newPassInput) newPassInput.value = "";
          if (confPassInput) confPassInput.value = "";

          showAlert("Senha alterada com sucesso! Você já pode utilizar todas as funcionalidades.", false);
          await refreshAIStatus();
          await loadRunsHistory();
          if (state.currentUser && state.currentUser.role === "admin") {
            await loadUsersList();
          }
        } catch (_err) {
          if (errEl) {
            errEl.style.display = "block";
            errEl.textContent = "Erro ao conectar ao servidor.";
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // 3. Logout Buttons
    const logoutBtn = document.getElementById("logout-btn");
    const cpLogoutBtn = document.getElementById("change-password-logout-btn");

    async function handleLogout() {
      try {
        await fetch("/api/auth/logout", { method: "POST" });
      } catch (_e) {}
      state.currentUser = null;
      updateUserUI(null);

      const cpDialog = document.getElementById("change-password-dialog");
      if (cpDialog && typeof cpDialog.close === "function") {
        cpDialog.close();
      }
      showLoginModal();
    }

    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
    if (cpLogoutBtn) cpLogoutBtn.addEventListener("click", handleLogout);

    // 4. User Management Controls (Tab 6 - Admin)
    const createUserForm = document.getElementById("create-user-form");
    if (createUserForm) {
      createUserForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const usernameEl = document.getElementById("new-user-username");
        const passwordEl = document.getElementById("new-user-password");
        const roleEl = document.getElementById("new-user-role");
        const feedbackEl = document.getElementById("create-user-feedback");
        const submitBtn = document.getElementById("btn-create-user");

        const username = usernameEl ? usernameEl.value.trim() : "";
        const password = passwordEl ? passwordEl.value : "";
        const role = roleEl ? roleEl.value : "user";

        if (!username || !password) {
          if (feedbackEl) {
            feedbackEl.style.display = "block";
            feedbackEl.style.background = "var(--colorPaletteRedBackground1)";
            feedbackEl.style.color = "var(--colorPaletteRedForeground1)";
            feedbackEl.textContent = "Preencha todos os campos do formulário.";
          }
          return;
        }

        if (submitBtn) submitBtn.disabled = true;
        try {
          const resp = await fetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username, password: password, role: role }),
          });
          const data = await resp.json();
          if (!resp.ok) {
            if (feedbackEl) {
              feedbackEl.style.display = "block";
              feedbackEl.style.background = "var(--colorPaletteRedBackground1)";
              feedbackEl.style.color = "var(--colorPaletteRedForeground1)";
              feedbackEl.textContent = data.detail || "Erro ao criar usuário.";
            }
            return;
          }

          if (feedbackEl) {
            feedbackEl.style.display = "block";
            feedbackEl.style.background = "var(--colorPaletteGreenBackground1)";
            feedbackEl.style.color = "var(--colorPaletteGreenForeground1)";
            feedbackEl.textContent = "Usuário '" + data.username + "' cadastrado com sucesso (deverá trocar de senha no 1º login).";
          }
          if (usernameEl) usernameEl.value = "";
          if (passwordEl) passwordEl.value = "";
          await loadUsersList();
        } catch (_err) {
          if (feedbackEl) {
            feedbackEl.style.display = "block";
            feedbackEl.style.background = "var(--colorPaletteRedBackground1)";
            feedbackEl.style.color = "var(--colorPaletteRedForeground1)";
            feedbackEl.textContent = "Erro de conexão ao criar usuário.";
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }
  }

  async function loadUsersList() {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;

    try {
      const resp = await fetch("/api/users");
      if (!resp.ok) {
        clearChildren(tbody);
        const tr = el("tr");
        const td = el("td", { colspan: "7", style: "padding:16px; text-align:center; color:var(--colorPaletteRedForeground1);" }, "Acesso negado ou erro ao carregar usuários.");
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
      }

      const users = await resp.json();
      clearChildren(tbody);

      if (!Array.isArray(users) || users.length === 0) {
        const tr = el("tr");
        const td = el("td", { colspan: "7", style: "padding:16px; text-align:center; color:var(--colorNeutralForeground3);" }, "Nenhum usuário cadastrado.");
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
      }

      users.forEach((u) => {
        const tr = el("tr", { style: "border-bottom:1px solid var(--colorNeutralStroke1);" });
        tr.appendChild(el("td", { style: "padding:8px;" }, String(u.id)));
        tr.appendChild(el("td", { style: "padding:8px; font-weight:600;" }, u.username));

        const tdRole = el("td", { style: "padding:8px;" });
        const roleBadge = el("span", {
          className: u.role === "admin" ? "badge badge-PASS" : "badge badge-INCONCLUSIVE",
        }, u.role.toUpperCase());
        tdRole.appendChild(roleBadge);
        tr.appendChild(tdRole);

        tr.appendChild(el("td", { style: "padding:8px;" }, u.must_change_password ? "Sim" : "Não"));

        const tdStatus = el("td", { style: "padding:8px;" });
        const statusBadge = el("span", {
          className: u.is_active ? "badge badge-PASS" : "badge badge-FAIL",
        }, u.is_active ? "ATIVO" : "INATIVO");
        tdStatus.appendChild(statusBadge);
        tr.appendChild(tdStatus);

        const dateStr = u.created_at ? new Date(u.created_at).toLocaleString("pt-BR") : "-";
        tr.appendChild(el("td", { style: "padding:8px; font-size:12px; color:var(--colorNeutralForeground2);" }, dateStr));

        const tdAction = el("td", { style: "padding:8px;" });
        const toggleBtn = el("button", {
          type: "button",
          className: u.is_active ? "fluent-btn fluent-btn-danger" : "fluent-btn fluent-btn-primary",
          style: "padding:2px 8px; font-size:12px;",
        }, u.is_active ? "Desativar" : "Ativar");

        if (state.currentUser && state.currentUser.id === u.id) {
          toggleBtn.disabled = true;
          toggleBtn.title = "Não é permitido desativar sua própria conta ativa.";
        } else {
          toggleBtn.addEventListener("click", async () => {
            toggleBtn.disabled = true;
            try {
              const patchResp = await fetch("/api/users/" + encodeURIComponent(u.id) + "/status", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: !u.is_active }),
              });
              if (!patchResp.ok) {
                const errData = await patchResp.json();
                showAlert(errData.detail || "Erro ao alterar status do usuário.", true);
              } else {
                await loadUsersList();
              }
            } catch (_e) {
              showAlert("Falha ao comunicar com o servidor.", true);
            } finally {
              toggleBtn.disabled = false;
            }
          });
        }
        tdAction.appendChild(toggleBtn);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
      });
    } catch (_err) {
      clearChildren(tbody);
      const tr = el("tr");
      const td = el("td", { colspan: "7", style: "padding:16px; text-align:center; color:var(--colorPaletteRedForeground1);" }, "Erro ao carregar lista de usuários.");
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
  }

  // ===========================================================================
  // Bootstrap on DOMContentLoaded
  // ===========================================================================

  // Ensure collapsible technical details are fully expanded in print/PDF output.
  window.addEventListener("beforeprint", () => {
    document.querySelectorAll("details.tech-details").forEach((d) => d.setAttribute("open", ""));
  });

  document.addEventListener("DOMContentLoaded", async () => {
    initThemeToggle();
    initTabs();
    const heroCta = document.getElementById("compliance-hero-cta");
    if (heroCta) {
      heroCta.addEventListener("click", () => activateTab(document.getElementById("tab-assessment")));
    }
    initAssessmentForm();
    initModalsAndFilters();
    initSelectiveRerunControls();
    initComparisonControls();
    initAuthControls();
    scheduleZapAutoCheck();

    const currentUser = await checkAuthSession();
    if (currentUser) {
      scheduleZapAutoCheck();
      await refreshAIStatus();
      await loadRunsHistory();
      if (currentUser.role === "admin") {
        await loadUsersList();
      }
    }
  });
})();

