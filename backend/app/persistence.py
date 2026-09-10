import os
from pathlib import Path
from sqlalchemy import create_engine, String, Text, Integer, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from .models import Incident, TimelineEvent
from .reporting import generate_report


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(Text)


class ActionRow(Base):
    __tablename__ = "network_actions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[str] = mapped_column(Text)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[str] = mapped_column(Text)


class ReportRow(Base):
    __tablename__ = "reports"
    incident_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class Repository:
    def __init__(self, url: str | None = None):
        if url is None:
            directory = Path(__file__).resolve().parents[1] / "data"
            directory.mkdir(parents=True, exist_ok=True)
            url = os.getenv("GUARDIAN_DATABASE_URL", f"sqlite:///{directory / 'guardianmesh.db'}")
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)

    def save(self, incident: Incident) -> None:
        # Each event, its action/approval and the complete snapshot commit atomically.
        with Session(self.engine) as session, session.begin():
            session.merge(IncidentRow(id=incident.id, status=incident.status, payload=incident.model_dump_json()))
            for event in incident.timeline:
                session.merge(EventRow(id=f"{incident.id}:{event.seq}", incident_id=incident.id, seq=event.seq, payload=event.model_dump_json()))
            for action in incident.actions:
                session.merge(ActionRow(id=f"{incident.id}:{action.id}", incident_id=incident.id, payload=action.model_dump_json()))
            for i, approval in enumerate(incident.approvals):
                session.merge(ApprovalRow(id=f"{incident.id}:{i}", incident_id=incident.id, payload=approval.model_dump_json()))
            if incident.report:
                session.merge(ReportRow(incident_id=incident.id, payload=incident.report.model_dump_json()))

    def get(self, incident_id: str) -> Incident | None:
        with Session(self.engine) as session:
            row = session.get(IncidentRow, incident_id)
            return Incident.model_validate_json(row.payload) if row else None

    def list(self) -> list[Incident]:
        with Session(self.engine) as session:
            rows = session.scalars(select(IncidentRow).order_by(func.json_extract(IncidentRow.payload, "$.started_at").desc()).limit(100)).all()
            return sorted([Incident.model_validate_json(r.payload) for r in rows], key=lambda i: i.started_at, reverse=True)

    def recover(self) -> None:
        # Recovery must include every unfinished record, including records older
        # than the UI's 100-entry history page after repeated fast resets.
        with Session(self.engine) as session:
            rows = session.scalars(select(IncidentRow).where(IncidentRow.status.in_(["RUNNING", "PAUSED", "AWAITING_APPROVAL", "CONTAINED"]))).all()
            incidents = [Incident.model_validate_json(row.payload) for row in rows]
        for incident in incidents:
            if incident.status in ("RUNNING", "PAUSED", "AWAITING_APPROVAL"):
                incident.status = "INTERRUPTED"
                incident.outcome = "Backend restarted; start a fresh deterministic run."
                self.save(incident)
            elif incident.status == "CONTAINED" and incident.report is None:
                incident.phase = "COMPLETE"
                report_agent = next(a for a in incident.agents if a.name == "Report")
                report_agent.state = "COMPLETE"
                report_agent.finding = "Report recovered from persisted containment evidence."
                incident.timeline.append(TimelineEvent(seq=len(incident.timeline)+1, type="REPORT_GENERATED", agent="Report", message="Report recovered after backend restart; persisted containment evidence preserved."))
                incident.report = generate_report(incident)
                self.save(incident)
