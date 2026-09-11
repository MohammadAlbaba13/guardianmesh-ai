import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {NetworkEvidence,IncidentReplay,MissionControl,defaultOptions} from './MissionControl';
import {testIncident} from '../fixtures';
import {request} from '../api';
vi.mock('../api',()=>({request:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();vi.unstubAllGlobals();});
it('distinguishes live API proof from sandbox and simulation metrics',()=>{
 const incident=testIncident();incident.execution_mode='LIVE';incident.status='CONTAINED';
 incident.actions=[{id:'qod-1',kind:'qod',target:'hospital',endpoint:'/qod',rationale:'Protect flow',expected_effect:'Priority',status:'COMPLETE',executed_at:null,result:{mode:'LIVE',execution_state:'LIVE',provider:'nokia',provider_environment:'SANDBOX',external_session_id:'session-123',qos_status:'AVAILABLE',http_status:201,verification:'VERIFIED'}}];
 render(<NetworkEvidence incident={incident}/>);
 expect(screen.getByText('LIVE API ACTION')).toBeInTheDocument();expect(screen.getByText('SANDBOX')).toBeInTheDocument();expect(screen.getByText('session-123')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Verify status'}));
 expect(request).toHaveBeenCalledWith('/incidents/GM-TEST/actions/qod-1/lookup',{});
});
it('does not turn a failed live response into verified success',()=>{
 const incident=testIncident();incident.actions=[{id:'qod',kind:'qod',target:'hospital',endpoint:'/qod',rationale:'Priority',expected_effect:'Priority',status:'FAILED',executed_at:null,result:{mode:'LIVE_FAILED',execution_state:'LIVE_FAILED',verification:'NOT_VERIFIED',summary:'AUTH_FAILED'}}];
 render(<NetworkEvidence incident={incident}/>);
 expect(screen.queryByText('LIVE API ACTION')).not.toBeInTheDocument();expect(screen.getByText('LIVE_FAILED')).toBeInTheDocument();expect(screen.getByText('NOT_VERIFIED')).toBeInTheDocument();
});
it('replays stored evidence using only a read request',async()=>{
 const incident=testIncident();incident.status='CONTAINED';vi.mocked(request).mockResolvedValue(incident.timeline);
 render(<IncidentReplay incident={incident}/>);fireEvent.click(screen.getByRole('button',{name:'Replay Incident'}));
 await waitFor(()=>expect(screen.getByText('INCIDENT STARTED')).toBeInTheDocument());
 expect(request).toHaveBeenCalledExactlyOnceWith('/incidents/GM-TEST/timeline');
 fireEvent.change(screen.getByLabelText('Replay position'),{target:{value:'1'}});
 expect(screen.getByText('Synthetic camera attack.')).toBeInTheDocument();
});
it('keeps unavailable live demo disabled and enables local simulation after real preflight',async()=>{
 class Socket {onmessage:((e:{data:string})=>void)|null=null;onerror=null;constructor(){setTimeout(()=>this.onmessage?.({data:'{"status":"READY"}'}),0);}close(){}}
 vi.stubGlobal('WebSocket',Socket);vi.mocked(request).mockResolvedValue({backend:'READY',database:'READY',ai:{state:'UNAVAILABLE'},network:{configured:false,notice:'Missing credentials'}});
 const reset=vi.fn();const props={options:{...defaultOptions,execution_mode:'LIVE' as const},onChange:vi.fn(),active:false,judge:true,onJudge:vi.fn(),connection:'ready',onHero:vi.fn(),onReset:reset,canRun:true};
 const {rerender}=render(<MissionControl {...props}/>);
 await screen.findByText('CONNECTED');expect(screen.getByRole('button',{name:'Start Live Demo'})).toBeDisabled();
 rerender(<MissionControl {...props} options={defaultOptions}/>);
 expect(screen.getByRole('button',{name:'Inject Hospital Incident'})).toBeEnabled();
 fireEvent.click(screen.getByRole('button',{name:'Reset Demo'}));expect(reset).toHaveBeenCalledOnce();
});
