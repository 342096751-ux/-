import { Handle, type NodeProps, Position, useNodeId } from '@xyflow/react';
import { Bot } from 'lucide-react';
import { usePlatformStore } from '../store/platformStore';
import { cn } from '../utils/cn';

export function AgentNode(_props: NodeProps) {
  const id = useNodeId() ?? '';
  const a = usePlatformStore((s) => s.agents.find((ag) => ag.id === id));
  if (!a) return null;

  return (
    <div
      className={cn(
        'w-[160px] rounded-xl border bg-slate-900/80 px-3 py-2 shadow-lg backdrop-blur',
        a.status === 'thinking' && 'border-cyan-400/70 shadow-cyan-500/20',
        a.status === 'done' && 'border-slate-500/60',
        a.status === 'idle' && 'border-slate-600/50',
      )}
    >
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-400" />
      <div className="flex items-center gap-2 text-xs font-medium text-slate-100">
        <Bot className="h-4 w-4 shrink-0 text-cyan-300" />
        <span className="truncate">{a.name}</span>
      </div>
      <p className="mt-0.5 line-clamp-2 text-[10px] text-slate-500">{a.role}</p>
      {a.lastNote && (
        <p className="mt-1 line-clamp-2 border-t border-slate-700/60 pt-1 text-[10px] text-slate-400">
          {a.lastNote}
        </p>
      )}
    </div>
  );
}
