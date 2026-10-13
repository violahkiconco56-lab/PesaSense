from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import (
    GoalContribution,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/goals", tags=["Goals"])


def build_goal_response(goal: Goal) -> GoalResponse:
    """Add the calculated progress fields to a goal."""
    response = GoalResponse.model_validate(goal)

    remaining = max(goal.target_amount - goal.saved_amount, 0)
    response.amount_remaining = remaining
    response.percent_saved = round(
        min(goal.saved_amount / goal.target_amount * 100, 100), 1
    )
    response.is_completed = remaining == 0

    if goal.deadline and remaining > 0:
        deadline = goal.deadline.replace(tzinfo=None)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        months_left = max((deadline - now).days / 30.44, 1)
        response.monthly_needed = round(remaining / months_left, 2)

    return response


def get_user_goal(db: Session, goal_id: int, user_id: int) -> Goal:
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == user_id)
        .first()
    )
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    return goal


@router.post("/", response_model=GoalResponse)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = Goal(**data.model_dump(), user_id=current_user.id)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return build_goal_response(goal)


@router.get("/", response_model=list[GoalResponse])
def list_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == current_user.id)
        .order_by(Goal.created_at.desc())
        .all()
    )
    return [build_goal_response(goal) for goal in goals]


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    data: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = get_user_goal(db, goal_id, current_user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return build_goal_response(goal)


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
def contribute_to_goal(
    goal_id: int,
    data: GoalContribution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = get_user_goal(db, goal_id, current_user.id)
    goal.saved_amount += data.amount
    db.commit()
    db.refresh(goal)
    return build_goal_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = get_user_goal(db, goal_id, current_user.id)
    db.delete(goal)
    db.commit()