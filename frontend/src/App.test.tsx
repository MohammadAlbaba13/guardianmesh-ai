import { render,screen,fireEvent,cleanup } from '@testing-library/react';
import { afterEach,it,expect,vi } from 'vitest';
import { testIncident,testTopology,testDomain,testDomains } from './fixtures';
import { ThreatPanel } from './components/Panels';
import App from './App';
const mocks=vi.hoisted(()=>({start:vi.fn(),control:vi.fn(),restart:vi.fn(),approve:vi.fn(),switchDomain:vi.fn()}));
vi.mock('./useGuardian',()=>({useGuardian:()=>({domains:testDomains,domain:testDomain(),topology:testTopology,scenarios:[{id:'camera',title:'Compromised IoT Camera'}],incident:null,error:'',setError:vi.fn(),ready:true,busy:false,connection:'ready',...mocks,initialize:vi.fn()})}));
vi.mock('@xyflow/react',()=>({ReactFlow:({children}:{children:React.ReactNode})=><div data-testid="flow">{children}</div>,Background:()=>null,Controls:()=>null,Handle:()=>null,Position:{Left:'left',Right:'right'},MarkerType:{ArrowClosed:'arrow'}}));
vi.mock('recharts',()=>({ResponsiveContainer:({children}:{children:React.ReactNode})=><div>{children}</div>,AreaChart:()=>null,Area:()=>null,YAxis:()=>null,Tooltip:()=>null}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('requires operator approval when selecting live execution',()=>{
  render(<App/>);
  fireEvent.change(screen.getByLabelText('Network execution'),{target:{value:'LIVE'}});
  expect(screen.getByRole('checkbox',{name:'Demo auto-approval'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Run Autonomous Defense Demo'}));
  expect(mocks.start).toHaveBeenCalledWith('camera','fast',false,expect.objectContaining({execution_mode:'LIVE',manual_approval:true}));
});
it('renders the primary command center and launches the configured demo',()=>{
  render(<App/>);
  expect(screen.getByRole('heading',{name:'Keep the city moving.'})).toBeInTheDocument();
  expect(screen.getByLabelText('Six coordinated agents')).toBeInTheDocument();
  expect(screen.getByText(/SIMULATION REQUESTED.*PER-ACTION PROVENANCE/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Run Autonomous Defense Demo'}));
  expect(mocks.start).toHaveBeenCalledWith('camera','fast',true,expect.objectContaining({execution_mode:'SIMULATION',manual_approval:false}));
  expect(screen.getByRole('button',{name:'Pause'})).toBeDisabled();
});

it('offers all seven backend domains and delegates selection to the shared engine',()=>{
  render(<App/>);
  expect(screen.getByRole('heading',{name:/Autonomous Multi-Domain Resilience & Trust Platform/})).toBeInTheDocument();
  for(const domain of testDomains) expect(screen.getByRole('button',{name:domain.name})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'fintech'}));
  expect(mocks.switchDomain).toHaveBeenCalledWith('fintech');
});

it('uses operational classification without fabricating MITRE or an isolated climate sensor',()=>{
  const domain=testDomain('climate',4);
  const incident=testIncident();
  incident.category='ENVIRONMENTAL';incident.status='CONTAINED';
  incident.classification={threat_type:'Flood warning',confidence:.9,source:'camera',evidence:['Water level exceeded'],reasoning:'Threshold evaluation',techniques:[]};
  const {container}=render(<ThreatPanel domain={domain} incident={incident} topology={domain.topology} approve={vi.fn()} busy={false} onReport={vi.fn()}/>);
  expect(screen.getByText('ENVIRONMENTAL CLASSIFICATION')).toBeInTheDocument();
  expect(screen.getByText('Flood warning')).toBeInTheDocument();
  expect(container.textContent).toContain('4 / 4 CRITICAL SERVICES online.');
  expect(container.textContent).not.toContain('MITRE');
  expect(container.textContent).not.toContain('Source isolated.');
});
it('passes guided/manual configuration from visible controls',()=>{
  render(<App/>);
  fireEvent.click(screen.getByRole('button',{name:/Guided/}));
  fireEvent.click(screen.getByRole('checkbox',{name:'Demo auto-approval'}));
  fireEvent.click(screen.getByRole('button',{name:'Run Autonomous Defense Demo'}));
  expect(mocks.start).toHaveBeenCalledWith('camera','guided',false,expect.objectContaining({manual_approval:true,execution_mode:'SIMULATION'}));
});
it('renders real approval decisions with a safe rejection option',()=>{
  const incident=testIncident();incident.status='AWAITING_APPROVAL';incident.auto_approve=false;
  const approve=vi.fn();
  render(<ThreatPanel incident={incident} topology={testTopology} approve={approve} busy={false} onReport={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Reject · safe fallback'}));expect(approve).toHaveBeenCalledWith('REJECT');
  fireEvent.click(screen.getByRole('button',{name:'Approve'}));expect(approve).toHaveBeenCalledWith('APPROVE');
});
