import { memo, useState } from 'react';
import { ReactFlow, Background, Controls, Handle, Position, MarkerType } from '@xyflow/react';
import type { NodeProps, Node } from '@xyflow/react';
import { Camera, Radio, Router, Network, Hospital, Ambulance, Zap, TrafficCone, Shield, Building2, Cpu, Radar, X, LockKeyhole, ScanLine, Check, LoaderCircle, Smartphone, Fingerprint, Landmark, CreditCard, Factory, Bot, Compass, Leaf, CloudRain, Ticket, Glasses, Database } from 'lucide-react';
import type { Asset, Topology as Twin, Incident, DomainDetail } from '../types';
import { idleAgents } from '../types';
import '@xyflow/react/dist/style.css';

const icons:Record<string,typeof Shield>={camera:Camera,sensor:Radio,gateway:Router,core:Network,hospital:Hospital,emergency:Ambulance,energy:Zap,traffic:TrafficCone,safety:Shield,control:Building2,edge:Cpu,guardian:Radar,device:Smartphone,mobile:Smartphone,identity:Fingerprint,identity_provider:Fingerprint,bank:Landmark,payment:CreditCard,finance:Landmark,factory:Factory,robot:Bot,controller:Cpu,venue:Ticket,tourism:Compass,experience:Glasses,climate:CloudRain,environment:Leaf,database:Database,application:Building2,service:Building2};
type AssetNodeType=Node<{asset:Asset},'asset'>;
const AssetNode=memo(({data,selected}:NodeProps<AssetNodeType>)=>{
  const node=data.asset; const Icon=icons[node.kind]??Network;
  return <div className={`asset-node state-${node.state.toLowerCase()} ${node.critical?'critical-node':''} ${selected?'selected':''}`} data-testid={`asset-${node.id}`}>
    <Handle type="target" position={Position.Left} className="topology-handle topology-handle-target" aria-label={`${node.name} input connector`}/><Handle type="source" position={Position.Right} className="topology-handle topology-handle-source" aria-label={`${node.name} output connector`}/>
    <div className="asset-top"><span className="asset-icon"><Icon size={20}/></span>{node.critical&&<span className="asset-critical">CRITICAL</span>}{node.state==='ISOLATED'&&<LockKeyhole size={15}/>}</div>
    <strong>{node.name}</strong><div className="asset-state"><i/>{node.state.replace('_',' ')}{node.critical&&<span className="asset-uptime">{node.operational?'● online':'offline'}</span>}</div>
  </div>;
});
const nodeTypes={asset:AssetNode};

