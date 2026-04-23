<script setup lang="ts">
import type { Content } from '@/types/client'
import type { CurrencyProperties } from '@/types/currency'
import { createClient, updateClient } from '@/api/client'
import { getAllCurrency } from '@/api/currency'
import BasicInfo from './client-dialog-tabs/BasicInfo.vue'
import History from './client-dialog-tabs/History.vue'

// Validation error type for showAlert payload
export interface ShowAlertPayload {
  message: string
  type?: 'success' | 'error'
  errors?: { tab: string; fields?: string[] }[]
}

interface Emit {
  (e: 'submit', value: Content): void
  (e: 'success'): void
  (e: 'showAlert', payload: ShowAlertPayload): void
}

const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const dialogMode = ref<'Create' | 'Edit'>('Create')
const clientData = ref<Content | null>(null)


// Refs for tab components
const basicInfoRef = ref()
const historyRef = ref()

// Tabs configuration
const tabs = [
  { title: 'Basic info', component: 'BasicInfo', ref: basicInfoRef },
  { title: 'History', component: 'History', ref: historyRef },
]

const currentTab = ref(0)

// Data from each tab
const tabData = ref<Record<string, any>>({
  basicInfo: {},
  history: {},
})
const currencyItems = ref<Array<{ label: string; value: string }>>([])

const fetchCurrencyItems = async () => {
  try {
    const res = await getAllCurrency(1, 1000)
    const list = res?.data?.content ?? []
    currencyItems.value = (list as CurrencyProperties[])
      .filter(item => Boolean(item.uuid))
      .map(item => ({
        label: item.currency,
        value: item.uuid,
      }))
  }
  catch (error) {
    console.error('Failed to fetch currencies:', error)
    currencyItems.value = []
  }
}

onMounted(() => {
  fetchCurrencyItems()
})

const openDialog = async (mode: 'Create' | 'Edit', data: Content | null = null) => {
  dialogMode.value = mode
  clientData.value = data
  currentTab.value = 0

  if (mode === 'Edit' && data) {
    tabData.value = {
      basicInfo: data,
      history: {},
    }
  }
  else {
    tabData.value = {
      basicInfo: {},
      history: {},
    }
  }

  isDialogVisible.value = true
  console.log("TEST tabData",tabData.value)
}

// Handle data updates from tabs
const handleBasicInfoUpdate = (data: any) => {
  tabData.value.basicInfo = data
}

const handleBasicInfoAlert = (payload: ShowAlertPayload) => {
  emit('showAlert', payload)
}

// Expose methods to parent component
defineExpose({
  openDialog
})

// Form submission
const formSubmit = async () => {
  // Validate all tabs
  const validations = await Promise.all([
    basicInfoRef.value?.validate(),
  ])

  const tabNames = ['Basic Info']

  interface ValidationError {
    tab: string
    fields?: string[]
  }

  const errors: ValidationError[] = []
  validations.forEach((result, index) => {
    if (result === false) {
      errors.push({ tab: tabNames[index] })
    }
    else if (result && typeof result === 'object' && 'valid' in result && !result.valid) {
      errors.push({
        tab: tabNames[index],
        fields: result.errors || [],
      })
    }
  })

  const allValid = errors.length === 0

  if (allValid) {
    try {
      const editUuid = clientData.value && 'uuid' in clientData.value ? clientData.value.uuid : undefined
      const { tax_file_no_part1, tax_file_no_part2, ...basicInfoRest } = tabData.value.basicInfo as Record<string, unknown>
      const submitData: Partial<Content> = {
        ...basicInfoRest,
        ...(dialogMode.value === 'Edit' && editUuid ? { uuid: editUuid } : {}),
      }

      if (dialogMode.value === 'Create') {
        await createClient(submitData as Content)
        emit('success')
        emit('showAlert', { message: 'Client created successfully' })
      }
      else {
        await updateClient(submitData as Partial<Content>)
        emit('success')
        emit('showAlert', { message: 'Client updated successfully' })
      }

      isDialogVisible.value = false
    }
    catch (error) {
      console.error('Failed to submit client data:', error)
      emit('showAlert', { message: 'Failed to save client data' })
    }
  }
  else {
    emit('showAlert', {
      message: 'Please fill in all required fields',
      errors,
    })
  }
}

const resetClientData = () => {
  isDialogVisible.value = false

  nextTick(() => {
    clientData.value = null
    currentTab.value = 0
    tabData.value = {
      basicInfo: {},
      history: {},
    }
  })
}
</script>

<template>
  <VDialog
    v-model="isDialogVisible"
    max-width="70vw"
    height="95vh"
    scrollable
  >
    <VCard class="pa-sm-8 pa-4">
      <div class="d-flex justify-space-between align-center mb-4">
        <h4 class="text-h4">
          {{ dialogMode }}
        </h4>
        <!-- 👉 dialog close btn -->
        <DialogCloseBtn
          variant="text"
          size="default"
          @click="resetClientData"
        />
      </div>

      <VCardText class="pt-1 overflow-hidden px-0">
        <VTabs show-arrows v-model="currentTab" fixed>
          <VTab v-for="(tab, index) in tabs" :key="index">
            {{ tab.title }}
          </VTab>
        </VTabs>

        <VWindow v-model="currentTab" v-if="isDialogVisible">
          <VWindowItem class="overflow-y-auto overflow-x-hidden pb-3 pr-3 form-scroll">
            <!-- {{ tabData.basicInfo }} -->
            <BasicInfo
              ref="basicInfoRef"
              :initial-data="tabData.basicInfo"
              :currency-items="currencyItems"
              @update:data="handleBasicInfoUpdate"
              @showAlert="handleBasicInfoAlert"
            />
          </VWindowItem>

          <VWindowItem class="overflow-y-auto overflow-x-hidden pb-3 pr-3 form-scroll">
            <History ref="historyRef" />
          </VWindowItem>
        </VWindow>
      </VCardText>

      <VDivider />

      <!-- footer buttons -->
      <VCardText class="overflow-hidden d-flex justify-end flex-wrap gap-4 pt-3 pb-1 px-4">
        <VBtn
          color="secondary"
          variant="outlined"
          @click="resetClientData"
        >
          Cancel
        </VBtn>

        <VBtn
          type="submit"
          @click="formSubmit"
        >
          Submit
          <VIcon
            end
            icon="ri-check-line"
            class="flip-in-rtl"
          />
        </VBtn>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style lang="scss" scoped>
.form-scroll {
  height: calc(95vh - 210px);
}
</style>
<style>
.flatpickr-calendar.open {
  z-index: 2501 !important;
}
</style>
