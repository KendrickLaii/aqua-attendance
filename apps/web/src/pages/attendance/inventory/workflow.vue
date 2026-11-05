<script setup lang="ts">
definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const ready = ref(false)

onMounted(async () => {
  ready.value = await ensureAccess()
})

interface JobLink {
  label: string
  to: { name: string; query?: Record<string, string> }
}

interface SetupStep {
  title: string
  detail: string
  to: JobLink
}

interface Job {
  titleZh: string
  titleEn: string
  steps: string[]
  primary: JobLink
  secondary?: JobLink
}

const setup: SetupStep[] = [
  {
    title: '開一個倉庫',
    detail: '每個倉庫有自己的編號，單號會用它，例如 PO-MK-000001。',
    to: { label: '去倉庫', to: { name: 'attendance-inventory-warehouses' } },
  },
  {
    title: '建立品項',
    detail: '填名稱、售價、進價和安全庫存。沒有品項，後面的單都開不了。',
    to: { label: '新增品項', to: { name: 'attendance-inventory-items', query: { action: 'new' } } },
  },
  {
    title: '登記期初數量',
    detail: '在庫存總覽選倉庫，用 Record Movement（原因 Opening）或匯入 CSV。',
    to: { label: '登記期初', to: { name: 'attendance-inventory', query: { action: 'movement' } } },
  },
]

const jobs: Job[] = [
  {
    titleZh: '進了一批貨',
    titleEn: 'Goods arrived from a supplier',
    steps: [
      '建採購單，選倉庫、供應商和數量，再按 Order',
      '貨到後按 Receive goods，開一張收貨單',
      'Confirm 之後庫存才增加',
    ],
    primary: { label: '建立採購單', to: { name: 'attendance-inventory-purchase-orders', query: { action: 'new' } } },
    secondary: { label: '供應商', to: { name: 'attendance-inventory-suppliers' } },
  },
  {
    titleZh: '賣東西給客戶',
    titleEn: 'Sell and collect',
    steps: [
      '建銷售單，選倉庫、客戶和品項，按 Confirm 保留庫存',
      '按 Quick Fulfill & Invoice：開立發票並扣庫存',
      '同一視窗可勾出貨單和收據；不勾就之後再補',
    ],
    primary: { label: '建立銷售單', to: { name: 'attendance-inventory-sales-orders', query: { action: 'new' } } },
    secondary: { label: '客戶', to: { name: 'attendance-inventory-customers' } },
  },
  {
    titleZh: '壞了、遺失或送人',
    titleEn: 'Damage, loss, or gift',
    steps: [
      '在庫存總覽按 Record Movement',
      '選這個倉庫、出庫，以及原因',
      '損毀、遺失、贈送要寫備註，儲存後數量會扣減',
    ],
    primary: { label: '登記出庫', to: { name: 'attendance-inventory', query: { action: 'movement', type: 'out' } } },
  },
  {
    titleZh: '搬去另一個倉庫',
    titleEn: 'Move stock between warehouses',
    steps: [
      '按 Transfer，選品項',
      '選來源倉庫和目的倉庫，填數量',
      '儲存後兩邊一起更新',
    ],
    primary: { label: '調撥', to: { name: 'attendance-inventory', query: { action: 'transfer' } } },
  },
  {
    titleZh: '盤點',
    titleEn: 'Count what is on the shelf',
    steps: [
      '建盤點單，選一個倉庫',
      '填實際數到的數量，按 Save counts',
      'Apply 只調整差額，不會蓋掉盤點期間的進出貨',
    ],
    primary: { label: '開始盤點', to: { name: 'attendance-inventory-stocktakes', query: { action: 'new' } } },
  },
  {
    titleZh: '客戶退貨',
    titleEn: 'Customer return',
    steps: [
      '在 Sales Invoices 打開那張發票',
      '按 Create Credit Note，填退貨數量',
      '要加回庫存就勾 Restock，再 Confirm。已收齊的發票要先作廢收據',
    ],
    primary: { label: '找發票', to: { name: 'attendance-inventory-invoices' } },
  },
  {
    titleZh: '退貨給供應商',
    titleEn: 'Return goods to a supplier',
    steps: [
      '建採購退貨單，選倉庫和供應商',
      '填要退的品項和數量',
      'Confirm Return 之後庫存才扣減',
    ],
    primary: { label: '採購退貨', to: { name: 'attendance-inventory-purchase-returns' } },
  },
  {
    titleZh: '看還剩多少',
    titleEn: 'See what to reorder',
    steps: [
      'Dashboard 看低庫存、待開票和未收款',
      '庫存總覽裡，紅色代表低於安全庫存',
      '要補貨就去建採購單',
    ],
    primary: { label: 'Dashboard', to: { name: 'attendance-inventory-dashboard' } },
    secondary: { label: '庫存總覽', to: { name: 'attendance-inventory' } },
  },
]

interface FlowStep {
  en: string
  zh: string
}

