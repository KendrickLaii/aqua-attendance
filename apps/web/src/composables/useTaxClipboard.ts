import type { Content } from '@/types/client'
import type { BasicInformationData } from '@/types/working-section'
import { copyTextToClipboard } from '@/utils/clipboard'
import { formatValue } from '@/utils/review-format'
import { useToast } from '@/composables/useToast'

/**
 * useTaxClipboard composable
 *
 * WHY this exists:
 *   Review.vue had a `buildCompanyInfoString()` function with a hardcoded 40+ field
 *   mapping, plus a `copyClientInformationAndTaxComputation()` orchestrator.
 *   Extracting them here keeps the clipboard-copy concern self-contained.
 *
 * WHAT it does:
 *   1. Builds a pipe-delimited string of company & basic information fields.
 *   2. Combines that with the flattened tax computation string.
 *   3. Copies the result to the clipboard and shows a toast notification.
 *
 * FORMAT of the output string:
 *   key1|value1;key2|value2;...taxRate|16.50%;data-content-1-name|Salary;...
 *
 * NOTE on the fiscal period label mapping:
 *   The `fiscal_period` field stores a numeric index (0–3).
 *   We map it to a human-readable label before including it in the string.
 *   The typo `fisaclPeriodString` in the original code has been fixed here.
 */

// ────────────────────────────────────────────
// Fiscal period labels (index 0–3)
// ────────────────────────────────────────────

const FISCAL_PERIOD_LABELS = [
  'Year/ Year',
  'Year/ Period',
  'Period/ Year',
  'Period/ Period',
] as const

// ────────────────────────────────────────────
// Internal helpers
// ────────────────────────────────────────────

/**
 * Build a pipe-delimited string of company information fields.
 *
 * Each entry is formatted as `key|value;` — this string is consumed by external
 * tools/integrations that parse it back into structured data.
 */
function buildCompanyInfoString(
  basicInfo: BasicInformationData,
  clientData: Content,
): string {
  // Map fiscal_period index to a human-readable label
  const fiscalPeriodLabel = FISCAL_PERIOD_LABELS[Number(basicInfo.fiscal_period)] ?? ''

  // Manually map the fields we want to include in the clipboard string.
  // This is intentionally explicit (not dynamic) so we control the exact
  // set of fields and their order in the output.
  const data: Record<string, unknown> = {
    L_year_start: basicInfo.L_year_start,
    L_year_end: basicInfo.L_year_end,
    f_year_start: basicInfo.f_year_start,
    f_year_end: basicInfo.f_year_end,
    report_date: basicInfo.report_date,
    engage_date: basicInfo.engage_date,
    fiscal_period: fiscalPeriodLabel,
    due_date: basicInfo.due_date,
    tax_file_no: basicInfo.taxFileNumber,
    practising_certificate_number: basicInfo.practising_certificate_number,
    position_of_signing_partner: basicInfo.position_of_signing_partner,
    signing_partner: basicInfo.signing_partner,
    year_of_assessment: basicInfo.year_of_assessment,
    year_of_assessment_ly: basicInfo.year_of_assessment_ly,
    provisional: basicInfo.provisional,
    provisional_ly: basicInfo.provisional_ly,
    company_name_en: clientData.company_name_en,
    registered_office: clientData.registered_office,
    staff_in_charge: clientData.staff_in_charge,
    deleted_at: clientData.deleted_at,
    incorporation_date: clientData.incorporation_date,
    place_of_incorporation: clientData.place_of_incorporation,
    contact_person: clientData.contact_person,
    company_no: clientData.company_no,
    manager: clientData.manager,
    reportin_standards: clientData.reportin_standards,
    login_date: clientData.login_date,
    uuid: clientData.uuid,
    business_nature_uuid: clientData.business_nature_uuid,
    logout_date: clientData.logout_date,
    id: clientData.id,
    principal_activity: clientData.principal_activity,
    main_signer: clientData.main_signer,
    assignee_uuid: clientData.assignee_uuid,
    currency: clientData.currency,
    status: clientData.status,
    created_at: clientData.created_at,
    company_name: clientData.company_name,
    main_signer_position: clientData.main_signer_position,
    updated_at: clientData.updated_at,
  }

  return Object.entries(data)
    .map(([key, value]) => `${key}|${formatValue(value)};`)
    .join('')
}

// ────────────────────────────────────────────
// Composable
// ────────────────────────────────────────────

interface UseTaxClipboardOptions {
  /** The basic information data from the working section. */
  basicInformationData: () => BasicInformationData
  /** The client profile data (may be null). */
  clientData: () => Content | null | undefined
  /**
   * A function that flattens the tax computation into a string.
   * Provided by the `useTaxComputationReview` composable.
   */
  flattenTaxComputationData: () => { flattenedString: string } | null
}

export function useTaxClipboard(options: UseTaxClipboardOptions) {
  const { show: showToast } = useToast()

  /**
   * Copy the combined company-info + tax-computation string to the clipboard.
   *
   * Steps:
   *   1. Build the company information string from basic info + client data.
   *   2. Get the flattened tax computation string from the composable.
   *   3. Concatenate them and copy to clipboard.
   *   4. Show a success or error toast.
   */
  async function copyClientInformationAndTaxComputation() {
    const clientData = options.clientData()
    const basicInfo = options.basicInformationData()

    if (!clientData || !basicInfo) {
      showToast('No client information or tax computation data to copy', 'error')
      return
    }

    // Step 1: Build company information string
    const companyInformationString = buildCompanyInfoString(basicInfo, clientData)

    // Step 2: Flatten tax computation data
    const taxRes = options.flattenTaxComputationData()
    const taxString = taxRes?.flattenedString ?? ''

    // Step 3: Combine and copy
    const combined = [companyInformationString, taxString].filter(Boolean).join('')
    if (!combined) {
      showToast('No client information or tax computation data to copy', 'error')
      return
    }

    try {
      await copyTextToClipboard(combined)
      showToast('Client information and Tax computation copied to clipboard successfully', 'success', 5000)
    }
    catch (e) {
      showToast('Copy failed, please try again', 'error')
      console.error('Clipboard copy failed:', e)
    }
  }

  return {
    copyClientInformationAndTaxComputation,
  }
}
