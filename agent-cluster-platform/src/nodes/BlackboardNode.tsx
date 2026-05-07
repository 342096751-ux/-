import { Handle, type NodeProps, Position } from '@xyflow/react';
import { Chalkboard } from 'lucide-react';
import { usePlatformStore } from '../store/platformStore';
import { cn } from '../utils/cn';

export function BlackboardNode(_props: NodeProps) {
  const lines = usePlatformStore((s) => s.blackboardLines);
  return (
    <div className="w-[min(420px,36vw)] rounded-2xl border border-amber-500/30 bg-amber-950/40 p-3 shadow-2xl backdrop-blur">
      <Handle type="target" position={Position.Top} id="brain-in" className="!h-2 !w-2 !bg-amber-400" />
      <Handle type="target" position={Position.Bottom} id="agent-in" className="!h-2 !w-2 !bg-amber-500/60" />
      <div className="mb-2 flex items-center gap-2 text-amber-200/90">
        <Chalkboard className="h-4 w-4" />
        <span className="text-xs font-semibold tracking-wide">共享黑板 Blackboard</span>
      </div>
      <ul
        className={cn(
          'max-h-[180px] space-y-1.5 overflow-y-auto rounded-lg bg-black/30 p-2 font-mono text-[11px] leading-relaxed text-amber-100/90',
        )}
      >
        {lines.map((line, i) => (
          <li key={i} className="border-b border-amber-500/10 pb-1 last:border-0">
            {line}
          </li>
        ))}
      </ul>
    </div>
  );
}
