import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
} from '@xyflow/react';
import type { OnEdgesChange, OnNodesChange } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback } from 'react';
import { LeftPanel } from './components/LeftPanel';
import { RightPanel } from './components/RightPanel';
import { AgentNode } from './nodes/AgentNode';
import { BlackboardNode } from './nodes/BlackboardNode';
import { BrainNode } from './nodes/BrainNode';
import { usePlatformStore } from './store/platformStore';

const nodeTypes = { agent: AgentNode, blackboard: BlackboardNode, brain: BrainNode };

function FlowCanvas() {
  const nodes = usePlatformStore((s) => s.nodes);
  const edges = usePlatformStore((s) => s.edges);
  const onNodesChange: OnNodesChange = useCallback((changes) => {
    usePlatformStore.setState((st) => ({ nodes: applyNodeChanges(changes, st.nodes) }));
  }, []);
  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    usePlatformStore.setState((st) => ({ edges: applyEdgeChanges(changes, st.edges) }));
  }, []);

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        minZoom={0.4}
        maxZoom={1.2}
        fitView
        proOptions={{ hideAttribution: true }}
        className="!bg-transparent"
        defaultEdgeOptions={{ style: { strokeWidth: 1.2 } }}
      >
        <Background color="rgb(51 65 85 / 0.35)" gap={20} size={1} />
        <Controls
          className="!m-2 !overflow-hidden !rounded-lg !border !border-slate-600/50 !bg-slate-900/80 !shadow-lg"
          showInteractive={false}
        />
        <MiniMap
          className="!m-2 !overflow-hidden !rounded-lg !border !border-slate-600/50 !bg-slate-900/60"
          maskColor="rgb(0 0 0 / 0.45)"
          nodeColor={() => 'rgb(34 211 238 / 0.5)'}
        />
      </ReactFlow>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-700/50 bg-panel px-4 py-2 backdrop-blur">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-slate-100">
            智能审核 Agent 集群平台
          </h1>
          <p className="text-[11px] text-slate-500">Blackboard 协作 · Brain 终裁</p>
        </div>
        <div className="text-[10px] text-slate-600">Vite + React 18 + TS · @xyflow/react</div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(240px,280px)_1fr_minmax(260px,300px)] gap-0 border-slate-800/50">
        <LeftPanel />
        <main className="relative min-h-0 min-w-0 border-x border-slate-800/50 bg-[#0c0c14]">
          <ReactFlowProvider>
            <FlowCanvas />
          </ReactFlowProvider>
        </main>
        <RightPanel />
      </div>
    </div>
  );
}
