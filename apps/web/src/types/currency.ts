export interface CurrencyProperties {
  id: number
  uuid: string
  currency: string
  currency_symbol: string
  exchange_rate: number
  status: 'enable' | 'disable'
  created_at: string | null
  updated_at: string | null
  deleted_at: string | null
}

export interface CurrencyListData {
  content?: CurrencyProperties[]
  count?: number
}

export interface CurrencyListResponse {
  status_code?: number
  message?: string
  data?: CurrencyListData
}

export interface CurrencyPayload {
  currency: string
  currency_symbol: string
  exchange_rate: number
  status: 'enable' | 'disable'
}

export interface CurrencyEditPayload extends CurrencyPayload {
  uuid: string
}

export interface CurrencyMutationResponse {
  status_code?: number
  message?: string
  data?: string
}
