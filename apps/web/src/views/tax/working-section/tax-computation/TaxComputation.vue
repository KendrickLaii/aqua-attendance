<script setup lang="ts">
//Components
import TaxMenu from './components/TaxMenu.vue'
import ProfitsTaxComputation from './components/ProfitsTaxComputation.vue'
import DPL from './components/DPL.vue'
//Types
import type { Content } from '@/types/client'
import type { BasicInformationData } from '@/types/working-section'
import type { TaxMenuItem } from './components/TaxMenu.vue'
import type { DPLGroupedData, GroupedDataItem } from './components/DPL.vue'
//API
import { getTaxComputationByWorkingRecordUuid, editTaxComputation, printScheduleOne } from '@/api/tax-computation'
//helpers
import { createDefaultAmountList, createDefaultTaxComputationSections, DEFAULT_TAX_RATE } from '@/helper/taxComputation'

interface Section {
  id: number
  title: string
  description: string
  dataContentList: any[]
}
export interface AmountList{
  title: string
  type: string
  current_year: number
  prior_year: number
}
interface Props {
  clientData: Content
  clientCurrency?: { currency: string; symbol: string; uuid: string } | null
  basicInformationData: BasicInformationData
  workingRecordUuid?: string
  mode: 'create' | 'edit'
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'toast', message: string, type: 'success' | 'error' | 'info' | 'warning'): void
}>()
const { clientData, basicInformationData, mode } = toRefs(props)
const taxCurrencyLabel = computed(() => props.clientCurrency?.currency || props.clientData?.currency || 'HKD')
const taxComputationUuid = ref<string>('')
const pendingDplRestoreData = ref<DPLGroupedData | GroupedDataItem[] | null>(null)
const amountList = ref<AmountList[]>(createDefaultAmountList())
const taxMenu = ref<TaxMenuItem[]>([
  { id: 0, scheduleNumber: 1, isIncluded: true, analysis: 'Profits Tax Computation' },
  { id: 1, scheduleNumber: 2, isIncluded: true, analysis: 'Computation of Depreciation Allowances' },
  { id: 2, scheduleNumber: 3, isIncluded: true, analysis: 'Additions to Property Plant and Equipment' },
  { id: 3, scheduleNumber: 4, isIncluded: true, analysis: 'Movement in Obligations under Finance Lease' },
  { id: 4, scheduleNumber: 5, isIncluded: true, analysis: 'Detailed Income Statement' },
  { id: 5, scheduleNumber: 6, isIncluded: true, analysis: 'Supporting Schedule' },
])

const sections=ref<Section[]>(createDefaultTaxComputationSections(basicInformationData.value, taxCurrencyLabel.value))
const selectedSection = ref<Section | null>(null)
const updateSelectedSection = (value: number) => {
  selectedSection.value = sections.value.find((section: Section) => section.id === value) ?? null
}
const taxRateItems = [
  { title: '16.5%', value: 0.165 },
  { title: '8.25%', value: 0.0825 },
]
const taxRate = ref<number>(DEFAULT_TAX_RATE)
const updateTaxMenu = (value: TaxMenuItem[]) => {
  taxMenu.value = value
}
const localDPL = ref<string>('')
const isDebugMode = import.meta.env.VITE_ENV_MODE === 'dev' ? true : false // for debugging
const onPostAll = () =>{
  console.log('onPostAll',selectedSection.value?.dataContentList)
}
const consoleAmountList = () =>{
  console.log('amount list:',amountList.value)
  console.log('tax computation uuid:',taxComputationUuid.value)
}
async function saveTaxComputation() {
  const payload = {
    data_content: {
      data: sections.value, //middle
      taxMenu: taxMenu.value, //left
      taxRate: taxRate.value,
    },
    data_content_amount_list: amountList.value,
    remark: '',
    status: 'pending',
    tax_computation: groupedDataFromDpl.value,
    uuid: taxComputationUuid.value,
    working_record_uuid: props.workingRecordUuid,
  }
  const res = await editTaxComputation(payload)
  console.log('res',res)
  return res
}

function mergeAmountListFromApi(list: unknown[]): AmountList[] {
  const defaults = createDefaultAmountList()
  if (!Array.isArray(list) || list.length === 0) return defaults

  return defaults.map((defaultItem) => {
    const apiItem = list.find((item): item is Partial<AmountList> =>
      typeof item === 'object' && item != null && 'type' in item && item.type === defaultItem.type,
    )

    return apiItem
      ? {
          ...defaultItem,
          ...apiItem,
          current_year: Number(apiItem.current_year ?? defaultItem.current_year),
          prior_year: Number(apiItem.prior_year ?? defaultItem.prior_year),
        }
      : defaultItem
  })
}

