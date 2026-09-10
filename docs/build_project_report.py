"""Build the evidence-based GuardianMesh report without changing the application.

Screenshots are original browser captures. PDF clipping selects readable regions;
the original PNGs are retained unchanged in report-assets.
"""
import json, math, re, textwrap, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/report-assets'
PDF=ROOT/'GuardianMesh_AI_Complete_Project_Report.pdf'
MD=ROOT/'GuardianMesh_AI_Complete_Project_Report.md'
def read(name): return json.loads((ASSETS/name).read_text(encoding='utf-8-sig'))
R=read('runtime-summary.json')
CAM=read('camera-fast-final.json')
GUIDE=read('camera-guided-uninterrupted.json')
WALK=read('camera-guided-final.json')
IDENT=read('identity-final.json')
ENERGY=read('energy-approve-final.json')
REJECT=read('energy-reject-final.json')
TOPO=read('topology.json')
STATUS=json.loads((ROOT/'docs/report-status.json').read_text())
if isinstance(STATUS,dict): STATUS=STATUS.get('features',STATUS.get('rows',STATUS.get('status',[])))
INK=colors.HexColor('#172936'); MUTED=colors.HexColor('#536777'); TEAL=colors.HexColor('#157e70')
PALE=colors.HexColor('#edf6f3'); LINE=colors.HexColor('#dbe5e8'); DARK=colors.HexColor('#0b1720'); CORAL=colors.HexColor('#bf644c')
for name,file in [('GM','segoeui.ttf'),('GM-Bold','segoeuib.ttf'),('GM-Italic','segoeuii.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('GM',normal='GM',bold='GM-Bold',italic='GM-Italic',boldItalic='GM-Bold')
S=ParagraphStyle('body',fontName='GM',fontSize=10.2,leading=15,textColor=INK,spaceAfter=9)
SM=ParagraphStyle('small',parent=S,fontSize=8.6,leading=12)
CAP=ParagraphStyle('caption',parent=S,fontSize=9,leading=12,textColor=MUTED)
H=ParagraphStyle('heading',parent=S,fontName='GM-Bold',fontSize=13,leading=18,spaceAfter=8)
MONO=ParagraphStyle('mono',parent=S,fontName='Mono',fontSize=8.7,leading=12)
pages=[]; used={}; markdown=[]
c=canvas.Canvas(str(PDF),pagesize=A4,pageCompression=1)
c.setTitle('GuardianMesh AI - Complete Project Report')
c.setAuthor('GuardianMesh AI project verification')
c.setSubject('Actual implementation, screenshots, deterministic incident evidence and verification results')

def clean(t):
    return str(t).replace('\u2011','-').replace('\u2013','-').replace('\u2014',' - ').replace('\u00a0',' ')
def ptext(t):return escape(clean(t)).replace('\n','<br/>')
class Page:
    def __init__(self,section,title,subtitle='',size=A4,key=None):
        self.w,self.h=size; self.m=44; self.width=self.w-88; self.y=self.h-112
        self.n=len(pages)+1; self.key=key or f'page-{self.n}'
        pages.append({'page':self.n,'section':section,'title':title,'key':self.key,'size':size})
        c.setPageSize(size); c.bookmarkPage(self.key)
        c.setFillColor(TEAL);c.rect(0,self.h-7,self.w,7,fill=1,stroke=0)
        c.setFillColor(MUTED);c.setFont('GM-Bold',8.5);c.drawString(44,self.h-35,'GUARDIANMESH AI  /  '+section.upper())
        title_size=min(23,23*self.width/pdfmetrics.stringWidth(title,'GM-Bold',23))
        c.setFillColor(INK);c.setFont('GM-Bold',title_size);c.drawString(44,self.h-70,title)
        if subtitle:
            para=Paragraph(ptext(subtitle),CAP);_,height=para.wrap(self.width,40);para.drawOn(c,44,self.h-82-height)
            self.y=min(self.y,self.h-94-height)
        markdown.append('\n\n## '+section+' - '+title+'\n\n'+subtitle+'\n')
    def para(self,text,style=S,x=None,width=None):
        x=self.m if x is None else x;width=self.width if width is None else width
        q=Paragraph(ptext(text),style);_,h=q.wrap(width,10000)
        self.require(h+9);q.drawOn(c,x,self.y-h);self.y-=h+9
        markdown.append(clean(text)+'\n')
        return h+9
    def rich(self,text,style=S):
        q=Paragraph(text,style);_,h=q.wrap(self.width,10000);self.require(h+9);q.drawOn(c,self.m,self.y-h);self.y-=h+9
    def heading(self,text): self.para(text,H)
    def bullet(self,text):self.para('• '+text)
    def require(self,h):
        if self.y-h<52: raise ValueError(f'Page {self.n} {pages[-1]["title"]}: overflow {h:.1f} at {self.y:.1f}')
    def table(self,headers,rows,widths=None,font=9.1):
        widths=widths or [self.width/len(headers)]*len(headers)
        sty=ParagraphStyle('cell',parent=S,fontSize=font,leading=font*1.34,spaceAfter=0)
        bold=ParagraphStyle('cellhead',parent=sty,fontName='GM-Bold',textColor=colors.white)
        data=[[Paragraph(ptext(v),bold) for v in headers]]+[[Paragraph(ptext(v),sty) for v in row] for row in rows]
        t=Table(data,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f2f6f7')]),('LINEBELOW',(0,0),(-1,0),1,TEAL),('LINEBELOW',(0,1),(-1,-1),.35,LINE)]))
        _,h=t.wrap(self.width,10000);self.require(h+12);t.drawOn(c,self.m,self.y-h);self.y-=h+12
        markdown.append('| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(clean(v).replace('\n','; ') for v in row)+' |' for row in rows)+'\n')
    def code(self,text,font=8.7):
        sty=ParagraphStyle('codeblock',parent=MONO,fontSize=font,leading=font*1.38)
        q=Paragraph(ptext(text).replace(' ','&#160;'),sty);_,h=q.wrap(self.width-22,10000);self.require(h+24)
        c.setFillColor(colors.HexColor('#f0f4f6'));c.roundRect(self.m,self.y-h-14,self.width,h+20,5,fill=1,stroke=0)
        q.drawOn(c,self.m+11,self.y-h-4);self.y-=h+28
        markdown.append('```text\n'+clean(text)+'\n```\n')
    def shot(self,name,caption,crop=None,width=None,max_h=None,x=None):
        width=width or self.width;x=self.m if x is None else x
        path=ASSETS/(name+'.png'); iw,ih=PILImage.open(path).size
        cx,cy,cw,ch=crop or (0,0,iw,ih)
        assert min(cx,cy)>=0 and cx+cw<=iw+1 and cy+ch<=ih+1,(name,crop,(iw,ih))
        scale=width/cw
        if max_h and ch*scale>max_h:scale=max_h/ch;width=cw*scale
        h=ch*scale;cap=Paragraph(ptext(caption),CAP);_,cap_h=cap.wrap(width,10000)
        self.require(h+cap_h+20)
        c.saveState();clip=c.beginPath();clip.rect(x,self.y-h,width,h);c.clipPath(clip,stroke=0,fill=0)
        c.drawImage(ImageReader(str(path)),x-cx*scale,self.y-h-(ih-cy-ch)*scale,width=iw*scale,height=ih*scale)
        c.restoreState();c.setStrokeColor(LINE);c.rect(x,self.y-h,width,h,fill=0,stroke=1)
        cap.drawOn(c,x,self.y-h-cap_h-6);self.y-=h+cap_h+20
        used.setdefault(name,[]).append(self.n)
        markdown.append(f'![{caption}](docs/report-assets/{name}.png)\n')
    def footer(self,source=''):
        if source:
            source_style=ParagraphStyle('source',parent=CAP,fontSize=6.9,leading=8)
            source_p=Paragraph(ptext(source),source_style)
            _,source_h=source_p.wrap(self.width,30)
            assert source_h<=18,(self.n,source)
            source_p.drawOn(c,44,34)
        c.setStrokeColor(LINE);c.line(44,30,self.w-44,30)
        c.setFillColor(MUTED);c.setFont('GM',8);c.drawString(44,17,'LOCAL DETERMINISTIC PROTOTYPE  •  VERIFIED 07 SEPTEMBER 2026')
        c.setFont('GM-Bold',8);c.drawRightString(self.w-44,17,str(self.n));c.showPage()

def title(sec,title,sub='',size=A4,key=None):return Page(sec,title,sub,size,key)
def tech(incident):return incident['report']['technical']
def secdt(i,end):return (datetime.fromisoformat(end)-datetime.fromisoformat(i['started_at'])).total_seconds()
def summary_table(p):
    p.table(['Run','Containment / report','Risk / actions / uptime'],[[name,f"{R[key]['containment_seconds']:.2f}s / {R[key]['report_seconds']:.2f}s",f"{R[key]['peak_risk']} → 0 / {R[key]['actions']} actions / 6 of 6"] for name,key in [('Camera Fast Pitch','camera_fast'),('Camera Guided','camera_guided'),('Identity Fast Pitch','identity'),('Energy manual Approve','energy_approve'),('Energy manual Reject','energy_reject')]],widths=[168,163,176])

# 1 - Cover
p=title('Complete project report','GuardianMesh AI','Autonomous Cyber Resilience for Critical Infrastructure',key='cover')
c.setFillColor(DARK);c.roundRect(44,350,p.width,335,15,fill=1,stroke=0)
c.setFillColor(colors.HexColor('#87e3be'));c.setFont('GM-Bold',57);c.drawString(70,593,'6 / 6')
c.setFont('GM-Bold',18);c.drawString(70,555,'CRITICAL SERVICES ONLINE')
c.setFillColor(colors.white);c.setFont('GM',13);c.drawString(70,519,'Compromised camera isolated. Hospital protected.')
for j,(label,state) in enumerate([('DETECT','Telemetry rule'),('PREDICT','Graph impact'),('DEFEND','Policy + network')]):
    x=70+j*155;c.setFillColor(colors.HexColor('#19313a'));c.roundRect(x,410,139,72,7,fill=1,stroke=0)
    c.setFillColor(colors.HexColor('#87e3be'));c.setFont('GM-Bold',11);c.drawString(x+12,454,label)
    c.setFillColor(colors.white);c.setFont('GM',9);c.drawString(x+12,431,state)
c.setFillColor(colors.HexColor('#aabec7'));c.setFont('GM',9);c.drawString(70,379,'Illustrative architecture motif. Actual application screenshots follow.')
p.y=321
p.para('MENA Ignite Hackathon 2026 - GSMA × Nokia\nSmart Cities, Urban Safety & Mega-Project Infrastructure',H)
p.para('An evidence-based account of the current repository and running local prototype. Includes actual UI captures, six-agent logic, graph risk, approval decisions, incident records, tests, production build and a complete judge rehearsal.')
p.para('Scope: IMPLEMENTED deterministic software + SIMULATED telecom effects. No real Nokia/CAMARA carrier execution, external LLM or authorized carrier sandbox is claimed.',SM)
p.para('Verification date: 07 September 2026. Repository has no commits; source hashes and captured evidence identify the reviewed state.',SM)
p.footer('Project root: C:/Users/LOQ/Documents/ChatGPT/Win')

# 2 - Contents (page references set explicitly by final section bookmarks)
p=title('Reading guide','Contents','28 requested sections; code-backed descriptions, readable evidence, and a final Definition of Done.',key='contents')
contents=[('01','Executive overview',3),('02','Current project status',4),('03','Project architecture',6),('04','Actual data model',8),('05','Digital twin',10),('06','Six-agent system',12),('07','Focused MITRE ATT&CK mapping',15),('08','Graph impact and risk calculation',16),('09','Simulated Network-as-Code',17),('10','Human approval and rejection',19),('11','Camera: complete walkthrough',21),('12','Identity: complete walkthrough',27),('13','Energy: complete walkthrough',29),('14','Guided Demo and controls',31),('15','Fast Pitch Mode',32),('16','Incident reports',33),('17','REST API and Swagger',35),('18','WebSocket event system',37),('19','SQLite persistence',38),('20','Backend and frontend tests',39),('21','Production frontend build',40),('22','Docker configuration',41),('23','Exact Windows startup',42),('24','Judge rehearsal result',43),('25','Visual gallery',44),('26','Limitations',51),('27','Roadmap',52),('28','Final verification matrix',53)]
for num,label,page in contents:
    c.setFont('GM-Bold',9.5);c.setFillColor(TEAL);c.drawString(44,p.y,num)
    c.setFont('GM',10);c.setFillColor(INK);c.drawString(76,p.y,label);c.drawRightString(p.w-44,p.y,str(page))
    c.linkRect('',f'page-{page}',(44,p.y-4,p.w-44,p.y+12),relative=0,thickness=0)
    p.y-=20
p.y-=8
p.para('Evidence convention: S01-S29 refer to original PNG captures in docs/report-assets. Captions identify the incident and the specific state. Crops enlarge genuine screenshots; they do not alter application data.',SM)
p.para('All times in evidence tables use UTC. UI clocks use the browser locale (Asia/Hebron during capture). Test stdout was captured directly from the shell; it is typeset as a transcript, not a fabricated terminal screenshot.',SM)
p.footer('Companion Markdown, source hashes, JSON snapshots, stdout, JUnit XML and screenshot manifest are retained locally.')

# 3
p=title('01 / Executive overview','Defend the service, contain the source')
p.para('GuardianMesh demonstrates a closed defensive workflow for connected city infrastructure. The objective is to contain a compromised endpoint while maintaining connectivity for hospitals, emergency response, energy, traffic management, public safety and city control.')
p.heading('Problem and target users')
p.para('IoT, edge compute and telecom dependencies can connect a low-value endpoint to a high-consequence service. A security analyst, city operations lead or telecom service operator needs to see those dependencies before applying containment. The prototype makes that operational consequence visible in one command center.')
p.heading('What the local prototype contributes')
p.para('Six deterministic logical agents share a typed incident context. They inspect synthetic observations, explain a focused MITRE classification, traverse the dependency graph, order service-preserving actions, enforce policy and generate a traceable report. Network capabilities become a modeled defense actuator rather than only a source of alerts.')
p.table(['Stage','Observed implementation'],[['Attack → detection','Synthetic camera sessions exceed the explicit Sentinel threshold.'],['Classification → impact','T1210 and the camera-to-hospital dependency path appear; peak risk is 80/100.'],['Plan → policy → approval','Routes and QoD precede isolation. Energy shared-segment actions require a decision.'],['Network defense → containment','Local provider results mutate the twin; source isolation removes all attack paths.'],['Service continuity → report','Six operational services remain reachable; reports preserve decisions and measurements.']],widths=[169,338])
p.para('Hackathon context comes from the project brief: MENA Ignite 2026, GSMA × Nokia, Smart Cities / Urban Safety / Mega-Project Infrastructure. This report does not assert vendor certification, event endorsement or a live operator relationship.',SM)
p.footer('Sources: original project brief; README.md; backend/app/engine.py; agents.py; topology.py')

# 4-5 status
for index,rows in enumerate([STATUS[:17],STATUS[17:]]):
    p=title('02 / Current project status',f'Implementation matrix {index+1} of 2','Implementation labels describe software scope; verification describes actual evidence.',landscape(A3))
    p.table(['Feature','Implementation','Location in code','How verified','Notes / limitations'],[[r['feature'],r['implementation'],r['code'],r['verified'],r['notes']] for r in rows],widths=[137,121,252,260,p.width-770],font=9.6)
    if index==1:p.para('No mandatory local-demo feature failed the completed checks. Docker runtime remains PARTIAL. Optional LLM and production integrations remain unimplemented. All existing application code was preserved during this documentation run; additions are evidence and report builders.',SM)
    p.footer('Sources: inspected implementation; docs/report-status.json; fresh stdout and runtime records in docs/report-assets')

# 6 architecture
p=title('03 / Project architecture','One incident context, one coherent defense','The diagram represents actual module relationships, not a proposed distributed deployment.',landscape(A4))
boxes=[(44,390,218,68,'React command center','App / useGuardian / components'),(312,390,214,68,'REST + WebSocket','FastAPI create_app / routes'),(576,390,218,68,'SimulationEngine','Single task, gates and event order'),(576,274,218,68,'Shared Incident','Topology, evidence, plan, actions'),(310,274,218,68,'Six logical agents','Sentinel → Impact → Response...'),(44,274,218,68,'Compliance policies','Dry-run copy + approval gate'),(44,158,218,68,'NetworkProvider','In-process SIMULATED adapter'),(310,158,218,68,'Digital twin + risk','Protect / isolate / continuity'),(576,158,218,68,'SQLite + reports','Atomic evidence / actual reports')]
for x,y,w,h,label,desc in boxes:
    c.setFillColor(PALE);c.setStrokeColor(LINE);c.roundRect(x,y,w,h,8,fill=1,stroke=1)
    c.setFillColor(INK);c.setFont('GM-Bold',12);c.drawString(x+13,y+43,label)
    c.setFillColor(MUTED);c.setFont('GM',9);c.drawString(x+13,y+21,desc)
def arrow(x1,y1,x2,y2):
    c.setStrokeColor(TEAL);c.setFillColor(TEAL);c.setLineWidth(1.7);c.line(x1,y1,x2,y2)
    a=math.atan2(y2-y1,x2-x1);q=c.beginPath();q.moveTo(x2,y2);q.lineTo(x2-7*math.cos(a-.5),y2-7*math.sin(a-.5));q.lineTo(x2-7*math.cos(a+.5),y2-7*math.sin(a+.5));q.close();c.drawPath(q,fill=1,stroke=0)
for coords in [(262,424,310,424),(526,424,574,424),(685,390,685,344),(576,308,530,308),(310,308,264,308),(153,274,153,228),(262,192,308,192),(528,192,574,192)]:arrow(*coords)
p.y=126;p.para('The engine calls the agents and applies provider results to Incident.topology. Each emit persists state before publishing a full snapshot. The frontend renders that backend state; it does not run a separate scripted attack animation.',SM)
p.footer('Sources: backend/app/main.py, engine.py, agents.py, provider.py, persistence.py; frontend/src/useGuardian.ts')

# 7 module map
p=title('03 / Project architecture','Repository map and module responsibilities')
p.table(['Location','Important names and responsibility'],[['backend/app/main.py','create_app, JsonFormatter: application lifecycle, REST, origin checks, WebSocket reader and sender cleanup.'],['backend/app/engine.py','SimulationEngine: start/run/control/approve, timed gates, emit/publish, final checks and safe shutdown.'],['models.py + scenarios.py','Pydantic schemas; frozen Scenario catalog; scenario_telemetry returns deterministic observations.'],['topology.py + risk.py','build_topology, protect, isolate, continuity_verified; calculate_impact and risk_band.'],['agents.py + policies.py','Six agent classes; validate_plan dry-runs ordered actions against a deep-copied twin.'],['provider.py + reporting.py','NetworkProvider protocol, SimulatedNetworkProvider, ENDPOINTS; generate_report from actual Incident.'],['persistence.py','Repository; IncidentRow, EventRow, ActionRow, ApprovalRow, ReportRow; SQLAlchemy sessions.'],['frontend/src/App.tsx','Header, mode/scenario controls, service continuity, twin, incident and report dialog orchestration.'],['useGuardian.ts + api.ts','Initialization/restore, controls, reconnecting WebSocket; request and applySnapshot helpers.'],['components/','Topology.tsx: React Flow and asset inspector. Panels.tsx: agents/actions/timeline/risk. Reports.tsx: executive/JSON/history views.'],['styles.css + polish.css','Responsive layout, state colors, presentation styles. Assets and fonts for the primary demo are local.'],['tests / scripts / deployment','backend/tests and frontend *.test.*; setup/start/stop.ps1; Dockerfiles, nginx.conf and compose.yaml.']],widths=[176,331],font=9)
p.para('Git inspection: master has no commits and the current source is untracked. A blank git diff therefore does not mean an empty implementation. source-manifest.json records SHA-256 hashes of reviewed files. Installed dependencies, SQLite and process logs are ignored.',SM)
p.footer('Source inspection included major functions and call sites, not filenames alone. No application refactor was performed.')

# 8 models
p=title('04 / Actual data model','The shared Incident is the integration boundary')
p.table(['Actual model','Important fields / purpose'],[['Incident','id, scenario_id, title, source, started_at, ended_at, status, phase, mode, auto_approve, step_duration; owns all following evidence.'],['Asset / Link / Topology','Asset: criticality, exposure, protection, state, operational, latency_ms, x/y. Link: source/target, kind/weight, enabled, propagates_threat, carries_service, state. Topology holds both lists.'],['Telemetry','remote_sessions, baseline_sessions, exploit_signature, sim_swap_minutes_ago, ownership_confirmed, location_matches, service_stop_requests, maintenance_window.'],['Technique / Classification','Technique ID/name/tactic/domain/explanation/url; threat_type, confidence, source, evidence and reasoning.'],['AssetRisk / Impact','Per node: score, distance, path, critical flag, factors. Aggregate: score, severity, impacted, critical_services, propagation_path, explanation.'],['Action / Plan','Action id/kind/target/endpoint/rationale/expected_effect/status/result/executed_at. Plan id/version/strategy/rationale/ordered actions.'],['PolicyDecision / PolicyReview','Decision APPROVED / APPROVAL_REQUIRED / REJECTED; reasons and rules. Review binds a result to plan ID/version and timestamp.'],['Approval','plan_id, plan_version, decision APPROVE/REJECT, actor OPERATOR/DEMO_AUTOMATION, timestamp.'],['AgentState / TimelineEvent','Name/role/state/finding; event seq/timestamp/type/agent/message. Actual event model is TimelineEvent.'],['ServiceSample / Report','Sample step/online/risk/latency. Report generated_at plus executive and technical dictionaries.']],widths=[161,346],font=9)
p.footer('Source: backend/app/models.py; frontend/src/types.ts mirrors the transport shape.')

# 9 context lifecycle
p=title('04 / Actual data model','How information moves between agents')
p.table(['Producer','Writes shared state','Next consumer'],[['Scenario engine','Telemetry + compromised source + fresh Topology','SentinelAgent.inspect'],['Sentinel','Classification: rule evidence, technique and explanation','Impact / UI / Report'],['Impact','Impact: downstream nodes, risk factors and critical paths','ResponseAgent.plan'],['Response','Plan + immutable plan_history version','ComplianceAgent.validate'],['Compliance','PolicyDecision + plan-bound PolicyReview; Approval when required','Execution gate / fallback planning'],['Network','Executed Action records + twin mutation + residual_impact','Continuity verification / Report'],['Report','Executive and technical evidence dictionaries','UI, REST export, SQLite history']],widths=[103,255,149])
p.heading('Lifecycle and validation')
p.para('A run begins RUNNING at ATTACK. Timed phases are DETECT, CLASSIFY, IMPACT, PLAN, POLICY, NETWORK, CONTAINED and COMPLETE. PAUSED suspends timed execution. AWAITING_APPROVAL freezes the plan before network actions. RESET restores the baseline twin; FAILED stops safely; INTERRUPTED marks a run whose backend execution cannot be resumed after restart.')
p.para('Schema forbids extra fields. Pydantic constrains numeric ranges, scenario modes, action kinds, security states and approval actors. StartRequest accepts step_duration from 0.01 to 10 seconds. Report dictionaries and Action.result remain flexible JSON dictionaries; their individual fields are not all separately declared Pydantic schemas.')
p.para('Execution is intentionally single-process: one active task and an asyncio lock prevent overlapping starts and inconsistent control changes. Plan history stores deep copies, so rejecting version 1 does not erase the decision that led to version 2.')
p.footer('Sources: models.py; engine.py start/control/approve/run; useGuardian.ts restart and snapshot handling')

# 10 idle twin
p=title('05 / Digital twin','A complete city, ready to defend','S01 · Actual NORMAL / IDLE topology. Fourteen nodes; all six critical services are operational.',landscape(A3))
p.shot('01-idle','Notice the connected endpoints at left, telecom/core/edge dependencies in the middle, and the six green critical services. Selection, pan, zoom and Fit View are interactive.',crop=(38,498,1004,647),width=1050,max_h=630)
p.footer('Source: actual UI http://127.0.0.1:5173/; topology.py build_topology; 21 modeled links, 15 enabled initially')

# 11 node table
p=title('05 / Digital twin','Every node and every dependency category')
p.table(['Node ID / name','Zone','Criticality / exposure','Critical'],[[n['id']+' / '+n['name'],n['zone'],f"{n['criticality']:.2f} / {n['exposure']:.2f}",'Yes' if n['critical'] else 'No'] for n in TOPO['nodes']],widths=[196,119,133,59],font=8.6)
p.para('Primary routes: camera/sensor → telecom → core → city → six services; traffic → edge → energy/control. Guardian → core/edge are management links. Six disabled protected links lead directly from core to each critical service and activate on reroute.',SM)
p.para('Node states: ONLINE, WARNING, COMPROMISED, AT_RISK, PROTECTED, ISOLATED, OFFLINE. Edge states: NORMAL, THREAT, PROTECTED, BLOCKED. Risk state and operational availability are separate. Editing, connecting and dragging nodes are disabled; inspection, pan/zoom and Fit View are enabled.',SM)
p.footer('Source: topology.py build_topology, models.py SecurityState/Link, frontend/src/components/Topology.tsx')

# 12 agents
p=title('06 / Six-agent system','Sentinel, Impact and Response','All six agents are deterministic Python logic. No external LLM calls are made.')
for name,body in [
('SentinelAgent.inspect','Purpose: detect and classify. Input: Incident.telemetry and source. Logic: exactly one explicit correlated telemetry rule must match; normal or ambiguous observations raise ValueError. Output: Classification with three evidence statements, a focused technique and rule confidence. Camera role: 48 sessions versus baseline 2 plus exploit signature supports attempted T1210 lateral movement. The match is observation-driven rather than selected only by scenario label.'),
('ImpactAgent.analyze','Purpose: expose downstream service risk. Input: current topology, source and scenario severity. Logic: calls calculate_impact over enabled propagating simple paths, retaining maximum per-node scores. Output: Impact, critical service IDs and a selected path. Camera role: identifies Hospital at distance 4 with risk 80 and six critical services exposed. It runs again after isolation to establish residual risk 0.'),
('ResponseAgent.plan','Purpose: produce safe ordered actions. Input: impact critical_services, source and scenario approval flag. Logic: deterministic rule/template selection; context checks, reroutes, priority QoD, optional shared-segment isolation, then endpoint quarantine. Output: versioned Plan with rationale and expected effects. Camera role: eleven actions protect all six services and hospital/emergency latency before isolating the camera. This is not a scored search over competing strategies.')]:
    p.heading(name);p.para(body)
p.footer('Sources: backend/app/agents.py; scenarios.py; risk.py; camera-fast-final.json')

# 13 remaining agents
p=title('06 / Six-agent system','Compliance, Network and Report')
for name,body in [
('ComplianceAgent.validate','Purpose: guard operational safety. Input: current Plan, Incident and provider.simulated. Logic: validate_plan executes a dry-run on a deep copy, validates targets and capability labels, rejects critical-service isolation and broken routes, and requires approval for shared infrastructure. Output: PolicyDecision plus retained policy review. Camera role: APPROVED because endpoint isolation follows route protection. Energy role: WAITING for a plan-bound operator decision.'),
('NetworkAgent.execute','Purpose: dispatch the approved action. Input: Action and Incident. Logic: await provider.execute, with idempotency in SimulatedNetworkProvider. Output: explicit simulated result. The engine applies reroute/protection, latency or isolation to the digital twin and emits an evidence event. Camera role: eleven actions including six protected routes, two QoD sessions and camera quarantine. This wrapper does not contact a carrier.'),
('ReportAgent.generate','Purpose: explain the outcome. Input: the completed Incident, timeline, telemetry, plans, policy/approval history, executed actions and samples. Logic: generate_report derives both report dictionaries; no fixed placeholder incident is inserted. Output: Report. Camera role: records 80 → 0 risk, minimum six services online, eleven actions and measured containment duration. Report agent is marked COMPLETE before the report evidence is constructed.')]:
    p.heading(name);p.para(body)
p.para('Agent UI states are IDLE, ANALYZING, COMPLETE, WAITING and EXECUTING. States represent the current deterministic phase; they do not imply separate processes, machine-learning models or concurrent autonomous negotiations.',SM)
p.footer('Sources: agents.py, policies.py, provider.py, reporting.py and engine.py agent/emit')

# 14 agent evidence
p=title('06 / Six-agent system','Agents visibly process actual incident state')
p.shot('03-camera-sentinel','S03 · Sentinel is ANALYZING while other agents remain IDLE. The walkthrough was paused to preserve this actual processing state.',crop=(38,1214,677,270),width=507)
p.shot('06-camera-plan-policy','S06 · Compliance has APPROVED the plan and Network is EXECUTING. The findings reference the eleven ordered actions.',crop=(728,1220,676,270),width=507)
p.para('The compact six-agent strip above the twin mirrors these detailed cards. In Fast Pitch, the strip stays with the visual attack story; the full cards supply explainable findings below it. The backend agent list and the frontend DOM agreed in captured states.',SM)
p.footer('Evidence: S03/S06 DOM snapshots; GM-0D632E900149; engine.py agent; Panels.tsx AgentPanel')

# 15 MITRE
p=title('07 / MITRE ATT&CK','Three focused, explainable mappings')
p.table(['Scenario / technique','Actual detection rule and explanation'],[['Camera · T1210\nExploitation of Remote Services\nEnterprise / Lateral Movement','remote_sessions > 5 × baseline_sessions AND exploit_signature. 48 > 10 and signature=true. Exploit attempts support lateral movement; high volume alone is insufficient.'],['Identity · T1451\nSIM Card Swap\nMobile / Initial Access','Swap within 1,440 minutes AND unconfirmed ownership AND location mismatch. The 12-minute swap is correlated with identity anomalies; a legitimate SIM change alone is not proof.'],['Energy · T1489\nService Stop\nEnterprise / Impact','At least 10 service-stop requests AND outside maintenance. There are 26 synthetic requests. This is a compute-layer Enterprise mapping, not an ICS threat model.']],widths=[191,316],font=9.1)
p.shot('04-camera-classification','S04 · UI shows technique ID, name, domain, tactic and rule confidence alongside the graph path.',crop=(1076,716,300,330),width=272,max_h=285)
p.para('Confidence values 97%, 91% and 98% are fixed rule indicators, not empirically calibrated probabilities. Only these three focused mappings are implemented; no full ATT&CK knowledge base or live threat feed is claimed.',SM)
p.rich('Official technique references checked 07 September 2026: <link href="https://attack.mitre.org/techniques/T1210/" color="#157e70">MITRE T1210</link>, <link href="https://attack.mitre.org/techniques/T1451/" color="#157e70">MITRE T1451</link>, <link href="https://attack.mitre.org/techniques/T1489/" color="#157e70">MITRE T1489</link>.',SM)
p.footer('Sources: scenarios.py; SentinelAgent.inspect; test_sentinel_*; official MITRE pages')

# 16 risk
p=title('08 / Impact analysis','The hospital risk is calculated from the graph')
p.code('score = round(100 * severity\n  * (0.55 * criticality + 0.25 * exposure\n     + 0.20 / (1 + 0.2 * distance))\n  * product(edge weights) * (1 - protection))')
p.para('calculate_impact builds directed outgoing adjacency from enabled, threat-propagating links. Depth-first traversal enumerates simple paths, avoiding repeated nodes to bound cycles. Disabled links, isolated/offline targets, management and protected routes cannot propagate threats. The highest path score per destination wins, so a longer high-weight path may outrank a short low-weight path.')
p.table(['Hospital input','Actual camera value'],[['Selected path','camera → telecom → core → city → hospital'],['Severity / criticality / exposure','0.96 / 1.00 / 0.85'],['Distance / proximity','4 / 1 ÷ (1 + 0.2 × 4) = 0.555556'],['Path weight / protection','1 × 0.95 × 1 × 1 = 0.95 / 0'],['Arithmetic','100 × 0.96 × (0.55 + 0.2125 + 0.111111) × 0.95 = 79.6733'],['Rounded hospital score','80 / 100 → CRITICAL']],widths=[165,342])
p.para('The aggregate score is the worst critical-service score (otherwise the worst impacted node). Bands: LOW <30; MODERATE 30-59; HIGH 60-79; CRITICAL ≥80. Hospital wins an equal maximum to keep the flagship explanation consistent.')
p.para('Protection sets a modeled factor of 0.95. Final source isolation makes the outgoing attack graph unreachable and residual risk 0. Availability is checked separately from the healthy 5G core through enabled service links; the result is a model check, not a probability or a real outage measurement.',SM)
p.footer('Source: risk.py calculate_impact; topology.py continuity_verified; exact risk assertion in test_intelligence.py')

# 17 provider operations
p=title('09 / Network-as-Code','SIMULATED / LOCAL PROTOTYPE','These POST-style paths are internal operation labels. They are not public REST routes or exact carrier API contracts.',landscape(A4))
p.table(['Operation','Trigger / input','Simulated result','Twin effect / scenarios'],[['verify_location\n/device/location/verify','First action; source Asset + telemetry.location_matches','verification TRUE/FALSE, interpreted zone; mismatch adds trust RESTRICTED in action result','Context evidence; no Asset trust field. All three; identity mismatch.'],['sim_swap\n/sim-swap/check','Source plus swap time, ownership and location telemetry','swapped_in_24h, minutes_since_swap, derived_risk LOW/HIGH','Recorded context only. Identity returns 12 min / HIGH.'],['reroute\n/routes/reroute','Each impacted critical service ID','route protected-core-path, service ID','Sets PROTECTED, protection 0.95, activates core bypass. Six camera/identity; two energy.'],['qod\n/qod/sessions','Priority service ID; hospital/emergency, or energy','profile EMERGENCY_DEMO, latency_before_ms 45, latency_after_ms 8','Updates modeled asset latency to 8 ms. No real QoS reservation.'],['quarantine\n/slice/isolate','Source endpoint after service protection','isolated true, scope endpoint','ISOLATED source; incident links disabled/BLOCKED. All scenarios.'],['isolate_segment\n/slice/isolate','Shared edge; matching approval after dry-run','isolated true, scope shared-segment','ISOLATED edge; dependent routes already protected. Energy Approve only.']],widths=[146,192,194,222],font=9.1)
p.para('NetworkProvider.execute(Action, Incident) is a Python protocol. The implementation opens no network connection. Result dictionaries contain simulated=true and the provider name. Idempotency keys are (incident.id, action.id) in an in-memory cache. Arbitrary labels and critical isolation are rejected.',SM)
p.footer('Sources: provider.py ENDPOINTS/SimulatedNetworkProvider; engine.py action mutation; no authorized carrier sandbox installed')

# 18 network shots
p=title('09 / Network-as-Code','Route protection and QoD are visible evidence')
p.shot('08-camera-contained','S08 · Completed local action feed: camera quarantine plus emergency and hospital QoD. The feed is newest first; execution protected routes before isolation.',crop=(38,1528,674,380),width=507)
p.shot('09-hospital-protected-qod','S09 · Hospital inspector after defense: PROTECTED, operational Online, protection 95%, simulated latency 8 ms.',crop=(780,893,258,208),width=325,max_h=248)
p.para('The 45 → 8 ms figures are simulated telemetry on selected assets. ServiceSample.latency is the rounded mean of all six critical assets; after camera defense that mean is 33 ms because the other four remain at 45 ms.',SM)
p.footer('Evidence: camera-guided-final.json action results + Hospital asset; screenshots S08/S09')

# 19 approval
p=title('10 / Human-in-the-loop','Approve a guarded shared-segment action','Manual energy run: '+R['energy_approve']['id'])
p.para('Compliance requires approval because isolating Edge Compute Node affects shared infrastructure. The ordered dry-run first protects Energy Grid and Smart-City Control routes. The engine enters AWAITING_APPROVAL; the captured before-state has zero network actions. Pause and Skip are disabled at this gate.')
p.shot('13-energy-approval-before','S13 · Real decision card before execution. Approve and Reject are both available; no simulated network action has started.',crop=(1063,500,340,725),width=276,max_h=440)
p.para('The operator clicked Approve. Approval records plan ID, version 1, decision APPROVE, actor OPERATOR and timestamp 15:25:28.709 UTC. Revalidation still enforces hard safety policy. Seven actions then complete, including segment isolation followed by source quarantine.',SM)
p.footer('Evidence: energy-approve-before.json / energy-approve-final.json; engine.py approve/approval; policies.py')

# 20 reject
p=title('10 / Human-in-the-loop','Reject preserves evidence and chooses a safe fallback')
p.table(['Path','Actual outcome'],[['Approve · '+R['energy_approve']['id'],'Plan v1; seven completed actions. Both Traffic Controller and Edge Compute Node isolated. Energy and city-control routes protected.'],['Reject · '+R['energy_reject']['id'],'Plan v1 and its policy retained. REJECT by OPERATOR at 15:26:50.116 UTC. New v2 removes shared-segment isolation; six actions contain the source only.'],['Hard rejection','A plan that isolates a critical service or removes service continuity is rejected by policy and cannot be approved through the operator gate.'],['Controlled automatic demo','When enabled, the timer records actor DEMO_AUTOMATION. This is visibly disclosed and does not impersonate an operator.']],widths=[181,326])
p.shot('19-energy-reject-final','S19 · Final Reject outcome: Response records safe fallback v2; Compliance and Network are complete after six actions.',crop=(527,1298,735,211),width=507,max_h=210)
p.para('Rejection still ends at risk 0 with 6/6 services online. The outer persisted incident was later RESET; its retained report remains CONTAINED and preserves the original isolated source and approvals. The report, screenshot S19 and absence of isolate_segment in executed actions are the final rejection evidence.',SM)
p.para('Approval requests must match the active plan ID/version. Duplicate or stale decisions return 409. Skip cannot bypass approval. An operator decision accepted at the auto-approval deadline takes precedence; this race is covered by a backend test.',SM)
p.footer('Evidence: energy-reject-final.json report.technical; S17-S19; test_manual_rejection_wins_auto_approval_timer_race')

# 21 flagship summary
p=title('11 / Camera walkthrough','Flagship: from compromised camera to protected hospital')
p.para('The main rehearsal started from Reset, selected Compromised IoT Camera and Fast pitch with Demo auto-approval enabled, and clicked Run Autonomous Defense Demo. Camera does not require an operator decision because its bounded endpoint plan passes policy automatically.')
p.table(['Measured fact','Actual result'],[['Incident',R['camera_fast']['id']],['Started / contained / report (UTC)','20:45:49.123 / 20:46:09.470 / 20:46:11.358'],['Timing',f"{R['camera_fast']['containment_seconds']:.3f} s to containment; {R['camera_fast']['report_seconds']:.3f} s to report"],['Evidence / classification','48 unauthorized remote sessions in 10 s; baseline 2; exploit signature true; T1210, 97% rule confidence.'],['Impact','Hospital path distance 4; peak risk 80; six critical services exposed.'],['Response / policy','Eleven ordered actions; plan version 1; APPROVED; no human approval required.'],['Final state','Camera ISOLATED; hospital/emergency PROTECTED at 8 ms simulated; all six critical routes protected; residual risk 0.'],['Availability / evidence','Minimum 6/6 operational at all 35 sampled events; all six agents COMPLETE; both reports generated.']],widths=[154,353])
p.para('The following screenshots include an instrumented Guided run ('+R['camera_walkthrough']['id']+') to hold short phases still, and the uninterrupted Fast Pitch rehearsal. Captions distinguish them. Guided capture pauses explain its 167.295-second containment time; they are not Fast Pitch performance.',SM)
p.footer('Evidence: camera-fast-final.json, camera-guided-final.json; runtime-summary.json; S02-S09 and S23-S28')

# 22 camera start/detect
p=title('11 / Camera walkthrough','Attack begins; Sentinel examines the observations')
p.shot('02-camera-attack-paused','S02 · Compromised camera and early attack state. Other services remain operational; risk has not yet been calculated. Paused Guided evidence.',crop=(62,668,485,300),width=507,max_h=287)
p.shot('03-camera-sentinel','S03 · Sentinel actively inspects the synthetic evidence; other agents have not executed yet.',crop=(38,1214,677,270),width=507,max_h=220)
p.para('INCIDENT_STARTED immediately sets the source COMPROMISED. After the first timed interval, ANOMALY_DETECTED records the 48-versus-2 observation. The next interval stores THREAT_CLASSIFIED and begins Impact analysis. No packet capture, exploit or live camera control occurs.',SM)
p.footer('Sources: engine.py start/run; SentinelAgent.inspect; S02/S03 actual Guided screenshots')

# 23 impact hero
p=title('11 / Camera walkthrough','The graph explains why the hospital is exposed','S05 · Guided capture: hospital at risk, still Online; graph exposure and availability are separate.',landscape(A3))
p.shot('05-hospital-risk','Notice the red camera-to-telecom-to-core-to-city route. Hospital and the other dependent services become AT RISK while their live indicators remain on. The right panel names T1210 and the selected hospital path.',crop=(38,498,1366,675),width=1100,max_h=600)
p.para('Response then creates eleven ordered actions. S06 records Compliance APPROVED and Network EXECUTING; the hospital reroute has already completed. The full plan and original policy are preserved in the report even though the concise UI focuses on stage findings.',SM)
p.footer('Sources: camera-guided-final.json initial_impact / plan / policy; S05/S06; risk.py')

# 24 camera finalhero
p=title('11 / Camera walkthrough','Containment is the result, not just an alert','S26 · Uninterrupted Fast Pitch final topology with critical service continuity.',landscape(A3))
p.shot('26-fast-final','Compromised camera is now ISOLATED. Green protected routes preserve service connectivity. The incident panel shows residual risk 0 and the report action. All six agent stages are complete.',crop=(38,325,1366,855),width=1100,max_h=630)
p.footer('Evidence: GM-3760FF663212; camera-fast-final.json; Hospital/Emergency QoD 45 → 8 ms; all 35 samples online=6')

# 25-26 complete timeline, exact messages
events=CAM['timeline']
for part,chunk in enumerate([events[:18],events[18:]]):
    p=title('11 / Camera walkthrough',f'Complete measured timeline {part+1} of 2',CAM['id']+' · UTC clock; elapsed from backend started_at.',landscape(A3))
    rows=[]
    for e in chunk:
        rows.append([f"{e['seq']:02}",e['timestamp'][11:23],f"+{secdt(CAM,e['timestamp']):.3f}s",e['agent'] or 'SYSTEM',e['type'],e['message']])
    p.table(['#','UTC','Elapsed','Agent','Event','Actual message'],rows,widths=[32,91,74,83,197,p.width-477],font=9.5)
    p.footer('Source: camera-fast-final.json timeline; all events included. Policy approved before actions; reroute before isolation.')

# 27 identity
p=title('12 / Identity walkthrough','Correlate the identity anomaly before containment')
p.table(['Stage','Actual scenario 2 behavior'],[['Clean start','Reset then select Telecom Identity / SIM-Swap Risk, Fast pitch, Run. Source sensor begins COMPROMISED.'],['Detection','Trusted sensor re-registers from unexpected zone. Swap 12 min ago; ownership unconfirmed; location mismatch.'],['Classification / impact','Mobile T1451 SIM Card Swap; rule confidence 91%; suspected takeover. Risk 73/100; six dependent services, including Hospital.'],['Context and trust','Location verification FALSE / unexpected-zone; action result trust RESTRICTED. SIM check swapped_in_24h=true, minutes_since_swap=12, derived_risk=HIGH.'],['Plan / policy','Eleven actions; endpoint-only containment automatically APPROVED. Six reroutes, hospital/emergency QoD, source quarantine.'],['Outcome','Environmental Sensor ISOLATED, risk 0; all agents COMPLETE; 35 events; minimum six services online.']],widths=[140,367])
p.shot('21-identity-contained','S21 · Actual final panel confirms T1451, isolated sensor, residual risk 0 and 6/6 critical services.',crop=(1078,665,309,510),width=200,max_h=313)
p.footer('Evidence: GM-B7F27B4C6506; identity-final.json. Containment 19.854 s; report 21.609 s.')

# 28 identityevidence
p=title('12 / Identity walkthrough','The location and SIM results are actual incident data')
p.shot('22-identity-context-checks','S22 · The action list was scrolled to its earliest results: location mismatch and recent SIM change. These are simulated context checks, followed by protected rerouting.',crop=(38,1528,674,470),width=507,max_h=354)
loc=next(a for a in IDENT['actions'] if a['kind']=='verify_location')['result'];swap=next(a for a in IDENT['actions'] if a['kind']=='sim_swap')['result']
p.code(json.dumps({'location':{k:loc[k] for k in ['verification','zone','trust','simulated']},'sim_swap':{k:swap[k] for k in ['swapped_in_24h','minutes_since_swap','derived_risk','simulated']}},indent=2),font=8.6)
p.para('Trust reduction is a recorded action result, not a persistent Asset trust field or live telecom identity enforcement. A real integration would need explicit identity authorization and an operator-supported policy action. The local scenario instead demonstrates the risk-informed containment path.',SM)
p.footer('Source: identity-final.json executed actions; engine.py verify_location branch; provider.py telemetry-derived results')

# 29 energytext
p=title('13 / Energy walkthrough','A different path through shared edge infrastructure')
p.para('Scenario 3 compromises Traffic Controller, whose enabled control links reach Edge Compute Node, Energy Grid and Smart-City Control. It does not use the camera-to-hospital path. Twenty-six unauthorized service-stop requests outside maintenance map to Enterprise T1489 for the edge compute layer.')
p.table(['Stage','Observed result'],[['Impact','Risk 72/100; two critical services exposed. Selected path traffic → edge → energy.'],['Plan v1','verify_location traffic; sim_swap traffic; reroute energy; reroute control; qod energy; isolate_segment edge; quarantine traffic.'],['Policy','APPROVAL_REQUIRED. Protect both impacted services before isolating their shared segment. Zero actions executed at the gate.'],['Approve','OPERATOR approved v1; seven actions; edge and traffic ISOLATED. Two protected routes preserve critical reachability.'],['Reject','Version 2 removes edge isolation; six actions; traffic isolated while edge stays available. Original plan/policy/decision retained.'],['Outcome','Both paths reach CONTAINED, residual risk 0, six agents COMPLETE, minimum 6/6 services online and actual reports.']],widths=[113,394])
p.para('The manual Approve capture took 56.564 seconds to containment and 58.406 seconds to report, including deliberate approval waiting. Reject took 36.590 / 38.380 seconds, also including operator waiting. These durations are not automatic Fast Pitch benchmarks.',SM)
p.footer('Evidence: energy-approve-before/final.json; energy-reject-final.json retained report; S13-S19')

# 30 energyshot
p=title('13 / Energy walkthrough','Shared edge isolated; energy connectivity preserved','S15 · Completed manual Approve path.',landscape(A3))
p.shot('15-energy-approved-final','Traffic Controller and Edge Compute Node are isolated. Energy Grid and Smart-City Control use protected routes. The other four critical services remain operational on their existing connectivity. All six agents completed.',crop=(38,498,1366,680),width=1100,max_h=560)
p.para('The approved segment action is the distinct behavior in Scenario 3. QoD targets Energy Grid (45 → 8 ms simulated), while camera/identity prioritize Hospital and Emergency Response.',SM)
p.footer('Evidence: GM-48E962F8A27E / energy-approve-final.json; seven completed simulated actions')

# 31 guided
p=title('14 / Guided Demo','Every control was exercised against the backend')
p.table(['Control','Result','Actual verification'],[['Run','PASS','Guided selection starts a fresh camera incident with step_duration=5.'],['Pause','PASS','GM-0D632E900149 DEMO_PAUSE events hold a phase. First pause 15:21:11.661 to resume 15:21:42.967 has no intervening event.'],['Resume','PASS','DEMO_RESUME unblocks the existing run; current evidence and plan remain.'],['Skip','PASS','DEMO_SKIP advances the current delay. The next detection/phase appears; it does not bypass approval.'],['Restart','PASS','Energy run GM-48E962F8A27E reset; new GM-3B9DF73610B7 starts, captured in S16.'],['Reset','PASS','Cancels current execution and restores fourteen ONLINE nodes. Retains prior reports and timeline history.']],widths=[68,55,384],font=9.2)
p.para('How to run: choose a scenario, click Guided, choose automatic approval or manual energy approval, then Run. Use Pause to discuss a stage, Resume to continue, or Skip to advance the current timed interval. Restart uses frontend reset followed by start; Reset returns to standby.')
p.para('Uninterrupted camera Guided rehearsal '+R['camera_guided']['id']+f" took {R['camera_guided']['containment_seconds']:.3f} seconds to containment and {R['camera_guided']['report_seconds']:.3f} seconds to report. Expected final state: isolated source, 0 residual risk and 6/6 services. Manual approval and deliberate pauses add wall-clock time.")
p.shot('02-camera-attack-paused','S02 · Live stream PAUSED with Resume enabled. The control operates the backend gate.',crop=(38,1147,1004,53),width=507)
p.shot('29-guided-uninterrupted-final','S29 · Completed Guided run shows report availability and the preserved six-service result.',crop=(1063,968,340,206),width=285,max_h=155)
p.footer('Evidence: Guided timeline DEMO_* records; S02/S16/S29; camera-guided-uninterrupted.json; engine control tests')

# 32 fastpitch
p=title('15 / Fast Pitch Mode','A complete story in 22.24 seconds')
p.para('From a clean Reset: select Camera, Fast pitch, Demo auto-approval, then Run. No pause, skip or manual navigation was required to complete the defense. The backend timing parameter was 1.7 seconds per main stage; actions use 0.55 times that delay.')
p.table(['Milestone','Measured elapsed'],[[e['type'],f"{secdt(CAM,e['timestamp']):.3f} seconds"] for e in CAM['timeline'] if e['type'] in ['ANOMALY_DETECTED','THREAT_CLASSIFIED','IMPACT_ANALYSIS_COMPLETE','RESPONSE_PLAN_CREATED','NETWORK_RESPONSE_STARTED','INCIDENT_CONTAINED','REPORT_GENERATED']],widths=[334,173])
p.shot('24-fast-attack','S24 · Beginning: attack marker and compromised source. The live workflow has started.',crop=(38,440,1004,188),width=507,max_h=100)
p.shot('25-fast-middle','S25 · Middle: risk 80, T1210 and hospital propagation during response planning.',crop=(1063,684,340,359),width=236,max_h=206)
p.para('S26 on page 24 shows the final state. All 35 event samples record six services online. Containment is measured separately from report generation (20.347 versus 22.235 seconds). The panel and progress strip make the main story visible; Guided is clearer for detailed explanations.',SM)
p.footer('Evidence: camera-fast-final.json; S24/S25/S26; no DEMO_* control events in the uninterrupted run')

# 33 executive
p=title('16 / Incident reports','Executive summary from the actual run',size=A3)
p.shot('27-fast-executive','S27 · Actual Fast Pitch executive report: 20.4 seconds to containment, 11 actions, minimum 6/6 online and residual risk 0.',crop=(270,43,895,910),width=754,max_h=785)
p.para('The executive report derives what happened, initial service risk, selected response, action count, availability, minimum online, residual risk, final outcome and duration. Report generation occurs automatically after containment. The button labeled Generate Incident Report opens the completed report.',SM)
p.footer('Source: reporting.py generate_report; GM-3760FF663212; Report.executive')

# 34 technical
p=title('16 / Incident reports','Technical evidence, history and export')
p.shot('28-fast-technical','S28 · Enlarged excerpt of actual technical JSON: incident ID, timestamps and isolated source asset. The full view continues with the remaining evidence below.',crop=(306,398,565,416),width=507,max_h=407)
p.para('Technical fields: incident/scenario IDs; start/end; source asset; detection_telemetry; classification; initial/residual impact including path factors; plan and plan_history; all six agent_decisions; policy and policy_history; approval_history; network_actions; timeline; service_samples; final_state, outcome and simulation scope.',SM)
p.para('History loads the latest 100 incident summaries and filters completed reports. Reset does not erase reports. Export JSON returned HTTP 200 with an attachment filename matching the actual incident and matching technical.incident_id. Print is exposed as the browser print action; printer output was not separately certified.',SM)
p.code('GET /api/incidents/GM-3760FF663212/report?download=true\n200 OK\nContent-Disposition: attachment;\n filename="GM-3760FF663212-incident-report.json"',font=8.1)
p.footer('Sources: reporting.py; components/Reports.tsx; runtime-summary.json json_export; API report tests')

# 35 REST
p=title('17 / REST API','Actual routes and contracts','No invented telecom routes: conceptual provider labels are documented separately in section 09.',landscape(A4))
p.table(['Method / endpoint','Purpose','Input','Output'],[['GET /api/health','Read service health','None','status ok, simulation true, provider local, agents 6, critical_services 6'],['GET /api/topology','Baseline topology','None','Topology with 14 nodes and 21 links; not the active live twin'],['GET /api/scenarios','Selectable deterministic scenarios','None','id/title/subtitle/source/requires_approval catalog'],['GET /api/incidents','Recent persisted history','None','Up to 100 summaries ordered by started_at; has_report flag'],['POST /api/scenarios/{scenario_id}/start','Start one run','StartRequest: mode, auto_approve, optional step_duration','201 Incident; 409 if a task is active'],['GET /api/incidents/{incident_id}','Read full current or saved incident','Path ID','Incident with live topology, evidence and report'],['GET /api/incidents/{incident_id}/timeline','Read ordered evidence','Path ID','TimelineEvent array'],['GET /api/incidents/{incident_id}/report','Read/export report','Path ID; download=false/true','Report JSON; attachment if requested; 409 until ready'],['POST /api/incidents/{incident_id}/approval','Record plan-bound decision','ApprovalRequest: plan_id, plan_version, APPROVE/REJECT','Updated Incident; actor assigned by server'],['POST /api/incidents/{incident_id}/{command}','Control engine','command: pause/resume/skip/reset; UI sends {}','Updated Incident; unknown command 404; invalid state 409']],widths=[260,145,166,183],font=8.8)
p.footer('Source: main.py create_app; captured openapi.json. Invalid payloads 422; foreign mutating Origin 403; missing ID 404.')

# 36 swagger
p=title('17 / REST API','Swagger exposes the implemented backend','Actual API documentation opened at http://127.0.0.1:8000/docs.',landscape(A4))
p.shot('12-swagger','S12 · Generated Swagger UI lists the actual GET and POST operations. OpenAPI is available at /openapi.json. The full route inventory appears on page 35.',width=754,max_h=351)
p.para('FastAPI default Swagger assets are fetched from a CDN; the docs viewer may require internet or cached assets. This auxiliary viewer is not a dependency of the installed primary Command Center. A saved openapi.json is included for offline technical review.',SM)
p.footer('Evidence: actual Swagger capture S12; backend/app/main.py; docs/report-assets/openapi.json')

# 37 WS
p=title('18 / WebSocket event system','Backend events drive the visualization')
p.code('ws://127.0.0.1:5173/ws/incidents/{incident_id}\n{ "type": "SNAPSHOT", "seq": 46,\n  "incident": { ...full current context and timeline... } }\nClient optional text: ping     Server: { "type": "PONG" }',font=9)
p.para('Engine.emit appends a sequential TimelineEvent, samples availability/risk/mean latency, commits the incident and related evidence in SQLite, then publishes a complete snapshot. The Vite /ws proxy forwards it to FastAPI. useGuardian accepts matching incident IDs and applySnapshot rejects older sequence numbers. React renders topology colors, agent states, progress, risk, actions and timeline from that shared state.')
p.table(['Mechanism','Actual implementation / evidence'],[['First connection / reconnect','subscribe queues the current full snapshot. UI reconnects after 1.5 s; prior state can be reconstructed without replaying commands.'],['Slow client','Queue maxsize 8. Old snapshots may be coalesced; the latest still contains the complete ordered timeline.'],['Message validation','Only text ping accepted from clients. Unknown IDs, foreign Origin, binary or other messages close with code 1008.'],['Runtime probe','21 live messages including PONG. Ordered snapshots through sequence 46 and REPORT_GENERATED; online=6 throughout observed messages.'],['Visual verification','S07 network execution and S08 final state changed while the browser subscribed to the same actual incident. No frontend-only simulation engine exists.']],widths=[137,370])
p.para('Important events: INCIDENT_STARTED, ANOMALY_DETECTED, THREAT_CLASSIFIED, IMPACT_ANALYSIS_COMPLETE, RESPONSE_PLAN_CREATED, POLICY_CHECK_COMPLETE, APPROVAL_REQUIRED, APPROVAL_RECORDED, SAFE_FALLBACK_SELECTED, ACTION_EXECUTING, CONTEXT_VERIFIED, TRAFFIC_REROUTED, QOD_ACTIVATED, DEVICE_ISOLATED, SEGMENT_ISOLATED, INCIDENT_CONTAINED, REPORT_GENERATED, DEMO_* and INCIDENT_RESET.',SM)
p.footer('Evidence: websocket-runtime.json; engine.py snapshot/emit/publish; main.py stream; useGuardian.ts; api.ts')

# 38 database
p=title('19 / Database','SQLite retains the decision trail')
db=read('database.json')
p.table(['Table','Important fields','Observed rows'],[[t,', '.join(row[1] for row in v['schema']),str(v['rows'])] for t,v in db.items()],widths=[124,307,76])
p.para('Repository automatically creates backend/data/guardianmesh.db and the five tables using SQLAlchemy metadata. GUARDIAN_DATABASE_URL can override the location. Incident payloads are JSON text; events, actions, approvals and reports also have their own rows. Each emitted state and its evidence commit in one transaction.')
p.code('Example retained incident (synthetic local data):\n'+json.dumps({'id':CAM['id'],'status':'CONTAINED','scenario_id':'camera','source':'camera','events':35,'peak_risk':80,'residual_risk':0,'actions':11,'minimum_services_online':6},indent=2))
p.heading('What persists; what does not')
p.para('Persisted: incidents, ordered events, executed actions, approval actors/versions, reviewed plans/policies inside incident/report JSON, reports and continuity samples. Reset preserves history. An unfinished run becomes INTERRUPTED after restart; verified containment with a missing report can recover the report from saved evidence.')
p.para('Not durable: active asyncio task, pause/skip/approval gates, subscriber queues and provider idempotency cache. No execution replay, cross-restart exactly-once guarantee, migration framework, retention policy or distributed database is implemented. UI history is capped at 100 recent incidents.',SM)
p.footer('Source: persistence.py; read-only PRAGMA table_info and row counts in database.json; no database content was deleted.')

# 39 tests
p=title('20 / Testing','Fresh tests passed; warnings are retained')
p.code('PS ...\\Win\\backend> ..\\.venv\\Scripts\\python.exe -m pytest -q\n........................................................... [100%]\n59 passed, 2 warnings in 33.88s')
p.table(['Suite','Actual result'],[['Backend pytest','59 passed; 0 failed; 0 skipped; 2 warnings; 33.88 s. Full stdout and JUnit XML saved.'],['Frontend Vitest','11 passed in 4 files; 0 failed; 2.15 s. API 3, hook 3, App 3, Reports 2.'],['Additional runtime assertions','Captured reports checked for source isolation, 0 residual risk, six complete agents, all simulated actions COMPLETE and minimum 6 online. JSON export verified HTTP 200.']],widths=[141,366])
p.heading('What the suite checks')
p.para('Risk direction, isolation, protection, cycles and alternative paths; bands and exact hospital score; focused mappings and insufficient observations; all six agents; ordered response and policy hard rejections; shared approval and rejection fallback; provider validation/idempotency; complete three-scenario lifecycles; pause/resume/skip/reset and overlapping starts; cancellation during provider work; provider failure; WebSocket malformed messages, origin, reconnect and backpressure; report and history persistence; restart recovery.')
p.heading('Actual warnings, not hidden failures')
p.para('StarletteDeprecationWarning: using httpx with starlette.testclient is deprecated; the installed library suggests httpx2. DeprecationWarning: anyio.abc.BlockingPortal alias is deprecated in favor of anyio.from_thread.BlockingPortal. Both are upstream test-client warnings. Application code and pinned dependencies were preserved.',SM)
p.code('PS ...\\Win\\frontend> npm test\nTest Files  4 passed (4)\nTests       11 passed (11)\nDuration    2.15s',font=9)
p.footer('Evidence: backend-tests.txt/xml; frontend-tests.txt; verify_report_evidence.py. No failing check was suppressed.')

# 40 build
p=title('21 / Frontend production build','TypeScript and Vite production output succeeded')
p.code('PS ...\\Win\\frontend> npm run build\n> guardianmesh-command-center@1.0.0 build\n> tsc -b && vite build\n\nvite v6.4.3 building for production...\ntransforming...\n2292 modules transformed.\nrendering chunks...\ncomputing gzip size...\n\ndist/index.html                   0.78 kB\ndist/assets/index-CNldKenc.css    52.68 kB\ndist/assets/topology-CitRzoT2.js 197.84 kB\ndist/assets/index-CI_OBj68.js    227.99 kB\ndist/assets/charts-BX467RyK.js   339.60 kB\n\nbuilt in 7.26s',font=9.5)
p.table(['Check','Result'],[['TypeScript project build','PASS - tsc -b completed before Vite bundling.'],['Production bundle','PASS - 2,292 transformed modules; generated frontend/dist.'],['Warnings / errors','No build warnings or errors in captured stdout.'],['Visual/runtime scope','Browser rehearsals used the Vite development server. The production bundle was built successfully; Nginx/container runtime is separately unverified.']],widths=[178,329])
p.para('Stack observed in source and locks: React 19, TypeScript, Vite 6, Tailwind 4, React Flow (@xyflow/react), Recharts and Lucide. Vite separates topology and chart chunks. No external paid frontend service or API key is required.',SM)
p.footer('Evidence: frontend-build.txt; package.json / package-lock.json / vite.config.ts; output listed verbatim from fresh build')

# 41 docker
p=title('22 / Docker','Configuration present; runtime remains PARTIAL')
p.para('Docker could not be executed: the docker command is unavailable on this machine. This report does not claim image build, container startup, healthcheck success or browser rehearsal through Nginx. Static inspection found referenced files, volume paths and proxy routes consistent.')
p.table(['Component','Actual configuration'],[['Backend image','Python 3.12-slim; locked dependencies; non-root guardian UID 10001; /app/data writable; one Uvicorn worker.'],['Frontend image','Node 22-alpine build stage runs npm ci and npm run build; Nginx 1.28-alpine serves dist.'],['Compose backend','Host 127.0.0.1:8000 → container 8000; named incident-data volume at /app/data; HTTP healthcheck.'],['Compose frontend','Host 127.0.0.1:8080 → Nginx 80; waits for healthy backend.'],['Proxy','/api forwards to backend:8000; /ws forwards Upgrade/Connection with HTTP/1.1 and a long read timeout.'],['Persistence / restart','Both services restart unless-stopped. Named volume survives normal docker compose down.']],widths=[145,362])
p.code('docker compose up --build -d\ndocker compose logs -f\ndocker compose down\n\nCommand Center: http://127.0.0.1:8080/\nBackend API:    http://127.0.0.1:8000/api/health')
p.para('Stop the local development backend first to avoid port 8000 conflict. Initial images and packages require download. Do not use docker compose down -v if incident history should survive. Before any Docker-based presentation, build and rehearse on a Docker-equipped machine.',SM)
p.footer('Sources: compose.yaml, backend/Dockerfile, frontend/Dockerfile, frontend/nginx.conf; Docker CLI availability check')

# 42 startup
p=title('23 / Exact startup','Run the existing local application on Windows')
p.heading('Existing installation: one command')
p.code('Set-Location "C:\\Users\\LOQ\\Documents\\ChatGPT\\Win"\n.\\scripts\\start.ps1\n\n# Stop only the servers owned by this launcher\n.\\scripts\\stop.ps1',font=9)
p.para('The launcher checks/reuses GuardianMesh services and starts missing processes hidden. It writes stdout/stderr and validated process records in .logs. Processes started manually should be stopped with Ctrl+C in their own terminals.',SM)
p.heading('Manual startup: two PowerShell terminals')
p.code('# Terminal 1: backend, exactly one worker\nSet-Location "C:\\Users\\LOQ\\Documents\\ChatGPT\\Win"\n.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app `\n  --app-dir backend --host 127.0.0.1 --port 8000\n\n# Terminal 2: frontend\nSet-Location "C:\\Users\\LOQ\\Documents\\ChatGPT\\Win\\frontend"\nnpm run dev',font=9)
p.table(['Surface','Exact URL'],[['Command Center','http://127.0.0.1:5173/'],['Swagger API documentation','http://127.0.0.1:8000/docs'],['Health / OpenAPI','http://127.0.0.1:8000/api/health\nhttp://127.0.0.1:8000/openapi.json'],['Docker frontend (unverified runtime)','http://127.0.0.1:8080/']],widths=[194,313])
p.para('Fresh installation only: install Python 3.12+ and Node.js 22+, then run .\\scripts\\setup.ps1 from the project root while online. It creates .venv if absent, installs requirements.lock.txt and runs npm ci. Do not reinstall or upgrade dependencies immediately before judging. SQLite initializes automatically.',SM)
p.footer('Source: README.md; scripts/setup.ps1, start.ps1, stop.ps1; Vite strictPort 5173; verified running backend/frontend')

# 43 judge
p=title('24 / Judge experience','JUDGE REHEARSAL RESULT: PASS')
p.table(['Judge criterion','Result / evidence'],[['Problem and response objective obvious','PASS - headline, service banner, incident source and progress stages share one visual story.'],['Attack obvious','PASS - camera becomes COMPROMISED; later graph threat routes are red. S02/S24.'],['Agents visibly working','PASS - processing cards captured; compact strip stays above twin. S03/S06. Deterministic scope disclosed.'],['Hospital threat understandable','PASS - risk 80 and full projected camera-to-hospital path appear. S05/S25.'],['Network defends connectivity','PASS - protected routes, context results, QoD and quarantine reflect backend actions. S07-S09.'],['Simulation label clear','PASS - LOCAL SIMULATION header, SIMULATED NETWORK-AS-CODE ACTIONS feed and report disclaimer.'],['Containment and 6/6 obvious','PASS - isolated source, residual risk 0 and six-service banner. S26.'],['Reports explain actual incident','PASS - executive values and technical ID/timeline match captured API. S27/S28.'],['Coherent layout / visual defects','PASS for observed desktop rehearsal - no clipping, overlaps or broken app panels observed; detailed agent/feed content requires scrolling.'],['Console / backend runtime','PASS - captured browser error/warn log empty; all report assertions pass. No application runtime failure found.']],widths=[180,327],font=9)
p.para('Rehearsal: clean Reset → Camera → Fast pitch → Run → observe classification, hospital risk and response → contained source with 6/6 → open executive and technical report. Measured 20.347 seconds to containment and 22.235 seconds to report. No application changes were necessary during this documentation pass.',SM)
p.para('Presentation advice: use a wide desktop window and Fast pitch for the first story, then Guided for questions. Explain that risk is graph exposure and QoD is simulated. Do not introduce new dependencies, change timing, delete SQLite, enable multiple workers or alter safety policy before submission.',SM)
p.footer('Evidence: camera-fast-final.json; S23-S28; browser-console.json; runtime-summary.json; actual clean UI rehearsal')

# 44-49 gallery
p=title('25 / Visual gallery','01  |  Idle Command Center','S01 · A normal city twin, six operational services and a ready defense engine.',landscape(A3))
p.shot('01-idle','Review cue: all fourteen assets are normal. No actions or incident evidence exist until a scenario starts.',crop=(38,325,1366,855),width=1100,max_h=630)
p.footer('Gallery reuses original evidence captures; screenshots are not synthetic mockups.')

p=title('25 / Visual gallery','02  |  Attack, classification and impact','S04 · Compromised source, threat paths, MITRE mapping and hospital exposure in one view.',landscape(A3))
p.shot('04-camera-classification','Review cue: camera red, upstream dependencies WARNING, critical services AT RISK but operational. Risk 80 and T1210 support the projected hospital path.',crop=(38,498,1366,675),width=1100,max_h=560)
p.footer('Evidence: instrumented Guided run GM-0D632E900149; same deterministic findings as the uninterrupted flagship run.')

p=title('25 / Visual gallery','03  |  Six agents and operator oversight')
p.shot('06-camera-plan-policy','S06 · Service-preserving planning, completed Compliance and active Network execution.',crop=(38,1220,1366,269),width=507,max_h=160)
p.shot('13-energy-approval-before','S13 · Explicit approval scope and safe rejection choice for a shared segment.',crop=(1089,1030,289,165),width=420,max_h=240)
p.shot('15-energy-approved-final','S15 · After Approve, the completed feed records source quarantine and shared-edge isolation. The provider is labeled simulated.',crop=(38,1507,674,295),width=507,max_h=215)
p.footer('Evidence: S06/S13/S15. Agent findings and approval controls are live backend-driven UI.')

p=title('25 / Visual gallery','04  |  Network actions and protected hospital')
p.shot('08-camera-contained','S08 · Completed isolation and QoD actions with their actual local results.',crop=(38,1528,674,380),width=507,max_h=266)
p.shot('09-hospital-protected-qod','S09 · Protected Hospital remains Online at 8 ms simulated latency.',crop=(780,893,258,208),width=345,max_h=298)
p.footer('QoD values are modeled. Protected routes and disabled source links are actual mutations of the local digital twin.')

p=title('25 / Visual gallery','05  |  Fast Pitch: the winning moment','S26 · 6/6 services remain online while the compromised camera is isolated.',landscape(A3))
p.shot('26-fast-final','Final result after the uninterrupted 22.235-second demonstration, including report generation. All six agents complete; the report can be inspected immediately.',crop=(38,325,1366,855),width=1100,max_h=630)
p.footer('The executive and technical report screenshots on pages 33-34 complete this gallery evidence sequence.')

p=title('25 / Visual gallery','06  |  Two different incident paths','S21 and S15 · Identity risk and shared-edge disruption reach safe containment.',landscape(A3))
start_y=p.y
p.shot('21-identity-contained','Identity: T1451; isolated sensor; risk 0; six services.',crop=(1063,500,340,710),width=340,max_h=610,x=140)
p.y=start_y
p.shot('15-energy-approved-final','Energy: T1489; shared-segment approval; six services.',crop=(1063,500,340,688),width=340,max_h=610,x=670)
p.footer('Actual scenarios: GM-B7F27B4C6506 and GM-48E962F8A27E. No repeated camera animation substitutes for their graphs.')

# 50 gallery report
p=title('25 / Visual gallery','07  |  The incident record closes the story',size=A3)
p.shot('27-fast-executive','S27 · The actual executive report closes the uninterrupted Fast Pitch run: 20.4 seconds to containment, minimum 6/6 online, eleven actions and residual risk zero.',crop=(276,50,877,897),width=754,max_h=785)
p.para('The technical view on page 34 preserves the same incident ID, original telemetry, MITRE mapping, graph-risk factors, plans, policies, actions and complete timeline. Export JSON returned the corresponding actual incident record.',SM)
p.footer('Evidence: GM-3760FF663212; camera-fast-final.json; S27/S28; runtime-summary.json export check')

# 51 limitations
p=title('26 / Limitations','What the prototype proves - and what it does not')
p.table(['Category','Current boundary'],[['Simulation','Synthetic telemetry and an in-memory digital twin. Provider outputs, protected transport, isolation and QoD latency are simulated. No real Nokia/CAMARA execution or authorized sandbox integration exists.'],['Intelligence','Six deterministic logical agents, three focused rules and fixed confidence indicators. No external LLM, trained anomaly model, full ATT&CK corpus, real SIEM or packet ingestion.'],['Risk / continuity','A simplified graph-exposure formula and modeled service reachability. No calibrated likelihood, real latency SLA or real-world uptime guarantee.'],['Identity','Location/SIM checks derive from synthetic telemetry. RESTRICTED trust is evidence in an action result, not production identity enforcement.'],['Security','Payload/identifier/origin/message controls are implemented. Authentication, RBAC, tenancy, TLS termination, rate limiting and enterprise audit controls are not. Localhost only.'],['Scale / resilience','One process, one active simulation, SQLite and full snapshots. Simple-path enumeration and repeated snapshot persistence suit 14 nodes. No distributed queue or cross-restart exactly-once execution.'],['Deployment','Local startup/tests/build verified. Docker runtime and production Nginx-serving rehearsal remain unverified. Initial packages/images and optional external documentation need internet/cache.'],['Prototype UX','Topology is inspectable, not editable. Detailed feeds and technical JSON require scrolling. Generate Incident Report opens an already generated report. Printing was not separately certified.']],widths=[117,390],font=9)
p.para('The documentation run found no application defect requiring a code change. Browser automation briefly needed tab/viewport recovery; these capture-tool issues did not produce app console errors. Source functionality and dependency versions were preserved.',SM)
p.footer('Source: actual implementation boundaries; independent read-only audit; browser/runtime evidence; Docker unavailable')

# 51 roadmap
p=title('27 / Roadmap','Keep the proven prototype separate from future work')
p.table(['Current prototype','Post-hackathon work - not implemented'],[['Local simulated NetworkProvider','Authorized operator sandbox adapter with exact versioned API contracts, device IDs, consent, credentials and network permissions.'],['Deterministic observations / focused rules','Real telemetry ingestion, SIEM/SOC correlation, rule evaluation against labeled evidence and monitored false-positive/negative rates.'],['Versioned plan + policy gate','Operator-approved production control policies, service dependency validation, compensation/rollback and provider failure handling.'],['Rule-generated explanations and reports','Optional LLM provider for wording/explanation with grounded evidence, constrained outputs and a reliable deterministic fallback.'],['Local origin guard and schemas','Authentication, authorization/RBAC, tenant isolation, protected audit storage, TLS and secret management.'],['Single engine + SQLite','Durable job queue, production database, migrations, distributed coordination, idempotent recovery and retention.'],['Basic JSON logs and tests','Metrics/traces, operator dashboards, scale/chaos tests and incident playbooks.'],['Locally rehearsed demo','Telecom operator pilot with authorized sandbox tests first, then measured network service outcomes under reviewed controls.']],widths=[196,311],font=9.2)
p.heading('A practical pilot sequence')
p.para('First validate real topology and ownership. Then map only authorized sandbox capabilities behind NetworkProvider, with exact input/output contracts. Update the current SIMULATION_ONLY policy through review; it intentionally rejects non-simulated providers today. Add asynchronous session handling, cancellation, failure compensation and integration tests before any production control is enabled.')
p.para('Avoid substituting a live provider directly into the judge demo. The installed deterministic mode remains the reliable baseline and regression fixture while new integrations are developed separately.',SM)
p.footer('Roadmap items are proposals, not claims of existing implementation or approved deployment.')

# 52-53 DoD
mandatory=[
('Frontend starts','PASS','Actual Vite Command Center; S01; UI rehearsals.'),('Backend starts','PASS','/api/health status ok; six agents; actual REST/WS.'),('Database initializes','PASS','Repository create_all; five live SQLite tables; tests.'),('WebSocket works','PASS','21 captured messages, PONG, final seq46; DOM changes.'),('Approximately 14 nodes','PASS','14 assets / 21 links; S01 and topology.json.'),('Six agents implemented','PASS','Six real classes; all COMPLETE in every report.'),('MITRE mapping works','PASS','T1210 / T1451 / T1489 rules, evidence, tests and UI.'),('Dependency impact calculation','PASS','Directed simple-path scoring; hospital 80; tests.'),('Network-as-Code simulation','PASS','Six operation kinds; explicit simulated results; actions.'),('Human approval exists','PASS','Zero pre-approval actions; OPERATOR Approve/Reject; v2.'),('Three incident scenarios','PASS','Camera, identity, energy completed; reports / screenshots.'),('Clean scenario reset','PASS','Baseline restored; history retained; restart ID changed.'),('Guided Demo works','PASS','62.267 seconds to report; all controls exercised.'),('Fast Pitch Mode works','PASS','22.235 seconds to report; uninterrupted clean rehearsal.'),('Critical services visibly online','PASS','6/6 banner and minimum online6 at all camera events.'),('Timeline reflects backend events','PASS','Actual 35-event camera timeline on pp25-26; WS chain.'),('Reports generated','PASS','Executive/technical actual data; JSON attachment200.'),('Tests pass','PASS','Backend59; frontend11; two disclosed test warnings.'),('Production frontend build','PASS','tsc + Vite; 2,292 modules; 7.26s; no build warnings.'),('Docker works or blocker disclosed','PARTIAL','Configuration inspected; Docker unavailable. Original DoD permits disclosed blocker.'),('README exact startup','PASS','Manual and script commands match source; pp41-42.')]
for index,chunk in enumerate([mandatory[:11],mandatory[11:]]):
    p=title('28 / Final verification matrix',f'Definition of Done {index+1} of 2','Judgments apply to the deterministic local prototype, with limitations stated explicitly.')
    p.table(['Original major requirement','Result','Evidence / reference'],chunk,widths=[185,68,254],font=9.2)
    if index==1:
        p.table(['Additional scope','Status'],[['Real carrier execution / authorized sandbox','NOT APPLICABLE to local DoD; NOT IMPLEMENTED.'],['Optional LLM interface','NOT APPLICABLE to mandatory DoD; optional, unimplemented.'],['Production auth / distributed deployment','NOT APPLICABLE to hackathon scope; future work.'],['Report package and visual verification','PASS - 28 sections, actual screenshots, source hashes, stdout, PDF rendering and visual QA.']],widths=[235,272],font=8.8)
        p.para('No mandatory local-demo feature remains FAIL. Docker runtime remains PARTIAL. The disclosed-blocker requirement is satisfied, while real container execution remains an explicit open verification item. All scenario outcomes are simulated service-protection evidence, not claims about a carrier network.',SM)
    p.footer('Final evidence set: docs/report-assets; original requirements section 28; runtime-summary.json; backend-tests.xml')

assert len(pages)==54,len(pages)
c.save()
MD.write_text('# GuardianMesh AI - Complete Project Report\n\nVerified 07 September 2026. Companion to the 54-page PDF.\n'+''.join(markdown),encoding='utf-8')
(ASSETS/'report-manifest.json').write_text(json.dumps({'pdf':str(PDF),'page_count':len(pages),'unique_screenshots':len(used),'screenshot_placements':sum(len(v) for v in used.values()),'screenshots':used,'pages':pages},indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(PDF),'pages':len(pages),'unique_screenshots':len(used),'placements':sum(len(v) for v in used.values()),'bytes':PDF.stat().st_size},indent=2))








