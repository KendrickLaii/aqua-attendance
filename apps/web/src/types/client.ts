export interface ClientProperties {
  status_code: number;
  message:     string;
  data:        Data;
}

export interface Data {
  content: Content[];
  count:   number;
}

export interface Content {
  id?: number
  uuid?: string
  L_year_end: string
  L_year_start: string
  business_nature_uuid: string
  company_name: string
  company_name_en: string
  company_no: string
  contact_person: string
  currency: string
  due_date: string
  engage_date: string
  f_year_end: string
  f_year_start: string
  fiscal_period: string | null
  incorporation_date: string
  main_signer: string
  main_signer_position?: string | null
  manager: string
  place_of_incorporation: string
  position_of_signing_partner: string
  practising_certificate_number: string
  principal_activity: string
  provisional: string
  provisional_ly: string
  registered_office: string
  report_date: string
  reportin_standards: string
  signing_partner: string
  staff_in_charge: string
  status: string
  tax_file_no: string
  year_of_assessment: string
  year_of_assessment_ly: string
  // Timestamps & relations (present in fuzzy search / detail responses)
  assignee_uuid?: string | null
  created_at?: string | null
  updated_at?: string | null
  deleted_at?: string | null
  login_date?: string | null
  logout_date?: string | null
}

/** Response shape for GET /client_profile/fuzzy_search */
export type FuzzySearchResponse = ClientProperties

/** Response shape for GET /v1/aqua/audit/clientProfile/get */
export interface AquaAuditClientProfile {
  uuid: string
  company_no: string
  co_signer: string
  update_at: string
  assignee_uuid: string[]
  tax_file_no: string
  contact_person: string
  delete_at: string
  principal_activity: string
  email: string
  currency_uuid: string
  place_of_incorporation: string
  telephone: string
  business_nature_uuid: string
  registered_office: string
  referrer: string
  id: number
  company_name: string
  engage_date: string
  variable_scenario: string
  company_name_en: string
  report_date: string
  create_at: string
  incorporation_date: string
  main_signer: string
}
