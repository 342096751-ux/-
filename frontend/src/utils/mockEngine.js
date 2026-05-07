import { clusterStore, resetOutputsFrom, updateAgentConfig } from "../store/clusterStore";

function getByPath(obj, path) {
  return String(path || "")
    .split(".")
    .filter(Boolean)
    .reduce((acc, key) => (acc && key in acc ? acc[key] : undefined), obj);
}

function renderTemplate(template, ctx) {
  return String(template || "").replace(/\{\{\s*([^}]+)\s*\}\}/g, (_, expr) => {
    const val = getByPath(ctx, expr.trim());
    return val == null ? "" : String(val);
  });
}

function parseSchema(schemaText) {
  try {
    return { schema: JSON.parse(schemaText), error: "" };
  } catch (error) {
    return { schema: null, error: `Schema JSON 无法解析: ${String(error.message || error)}` };
  }
}

function validateAgainstSchema(output, schema) {
  if (!schema || schema.type !== "object") return { ok: true, error: "" };
  if (typeof output !== "object" || output === null || Array.isArray(output)) {
    return { ok: false, error: "输出不是 object" };
  }
  const required = Array.isArray(schema.required) ? schema.required : [];
  for (const key of required) {
    if (!(key in output)) return { ok: false, error: `缺少必填字段: ${key}` };
  }
  const props = schema.properties || {};
  for (const key of Object.keys(props)) {
    if (!(key in output)) continue;
    const rule = props[key] || {};
    const val = output[key];
    if (rule.type === "string" && typeof val !== "string") return { ok: false, error: `${key} 必须是 string` };
    if (rule.type === "number" && typeof val !== "number") return { ok: false, error: `${key} 必须是 number` };
    if (Array.isArray(rule.enum) && !rule.enum.includes(val)) {
      return { ok: false, error: `${key} 不在 enum 范围内` };
    }
    if (typeof rule.minimum === "number" && typeof val === "number" && val < rule.minimum) {
      return { ok: false, error: `${key} 小于最小值` };
    }
    if (typeof rule.maximum === "number" && typeof val === "number" && val > rule.maximum) {
      return { ok: false, error: `${key} 大于最大值` };
    }
  }
  return { ok: true, error: "" };
}

function fakeOutputByPrompt(prompt, input, cfg) {
  const text = `${prompt || ""}\n${JSON.stringify(input || {})}`.toLowerCase();
  const risky = /(引流|加微信|私聊|返现|博彩|裸聊|暴力|仇恨|政治对立|诈骗)/.test(text);
  const confidence = risky ? 0.78 : 0.22;
  const threshold = Number(cfg?.confidenceThreshold ?? 0.6);
  const result = {
    verdict: confidence >= threshold ? "违规" : "不违规",
    confidence,
    evidence: risky ? "命中潜在高风险语义" : "未命中明显违规模式",
  };
  return {
    ...result,
    _meta: {
      timestamp: Date.now(),
      durationMs: 600 + Math.round(Math.random() * 700),
      model: cfg?.model || "gpt-4o-mini",
      temperature: Number(cfg?.temperature ?? 0.2),
    },
    _input: {
      systemPrompt: String(cfg?.systemPrompt || ""),
      userPrompt: `请审核以下内容：\n\n${String(input?.content || "")}`,
      context: input,
    },
    _thinking: [
      `1. 开始审核输入内容（${String(input?.content || "").length}字）`,
      risky ? "2. 命中高风险语义与敏感模式，进入严格判定。" : "2. 未命中明显高风险语义，进入常规判定。",
      `3. 结合阈值(${threshold})计算 confidence=${confidence.toFixed(2)}。`,
      `4. 输出 verdict=${result.verdict}，并补充 evidence。`,
    ].join("\n"),
    _rawOutput: JSON.stringify(result, null, 2),
  };
}

