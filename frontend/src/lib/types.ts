export interface DiscoveryCandidate {
  company_name: string
  website: string | null
  industry: string | null
  short_description: string | null
  match_explanation: string
  supporting_source_urls: string[]
  source_provider: string | null
  source_record_id: string | null
  source_retrieved_at: string | null
  source_data_release: string | null
  formatted_address: string | null
  business_status: string | null
  phone_number: string | null
  website_verification_state: 'listed_unverified' | null
  identity_state: 'needs_review'
  discovery_source_types: ('local_places' | 'web_search' | 'social_search')[]
  social_profile_urls: string[]
}

export interface DiscoveryResponse {
  candidates: DiscoveryCandidate[]
}

export interface DiscoveryObjective {
  goal_type: string
  seller_role: string | null
  offering: string | null
  target_sectors: string[]
  target_geographies: string[]
  company_size: string | null
  stage: string | null
  triggers: string[]
  signals_to_look_for: string[]
  decision_makers: string[]
  search_queries: string[]
  fit_rubric: string
  desired_outcome: string
}

export interface ParseDiscoveryResponse {
  objective: DiscoveryObjective
  supported: boolean
  message: string | null
}

export type OpportunityModelId =
  | 'web_conversion.no_verified_web_presence'
  | 'web_conversion.mobile_performance'
  | 'web_conversion.booking_contact_path'
  | 'web_conversion.restaurant_reservation_path'
  | 'social_presence.dormant_official_presence'

export interface EvidenceSource {
  provider: string
  provider_record_id: string | null
  source_url: string | null
  retrieved_at: string
}

export interface EvidenceSignal {
  signal_type: string
  evidence_type: 'observed' | 'inference'
  supporting_value: string
  numeric_value: number | null
  source: EvidenceSource
  captured_at: string
  inference_basis: string | null
}

export interface DiscoveryOpportunityReason {
  model_id: OpportunityModelId
  signal_type: string
  supporting_value: string
  source: EvidenceSource
  captured_at: string
}

export interface PreparedDiscoveryOpportunity {
  queue_entry: {
    candidate_index: number
    company_name: string
    reasons: DiscoveryOpportunityReason[]
  }
  candidate_input: {
    candidate: DiscoveryCandidate
    evidence_signals: EvidenceSignal[]
    social_observations: unknown[]
  }
  shortlist_entry: {
    candidate_index: number
    company_name: string
    state: 'excluded' | 'needs_identity_review' | 'needs_evidence' | 'eligible_for_deeper_research'
    model_evaluations: unknown[]
    next_evidence_action: string
  }
}

export interface DiscoveryOpportunityPreparationResponse {
  candidates: PreparedDiscoveryOpportunity[]
  needs_verification_count: number
  not_surfaced_count: number
}

export interface CampaignResponse {
  id: string
  title: string
  goal: string | null
  criteria: Record<string, unknown>
  model_selection: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface CampaignRunResponse {
  id: string
  campaign_id: string
  status: string
  criteria_snapshot: Record<string, unknown>
  model_selection_snapshot: Record<string, unknown>
  provider_summary: Record<string, number>
  discovered_candidate_count: number
  created_at: string
}

export interface CampaignRecommendedBatchResponse {
  selections: {
    id: string
    campaign_run_id: string
    company_id: string
    research_request_id: string
    source_identity_key: string
    created_at: string
  }[]
}

export interface Company {
  id: string
  name: string
  website: string | null
  created_at: string
  updated_at: string
}

export interface ResearchRequest {
  id: string
  company_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  objective: Record<string, unknown> | null
  evidence_gate_state: 'not_run' | 'ready_for_deeper_research' | 'needs_review'
  evidence_gate_reason: string | null
  evidence_gated_at: string | null
  website_audit_state: 'not_run' | 'completed' | 'unavailable'
  website_audit_reason: string | null
  website_audited_at: string | null
}

export interface ResearchEvidence {
  id: string
  research_request_id: string
  signal_type: string
  evidence_type: 'observed' | 'inference'
  supporting_value: string
  numeric_value: number | null
  source_provider: string
  source_record_id: string | null
  source_url: string
  retrieved_at: string
  captured_at: string
}

export interface KnownProspectResolution {
  business_name: string
  location: string | null
  website: string | null
  identity_state: 'verified' | 'needs_review' | 'rejected'
  source: {
    provider: string
    provider_record_id: string | null
    source_url: string | null
    retrieved_at: string
  } | null
  reason: string
}

export interface ResearchSource {
  id: string
  url: string
  title: string | null
  excerpt: string | null
  source_type: string
  retrieved_at: string
  admission_state: 'pending' | 'accepted' | 'excluded' | 'needs_review'
  admission_reason: string | null
}

export interface ReportListItem {
  id: string
  research_request_id: string
  company_id: string
  company_name: string
  opportunity_score: number
  contact_recommendation: string
  review_status: 'draft' | 'approved'
  generated_at: string
}

export interface ReportListResponse {
  items: ReportListItem[]
  total: number
  page: number
  page_size: number
}

export interface DashboardActivity {
  event_type: string
  company_name: string
  status: string | null
  occurred_at: string
}

export interface DashboardSummary {
  reports_generated: number
  companies_researched: number
  industries_researched: number
  most_researched_industries: { industry: string; report_count: number }[]
  average_opportunity_score: number | null
  recent_activity: DashboardActivity[]
}