export function Topology({topology,incident,domain}:{topology:Twin;incident:Incident|null;domain?:DomainDetail|null}) {
  const [selected,setSelected]=useState<string|null>(null);
  const selectedAsset=topology.nodes.find(n=>n.id===selected);
  // React Flow hides nodes until it has measured them. The twin can update while
  // a run is active (and during a reset), so provide stable dimensions up front
  // instead of allowing a state update to briefly drop every node back to hidden.
  const nodes:AssetNodeType[]=topology.nodes.map(asset=>({id:asset.id,type:'asset',position:{x:asset.x,y:asset.y},data:{asset},draggable:false,selected:asset.id===selected,width:194,height:94,zIndex:2,style:{width:194,height:94}}));
  const edges=topology.edges.filter(edge=>edge.kind!=='protected'||edge.enabled).map(edge=>{
    const color=edge.state==='THREAT'?'#ed806e':edge.state==='PROTECTED'?'#77dcb5':edge.state==='BLOCKED'?'#a4798a':edge.kind==='management'?'#60788c':'#6f8ea2';
    return {...edge,animated:edge.state==='THREAT'||edge.state==='PROTECTED',type:'smoothstep',zIndex:1,style:{stroke:color,strokeWidth:edge.state==='NORMAL'?2:3,strokeDasharray:edge.state==='BLOCKED'?'6 5':edge.kind==='management'?'4 5':undefined,opacity:edge.state==='BLOCKED'?.8:edge.kind==='management'?.75:1},markerEnd:{type:MarkerType.ArrowClosed,color,width:16,height:16}};
  });
  return <section className="panel twin-panel" aria-label="Live digital twin">
    <div className="panel-heading"><div><span className="eyebrow">LIVE DIGITAL TWIN</span><h2>{domain?.twin_title??'Operational infrastructure'}</h2></div><span className="micro-label"><i className="status-dot"/>{topology.nodes.length} assets · {topology.nodes.filter(n=>n.critical).length} critical services</span></div>
    <div className="twin-agent-strip" aria-label="Live agent progress">{(incident?.agents??idleAgents).map(agent=><span key={agent.name} className={`trace-${agent.state.toLowerCase()}`} title={`${agent.name}: ${agent.state}. ${agent.finding}`}>{agent.state==='COMPLETE'?<Check size={12}/>:['ANALYZING','EXECUTING'].includes(agent.state)?<LoaderCircle size={12} className="spin"/>:<i/>}{agent.name}</span>)}</div>
    <div className="twin-stage">
      <div className="network-zones"><span>ENDPOINTS & SIGNALS</span><span>NETWORK & DEPENDENCIES</span><span>CRITICAL SERVICES</span></div>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.08}} minZoom={.2} maxZoom={1.8} onNodeClick={(_,node)=>setSelected(node.id)} onPaneClick={()=>setSelected(null)} nodesConnectable={false} zoomOnScroll={false} preventScrolling={false} aria-label="Interactive domain network">
        <Background color="#2a3946" gap={24} size={1}/><Controls showInteractive={false}/>
      </ReactFlow>
      {selectedAsset&&<div className="asset-detail"><button className="icon-button" aria-label="Close asset details" onClick={()=>setSelected(null)}><X size={16}/></button><span className="eyebrow">ASSET INSPECTOR</span><h3>{selectedAsset.name}</h3><p>{selectedAsset.zone} · {selectedAsset.state.replace('_',' ')}</p><dl><div><dt>Service availability</dt><dd>{selectedAsset.operational?'Online':'Offline'}</dd></div><div><dt>Modeled protection</dt><dd>{Math.round(selectedAsset.protection*100)}%</dd></div><div><dt>Simulated latency</dt><dd>{selectedAsset.latency_ms} ms</dd></div>{selectedAsset.trust_score!==undefined&&<div><dt>Context trust</dt><dd>{selectedAsset.trust_score} / 100</dd></div>}{selectedAsset.session_restricted&&<div><dt>Session</dt><dd>Restricted</dd></div>}{selectedAsset.verification_required&&<div><dt>Verification</dt><dd>Required</dd></div>}{selectedAsset.shared&&<div><dt>Infrastructure</dt><dd>Shared</dd></div>}<div><dt>Dependencies</dt><dd>{topology.edges.filter(e=>e.enabled&&(e.source===selectedAsset.id||e.target===selectedAsset.id)).map(e=>e.source===selectedAsset.id?e.target:e.source).join(', ')||'None'}</dd></div><div><dt>{incident?.residual_impact?'Residual risk':'Projected risk'}</dt><dd>{(incident?.residual_impact??incident?.impact)?.impacted.find(n=>n.node_id===selectedAsset.id)?.score??0}/100</dd></div>{incident?.actions.filter(a=>a.target===selectedAsset.id&&a.kind==='qod').map(a=><div key={a.id}><dt>QoD {String(a.result.mode??'PENDING')}</dt><dd>{String(a.result.qos_status??a.status)}<br/>{String(a.result.external_session_id??'No external session')}</dd></div>)}</dl></div>}
      {!incident&&<div className="twin-idle"><ScanLine size={16}/><span>Monitoring all dependency paths</span></div>}
    </div>
    <div className="twin-footer"><div className="legend"><span><i className="legend-normal"/>Online</span><span><i className="legend-threat"/>Threat path</span><span><i className="legend-protected"/>Protected route</span><span><i className="legend-isolated"/>Isolated</span></div><span className="muted">Select an asset to inspect</span></div>
  </section>;
}