function normalizeExpr(expr) {
  return String(expr || "")
    .replace(/\boutput\./g, "ctx.output.")
    .replace(/\binput\./g, "ctx.input.")
    .replace(/\bblackboard\./g, "ctx.blackboard.");
}

function evalRule(rule, ctx) {
  const expr = String(rule?.when || "").trim();
  if (!expr) return false;
  const jsExpr = normalizeExpr(expr);
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function("ctx", `return Boolean(${jsExpr});`);
    return !!fn(ctx);
  } catch {
    return false;
  }
}

function buildAgentInput(cfg, upstreamOutput, blackboard) {
  const input = {};
  for (const f of cfg.inputFields || []) {
    const key = String(f.key || "").trim();
    if (!key) continue;
    let v;
    if (f.source === "blackboard") {
      v = f.from ? getByPath(blackboard, f.from) : blackboard[key];
    } else {
      v = f.from ? getByPath(upstreamOutput, f.from) : upstreamOutput?.[key];
      if (v == null && key === "content") v = blackboard.content;
    }
    if (v == null && f.required) v = "";
    input[key] = v;
  }
  return input;
}

function appendLog(log, onLog) {
  const normalized = {
    id: log?.id || `log_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    timestamp: Number(log?.timestamp || Date.now()),
    from: log?.from || log?.source || "",
    to: log?.to || "",
    messageType: log?.messageType || "self",
    summary: log?.summary || log?.text || "",
    fullContext: log?.fullContext || { input: {}, thinking: "", rawOutput: "", parsedOutput: {} },
    ...log,
  };
  clusterStore.lastRunLogs.unshift(normalized);
  onLog?.(normalized);
}

function nodeNameById(nodes, id) {
  const node = (nodes || []).find((n) => n.id === id);
  return node?.data?.name || node?.data?.label || id || "未知节点";
}

function runValidationRouting({ cfg, output, input, blackboard, nodes, onLog }) {
  const routing = cfg?.routing;
  if (!routing?.enabled || !routing.validatorNodeId) return { output, routedTo: "" };

  const validatorCfg = clusterStore.configByAgentId[routing.validatorNodeId];
  if (!validatorCfg) {
    appendLog(
      {
        at: new Date().toISOString(),
        source: "Router",
        text: `验证器节点不存在: ${routing.validatorNodeId}`,
      },
      onLog,
    );
    return { output, routedTo: routing.successTargetNodeId || "" };
  }

  const maxRounds = Math.max(1, Math.min(3, Number(routing.maxRounds || 1)));
  const successTargetNodeId = routing.successTargetNodeId || "";
  let currentOutput = output;

  for (let round = 1; round <= maxRounds; round += 1) {
    const validationRaw = fakeOutputByPrompt(
      validatorCfg.systemPrompt,
      { ...input, originalOutput: currentOutput, round, nodeName: cfg.name },
      validatorCfg,
    );
    const validatorThreshold = Number(validatorCfg.confidenceThreshold ?? 0.6);
    const verdict = Number(validationRaw.confidence || 0) >= validatorThreshold ? "confirmed" : "challenged";

    appendLog(
      {
        at: new Date().toISOString(),
        source: nodeNameById(nodes, routing.validatorNodeId),
        text: `${cfg.name} 第${round}轮验证: ${verdict}`,
      },
      onLog,
    );

    if (verdict === "confirmed") {
      appendLog(
        {
          at: new Date().toISOString(),
          source: "Router",
          text: `${cfg.name} 验证通过 -> ${nodeNameById(nodes, successTargetNodeId)}`,
        },
        onLog,
      );
      return { output: currentOutput, routedTo: successTargetNodeId };
    }

    if (routing.challengeAction === "arbitrate" && routing.arbitratorNodeId) {
      const arbitratorCfg = clusterStore.configByAgentId[routing.arbitratorNodeId];
      if (arbitratorCfg) {
        const arbitration = fakeOutputByPrompt(
          arbitratorCfg.systemPrompt,
          { originalOutput: currentOutput, validatorChallenge: validationRaw, fromNode: cfg.name },
          arbitratorCfg,
        );
        const arbitratedOutput = {
          ...arbitration,
          finalVerdict: arbitration.verdict || "不违规",
          _arbitratedFrom: cfg.id,
        };
        appendLog(
          {
            at: new Date().toISOString(),
            source: nodeNameById(nodes, routing.arbitratorNodeId),
            text: `对 ${cfg.name} 作出仲裁: ${arbitratedOutput.finalVerdict}`,
          },
          onLog,
        );
        return { output: arbitratedOutput, routedTo: successTargetNodeId };
      }
    }

    appendLog(
      {
        at: new Date().toISOString(),
        source: cfg.name,
        text: `第${round}轮被质疑，返回重试。`,
      },
      onLog,
    );
  }

  appendLog(
    {
      at: new Date().toISOString(),
      source: "Router",
      text: `${cfg.name} 达到最大辩论轮数，结束并发送到 ${nodeNameById(nodes, successTargetNodeId)}`,
    },
    onLog,
  );
  return { output: currentOutput, routedTo: successTargetNodeId };
}

export async function runMockEngine({ graph, inputText, startAtAgentId = "", onLog }) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const agentIds = nodes.filter((n) => n.kind === "agent").map((n) => n.id);
  const inboundCount = new Map(nodes.map((n) => [n.id, 0]));
  const outgoing = new Map(nodes.map((n) => [n.id, []]));
  edges.forEach((edge) => {
    inboundCount.set(edge.target, (inboundCount.get(edge.target) || 0) + 1);
    const list = outgoing.get(edge.source) || [];
    list.push(edge.target);
    outgoing.set(edge.source, list);
  });

  const startNodeIds = nodes
    .filter((n) => (inboundCount.get(n.id) || 0) === 0)
    .map((n) => n.id);
  const startIds = startAtAgentId ? [startAtAgentId] : startNodeIds;

  clusterStore.runState.order = agentIds;
  clusterStore.runState.currentIndex = 0;
  clusterStore.running = true;
  clusterStore.pausedNodeId = "";
  if (!startAtAgentId) clusterStore.lastRunLogs = [];
  if (startAtAgentId) resetOutputsFrom(startAtAgentId);

  const blackboard = { content: inputText, context: "shared-memory", ts: Date.now() };
  const outputs = {};
  const completed = new Set();
  const runningPromises = new Map();
  const arrivedCount = new Map();
  const pendingInputs = new Map();

  async function executeNode(nodeId, upstreamOutput = { content: inputText }, force = false) {
    if (!nodeId) return;
    if (!force) {
      pendingInputs.set(nodeId, upstreamOutput);
      const count = Number(arrivedCount.get(nodeId) || 0) + 1;
      arrivedCount.set(nodeId, count);
      const need = Math.max(1, Number(inboundCount.get(nodeId) || 0));
      if (count < need) return;
    }
    if (completed.has(nodeId)) return;
    if (runningPromises.has(nodeId)) return runningPromises.get(nodeId);
    const agentId = nodeId;
    const cfg = clusterStore.configByAgentId[agentId];
    if (!cfg) return;
    const task = (async () => {
      clusterStore.runState.currentIndex += 1;
      clusterStore.pausedNodeId = agentId;
      const inputSource = pendingInputs.get(nodeId) || upstreamOutput || { content: inputText };
      const input = buildAgentInput(cfg, inputSource, blackboard);
      const output = fakeOutputByPrompt(cfg.systemPrompt, input, cfg);

      const { schema, error: schemaParseErr } = parseSchema(cfg.outputSchema);
      const check = schemaParseErr ? { ok: false, error: schemaParseErr } : validateAgainstSchema(output, schema);

      updateAgentConfig(agentId, {
        lastOutput: output,
        schemaError: check.ok ? "" : check.error,
      });
      outputs[agentId] = output;

      appendLog(
      {
        at: new Date().toISOString(),
        timestamp: Date.now(),
        from: cfg.name,
        to: "",
        messageType: "self",
        summary: check.ok
          ? `${cfg.name} 初审完成：${output.verdict}(${Number(output.confidence || 0).toFixed(2)})`
          : `${cfg.name} 输出格式不匹配`,
        fullContext: {
          input: output?._input || {},
          thinking: output?._thinking || "",
          rawOutput: output?._rawOutput || "",
          parsedOutput: {
            verdict: output?.verdict,
            confidence: output?.confidence,
            evidence: output?.evidence,
          },
        },
        source: cfg.name,
        text: check.ok
          ? `${cfg.name} 输出通过 schema 校验，verdict=${output.verdict}, confidence=${output.confidence}`
          : `${cfg.name} 输出格式不匹配：${check.error}`,
      },
      onLog,
      );

      if (!check.ok && cfg.strictMode) {
        clusterStore.running = false;
        appendLog(
        {
          at: new Date().toISOString(),
          source: "Engine",
          text: `严格模式生效：在 ${cfg.name} 处终止。`,
        },
        onLog,
        );
        throw new Error(check.error);
      }

      const routeCtx = { output, input, blackboard };
      const hitRules = (cfg.routeRules || []).filter((r) => evalRule(r, routeCtx));
      for (const rule of hitRules) {
        appendLog(
        {
          at: new Date().toISOString(),
          source: "Router",
          text: `${cfg.name} 触发规则【${rule.when}】 -> ${rule.toAgentId || "(未设置目标)"}`,
        },
        onLog,
        );
        const template = (cfg.messageTemplates || []).find((t) => t.id === rule.templateId) || cfg.messageTemplates?.[0];
        if (template) {
          const rendered = renderTemplate(template.template, {
          input,
          self: { output },
          blackboard,
          dimension: "内容安全",
        });
          appendLog(
          {
            at: new Date().toISOString(),
            timestamp: Date.now(),
            from: cfg.name,
            to: template.targetAgent || rule.toAgentId || "下游",
            messageType: "send",
            summary: `${cfg.name} → ${template.targetAgent || rule.toAgentId || "下游"}：路由消息`,
            fullContext: {
              input: output?._input || {},
              thinking: output?._thinking || "",
              rawOutput: output?._rawOutput || "",
              parsedOutput: output,
            },
            source: cfg.name,
            text: `发给 ${template.targetAgent || rule.toAgentId || "下游"} 的消息：${rendered}`,
          },
          onLog,
          );
        }
      }

      const routed = runValidationRouting({
        cfg,
        output,
        input,
        blackboard,
        nodes,
        onLog,
      });
      if (routed.output && routed.output !== output) {
        updateAgentConfig(agentId, { lastOutput: routed.output });
        outputs[agentId] = routed.output;
      }
      await new Promise((resolve) => setTimeout(resolve, 180));
      const nextIds = outgoing.get(nodeId) || [];
      if (routed.routedTo) {
        await executeNode(routed.routedTo, outputs[nodeId] || output);
      } else if (nextIds.length > 1) {
        await Promise.all(nextIds.map((nextId) => executeNode(nextId, outputs[nodeId] || output)));
      } else if (nextIds.length === 1) {
        await executeNode(nextIds[0], outputs[nodeId] || output);
      }
      completed.add(nodeId);
    })();
    runningPromises.set(nodeId, task);
    try {
      await task;
    } finally {
      runningPromises.delete(nodeId);
    }
  }

  try {
    await Promise.all(startIds.map((id) => executeNode(id, { content: inputText }, true)));
  } catch (error) {
    clusterStore.running = false;
    clusterStore.pausedNodeId = "";
    clusterStore.runState.currentIndex = -1;
    return { ok: false, reason: String(error.message || error) };
  }

  clusterStore.running = false;
  clusterStore.pausedNodeId = "";
  clusterStore.runState.currentIndex = -1;
  return { ok: true };
}
