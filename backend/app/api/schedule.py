from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import db, get_runtime, require_user
from app.db.models import TaskStatus
from app.runtime import Runtime
from app.services.schedule_service import CreatedEvent, EventOut, PlanOut, ScheduleService, TaskOut

router = APIRouter(prefix="/api", tags=["schedule"], dependencies=[Depends(require_user)])


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    location: str = ""
    note: str = ""


class EventPatch(BaseModel):
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    note: str | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    duration_min: int = Field(gt=0, le=600)
    deadline: datetime | None = None
    priority: int = Field(2, ge=1, le=3)


class SuggestIn(BaseModel):
    start: date
    end: date
    task_ids: list[int] | None = None


@router.get("/events")
def events(start: date, end: date, s: Session = Depends(db)) -> list[EventOut]:
    return ScheduleService(s).list_events(start, end)


@router.post("/events")
def create_event(body: EventIn, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> CreatedEvent:
    out = ScheduleService(s).create_event(body.title, body.start_at, body.end_at, None, body.location, body.note)
    rt.audit.record("user:web", "web:create_event", f"event#{out.event.id}", body.model_dump(mode="json"), session=s)
    return out


@router.patch("/events/{event_id}")
def update_event(event_id: int, body: EventPatch, s: Session = Depends(db),
                 rt: Runtime = Depends(get_runtime)) -> CreatedEvent:
    out = ScheduleService(s).update_event(event_id, body.title, body.start_at, body.end_at, body.location, body.note)
    rt.audit.record("user:web", "web:update_event", f"event#{event_id}", body.model_dump(mode="json"), session=s)
    return out


@router.delete("/events/{event_id}")
def delete_event(event_id: int, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> EventOut:
    out = ScheduleService(s).delete_event(event_id)
    rt.audit.record("user:web", "web:delete_event", f"event#{event_id}", out.model_dump(mode="json"), session=s)
    return out


@router.get("/tasks")
def tasks(status: TaskStatus | None = None, s: Session = Depends(db)) -> list[TaskOut]:
    return ScheduleService(s).list_tasks(status)


@router.post("/tasks")
def add_task(body: TaskIn, s: Session = Depends(db)) -> TaskOut:
    return ScheduleService(s).add_task(body.title, body.duration_min, body.deadline, body.priority)


@router.post("/tasks/{task_id}/done")
def complete_task(task_id: int, s: Session = Depends(db)) -> TaskOut:
    return ScheduleService(s).complete_task(task_id)


@router.post("/schedule/suggest")
def suggest(body: SuggestIn, s: Session = Depends(db)) -> PlanOut:
    return ScheduleService(s).suggest_schedule(body.start, body.end, body.task_ids)


@router.post("/schedule/plans/{plan_id}/apply")
def apply(plan_id: int, s: Session = Depends(db), rt: Runtime = Depends(get_runtime)) -> list[EventOut]:
    out = ScheduleService(s).apply_schedule(plan_id)
    rt.audit.record("user:web", "web:apply_schedule", f"plan#{plan_id}", {"events": [e.id for e in out]}, session=s)
    return out
