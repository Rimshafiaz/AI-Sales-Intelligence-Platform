import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignCandidateSelectionCreate,
    CampaignCandidateSelectionResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignRunCreate,
    CampaignRunResponse,
)
from app.services.campaigns import (
    CampaignWorkflowError,
    campaign_candidate_selection_response,
    campaign_response,
    campaign_run_response,
    create_campaign,
    create_campaign_run,
    create_candidate_selection_and_research_request,
    get_campaign_for_user,
    get_campaign_run_for_user,
    list_campaign_selections_for_user,
    list_campaigns_for_user,
)


router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign_endpoint(
    request: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return campaign_response(create_campaign(db, current_user, request))


@router.get("", response_model=list[CampaignResponse])
def list_campaigns_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        campaign_response(campaign)
        for campaign in list_campaigns_for_user(db, current_user.id)
    ]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_endpoint(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = get_campaign_for_user(db, campaign_id, current_user.id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign_response(campaign)


@router.post(
    "/{campaign_id}/runs",
    response_model=CampaignRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign_run_endpoint(
    campaign_id: uuid.UUID,
    request: CampaignRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = get_campaign_for_user(db, campaign_id, current_user.id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign_run_response(create_campaign_run(db, campaign, request))


@router.post(
    "/runs/{campaign_run_id}/selections",
    response_model=CampaignCandidateSelectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def select_campaign_candidate_endpoint(
    campaign_run_id: uuid.UUID,
    request: CampaignCandidateSelectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign_run = get_campaign_run_for_user(db, campaign_run_id, current_user.id)
    if campaign_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign run not found")
    try:
        selection, research_request = create_candidate_selection_and_research_request(
            db,
            campaign_run,
            current_user,
            request,
        )
    except CampaignWorkflowError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return campaign_candidate_selection_response(selection, research_request)


@router.get(
    "/{campaign_id}/selections",
    response_model=list[CampaignCandidateSelectionResponse],
)
def list_campaign_selections_endpoint(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = get_campaign_for_user(db, campaign_id, current_user.id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return [
        campaign_candidate_selection_response(selection, research_request)
        for selection, research_request in list_campaign_selections_for_user(
            db,
            campaign.id,
            current_user.id,
        )
    ]
