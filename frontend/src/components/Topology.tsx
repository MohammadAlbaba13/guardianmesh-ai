import { memo, useState } from 'react';
import { ReactFlow, Background, Controls, Handle, Position, MarkerType } from '@xyflow/react';
import type { NodeProps, Node } from '@xyflow/react';
import { Camera, Radio, Router, Network, Hospital, Ambulance, Zap, TrafficCone, Shield, Building2, Cpu, Radar, X, LockKeyhole, ScanLine, Check, LoaderCircle } from 'lucide-react';
import type { Asset, Topology as Twin, Incident } from '../types';
import { idleAgents } from '../types';
import '@xyflow/react/dist/style.css';

const icons:Record<string,typeof Shield>={camera:Camera,sensor:Radio,gateway:Router,core:Network,hospital:Hospital,emergency:Ambulance,energy:Zap,traffic:TrafficCone,safety:Shield,control:Building2,edge:Cpu,guardian:Radar};
type AssetNodeType=Node<{asset:Asset},'asset'>;
const AssetNode=memo(({data,selected}:NodeProps<AssetNodeType>)=>{
  const node=data.asset; const Icon=icons[node.kind]??Network;
  return <div className={`asset-node state-${node.state.toLowerCase()} ${node.critical?'critical-node':''} ${selected?'selected':''}`} data-testid={`asset-${node.id}`}>
    <Handle type="target" position={Position.Left}/><Handle type="source" position={Position.Right}/>
    <div className="asset-top"><span className="asset-icon"><Icon size={20}/></span>{node.critical&&<span className="asset-critical">CRITICAL</span>}{node.state==='ISOLATED'&&<LockKeyhole size={15}/>}</div>
    <strong>{node.name}</strong><div className="asset-state"><i/>{node.state.replace('_',' ')}{node.critical&&<span className="asset-uptime">{node.operational?'● live':'offline'}</span>}</div>
  </div>;
});
const nodeTypes={asset:AssetNode};

export function Topology({topology,incident}:{topology:Twin;incident:Incident|null}) {
  const [selected,setSelected]=useState<string|null>(null);
  const selectedAsset=topology.nodes.find(n=>n.id===selected);
  const nodes:AssetNodeType[]=topology.nodes.map(asset=>({id:asset.id,type:'asset',position:{x:asset.x,y:asset.y},data:{asset},draggable:false,selected:asset.id===selected}));
  const edges=topology.edges.filter(edge=>edge.kind!=='protected'||edge.enabled).map(edge=>{
    const color=edge.state==='THREAT'?'#ed806e':edge.state==='PROTECTED'?'#77dcb5':edge.state==='BLOCKED'?'#775d64':edge.kind==='management'?'#435567':'#46596a';
    return {...edge,animated:edge.state==='THREAT'||edge.state==='PROTECTED',type:'smoothstep',style:{stroke:color,strokeWidth:edge.state==='NORMAL'?1.25:2,strokeDasharray:edge.state==='BLOCKED'?'5 5':edge.kind==='management'?'3 5':undefined,opacity:edge.state==='BLOCKED'?.5:edge.kind==='management'?.5:.9},markerEnd:{type:MarkerType.ArrowClosed,color,width:14,height:14}};
  });
  return <section className="panel twin-panel" aria-label="Live digital twin">
    <div className="panel-heading"><div><span className="eyebrow">LIVE DIGITAL TWIN</span><h2>City infrastructure</h2></div><span className="micro-label"><i className="status-dot"/>14 assets · 6 critical services</span></div>
    <div className="twin-agent-strip" aria-label="Live agent progress">{(incident?.agents??idleAgents).map(agent=><span key={agent.name} className={`trace-${agent.state.toLowerCase()}`} title={`${agent.name}: ${agent.state}. ${agent.finding}`}>{agent.state==='COMPLETE'?<Check size={12}/>:['ANALYZING','EXECUTING'].includes(agent.state)?<LoaderCircle size={12} className="spin"/>:<i/>}{agent.name}</span>)}</div>
    <div className="twin-stage">
      <div className="network-zones"><span>CONNECTED ENDPOINTS</span><span>TELECOM & EDGE</span><span>CRITICAL SERVICES</span></div>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.08}} minZoom={.2} maxZoom={1.8} onNodeClick={(_,node)=>setSelected(node.id)} onPaneClick={()=>setSelected(null)} nodesConnectable={false} zoomOnScroll={false} preventScrolling={false} aria-label="Interactive city network">
        <Background color="#2a3946" gap={24} size={1}/><Controls showInteractive={false}/>
      </ReactFlow>
      {selectedAsset&&<div className="asset-detail"><button className="icon-button" aria-label="Close asset details" onClick={()=>setSelected(null)}><X size={16}/></button><span className="eyebrow">ASSET INSPECTOR</span><h3>{selectedAsset.name}</h3><p>{selectedAsset.zone} · {selectedAsset.state.replace('_',' ')}</p><dl><div><dt>Service availability</dt><dd>{selectedAsset.operational?'Online':'Offline'}</dd></div><div><dt>Protection</dt><dd>{Math.round(selectedAsset.protection*100)}%</dd></div><div><dt>Simulated latency</dt><dd>{selectedAsset.latency_ms} ms</dd></div></dl></div>}
      {!incident&&<div className="twin-idle"><ScanLine size={16}/><span>Monitoring all dependency paths</span></div>}
    </div>
    <div className="twin-footer"><div className="legend"><span><i className="legend-normal"/>Online</span><span><i className="legend-threat"/>Threat path</span><span><i className="legend-protected"/>Protected route</span><span><i className="legend-isolated"/>Isolated</span></div><span className="muted">Select an asset to inspect</span></div>
  </section>;
}
