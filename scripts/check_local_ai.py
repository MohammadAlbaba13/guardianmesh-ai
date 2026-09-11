"""Run the hospital twin with a real local advisor, recording actual mode/fallback."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from app.engine import SimulationEngine
from app.persistence import Repository
from app.models import StartRequest
from app.intelligence import choose_reasoner


async def main():
    with tempfile.TemporaryDirectory() as directory:
        repo=Repository('sqlite:///' + str(Path(directory)/'ai.db'))
        engine=SimulationEngine(repo, reasoner=choose_reasoner('local_llm'))
        incident=await engine.start('camera',StartRequest(step_duration=.01,execution_mode='SIMULATION'))
        await engine.task
        evidence={'incident_id':incident.id,'status':incident.status,'reasoning':incident.reasoning.model_dump(),
                  'policy':incident.policy.decision,'agents_complete':sum(a.state=='COMPLETE' for a in incident.agents),
                  'residual_risk':incident.residual_impact.score if incident.residual_impact else None}
        (ROOT/'docs/live-ai-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
        print(json.dumps(evidence))
        await engine.close();repo.engine.dispose()


if __name__=='__main__':asyncio.run(main())
