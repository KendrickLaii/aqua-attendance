export interface BasicInformationData {
  title: string
  year: string
  companyNameEn: string
  referor: string
  companyNumber: string
  taxFileNumber: string
  f_year_start: string
  f_year_end: string
  L_year_start: string
  L_year_end: string
  fiscal_period: string | null
  year_of_assessment: string
  year_of_assessment_ly: string
  provisional: string
  provisional_ly: string
  engage_date: string
  due_date: string
  report_date: string
  signing_partner: string
  position_of_signing_partner: string
  practising_certificate_number: string
  description: string
  remark: string
}

export interface WorkingSectionProperties {
  id?: number
  uuid?: string
  clientUuid: string
  name: string
  companyNumber: string
  taxFileNumber: string
  tax_year: string
  title: string
  status: string
  created_at?: string | null
  updated_at?: string | null
  deleted_at?: string | null
  /** Used for list page edit redirect, from API profile_uuid */
  profile_uuid?: string
}

/** Response item from GET /working_record/get/all */
export interface WorkingRecordListItem {
  id?: number
  uuid?: string
  profile_uuid?: string
  title?: string
  tax_file_no?: string
  tax_year?: string
  status?: string
  updated_at?: string | null
  created_at?: string | null
  deleted_at?: string | null
  DPLC?: string
  DPLC_note_index?: string
  DPL?: string
  DPL_note_index?: string
  PL?: string
  PL_note_index?: string
  referor?: string
  start_date?: string
  end_date?: string
  description?: string
  remark?: string
  tax_computation_uuid?: string | null
  tax_additional_info?: Record<string, unknown>
  tax_data?: Record<string, unknown>
  // fiscal year dates
  f_year_start?: string
  f_year_end?: string
  L_year_start?: string
  L_year_end?: string
  fiscal_period?: string | null
  // year of assessment
  year_of_assessment?: string
  year_of_assessment_ly?: string
  provisional?: string
  provisional_ly?: string
  // dates
  engage_date?: string
  due_date?: string
  report_date?: string
  // signing info
  signing_partner?: string
  position_of_signing_partner?: string
  practising_certificate_number?: string
}

/** Payload for POST /working_record/create and PUT /working_record/update */
export interface WorkingRecordPayload {
  DPL: string
  DPLC: string
  DPLC_note_index: string
  DPL_note_index: string
  PL: string
  PL_note_index: string
  description: string
  end_date: string
  start_date: string
  report_date: string
  profile_uuid: string
  referor: string
  remark: string
  status: string
  tax_additional_info: object
  tax_data: object
  tax_file_no: string
  tax_year: string
  title: string
  tax_computation_uuid?: string
  // Fiscal year dates
  f_year_start: string
  f_year_end: string
  L_year_start: string
  L_year_end: string
  fiscal_period: string | null
  // Year of assessment
  year_of_assessment: string
  year_of_assessment_ly: string
  provisional: string
  provisional_ly: string
  // Dates
  engage_date: string
  due_date: string
  // Signing info
  signing_partner: string
  position_of_signing_partner: string
  practising_certificate_number: string
  main_signer: string
  main_signer_position: string
  // Staff
  contact_person: string
  manager: string
  staff_in_charge: string
}
