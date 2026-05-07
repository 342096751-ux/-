import { useEffect, useState } from "react";

import { getAgents, listModelConfigs, testAgent, updateAgent } from "../services/api";
import type { AgentConfig, ModelConfig } from "../types/audit";

type Tab =
  | "text_cleaner"
  | "rule_executor"
  | "adversarial_detective"
  | "case_executor"
  | "confidence_evaluator"
  | "chief_judge"
  | "aggregator";

const tabs: Array<{ id: Tab; label: string }> = [
  { id: "text_cleaner", label: "文本清洗员" },
  { id: "rule_executor", label: "规则执行员" },
  { id: "adversarial_detective", label: "对抗侦探" },
  { id: "case_executor", label: "判例执行员" },
  { id: "confidence_evaluator", label: "置信度评估员" },
  { id: "chief_judge", label: "大法官" },
  { id: "aggregator", label: "聚合器" },
];

/** 聚合器中各 Agent 在界面上的中文名（与内部 key 一一对应） */
const AGGREGATOR_WEIGHT_LABELS: Record<string, string> = {
  rule_executor: "规则执行员",
  adversarial_detective: "对抗侦探",
  case_executor: "判例执行员",
  chief_judge: "大法官",
};

const AGGREGATOR_STRATEGY_HINTS: Record<string, string> = {
  one_vote_veto: "任一有效参与结果为「违规」则最终为违规；适合从严管控。当前实现会优先采用置信度评估员的有效票。",
  majority_vote: "按多数 Agent 的判定意见汇总（需满足下方最少参与人数）。",
  weighted_vote: "按下方各 Agent 的权重对意见加权后再汇总，权重越大影响越大。",
  all_pass: "需所有参与 Agent 均为「正常」才判为通过，否则为不通过或需人工复核。",
};