const steps: FlowStep[] = [
  { en: 'Create a warehouse. Its code is printed on document numbers.', zh: '先開倉庫。倉庫編號會印在單號上。' },
  { en: 'Create items with a sale price, purchase price, and reorder level.', zh: '建立品項：售價、進價、安全庫存。' },
  { en: 'Record opening quantities for that warehouse, or import a CSV.', zh: '在該倉庫登記期初數量，或用 CSV 匯入。' },
  { en: 'Create a purchase order for a supplier, then mark it ordered.', zh: '向供應商建採購單，再按 Order 下單。' },
  { en: 'Confirm a goods receipt. Stock and average cost update only then.', zh: '確認收貨單後，庫存和平均成本才更新。' },
  { en: 'Create a sales order. Confirming it reserves available stock.', zh: '建銷售單。Confirm 會保留可用庫存。' },
  { en: 'Issue the invoice. Stock is deducted at issue, not when the delivery order is confirmed.', zh: '開立發票時扣庫存。出貨單只記錄送了什麼。' },
  { en: 'Record a receipt when the customer pays.', zh: '客戶付款時登記收據。' },
  { en: 'A credit note reduces the balance. Tick Restock only for goods that come back.', zh: '折讓單減少應收。貨退回來才勾 Restock。' },
  { en: 'A purchase return deducts stock when you confirm it.', zh: '退給供應商的貨，確認退貨單後才扣庫存。' },
  { en: 'Stocktakes adjust by the difference. Movements keeps the trail.', zh: '盤點按差額調整。異動紀錄留在 Movements。' },
]
</script>

<template>
  <VContainer
    v-if="ready"
    class="workflow-sheet"
  >
    <header class="sheet-head">
      <p class="sheet-kicker">
        Inventory
      </p>
      <h1 class="text-h4 font-weight-medium mb-2">
        從這裡開始
      </h1>
      <p class="text-body-1 text-medium-emphasis mb-0">
        選一件現在要做的事。平常買賣記這句：收貨確認才加庫存，發票開立才扣庫存。出貨單只記錄送貨。
      </p>
    </header>

    <section
      class="setup"
      aria-labelledby="setup-heading"
    >
      <h2
        id="setup-heading"
        class="section-label"
      >
        開始前
      </h2>
      <ol class="setup-rail">
        <li
          v-for="(item, index) in setup"
          :key="item.title"
        >
          <span
            class="step-index"
            aria-hidden="true"
          >{{ String(index + 1).padStart(2, '0') }}</span>
          <h3 class="text-subtitle-1 font-weight-medium mt-2 mb-1">
            {{ item.title }}
          </h3>
          <p class="text-body-2 text-medium-emphasis mb-3">
            {{ item.detail }}
          </p>
          <VBtn
            size="small"
            variant="tonal"
            :to="item.to.to"
          >
            {{ item.to.label }}
          </VBtn>
        </li>
      </ol>
    </section>

    <section aria-labelledby="jobs-heading">
      <h2
        id="jobs-heading"
        class="section-label"
      >
        要做的事
      </h2>
      <ol class="job-list">
        <li
          v-for="job in jobs"
          :key="job.titleZh"
          class="job"
        >
          <div class="job-copy">
            <h3 class="text-subtitle-1 font-weight-medium mb-0">
              {{ job.titleZh }}
            </h3>
            <p class="text-caption text-medium-emphasis mb-2">
              {{ job.titleEn }}
            </p>
            <ol class="job-steps text-body-2">
              <li
                v-for="(step, index) in job.steps"
                :key="index"
              >
                {{ step }}
              </li>
            </ol>
          </div>
          <div class="job-actions">
            <VBtn
              color="primary"
              size="small"
              :to="job.primary.to"
            >
              {{ job.primary.label }}
            </VBtn>
            <VBtn
              v-if="job.secondary"
              size="small"
              variant="text"
              :to="job.secondary.to"
            >
              {{ job.secondary.label }}
            </VBtn>
          </div>
        </li>
      </ol>
    </section>

    <VExpansionPanels class="mt-8">
      <VExpansionPanel title="完整流程圖">
        <VExpansionPanelText>
          <div class="overflow-x-auto">
            <img
              src="/inventory-workflow.svg"
              alt="Inventory workflow: purchase order to goods receipt to stock, then sales order to invoice to receipt. Delivery orders, credit notes and stocktakes branch off."
              style="max-width: 100%; height: auto; min-width: 640px"
            >
          </div>
        </VExpansionPanelText>
      </VExpansionPanel>
      <VExpansionPanel title="完整順序">
        <VExpansionPanelText>
          <ol class="advanced-steps">
            <li
              v-for="(step, index) in steps"
              :key="index"
            >
              <span class="text-body-2">{{ step.zh }}</span>
              <span class="text-caption text-medium-emphasis d-block">{{ step.en }}</span>
            </li>
          </ol>
        </VExpansionPanelText>
      </VExpansionPanel>
    </VExpansionPanels>
  </VContainer>
</template>

<style scoped lang="scss">
.workflow-sheet {
  max-width: 880px;
}

.sheet-head {
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.sheet-kicker {
  margin: 0 0 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgb(var(--v-theme-primary));
}

.section-label {
  margin: 2rem 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.setup-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.setup-rail > li {
  padding-top: 0.75rem;
  border-top: 2px solid rgb(var(--v-theme-primary));
}

.step-index {
  font-variant-numeric: tabular-nums;
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: rgb(var(--v-theme-primary));
}

.job-list {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: job;
}

.job {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem 1.5rem;
  padding: 1.25rem 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.job-steps {
  margin: 0;
  padding-left: 1.15rem;
}

.job-steps li + li {
  margin-top: 0.25rem;
}

.job-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.advanced-steps {
  margin: 0;
  padding-left: 1.25rem;
}

.advanced-steps li + li {
  margin-top: 0.85rem;
}

@media (max-width: 720px) {
  .setup-rail {
    grid-template-columns: 1fr;
  }

  .job {
    grid-template-columns: 1fr;
  }

  .job-actions {
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
  }
}
</style>
