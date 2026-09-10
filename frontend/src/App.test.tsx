import { render,screen,fireEvent,cleanup } from '@testing-library/react';
import { afterEach,it,expect,vi } from 'vitest';
import { testIncident,testTopology } from './fixtures';
import { ThreatPanel } from './components/Panels';
import App from './App';
const mocks=vi.hoisted(()=>({start:vi.fn(),control:vi.fn(),restart:vi.fn(),approve:vi.fn()}));
vi.mock('./useGuardian',()=>({useGuardian:()=>({topology:testTopology,scenarios:[{id:'camera',title:'Compromised IoT Camera'}],incident:null,error:'',setError:vi.fn(),ready:true,busy:false,connection:'ready',...mocks,initialize:vi.fn()})}));
vi.mock('@xyflow/react',()=>({ReactFlow:({children}:{children:React.ReactNode})=><div data-testid="flow">{children}</div>,Background:()=>null,Controls:()=>null,Handle:()=>null,Position:{Left:'left',Right:'right'},MarkerType:{ArrowClosed:'arrow'}}));
vi.mock('recharts',()=>({ResponsiveContainer:({children}:{children:React.ReactNode})=><div>{children}</div>,AreaChart:()=>null,Area:()=>null,YAxis:()=>null,Tooltip:()=>null}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('renders the primary command center and launches the configured demo',()=>{
  render(<App/>);
  expect(screen.getByRole('heading',{name:'Keep the city moving.'})).toBeInTheDocument();
  expect(screen.getByLabelText('Six coordinated agents')).toBeInTheDocument();
  expect(screen.getByText('SIMULATED NETWORK-AS-CODE ACTIONS')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Run Autonomous Defense Demo'}));
  expect(mocks.start).toHaveBeenCalledWith('camera','fast',true);
  expect(screen.getByRole('button',{name:'Pause'})).toBeDisabled();
});
it('passes guided/manual configuration from visible controls',()=>{
  render(<App/>);
  fireEvent.click(screen.getByRole('button',{name:/Guided/}));
  fireEvent.click(screen.getByRole('checkbox',{name:'Demo auto-approval'}));
  fireEvent.click(screen.getByRole('button',{name:'Run Autonomous Defense Demo'}));
  expect(mocks.start).toHaveBeenCalledWith('camera','guided',false);
});
it('renders real approval decisions with a safe rejection option',()=>{
  const incident=testIncident();incident.status='AWAITING_APPROVAL';incident.auto_approve=false;
  const approve=vi.fn();
  render(<ThreatPanel incident={incident} topology={testTopology} approve={approve} busy={false} onReport={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Reject · safe fallback'}));expect(approve).toHaveBeenCalledWith('REJECT');
  fireEvent.click(screen.getByRole('button',{name:'Approve'}));expect(approve).toHaveBeenCalledWith('APPROVE');
});