export function AgentsPage() {
  const [tab, setTab] = useState<Tab>("rule_executor");
  const [agents, setAgents] = useState<Record<string, AgentConfig>>({});
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([]);
  const [aggregator, setAggregator] = useState({
    strategy: "one_vote_veto",
    chief_judge_priority: true,
    min_participants: 2,
    confidence_threshold: 0.5,
    weights: {
      rule_executor: 1.0,
      adversarial_detective: 1.2,
      case_executor: 1.0,
      chief_judge: 2.0,
    },
  });

  useEffect(() => {
    getAgents().then(setAgents).catch(() => setAgents({}));
    listModelConfigs().then(setModelConfigs).catch(() => setModelConfigs([]));
  }, []);

  const enabledModelConfigs = modelConfigs.filter((m) => m.enabled);
  const defaultModelConfig = enabledModelConfigs.find((m) => m.is_default) ?? enabledModelConfigs[0];
  const modelOptions = Array.from(
    new Set(
      enabledModelConfigs.flatMap((m) => [m.small_model, m.strong_model]).filter(Boolean),
    ),
  );
  const fallbackModelByAgent: Record<string, string> = {
    text_cleaner: defaultModelConfig?.small_model ?? "gpt-3.5-turbo",
    rule_executor: defaultModelConfig?.small_model ?? "gpt-3.5-turbo",
    adversarial_detective: defaultModelConfig?.small_model ?? "gpt-3.5-turbo",
    case_executor: defaultModelConfig?.small_model ?? "gpt-3.5-turbo",
    confidence_evaluator: defaultModelConfig?.small_model ?? "gpt-3.5-turbo",
    chief_judge: defaultModelConfig?.strong_model ?? "gpt-4o",
  };
  const cfg = agents[tab] ?? {
    enabled: true,
    model: fallbackModelByAgent[tab] ?? "gpt-3.5-turbo",
    temperature: 0.3,
    prompt: "",
    top_k: 5,
  };
  const [testInput, setTestInput] = useState("这是一个测试内容");
  const [testResult, setTestResult] = useState<string>("");
  const promptTemplates: Record<string, string> = {
    text_cleaner: "你是文本清洗员。只做字符级与智能清洗，不改变语义，不加任何解释。输出纯文本。",
    rule_executor: "你是一个内容安全规则执行员，优先依据规则库判断违规。",
    adversarial_detective: "你是对抗侦探，重点识别变体表达和规避手法。",
    case_executor: "你是判例执行员，检索判例后进行多数投票。",
    confidence_evaluator: "你是置信度评估员，对R/V/C结论进行校准，输出冲突检测与是否建议仲裁。",
    chief_judge: "你是大法官，在冲突或不确定时最终仲裁。",
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button key={t.id} className={`rounded px-3 py-2 text-sm ${tab === t.id ? "bg-blue-600 text-white" : "bg-white ring-1 ring-slate-300"}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab !== "aggregator" ? (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <div className="mb-2 text-lg font-semibold">基础配置</div>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={Boolean(cfg.enabled)} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, enabled: e.target.checked } }))} />
                启用状态（{cfg.enabled ? "运行中" : "已停用"}）
              </label>
              <select className="rounded border p-2 text-sm" value={String(cfg.model ?? "gpt-3.5-turbo")} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, model: e.target.value } }))}>
                {modelOptions.length > 0 ? (
                  modelOptions.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                    <option value="gpt-4o">gpt-4o</option>
                  </>
                )}
              </select>
              <div className="md:col-span-2">
                <label className="text-sm">Temperature: {Number(cfg.temperature ?? 0.3).toFixed(1)}（默认0.3，范围0-2）</label>
                <input type="range" min={0} max={2} step={0.1} value={Number(cfg.temperature ?? 0.3)} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, temperature: Number(e.target.value) } }))} />
              </div>
              <input className="rounded border p-2 text-sm" type="number" value={Number(cfg.max_tokens ?? 2048)} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, max_tokens: Number(e.target.value) } }))} placeholder="Max Tokens" />
            </div>
          </div>

          <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <div className="mb-2 text-lg font-semibold">专属参数</div>
            {tab === "text_cleaner" ? (
              <p className="text-xs text-slate-500">无专属参数（仅做预处理输出纯文本到 preprocess_zone）</p>
            ) : tab === "confidence_evaluator" ? (
              <div className="space-y-2">
                <div className="text-xs text-slate-500">weights（历史准确率权重）</div>
                {(["rule_executor", "adversarial_detective", "case_executor"] as const).map((name) => (
                  <div key={name} className="flex items-center justify-between gap-3">
                    <span className="text-sm">{name}</span>
                    <input
                      className="w-40 rounded border p-2 text-sm"
                      type="number"
                      step="0.01"
                      min={0}
                      max={2}
                      value={Number((cfg.weights as Record<string, number> | undefined)?.[name] ?? (name === "rule_executor" ? 0.9 : name === "adversarial_detective" ? 0.85 : 0.8))}
                      onChange={(e) =>
                        setAgents((prev) => ({
                          ...prev,
                          [tab]: {
                            ...cfg,
                            weights: {
                              ...((cfg.weights as Record<string, number> | undefined) ?? {}),
                              [name]: Number(e.target.value),
                            },
                          },
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            ) : (
              <>
                <input className="w-full rounded border p-2 text-sm" type="number" value={Number(cfg.top_k ?? 5)} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, top_k: Number(e.target.value) } }))} />
                <p className="mt-1 text-xs text-slate-500">检索Top-K数量，默认5，范围1-20</p>
              </>
            )}
          </div>

          <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-lg font-semibold">System Prompt</div>
              <select className="rounded border p-2 text-sm" onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, prompt: promptTemplates[e.target.value] ?? cfg.prompt } }))}>
                <option value="">使用模板</option>
                {Object.entries(promptTemplates).map(([k, v]) => (
                  <option key={k} value={k}>{v.slice(0, 14)}...</option>
                ))}
              </select>
            </div>
            <textarea className="min-h-64 w-full rounded border p-3 text-sm" placeholder="编辑System Prompt..." value={String(cfg.prompt ?? "")} onChange={(e) => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, prompt: e.target.value } }))} />
            <div className="mt-3 flex gap-2">
              <button
                className="rounded border px-3 py-2 text-sm"
                onClick={() =>
                  setAgents((prev) => ({
                    ...prev,
                    [tab]: { ...cfg, model: fallbackModelByAgent[tab] ?? String(cfg.model ?? "") },
                  }))
                }
              >
                同步默认模型
              </button>
              <button className="rounded border px-3 py-2 text-sm" onClick={() => setAgents((prev) => ({ ...prev, [tab]: { ...cfg, prompt: promptTemplates[tab] ?? "" } }))}>恢复默认</button>
              <button className="rounded bg-blue-600 px-3 py-2 text-sm text-white" onClick={async () => { const updated = await updateAgent(tab, cfg); setAgents((prev) => ({ ...prev, [tab]: updated })); }}>
                保存
              </button>
              <button
                className="rounded border px-3 py-2 text-sm"
                onClick={() =>
                  setAgents((prev) => ({
                    ...prev,
                    [tab]:
                      tab === "text_cleaner"
                        ? { enabled: true, model: "gpt-3.5-turbo", temperature: 0.0, prompt: promptTemplates[tab] ?? "", top_k: 0, max_tokens: 2048 }
                        :
                      tab === "confidence_evaluator"
                        ? {
                            enabled: true,
                            model: "gpt-3.5-turbo",
                            temperature: 0.3,
                            prompt: promptTemplates[tab] ?? "",
                            top_k: 0,
                            max_tokens: 2048,
                            weights: {
                              rule_executor: 0.9,
                              adversarial_detective: 0.85,
                              case_executor: 0.8,
                            },
                          }
                        : { enabled: true, model: "gpt-3.5-turbo", temperature: 0.3, prompt: promptTemplates[tab] ?? "", top_k: 5, max_tokens: 2048 },
                  }))
                }
              >
                重置默认
              </button>
            </div>
          </div>

          <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <div className="mb-2 text-lg font-semibold">快速测试</div>
            <textarea className="min-h-24 w-full rounded border p-2 text-sm" value={testInput} onChange={(e) => setTestInput(e.target.value)} />
            <button className="mt-2 rounded bg-blue-600 px-3 py-2 text-sm text-white" onClick={async () => {
              const res = await testAgent(tab, testInput);
              setTestResult(`判定: ${res.final_verdict} | 置信度: ${Math.round(res.confidence * 100)}%\n日志数: ${res.logs.length}`);
            }}>运行测试</button>
            <pre className="mt-2 min-h-24 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs text-slate-100">{testResult || "尚未运行测试"}</pre>
          </div>
        </div>
      ) : (
        <div className="space-y-4 rounded-xl bg-white p-4 ring-1 ring-slate-200">
          <div>
            <div className="text-lg font-semibold">聚合器配置</div>
            <p className="mt-1 text-xs text-slate-500">
              汇总各 Agent 的判定为大屏「最终判定」。下方数字仅在对应策略生效时起作用；一票否决主要看是否有任一路判定违规。
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">聚合策略</label>
            <select className="w-full rounded border p-2 text-sm" value={aggregator.strategy} onChange={(e) => setAggregator((s) => ({ ...s, strategy: e.target.value }))}>
              <option value="one_vote_veto">一票否决</option>
              <option value="majority_vote">多数投票</option>
              <option value="weighted_vote">加权投票</option>
              <option value="all_pass">全票通过</option>
            </select>
            <p className="text-xs leading-relaxed text-slate-500">{AGGREGATOR_STRATEGY_HINTS[aggregator.strategy] ?? ""}</p>
          </div>

          <label className="flex cursor-pointer flex-col gap-1 rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm">
            <span className="flex items-center gap-2 font-medium text-slate-800">
              <input type="checkbox" checked={aggregator.chief_judge_priority} onChange={(e) => setAggregator((s) => ({ ...s, chief_judge_priority: e.target.checked }))} />
              大法官优先
            </span>
            <span className="text-xs text-slate-500">
              开启后：若大法官给出了参与式裁决（非「不参与」），则直接以大法官的结论与置信度为准，不再与其他 Agent 做投票合并。
            </span>
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-slate-700">最少生效参与人数</span>
              <input
                className="rounded border p-2 text-sm"
                type="number"
                min={1}
                step={1}
                value={aggregator.min_participants}
                onChange={(e) => setAggregator((s) => ({ ...s, min_participants: Number(e.target.value) }))}
              />
              <span className="text-xs text-slate-500">
                整数。表示至少有多少个 Agent 给出有效判定后，才把他们的意见纳入「多数」或「加权」统计；不足则结果可能仍为待定或沿用默认逻辑。上面的「2」即最少 2 路意见参与汇总。
              </span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-slate-700">置信度阈值</span>
              <input className="rounded border p-2 text-sm" type="number" step="0.1" min={0} max={1} value={aggregator.confidence_threshold} onChange={(e) => setAggregator((s) => ({ ...s, confidence_threshold: Number(e.target.value) }))} />
              <span className="text-xs text-slate-500">
                0～1 之间，如 0.5。含义：某条意见校准后的置信度若低于该阈值，可视为偏不确定、在合并多路意见时降低其权重或转入「存疑」类处理（以后端实际策略为准）。
              </span>
            </label>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <div className="mb-2 text-sm font-medium text-slate-700">各 Agent 投票权重</div>
            <p className="mb-3 text-xs text-slate-500">仅在「加权投票」等需要按份量计票时使用；数值越大，该角色的意见占比越高。以下为相对权重，常与 1.0、2.0 这类比例搭配。</p>
            <div className="space-y-3">
              {Object.keys(aggregator.weights).map((name) => (
                <div key={name} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                  <span className="min-w-[6rem] text-sm text-slate-800">{AGGREGATOR_WEIGHT_LABELS[name] ?? name}</span>
                  <input
                    className="w-full max-w-[12rem] rounded border p-2 text-sm sm:ml-auto"
                    type="number"
                    step="0.1"
                    min={0}
                    value={aggregator.weights[name as keyof typeof aggregator.weights]}
                    onChange={(e) => setAggregator((s) => ({ ...s, weights: { ...s.weights, [name]: Number(e.target.value) } }))}
                  />
                </div>
              ))}
            </div>
          </div>

          <button className="rounded bg-blue-600 px-3 py-2 text-sm text-white" onClick={() => window.alert("聚合器配置已保存（当前为前端态）")}>
            保存聚合器配置
          </button>
        </div>
      )}
    </div>
  );
}
