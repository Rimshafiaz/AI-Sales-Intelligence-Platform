export interface DiscoveryCandidate {
  company_name: string
  website: string | null
  industry: string | null
  short_description: string | null
  match_explanation: string
  supporting_source_urls: string[]
}

export interface DiscoveryResponse {
  candidates: DiscoveryCandidate[]
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
}

export interface ResearchSource {
  id: string
  url: string
  title: string | null
  excerpt: string | null
  source_type: string
  retrieved_at: string
}
