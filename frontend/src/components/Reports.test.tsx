import { render,screen,fireEvent,cleanup } from '@testing-library/react';
import { it,expect,vi,afterEach } from 'vitest';
import { Reports } from './Reports';
import { testIncident } from '../fixtures';

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function reportIncident(){
  const incident=testIncident();
  incident.report={generated_at:'2026-09-07T10:00:00Z',executive:{headline:'Recorded outcome',what_happened:'Observed evidence',service_risk:'Graph risk',response:'Protect then isolate',actions_completed:4,availability:'5/6 critical services online',minimum_services_online:5,residual_risk:7,outcome:'Recorded outcome',duration_seconds:23,simulation:true},technical:{incident_id:incident.id,classification:{technique:'T1210'},timeline:incident.timeline}};
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>[{id:incident.id,title:incident.title,status:'CONTAINED',started_at:incident.started_at,has_report:true}]}));
  return incident;
}
it('renders executive metrics from report data and links to the server JSON export',async()=>{
  const incident=reportIncident();
  render(<Reports incident={incident} onClose={vi.fn()}/>);
  expect(await screen.findByText('5/6')).toBeInTheDocument();
  expect(screen.getByText('7')).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Export JSON'})).toHaveAttribute('href','/api/incidents/GM-TEST/report?download=true');
});
it('technical view contains actual incident evidence and close is operable',async()=>{
  const incident=reportIncident();const close=vi.fn();
  render(<Reports incident={incident} onClose={close}/>);
  await screen.findByRole('dialog');
  fireEvent.click(screen.getByRole('tab',{name:'Technical report'}));
  expect(document.querySelector('.technical-report')).toHaveTextContent('INCIDENT_STARTED');
  expect(document.querySelector('.technical-report')).toHaveTextContent('T1210');
  fireEvent.click(screen.getByRole('button',{name:'Close report'}));expect(close).toHaveBeenCalledOnce();
});

it('renders a historical domain denominator and reasoning mode from that report',async()=>{
  const incident=reportIncident();
  Object.assign(incident.report!.executive,{total_services:4,minimum_services_online:4,availability:'4/4 trust services online',domain_name:'Trusted Digital Identity',reasoner_mode:'local_llm',provider_mode:'SIMULATED'});
  render(<Reports incident={incident} onClose={vi.fn()}/>);
  expect(await screen.findByText('4/4')).toBeInTheDocument();
  expect(screen.queryByText('4/6')).not.toBeInTheDocument();
  expect(screen.getByText('Trusted Digital Identity')).toBeInTheDocument();
  expect(screen.getByText(/AI Reasoning: Local LLM/)).toBeInTheDocument();
});
