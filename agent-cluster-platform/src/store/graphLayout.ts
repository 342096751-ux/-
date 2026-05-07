import type { Edge, Node } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import type { BrainVerdict, ReviewAgent } from '../types';

const brainId = 'node-brain';
const bbId = 'node-blackboard';

export function buildGraphFromState(
  _userContent: string,
  agents: ReviewAgent[],
  blackboardLines: string[],
  brainVerdict: BrainVerdict,
  brainDetail: string,
): { nodes: Node[]; edges: Edge[] } {
  const brainStatus =
    brainVerdict === 'pending' ? 'pending' : brainVerdict === '违规' ? 'violation' : 'ok';

  const nodes: Node[] = [
    {
      id: brainId,
      type: 'brain',
      position: { x: 300, y: 0 },
      data: { verdict: brainVerdict, detail: brainDetail, status: brainStatus },
    },
    {
      id: bbId,
      type: 'blackboard',
      position: { x: 200, y: 200 },
      data: { lines: blackboardLines },
    },
    ...agents.map((a, i) => {
      const n = agents.length;
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      const r = 240;
      const cx = 380;
      const cy = 320;
      return {
        id: a.id,
        type: 'agent',
        position: { x: cx + r * Math.cos(angle) - 70, y: cy + r * Math.sin(angle) - 36 },
        data: { agent: a },
      } satisfies Node;
    }),
  ];

  const edges: Edge[] = [
    {
      id: 'e-brain-bb',
      source: brainId,
      target: bbId,
      targetHandle: 'brain-in',
      animated: true,
      style: { stroke: 'rgb(100 116 139 / 0.6)' },
      markerEnd: { type: MarkerType.ArrowClosed, color: 'rgb(148 163 184)' },
    },
    ...agents.map((a) => ({
      id: `e-${a.id}-bb`,
      source: a.id,
      target: bbId,
      targetHandle: 'agent-in',
      animated: a.status === 'thinking',
      style: { stroke: 'rgb(34 211 238 / 0.45)' },
      markerEnd: { type: MarkerType.ArrowClosed, color: 'rgb(34 211 238)' },
    })),
  ];

  return { nodes, edges };
}
