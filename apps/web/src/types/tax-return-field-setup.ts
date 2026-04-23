/**
 * Tax return field setup types
 *
 * Organized into two clear sections:
 * 1. UI/Form models - Used in Vue components (camelCase)
 * 2. API models - Backend response/request format (snake_case)
 */

// ============================================
// Shared Models (UI and API use same format)
// ============================================

/** Single field structure (used by both UI and API) */
export type TemplateFieldValue = string | number | boolean | null

export interface TemplateField {
  name: string
  type: string | null
  aqua_mapping?: string
  ird_mapping?: string
  tax_return_number?: string
  tax_return_reference?: string
  /**
   * UI-only: store user input value for this field.
   * Optional to keep API template definition compatible.
   */
  value?: TemplateFieldValue
}

/** Form data structure used in dialog component */
export interface TemplateFormData {
  title: string
  description: string
  year: string
  status: string
  uuid?: string
  fields: TemplateField[]
}

// ============================================
// API Models
// ============================================

/** Template object from API responses */
export interface ApiTemplate {
  id?: number
  uuid?: string
  title?: string
  description?: string
  year?: string
  status?: string
  updated_at?: string | null
  created_at?: string | null
  deleted_at?: string | null
  content?: { fields?: TemplateField[] }
}

/** API response for list/get endpoints */
export interface ApiTemplateListResponse {
  data?: {
    content: ApiTemplate[]
    count: number
  }
}

/** API request body for create/update */
export interface ApiTemplateRequest {
  title: string
  description: string
  year: string
  status: string
  content: { fields?: TemplateField[] }
  uuid?: string
}

// ============================================
// Type Aliases (backward-friendly names)
// ============================================

/** @deprecated Use TemplateField instead */
export type TaxReturnFieldSetupField = TemplateField

/** @deprecated Use TemplateField instead */
export type TaxReturnFieldSetupContentItem = TemplateField

/** @deprecated Use ApiTemplate instead */
export type TaxReturnFieldSetupListItem = ApiTemplate

/** @deprecated Use ApiTemplateListResponse instead */
export type TaxReturnFieldSetupListResponse = ApiTemplateListResponse

/** @deprecated Use ApiTemplateRequest instead */
export type TaxReturnFieldSetupPayload = ApiTemplateRequest

// ============================================
// Utility Functions
// ============================================

/** Extract fields array from API content object */
export function parseContentToFields(
  content?: ApiTemplate['content']
): TemplateField[] {
  if (!content) return []
  return content.fields ?? []
}
