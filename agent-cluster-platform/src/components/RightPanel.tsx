import { Activity, Gavel, ScrollText } from 'lucide-react';
import { usePlatformStore } from '../store/platformStore';
import { cn } from '../utils/cn';

export function RightPanel() {
  const brainVerdict = usePlatformStore((s) => s.brainVerdict);
  const brainDetail = usePlatformStore((s) => s.brainDetail);
  const logs = usePlatformStore((s) => s.logs);
  const isRunning = usePlatformStore((s) => s.isRunning);

  return (
    <aside className="flex min-h-0 min-w-0 flex-col border-l border-slate-800/50 bg-panel backdrop-blur">
      <div className="shrink-0 border-b border-slate-800/50 p-3">
        <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-violet-300/90">
          <Gavel className="h-3.5 w-3.5" />
          Brain 终裁
        </div>
        <div
          className={cn(
            'rounded-xl border p-2.5',
            brainVerdict === '违规' && 'border-red-500/30 bg-red-950/20',
            brainVerdict === '不违规' && 'border-emerald-500/30 bg-emerald-950/20',
            brainVerdict === 'pending' && 'border-slate-600/50 bg-slate-950/40',
          )}
        >
          {isRunning && (
            <p className="mb-1 text-[10px] text-cyan-400/80">
              <Activity className="mr-1 inline h-3 w-3 animate-pulse" />
              综合黑板与各 Agent 意见中…
            </p>
          )}
          <div
            className={cn(
              'text-2xl font-bold',
              brainVerdict === '违规' && 'text-red-300',
              brainVerdict === '不违规' && 'text-emerald-300',
              brainVerdict === 'pending' && 'text-slate-500',
            )}
          >
            {brainVerdict === 'pending' ? '待输出' : brainVerdict}
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{brainDetail}</p>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden p-2">
        <div className="mb-1 flex items-center gap-1.5 px-1 text-[10px] font-medium text-slate-500">
          <ScrollText className="h-3 w-3" />
          协作日志
        </div>
        <ul className="h-[calc(100%-1.5rem)] space-y-1.5 overflow-y-auto pr-0.5">
          {logs.length === 0 && (
            <li className="px-1 text-[11px] text-slate-600">暂无。点击「开始协作审核」后，按时间倒序显示。</li>
          )}
          {logs.map((l) => (
            <li
              key={l.id}
              className="rounded-md border border-slate-800/50 bg-slate-950/40 px-2 py-1.5 text-[10px] leading-relaxed"
            >
              <span className="font-mono text-slate-600">{l.at}</span>{' '}
              <span className="text-cyan-500/80">{l.source}</span>
              <p className="mt-0.5 text-slate-300">{l.text}</p>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
