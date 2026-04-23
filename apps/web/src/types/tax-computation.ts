import type { DPLGroupedData, GroupedDataItem } from '@/views/tax/working-section/tax-computation/components/DPL.vue'

export type { DPLGroupedData, GroupedDataItem }

export interface TaxComputationCreatePayload {
  data_content: Record<string, unknown>
  data_content_amount_list: unknown[]
  remark: string
  status: string
  tax_computation: DPLGroupedData
  working_record_uuid: string
}

export interface TaxComputationEditPayload {
  data_content: Record<string, unknown>
  data_content_amount_list: unknown[]
  remark: string
  status: string
  tax_computation: DPLGroupedData
  uuid: string
  working_record_uuid?: string
}

export interface TaxComputationRecord {
  data_content_amount_list?: unknown[]
  uuid?: string
  working_record_uuid?: string
  remark?: string
  created_at?: string | null
  deleted_at?: string | null
  id?: number
  tax_computation?: DPLGroupedData | GroupedDataItem[]
  data_content?: Record<string, unknown>
  status?: string
  updated_at?: string | null
}

export interface TaxComputationListResponse {
  status_code?: number
  message?: string
  data?: {
    content?: TaxComputationRecord[]
    count?: number
  }
}

export interface NoteACFromAquaParams {
  company_name: string
  year_of_assessment: string | number
  year_of_assessment_ly: string | number
}

export interface NoteACFromAquaResponse {
  BS?: string
  BS_note_index?: object
  DPL?: string
  DPL_note_index?: null
  PL?: string
  PL_note_index?: object
  audit_report?: object
  calculation_variable?: object
  create_at?: Date
  delete_at?: string
  director_report?: object
  id?: number
  index?: object
  notes?: object
  profile_uuid?: string
  remark?: string
  report_uuid?: string
  update_at?: Date
  uuid?: string
}
