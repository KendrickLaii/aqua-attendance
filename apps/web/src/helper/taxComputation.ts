import type { BasicInformationData } from "@/types/working-section"

/**
 * Profits tax computation data content (cards/tables + text block).
 * Pass year for dynamic labels e.g. "Total tax payable for the year of assessment {year}..."
 */
export const DEFAULT_TAX_RATE = 0.165

function resolveCurrencyLabel(currency?: string): string {
  const normalized = String(currency ?? '').trim()
  return normalized || 'HKD'
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

// fiscal_period: "0"|"1" → "Year", "2"|"3" → "Period"
export function getFiscalPeriodLabel(basicInformationData: BasicInformationData): 'Year' | 'Period' {
  const fp = String(basicInformationData?.fiscal_period ?? '').trim()
  return fp === '2' || fp === '3' ? 'Period' : 'Year'
}

// Format f_year_end (e.g. "2025-12-31" or "31-12-2025") to "December 31, 2025".
// yearOffset adds to the parsed year (e.g. 1 for provisional).
export function formatFYearEnd(dateStr: string | null | undefined, yearOffset = 0): string {
  const s = String(dateStr ?? '').trim()
  if (!s) return ''
  const parts = s.split(/[-/]/).filter(Boolean)
  if (parts.length !== 3) return s
  let year: string
  let month: string
  let day: string
  if (parts[0].length === 4) {
    ;[year, month, day] = parts
  } else if (parts[2].length === 4) {
    ;[day, month, year] = parts
  } else {
    return s
  }
  const monthNum = parseInt(month, 10)
  if (Number.isNaN(monthNum) || monthNum < 1 || monthNum > 12) return s
  const yearNum = parseInt(year, 10)
  const displayYear = Number.isNaN(yearNum) ? year : String(yearNum + yearOffset)
  return `${MONTH_NAMES[monthNum - 1]} ${parseInt(day, 10)}, ${displayYear}`
}

export function buildYearsOfAssessmentLine(bi: BasicInformationData): string {
  const yoaLy = String(bi?.year_of_assessment_ly ?? '').trim() || '–'
  const yoa = String(bi?.year_of_assessment ?? '').trim() || '–'
  return `YEARS OF ASSESSMENT ${yoaLy}/${yoa}`
}

export function buildBasicPeriodLine(bi: BasicInformationData): string {
  return buildBasicPeriodText(bi, { yearOffset: 0, tense: 'ended' })
}

export function buildYearsOfAssessmentProvisionalLine(bi: BasicInformationData): string {
  const provLy = String(bi?.provisional_ly ?? '').trim() || '–'
  const prov = String(bi?.provisional ?? '').trim() || '–'
  return `YEARS OF ASSESSMENT ${provLy}/${prov} (PROVISIONAL)`
}

export function buildBasicPeriodProvisionalLine(bi: BasicInformationData): string {
  return buildBasicPeriodText(bi, { yearOffset: 1, tense: 'ending' })
}

export function buildBasicPeriodText(
  bi: BasicInformationData,
  opts: { yearOffset: number; tense: 'ended' | 'ending' },
): string {
  const label = getFiscalPeriodLabel(bi)
  const date = formatFYearEnd(bi?.f_year_end, opts.yearOffset)
  return `Basic period: ${label} ${opts.tense} ${date}`
}

export function createDefaultAmountList() {
  return [
    {
      title: 'amountBeforeTax',
      type: 'amount_before_tax',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'profitAdjustment',
      type: 'profit_adjustment',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'yearOfAssessment',
      type: 'year_of_assessment',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'netAssessableProfit',
      type: 'net_assessable_profit',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'profitTaxCurrentYear',
      type: 'profit_tax_current_year',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'yearOfAssessmentProvisional',
      type: 'year_of_assessment_provisional',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'profitTaxProvisional',
      type: 'profit_tax_provisional',
      current_year: 0,
      prior_year: 0,
    },
    {
      title: 'totalTaxPayable',
      type: 'total_tax_payable',
      current_year: 0,
      prior_year: 0,
    },
  ]
}

export function initProfitsTaxComputationDataContent(basicInformationData: BasicInformationData, currency?: string): any[] {
  const currencyLabel = resolveCurrencyLabel(currency)
  const yoaLine = buildYearsOfAssessmentLine(basicInformationData)
  const periodLine = buildBasicPeriodLine(basicInformationData)
  const provLine = buildYearsOfAssessmentProvisionalLine(basicInformationData)
  const provPeriodLine = buildBasicPeriodProvisionalLine(basicInformationData)

  // scheduleType = blankRow  display nothing in html, only show on printing
  // scheduleType = total display total row in html (blue disabled input field)
  // tag = row0 for sync target
  // tag = noInput not display amount input in html
  // tag = taxRatePercentage for sync target
  // tag = oneOffTaxReduction for sync target
  // tag = provisionalTaxAlreadyCharged for sync target
  // tag = remainingAt165 for sync target
  // tag = twoTierProfitsTaxRates for sync target
  return [
    {
      order: 1,
      type: 'info',
      tableType: 'profitAdjustment',
      tableData: [
        { titleSelect: true, name: '', schedule: 'Schedule', scheduleType: 'title', this: 'Amount', last: 'Amount' },
        { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { name: '', schedule: '', scheduleType: 'blankRow', tag:['row0'], this: '', last: '' },
        { itemSelect: true, name: 'Profit before tax', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['amountBeforeTax'], yearSum: true, this: '', last: '' },
        { itemSelect: true, name: 'Add: Non taxable expenses', schedule: '', scheduleType: 'input', type: 'breakdown', yearSum: true, this: '', last: '', number: 1, noTotalNum: 1 },
        { itemSelect: true, name: 'Less: Non taxable income', schedule: '', scheduleType: 'input', type: 'breakdown', yearSum: true, this: '', last: '', number: 2, noTotalNum: 2 },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: 'Adjusted profit', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 2,
      type: 'info',
      tableType: 'yearOfAssessment',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        // { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { itemSelect: true, name: yoaLine, schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { itemSelect: true, name: periodLine, schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { itemSelect: true, name: 'Adjusted profit per above', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['syncTarget'], yearSum: true, this: '', last: '' },
        { itemSelect: true, name: 'Less: Depreciation allowances', schedule: '', scheduleType: 'input', type: 'breakdown', yearSum: true, this: '', last: '', number: 1, noTotalNum: 1 },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: 'Assessable profits', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 3,
      type: 'info',
      tableType: 'netAssessableProfit',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        { itemSelect: true, name: 'Assessable profits per above', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['syncTarget','inputDisabled'], yearSum: true, this: '', last: '' },
        { itemSelect: true, name: 'Less: Tax allowable lossess brought forward', schedule: '', scheduleType: 'input', type: 'breakdown', yearSum: true, this: '', last: '', number: 1, noTotalNum: 1 },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: 'Net assessable profits', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 4,
      type: 'info',
      tableType: 'profitTaxCurrentYear',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        // { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { itemSelect: true, name: 'Profits tax thereon at two-tiered rate:', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        { itemSelect: true, name: 'Profits tax thereon @16.5%', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['taxRatePercentage'], yearSum: true, this: '', last: ''},
        { itemSelect: true, name: 'Less: one-off tax reduction (maximum HK$1,500)', schedule: '', scheduleType: 'comboBox', type: 'breakdown', tag:['oneOffTaxReduction','isBinDisabled'], yearSum: true, this: '', last: '', number: 1, noTotalNum: 1 },
        { itemSelect: true, name: '', schedule: '', scheduleType: 'label', type: 'blankRow', yearSum: false, this: '', last: '',},
        { itemSelect: true, name: '', schedule: '', scheduleType: 'label', type: 'subtotal', yearSum: false, this: '', last: '', start: 1, end: 2},
        { itemSelect: true, name: 'Less: Provisional tax already charged', schedule: '', scheduleType: 'input', type: 'breakdown', tag:['provisionalTaxAlreadyCharged','isBinDisabled'], yearSum: true, this: '', last: '', number: 2, noTotalNum: 2 },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: 'Balance undercharged bought forward', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 5,
      type: 'info',
      tableType: 'yearOfAssessmentProvisional',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        // { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { itemSelect: true, name: provLine, schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { itemSelect: true, name: provPeriodLine, schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: 'Assessable profit per above', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 6,
      type: 'info',
      tableType: 'profitTaxProvisional',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        // { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { itemSelect: true, name: 'Provisional profits tax thereon at two-tiered rate:', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '', number: 1, noTotalNum: 1 },
        { itemSelect: true, name: '  First HK$2,000,000 of assessable profit @16.5%', schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['taxRatePercentage'], yearSum: true, this: '', last: '', number: 2, noTotalNum: 2 },
        { name: '', schedule: '', scheduleType: 'blankRow', this: '', last: '' },
        { total: true, type: 'total', name: '', schedule: '', this: '-', last: '-', this_sum_error: false, last_sum_error: false, debit_sum_error: false, credit_sum_error: false },
      ],
    },
    {
      order: 7,
      type: 'info',
      tableType: 'totalTaxPayable',
      tableData: [
        { titleSelect: true, name: '', schedule: '', scheduleType: 'title', this: '', last: '' },
        // { name: '', schedule: '', scheduleType: 'currency', this: currencyLabel, last: currencyLabel },
        { itemSelect: true, name: `Total tax payable for the year of assessment ${basicInformationData.year_of_assessment_ly || '–'}/${basicInformationData.year_of_assessment || '–'}`, schedule: '', scheduleType: 'label', type: 'fixedRow', tag:['noInput'], yearSum: true, this: '', last: '' },
        {
          total: true,
          type: 'total',
          name: `\u00A0\u00A0\u00A0and ${basicInformationData.provisional_ly || '–'}/${basicInformationData.provisional || '–'} (provisional)`,
          schedule: '',
          this: '-',
          last: '-',
          this_sum_error: false,
          last_sum_error: false,
          debit_sum_error: false,
          credit_sum_error: false,
        },
      ],
    },
    {
        order: 8,
        type: 'checkboxes',
        selectedCheckbox: [],
        checkboxContent: [
          {
            title: 'Per relief measures announced in the {year of assessment}/{year of assessment} budget, subject to enactment.',
            value: 'perReliefMeasures',
          },
          {
            title: 'Non-taxable item under "Exemption from Profits Tax (Interest Income) Order".',
            value: 'nonTaxableItem',
          },
          {
            title: 'The Company fulfil the requirement of the two-tiered profits tax rates regime, under the two-tiered profits tax rates regime, the profits tax rate for the first HK$2 million of profits of corporations will be lowered to 8.25 per cent.',
            value: 'twoTierProfitsTaxRates',
          },
        ],
    },
  ]
}

export function createDefaultTaxComputationSections(basicInformationData: BasicInformationData, currency?: string): any[] {
  return [
    {
      id: 0,
      title: 'Profits Tax Computation',
      description: 'Details of profits tax computation for the assessment year.',
      dataContentList: initProfitsTaxComputationDataContent(basicInformationData, currency),
    },
    {
      id: 1,
      title: 'Computation of Depreciation Allowances',
      description: 'Calculation of depreciation allowances for fixed assets.',
      dataContentList: [],
    },
    {
      id: 2,
      title: 'Additions to Property Plant and Equipment',
      description: 'Details of additions to property, plant, and equipment during the assessment year.',
      dataContentList: [],
    },
    {
      id: 3,
      title: 'Movement in Obligations under Finance Lease',
      description: 'Analysis of movements in obligations under finance lease.',
      dataContentList: [],
    },
    {
      id: 4,
      title: 'Detailed Income Statement',
      description: 'Detailed income statement for the assessment year.',
      dataContentList: [],
    },
    {
      id: 5,
      title: 'Supporting Schedule',
      description: 'Supporting schedules and additional information.',
      dataContentList: [],
    },
  ]
}
