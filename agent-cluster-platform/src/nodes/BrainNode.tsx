import { Handle, type NodeProps, Position } from '@xyflow/react';
import { BrainCircuit, ShieldAlert, ShieldCheck } from 'lucide-react';
import { usePlatformStore } from '../store/platformStore';
import { cn } from '../utils/cn';

export function BrainNode(_props: NodeProps) {
  const verdict = usePlatformStore((s) => s.brainVerdict);
  const detail = usePlatformStore((s) => s.brainDetail);
  const running = usePlatformStore((s) => s.isRunning);

  return (
    <div
      className={cn(
        'w-[min(300px,28vw)] rounded-2xl border px-3 py-2 shadow-2xl backdrop-blur',
        verdict === '违规' && 'border-red-500/50 bg-red-950/30',
        verdict === '不违规' && 'border-emerald-500/50 bg-emerald-950/30',
        verdict === 'pending' && 'border-violet-500/40 bg-violet-950/25',
      )}
    >
      <Handle type="source" position={Position.Bottom} className="!bg-violet-400" />
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-100">
        {verdict === '违规' && <ShieldAlert className="h-4 w-4 text-red-300" />}
        {verdict === '不违规' && <ShieldCheck className="h-4 w-4 text-emerald-300" />}
        {verdict === 'pending' && <BrainCircuit className="h-4 w-4 text-violet-300" />}
        <span>中枢 Brain</span>
        {running && (
          <span className="ml-auto rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-cyan-300">推理中</span>
        )}
      </div>
      <div
        className={cn(
          'mt-1 text-2xl font-bold tracking-tight',
          verdict === '违规' && 'text-red-200',
          verdict === '不违规' && 'text-emerald-200',
          verdict === 'pending' && 'text-slate-400',
        )}
      >
        {verdict === 'pending' ? '待裁决' : verdict}
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{detail}</p>
    </div>
  );
}
