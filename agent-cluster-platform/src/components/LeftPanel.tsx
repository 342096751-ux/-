import { Play, RotateCcw, Sparkles } from 'lucide-react';
import { usePlatformStore } from '../store/platformStore';
import { cn } from '../utils/cn';

export function LeftPanel() {
  const userContent = usePlatformStore((s) => s.userContent);
  const setUserContent = usePlatformStore((s) => s.setUserContent);
  const agents = usePlatformStore((s) => s.agents);
  const isRunning = usePlatformStore((s) => s.isRunning);
  const runReview = usePlatformStore((s) => s.runReview);
  const reset = usePlatformStore((s) => s.reset);

  return (
    <aside className="flex min-h-0 flex-col border-r border-slate-800/50 bg-panel backdrop-blur">
      <div className="shrink-0 border-b border-slate-800/50 p-3">
        <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-cyan-300/90">
          <Sparkles className="h-3.5 w-3.5" />
          待审 UGC
        </div>
        <textarea
          value={userContent}
          onChange={(e) => setUserContent(e.target.value)}
          disabled={isRunning}
          className="h-32 w-full resize-none rounded-lg border border-slate-700/60 bg-slate-950/50 p-2 text-xs leading-relaxed text-slate-200 placeholder:text-slate-600 focus:border-cyan-600/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
          placeholder="粘贴或输入要送审的文本/描述…"
        />
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={() => void runReview()}
            disabled={isRunning || !userContent.trim()}
            className={cn(
              'inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition',
              isRunning || !userContent.trim()
                ? 'cursor-not-allowed bg-slate-800 text-slate-500'
                : 'bg-cyan-600 text-white hover:bg-cyan-500',
            )}
          >
            <Play className="h-3.5 w-3.5" />
            开始协作审核
          </button>
          <button
            type="button"
            onClick={reset}
            disabled={isRunning}
            className="inline-flex items-center justify-center rounded-lg border border-slate-600/60 p-1.5 text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
            title="重置"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <h2 className="mb-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">审核 Agent 集群</h2>
        <ul className="space-y-2">
          {agents.map((a) => (
            <li
              key={a.id}
              className="rounded-lg border border-slate-800/60 bg-surface px-2.5 py-2"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-medium text-slate-200">{a.name}</span>
                <span
                  className={cn(
                    'rounded px-1.5 py-0.5 text-[9px] font-medium',
                    a.status === 'idle' && 'bg-slate-800 text-slate-500',
                    a.status === 'thinking' && 'bg-cyan-950 text-cyan-300',
                    a.status === 'done' && 'bg-slate-800 text-emerald-400/90',
                  )}
                >
                  {a.status === 'idle' && '待命中'}
                  {a.status === 'thinking' && '推理'}
                  {a.status === 'done' && '已提交'}
                </span>
              </div>
              <p className="mt-0.5 text-[10px] text-slate-500">{a.role}</p>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
