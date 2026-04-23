export interface BusinessNatureItem {
  id: number
  uuid: string
  business_nature: string
  hsic_classification: string
  hsic_code: string
  status: 'enable' | 'disable'
  update_at: string | null
  created_at: string | null
  delete_at: string | null
}

export interface BusinessNatureListData {
  content?: BusinessNatureItem[]
  count?: number
}

export interface BusinessNatureListResponse {
  status_code?: number
  message?: string
  data?: BusinessNatureListData
}

export interface BusinessNaturePayload {
  business_nature: string
  hsic_classification: string
  hsic_code: string
  status: 'enable' | 'disable'
}

export interface BusinessNatureEditPayload extends BusinessNaturePayload {
  uuid: string
}

export interface BusinessNatureMutationResponse {
  status_code?: number
  message?: string
  data?: string
}