async function loadTaxComputation() {
  if (!props.workingRecordUuid) return

  const res = await getTaxComputationByWorkingRecordUuid(props.workingRecordUuid)
  if (res.status_code !== 200) return

  const { data } = res
  const dataContent = data?.data_content as { data?: Section[]; taxMenu?: TaxMenuItem[]; taxRate?: number } | undefined

  // Restore record identity and amount summary list
  taxComputationUuid.value = data?.uuid ?? ''
  amountList.value = mergeAmountListFromApi(data?.data_content_amount_list ?? [])

  // Stash restore payload first; apply when DPL ref is ready.
  pendingDplRestoreData.value = (data?.tax_computation ?? null) as DPLGroupedData | GroupedDataItem[] | null
  applyPendingDplRestoreData()

  // Restore tax computation sections (deep clone to avoid mutation)
  if (Array.isArray(dataContent?.data))
    sections.value = JSON.parse(JSON.stringify(dataContent.data))

  // Restore tax menu
  if (Array.isArray(dataContent?.taxMenu))
    taxMenu.value = dataContent.taxMenu

  // Restore tax rate
  if (typeof dataContent?.taxRate === 'number')
    taxRate.value = dataContent.taxRate

  updateSelectedSection(selectedSection.value?.id ?? 0)
}

function getAmountList() {
  return amountList.value.map(item => ({ ...item }))
}

function getDataContent() {
  return {
    data: JSON.parse(JSON.stringify(sections.value)),
    taxMenu: taxMenu.value,
    taxRate: taxRate.value,
  }
}

function getGroupedData(): DPLGroupedData {
  return {
    importedData: groupedDataFromDpl.value.importedData.map(item => ({ ...item, attr: { ...item.attr } })),
    mannualInputData: groupedDataFromDpl.value.mannualInputData.map(item => ({ ...item, attr: { ...item.attr } })),
  }
}

function getLocalDPL(): string {
  return localDPL.value || ''
}

defineExpose({
  getAmountList,
  getDataContent,
  getGroupedData,
  getLocalDPL,
  saveTaxComputation,
})

onMounted(async () => {
  updateSelectedSection(0)
  await loadTaxComputation()
})

watch(() => props.workingRecordUuid, async (value, oldValue) => {
  if (!value || value === oldValue) return
  await loadTaxComputation()
})

const dplRef = ref<InstanceType<typeof DPL> | null>(null)
function applyPendingDplRestoreData() {
  if (!dplRef.value)
    return
  dplRef.value.setGroupedData(pendingDplRestoreData.value)
}

watch(dplRef, () => {
  applyPendingDplRestoreData()
}, { immediate: true })

const groupedDataFromDpl = computed<DPLGroupedData>(() => {
  const g = dplRef.value?.groupedData
  const payload = (g && typeof g === 'object' && 'value' in g)
    ? (g as { value: DPLGroupedData }).value
    : (g as DPLGroupedData | undefined)

  return {
    importedData: Array.isArray(payload?.importedData) ? payload.importedData : [],
    mannualInputData: Array.isArray(payload?.mannualInputData) ? payload.mannualInputData : [],
  }
})

const groupedDataForProfitComputation = computed<GroupedDataItem[]>(() => [
  ...groupedDataFromDpl.value.importedData,
  ...groupedDataFromDpl.value.mannualInputData,
])

function onHandleSaveGroupedData(data: DPLGroupedData) {
  console.log('onHandleSaveGroupedData', data)
}

function setAmountListByType(type: string, current_year: number) {
  const item = amountList.value.find(a => a.type === type)
  if (item) item.current_year = current_year
}

function onUpdateTableData(payload: { order: number; tableData: any[] }) {
  const section = selectedSection.value
  if (!section?.dataContentList) return
  const item = section.dataContentList.find((i: any) => i.order === payload.order)
  if (item) item.tableData = payload.tableData
}

function onUpdateTextContent(payload: { order: number; content: string }) {
  const section = selectedSection.value
  if (!section?.dataContentList) return
  const item = section.dataContentList.find((i: any) => i.order === payload.order)
  if (item) item.content = payload.content
}

function onUpdateSelectedCheckbox(payload: { order: number; value: string[] }) {
  const section = selectedSection.value
  if (!section?.dataContentList) return
  const item = section.dataContentList.find((i: any) => i.order === payload.order)
  if (item) item.selectedCheckbox = payload.value
}

function onUpdateLocalDPL(val: string) {
  localDPL.value = val
}

