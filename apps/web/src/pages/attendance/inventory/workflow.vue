<script setup lang="ts">
definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const ready = ref(false)

onMounted(async () => {
  ready.value = await ensureAccess()
})

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
  { en: 'Deliver — create a Delivery Order from the SO and confirm it; stock actually leaves (Delivery Orders).', zh: '出貨 — 由 SO 建立出貨單並確認，庫存正式扣減（Delivery Orders）。' },
  { en: 'Invoice — issue an Inventory Invoice from the DO; optionally record a Receipt when paid (Invoices, Receipts).', zh: '開發票 — 由出貨單開立庫存發票；收款時登記收據（Invoices、Receipts）。' },
  { en: 'Handle returns — issue a Credit Note against the invoice; choose whether goods are restocked (Credit Notes).', zh: '處理退貨 — 對發票開立折讓單，可選擇是否回補庫存（Credit Notes）。' },
  { en: 'Reconcile — run stocktakes per location, check Movements for the audit trail, and watch the Dashboard alerts.', zh: '對帳 — 定期盤點、在 Movements 查閱異動流水，並留意 Dashboard 警示。' },
]
</script>

<template>
  <VContainer v-if="ready">
    <VRow class="mb-2">
      <VCol>
        <div class="text-h5 font-weight-medium">
          Workflow Guide 流程指南
        </div>
        <div class="text-body-2 text-medium-emphasis">
          The complete inventory flow from purchasing to invoicing.
          從採購到開票的完整庫存流程。
        </div>
      </VCol>
    </VRow>

    <VCard class="mb-4">
      <VCardTitle class="text-h6 py-3">
        Diagram 流程圖
      </VCardTitle>
      <VDivider />
      <VCardText class="overflow-x-auto">
        <img
          src="/inventory-workflow.svg"
          alt="Inventory workflow diagram: purchase order → goods receipt → stock → sales order → delivery order → invoice → receipt, with credit notes and stocktakes branching off."
          style="max-width: 100%; height: auto; min-width: 640px"
        >
      </VCardText>
    </VCard>

    <VCard>
      <VCardTitle class="text-h6 py-3">
        Step by step 逐步說明
      </VCardTitle>
      <VDivider />
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
    </VCard>
  </VContainer>
</template>
