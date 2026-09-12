import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.current_user import (
    AuthenticatedIdentity,
    get_authenticated_identity,
    get_current_user,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignCandidateSelectionCreate,
    CampaignCandidateSelectionResponse,
    CampaignCreate,
    CampaignRecommendedBatchCreate,
    CampaignRecommendedBatchResponse,
    CampaignResponse,
    CampaignRunCreate,
    CampaignRunResponse,
)
from app.schemas.campaign_prospect import (
    CampaignProspectCreate,
    CampaignProspectResponse,
    CampaignProspectUpdate,
)
from app.services.campaigns import (
    CampaignWorkflowError,
    campaign_candidate_selection_response,
    campaign_recommended_batch_response,
    campaign_response,
    campaign_run_response,
    create_campaign,
    create_recommended_research_batch,
    create_campaign_run,
    create_candidate_selection_and_research_request,
    get_campaign_for_user,
    get_campaign_run_for_user,
    list_campaign_selections_for_user,
    list_campaign_summaries_for_user,
)
from app.services.campaign_prospects import (
    CampaignProspectError,
    campaign_prospect_response,
    list_campaign_prospects,
    list_campaign_prospects_for_user,
    save_campaign_prospect,
    update_campaign_prospect,
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
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
):
    return [
        campaign_response(campaign, saved_count, ready_count)
        for campaign, saved_count, ready_count in list_campaign_summaries_for_user(
            db, current_user.id
        )
    ]


@router.get(
    "/prospects/bulk",
    response_model=list[CampaignProspectResponse],
)
def list_campaign_prospects_bulk_endpoint(
    campaign_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
):
    return [
        campaign_prospect_response(prospect)
        for prospect in list_campaign_prospects_for_user(db, current_user, campaign_id)
    ]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign_endpoint(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
):
    campaign = get_campaign_for_user(db, campaign_id, current_user.id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign_response(campaign)


@router.post(
    "/{campaign_id}/prospects",
    response_model=CampaignProspectResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_campaign_prospect_endpoint(
    campaign_id: uuid.UUID,
    request: CampaignProspectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prospect = save_campaign_prospect(db, campaign_id, current_user, request)
    except CampaignProspectError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) == "Campaign not found." else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    return campaign_prospect_response(prospect)


@router.get(
    "/{campaign_id}/prospects",
    response_model=list[CampaignProspectResponse],
)
def list_campaign_prospects_endpoint(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
):
    try:
        prospects = list_campaign_prospects(db, campaign_id, current_user)
    except CampaignProspectError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [campaign_prospect_response(prospect) for prospect in prospects]


@router.patch(
    "/{campaign_id}/prospects/{prospect_id}",
    response_model=CampaignProspectResponse,
)
def update_campaign_prospect_endpoint(
    campaign_id: uuid.UUID,
    prospect_id: uuid.UUID,
    request: CampaignProspectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prospect = update_campaign_prospect(
            db, campaign_id, prospect_id, current_user, request
        )
    except CampaignProspectError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return campaign_prospect_response(prospect)


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


@router.post(
    "/runs/{campaign_run_id}/recommended-batch",
    response_model=CampaignRecommendedBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recommended_research_batch_endpoint(
    campaign_run_id: uuid.UUID,
    request: CampaignRecommendedBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign_run = get_campaign_run_for_user(db, campaign_run_id, current_user.id)
    if campaign_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign run not found")
    try:
        selections = create_recommended_research_batch(
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
    return campaign_recommended_batch_response(selections)


@router.get(
    "/{campaign_id}/selections",
    response_model=list[CampaignCandidateSelectionResponse],
)
def list_campaign_selections_endpoint(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedIdentity = Depends(get_authenticated_identity),
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