async function onPrintScheduleOne() {
  if (!taxComputationUuid.value || !props.workingRecordUuid) return

  const result = await printScheduleOne(
    taxComputationUuid.value,
    props.workingRecordUuid,
    String((basicInformationData.value as any)?.company_name_en ?? (basicInformationData.value as any)?.companyNameEn ?? ''),
    String(basicInformationData.value?.year_of_assessment_ly ?? ''),
    String(basicInformationData.value?.year_of_assessment ?? ''),
  )
  const { blob, filename, errorMessage } = result
  if (errorMessage) {
    // emit('toast', errorMessage, 'error')
    emit('toast', 'Failed to print PDF', 'error')
    return
  }
  if (!blob || !filename) {
    emit('toast', 'Failed to print PDF', 'error')
    return
  }

  const url = URL.createObjectURL(blob)

  // Download the file
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function onResetSch1Data() {
  console.log('onResetSch1Data')
  sections.value[0].dataContentList = createDefaultTaxComputationSections(basicInformationData.value, taxCurrencyLabel.value)[0].dataContentList
}
</script>

<template>
  <VLayout v-if="taxComputationUuid || mode === 'create'" class="tax-computation-layout">
    <TaxMenu
      :tax-menu="taxMenu"
      @tax-menu-update="updateTaxMenu"
      @tab-change="updateSelectedSection"
    />
    <VMain class="tax-computation-main">
      <div class="tax-computation-middle pl-4">
      <VCard height="100vh" width="100%" class="border border-primary rounded pa-5 d-flex flex-column mb-3">
        <!-- Fixed: header text + button -->
        <div class="assessment-header-fixed">
          <h6 class="assessment-title text-h6">Years of Assessment {{basicInformationData.year_of_assessment_ly}}/{{basicInformationData.year_of_assessment}} and {{basicInformationData.provisional_ly}}/{{basicInformationData.provisional}} (Provisional)</h6>
          <p class="file-number">File Number: {{basicInformationData.taxFileNumber}}</p>
          <!-- <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="onPostAll">(Dev)Post all</VBtn> -->
          <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="onResetSch1Data" class="ml-2">(Dev)Reset sch1 data</VBtn>
          <VBtn v-if="isDebugMode" class ='ml-2' color="primary" size="x-small" @click="consoleAmountList">(Dev)Amount List</VBtn>
        </div>
        <VSheet class="sheet-wrap border border-primary rounded">
          <div class="sheet-header d-flex justify-space-between align-center pa-3" style="height: 64px;">
            <h6 class="sheet-title text-h6">{{ selectedSection?.title }}</h6>
            <div v-if="selectedSection?.id === 0" 
              class="d-flex gap-2 align-center"
              :style="{
                maxWidth: '25%',
                minWidth: taxComputationUuid && props.workingRecordUuid ? '200px' : '150px',
              }"
              >
              <VBtn v-if="taxComputationUuid && props.workingRecordUuid" color="primary" size="small" @click="onPrintScheduleOne">Print</VBtn>
              <VSelect density="compact" label="Tax rate" :items="taxRateItems" v-model="taxRate" />
            </div>
          </div>
          <VDivider />
          <div class="sheet-content">
            <!-- taxComputationUuid: {{ taxComputationUuid }}
            <br/>
            workingRecordUuid: {{ props.workingRecordUuid }} -->
            <ProfitsTaxComputation
              v-if="selectedSection?.id === 0"
              :data-content-list="selectedSection?.dataContentList ?? []"
              :client-data="clientData"
              :client-currency="props.clientCurrency ?? null"
              :basic-information-data="basicInformationData"
              :tax-rate="taxRate"
              :grouped-data="groupedDataForProfitComputation"
              :amount-list="amountList"
              @update:table-data="onUpdateTableData"
              @update:text-content="onUpdateTextContent"
              @update:selected-checkbox="onUpdateSelectedCheckbox"
              @update:amount-before-tax="(val) => setAmountListByType('amount_before_tax', val)"
              @update:net-assessable-profit="(val) => setAmountListByType('net_assessable_profit', val)"
              @update:profit-adjustment="(val) => setAmountListByType('profit_adjustment', val)"
              @update:year-of-assessment="(val) => setAmountListByType('year_of_assessment', val)"
              @update:year-of-assessment-provisional="(val) => setAmountListByType('year_of_assessment_provisional', val)"
              @update:profit-tax-current-year="(val) => setAmountListByType('profit_tax_current_year', val)"
              @update:profit-tax-provisional="(val) => setAmountListByType('profit_tax_provisional', val)"
              @update:total-tax-payable="(val) => setAmountListByType('total_tax_payable', val)"
            />
            <div v-if="selectedSection?.id === 4">
              <!-- {{ localDPL }} -->
            </div>
          </div>
        </VSheet>
      </VCard>
      </div>
      <div class="tax-computation-right">
        <DPL 
          ref="dplRef"
          :client-data="clientData"
          :client-currency="props.clientCurrency ?? null"
          :basic-information-data="basicInformationData"
          @save-grouped-data="onHandleSaveGroupedData"
          @update:localDPL="onUpdateLocalDPL"
        />
      </div>
    </VMain>
  </VLayout>
  <VLayout v-else>
    <div class="d-flex justify-center align-center pa-6">
      Tax Computation not found.
    </div>
  </VLayout>
</template>

<style lang="scss" scoped>
.tax-computation-layout {
  height: 100%;
}

.tax-computation-main {
  display: flex;
  align-items: stretch;
  min-width: 0;
  overflow-x: auto;
}

.tax-computation-middle {
  flex: 1 0 770px;
  inline-size: 770px;
  min-inline-size: 0;
}

.tax-computation-right {
  flex: 1 1 auto;
  min-width: 520px;
  min-inline-size: 520px;
  max-width: 720px;
  max-inline-size: 720px;
}

// Header section: fixed height, does not grow
.assessment-header-fixed {
  flex-shrink: 0;
  margin-block-end: 0.75rem;
}

.sheet-wrap {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sheet-header {
  flex-shrink: 0;
}

.sheet-content {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

</style>
