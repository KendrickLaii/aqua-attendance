<script setup lang="ts">
definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const ready = ref(false)

onMounted(async () => {
  ready.value = await ensureAccess()
})

interface TaskCard {
  icon: string
  titleZh: string
  titleEn: string
  steps: string[]
  primary: { label: string; to: { name: string; query?: Record<string, string> } }
  secondary?: { label: string; to: { name: string; query?: Record<string, string> } }
}

const tasks: TaskCard[] = [
  {
    icon: 'ri-flag-line',
    titleZh: '第一次使用',
    titleEn: 'First-time setup',
    steps: [
      '到 Items 新增品項（名稱、售價、安全庫存）',
      '到 Stock Overview 登記期初數量（原因選 opening）',
      '完成，之後就能進貨和賣貨',
    ],
    primary: { label: '新增品項', to: { name: 'attendance-inventory-items', query: { action: 'new' } } },
    secondary: { label: '登記期初庫存', to: { name: 'attendance-inventory', query: { action: 'movement' } } },
  },
  {
    icon: 'ri-shopping-cart-line',
    titleZh: '進了一批貨',
    titleEn: 'Got new stock from a supplier',
    steps: [
      '建採購單，選供應商和數量',
      '按 Order 下單',
      '貨到了按 Receive goods，再 Confirm，庫存自動增加',
    ],
    primary: { label: '建立採購單', to: { name: 'attendance-inventory-purchase-orders', query: { action: 'new' } } },
  },
  {
    icon: 'ri-store-2-line',
    titleZh: '賣東西給客戶',
    titleEn: 'Sell items',
    steps: [
      '建銷售單，選客戶和品項',
      '按 Quick Fulfill & Invoice，一次完成開票（扣庫存）、出貨單和收據',
      '之後在發票頁可再建出貨單記錄送貨、按 Record Payment 收款',
    ],
    primary: { label: '建立銷售單', to: { name: 'attendance-inventory-sales-orders', query: { action: 'new' } } },
  },
  {
    icon: 'ri-error-warning-line',
    titleZh: '東西壞了、遺失或送人',
    titleEn: 'Damaged / lost / gift',
    steps: [
      '開 Record Movement',
      '選出庫和原因（損毀、遺失、贈送需寫備註）',
      '儲存，庫存扣減並留紀錄',
    ],
    primary: { label: '登記出庫', to: { name: 'attendance-inventory', query: { action: 'movement', type: 'out' } } },
  },
  {
    icon: 'ri-exchange-line',
    titleZh: '分校之間搬貨',
    titleEn: 'Move stock between branches',
    steps: [
      '選品項、來源和目的分校',
      '填數量',
      '儲存，兩邊同時更新',
    ],
    primary: { label: '調撥', to: { name: 'attendance-inventory', query: { action: 'transfer' } } },
  },
  {
    icon: 'ri-survey-line',
    titleZh: '盤點',
    titleEn: 'Stocktake',
    steps: [
      '建盤點單選分校',
      '填實際數到的數量',
      'Save counts 後按 Apply，系統自動調整',
    ],
    primary: { label: '開始盤點', to: { name: 'attendance-inventory-stocktakes', query: { action: 'new' } } },
  },
  {
    icon: 'ri-refund-2-line',
    titleZh: '客戶退貨',
    titleEn: 'Customer return',
    steps: [
      '到 Sales Invoices 找到那張發票',
      '打開後按 Create Credit Note',
      '選退貨數量，勾「退回庫存」後 Confirm',
    ],
    primary: { label: '找發票', to: { name: 'attendance-inventory-invoices' } },
  },
  {
    icon: 'ri-search-eye-line',
    titleZh: '看還剩多少、要不要補貨',
    titleEn: 'Check stock',
    steps: [
      'Dashboard 看警示',
      'Stock Overview 紅色代表低於安全庫存',
      '需要補就去建採購單',
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
  { en: 'Create items — set up categories and items with sale/cost price and reorder level (Items).', zh: '建立品項 — 在 Items 設定分類、售價／成本價與補貨點。' },
  { en: 'Load opening stock — record opening balances per location, or import them via CSV (Stock Overview).', zh: '輸入期初庫存 — 在各分校登記期初數量，或用 CSV 匯入（Stock Overview）。' },
  { en: 'Create a purchase order — pick a supplier and order quantities (Purchase Orders).', zh: '建立採購單 — 選擇供應商與採購數量（Purchase Orders）。' },
  { en: 'Order the PO — move it from draft to ordered (Confirm on the PO).', zh: '送出採購單 — 將草稿 PO 確認為已下單。' },
  { en: 'Receive goods — create a Goods Receipt from the PO and confirm it; stock increases and avg cost updates (Goods Receipts).', zh: '收貨 — 由 PO 建立收貨單（GRN）並確認，庫存增加並更新平均成本（Goods Receipts）。' },
  { en: 'Create a sales order — pick a customer, items and prices (Sales Orders).', zh: '建立銷售單 — 選擇客戶、品項與價格（Sales Orders）。' },
  { en: 'Confirm the SO — available stock is reserved for the order.', zh: '確認銷售單 — 系統會為訂單保留可用庫存。' },
  { en: 'Invoice — create an Inventory Invoice from the SO and issue it; stock is deducted at issue (Invoices).', zh: '開發票 — 由銷售單建立庫存發票，開立（Issue）時庫存正式扣減（Invoices）。' },
  { en: 'Deliver — create Delivery Orders under the issued invoice; they record what was physically delivered, no stock effect (Delivery Orders).', zh: '送貨 — 在已開立的發票下建立出貨單，只記錄實際送貨，不影響庫存（Delivery Orders）。' },
  { en: 'Collect — record a Receipt when the customer pays (Receipts).', zh: '收款 — 客戶付款時登記收據（Receipts）。' },
  { en: 'Handle returns — issue a Credit Note against the invoice; choose whether goods are restocked (Credit Notes).', zh: '處理退貨 — 對發票開立折讓單，可選擇是否回補庫存（Credit Notes）。' },
  { en: 'Reconcile — run stocktakes per location, check Movements for the audit trail, and watch the Dashboard alerts.', zh: '對帳 — 定期盤點、在 Movements 查閱異動流水，並留意 Dashboard 警示。' },
]
</script>

<template>
  <VContainer v-if="ready">
    <VRow class="mb-2">
      <VCol>
        <div class="text-h5 font-weight-medium">
          從這裡開始 Start Here
        </div>
        <div class="text-body-2 text-medium-emphasis">
          選你現在要做的事，照 3 個步驟做就好。
        </div>
      </VCol>
    </VRow>

    <VRow>
      <VCol
        v-for="task in tasks"
        :key="task.titleZh"
        cols="12"
        md="6"
        lg="4"
      >
        <VCard class="h-100 d-flex flex-column">
          <VCardTitle class="d-flex align-center gap-2">
            <VIcon
              :icon="task.icon"
              color="primary"
            />
            <span>
              {{ task.titleZh }}
              <div class="text-caption text-medium-emphasis font-weight-regular">
                {{ task.titleEn }}
              </div>
            </span>
          </VCardTitle>
          <VCardText class="flex-grow-1">
            <ol class="ps-5">
              <li
                v-for="(step, i) in task.steps"
                :key="i"
                class="mb-1"
              >
                {{ step }}
              </li>
            </ol>
          </VCardText>
          <VCardActions class="px-4 pb-4">
            <VBtn
              color="primary"
              :to="task.primary.to"
            >
              {{ task.primary.label }}
            </VBtn>
            <VBtn
              v-if="task.secondary"
              variant="tonal"
              :to="task.secondary.to"
            >
              {{ task.secondary.label }}
            </VBtn>
          </VCardActions>
        </VCard>
      </VCol>
    </VRow>

    <VAlert
      type="info"
      variant="tonal"
      class="mt-4"
    >
      <strong>記住一件事 Key rule：</strong>
      庫存在「收貨確認」或「發票開立」時才會變動；出貨單只記錄送貨。
    </VAlert>

    <VExpansionPanels class="mt-4">
      <VExpansionPanel title="完整流程圖 Full diagram">
        <VExpansionPanelText>
          <div class="overflow-x-auto">
            <img
              src="/inventory-workflow.svg"
              alt="Inventory workflow diagram: purchase order → goods receipt → stock → sales order → invoice → receipt, with delivery orders, credit notes and stocktakes branching off."
              style="max-width: 100%; height: auto; min-width: 640px"
            >
          </div>
        </VExpansionPanelText>
      </VExpansionPanel>
      <VExpansionPanel title="完整步驟（進階） Full steps (advanced)">
        <VExpansionPanelText>
          <VList lines="three">
            <VListItem
              v-for="(step, i) in steps"
              :key="i"
            >
              <template #prepend>
                <VAvatar
                  color="primary"
                  variant="tonal"
                  size="32"
                  class="me-3"
                >
                  {{ i + 1 }}
                </VAvatar>
              </template>
              <VListItemTitle class="text-wrap">
                {{ step.en }}
              </VListItemTitle>
              <VListItemSubtitle class="text-wrap">
                {{ step.zh }}
              </VListItemSubtitle>
            </VListItem>
          </VList>
        </VExpansionPanelText>
      </VExpansionPanel>
    </VExpansionPanels>
  </VContainer>
</template>
