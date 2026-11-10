<script setup lang="ts">
definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const ready = ref(false)

onMounted(async () => {
  ready.value = await ensureAccess()
})

interface Bi {
  en: string
  zh: string
}

interface JobLink {
  label: string
  to: { name: string; query?: Record<string, string> }
}

interface SetupStep {
  title: Bi
  detail: Bi
  to: JobLink
}

interface Job {
  title: Bi
  steps: Bi[]
  primary: JobLink
  secondary?: JobLink
}

interface Faq {
  q: Bi
  a: Bi
}

const setup: SetupStep[] = [
  {
    title: { en: 'Create a warehouse', zh: '開一個倉庫' },
    detail: {
      en: 'Each warehouse has its own code, used in document numbers, e.g. PO-MK-000001.',
      zh: '每個倉庫有自己的編號，單號會用它，例如 PO-MK-000001。',
    },
    to: { label: 'Warehouses', to: { name: 'attendance-inventory-warehouses' } },
  },
  {
    title: { en: 'Set up categories and brands', zh: '建立分類和品牌' },
    detail: {
      en: 'Categories have two levels (e.g. Home Appliances › Smartphones). Brand is a separate field.',
      zh: '分類有兩層（例如 家用電器 › 智能手機），品牌是另一個獨立欄位。',
    },
    to: { label: 'Categories & Brands', to: { name: 'attendance-inventory-categories' } },
  },
  {
    title: { en: 'Add items', zh: '新增貨品' },
    detail: {
      en: 'Fill in name, price and reorder level. If it comes in sizes or colours, turn on variants.',
      zh: '填名稱、售價和安全庫存。有尺寸或顏色之分，就打開「多個規格」。',
    },
    to: { label: 'New item', to: { name: 'attendance-inventory-items', query: { action: 'new' } } },
  },
  {
    title: { en: 'Record opening stock', zh: '登記期初數量' },
    detail: {
      en: 'In Stock Overview pick a warehouse, then Record Movement (reason Opening) or import a CSV.',
      zh: '在庫存總覽選倉庫，用 Record Movement（原因 Opening）或匯入 CSV。',
    },
    to: { label: 'Record opening stock', to: { name: 'attendance-inventory', query: { action: 'movement' } } },
  },
]

const goodToKnow: Bi[] = [
  {
    en: 'Each variant has its own stock. Selling a size M only reduces size M.',
    zh: '每個規格獨立計庫存：賣出 M 碼，只扣 M 碼。',
  },
  {
    en: 'On purchase orders, sales orders and invoices you pick the exact variant, e.g. "School T-shirt M".',
    zh: '開採購單、銷售單、發票時，要選到哪一個規格，例如「校服 T-shirt M」。',
  },
  {
    en: 'Changing the item\'s name, brand or category updates all its variants.',
    zh: '改貨品名稱、品牌或分類，所有規格會一起更新。',
  },
  {
    en: 'Deactivating the item deactivates all variants. To stop selling just one variant, switch off that row.',
    zh: '停用整件貨品，所有規格一起停用；只停賣某個規格，就關掉表格中那一行。',
  },
  {
    en: 'A variant that has been used cannot be deleted (it has stock history) — deactivate it instead.',
    zh: '用過的規格不能刪除（有庫存紀錄），只能停用。',
  },
]

const devDiagram = `inventory_products  (one product, e.g. TSHIRT)
  options: {"尺寸": ["S","M","L","XL"]}
  brand_id ─► inventory_brands
  category_id ─► inventory_categories (parent_id, max 2 levels)
      │ 1 : N   (inventory_items.product_id)
      ▼
inventory_items  (one row per variant = SKU)
  TSHIRT-S   variant_attrs {"尺寸":"S"}
  TSHIRT-M   variant_attrs {"尺寸":"M"}
      │
      ▼  stock, movements and every document line point at the SKU`

const devNotes: string[] = [
  'The product only groups variants; it holds no stock.',
  '`skus` in the API response is computed, not stored.',
  'Create/edit a product with all its variants in one request: POST/PATCH /api/inventory/products with `skus` — all or nothing.',
  'Name, brand, category and unit cascade from product to variants; an inactive product forces all variants inactive.',
  'A single item is an inventory_items row with product_id = null.',
  'Rules: handbook §1.14. Open gaps: §5 #L8 (CSV variants), #L9 (BOM), #L10 (single → variants).',
]

const jobs: Job[] = [
  {
    title: { en: 'Maintain items', zh: '維護貨品' },
    steps: [
      {
        en: 'Add a new size: open the item, add the value (e.g. XXL) to the option, fill in its price, Save',
        zh: '加新尺寸：打開貨品，在規格加上新值（例如 XXL），填價錢後儲存',
      },
      {
        en: 'Change prices: open the item and edit the table, or use Apply to all',
        zh: '改價錢：打開貨品直接改表格，或用 Apply to all',
      },
      {
        en: 'Stop selling one variant: switch off its row; stop the whole item: switch off Active',
        zh: '停賣某個規格：關掉那一行；整件停賣：關掉 Active',
      },
    ],
    primary: { label: 'Items', to: { name: 'attendance-inventory-items' } },
    secondary: { label: 'Categories & Brands', to: { name: 'attendance-inventory-categories' } },
  },
  {
    title: { en: 'Goods arrived from a supplier', zh: '進了一批貨' },
    steps: [
      {
        en: 'Create a purchase order: choose the warehouse, supplier and quantities, then press Order',
        zh: '建採購單，選倉庫、供應商和數量，再按 Order',
      },
      { en: 'When the goods arrive, press Receive goods to create a goods receipt', zh: '貨到後按 Receive goods，開一張收貨單' },
      { en: 'Stock increases only after you Confirm', zh: 'Confirm 之後庫存才增加' },
    ],
    primary: { label: 'Create purchase order', to: { name: 'attendance-inventory-purchase-orders', query: { action: 'new' } } },
    secondary: { label: 'Suppliers', to: { name: 'attendance-inventory-suppliers' } },
  },
  {
    title: { en: 'Sell and collect', zh: '賣東西給客戶' },
    steps: [
      {
        en: 'Create a sales order: choose warehouse, customer and items, then Confirm to reserve stock',
        zh: '建銷售單，選倉庫、客戶和貨品，按 Confirm 保留庫存',
      },
      {
        en: 'Press Quick Fulfill & Invoice: it issues the invoice and deducts stock',
        zh: '按 Quick Fulfill & Invoice：開立發票並扣庫存',
      },
      {
        en: 'In the same window you can tick a delivery order and a receipt, or add them later',
        zh: '同一視窗可勾出貨單和收據；不勾就之後再補',
      },
    ],
    primary: { label: 'Create sales order', to: { name: 'attendance-inventory-sales-orders', query: { action: 'new' } } },
    secondary: { label: 'Customers', to: { name: 'attendance-inventory-customers' } },
  },
  {
    title: { en: 'Damage, loss, or gift', zh: '壞了、遺失或送人' },
    steps: [
      { en: 'In Stock Overview press Record Movement', zh: '在庫存總覽按 Record Movement' },
      { en: 'Choose the warehouse, Out, and a reason', zh: '選這個倉庫、出庫，以及原因' },
      {
        en: 'Damage, loss and gift need a note; the quantity is deducted when you save',
        zh: '損毀、遺失、贈送要寫備註，儲存後數量會扣減',
      },
    ],
    primary: { label: 'Record stock out', to: { name: 'attendance-inventory', query: { action: 'movement', type: 'out' } } },
  },
  {
    title: { en: 'Move stock between warehouses', zh: '搬去另一個倉庫' },
    steps: [
      { en: 'Press Transfer and choose the item', zh: '按 Transfer，選貨品' },
      { en: 'Choose the source and destination warehouses and enter the quantity', zh: '選來源倉庫和目的倉庫，填數量' },
      { en: 'Saving updates both warehouses', zh: '儲存後兩邊一起更新' },
    ],
    primary: { label: 'Transfer', to: { name: 'attendance-inventory', query: { action: 'transfer' } } },
  },
  {
    title: { en: 'Count what is on the shelf', zh: '盤點' },
    steps: [
      { en: 'Create a stocktake and pick one warehouse', zh: '建盤點單，選一個倉庫' },
      { en: 'Enter the counted quantities and press Save counts', zh: '填實際數到的數量，按 Save counts' },
      {
        en: 'Apply only adjusts the difference; it does not overwrite stock movements during the count',
        zh: 'Apply 只調整差額，不會蓋掉盤點期間的進出貨',
      },
    ],
    primary: { label: 'Start stocktake', to: { name: 'attendance-inventory-stocktakes', query: { action: 'new' } } },
  },
  {
    title: { en: 'Customer return', zh: '客戶退貨' },
    steps: [
      { en: 'Open the invoice in Sales Invoices', zh: '在 Sales Invoices 打開那張發票' },
      { en: 'Press Create Credit Note and enter the returned quantities', zh: '按 Create Credit Note，填退貨數量' },
      {
        en: 'Tick Restock to add stock back, then Confirm. For a fully paid invoice, void its receipts first',
        zh: '要加回庫存就勾 Restock，再 Confirm。已收齊的發票要先作廢收據',
      },
    ],
    primary: { label: 'Find invoice', to: { name: 'attendance-inventory-invoices' } },
  },
  {
    title: { en: 'Return goods to a supplier', zh: '退貨給供應商' },
    steps: [
      { en: 'Create a purchase return and choose the warehouse and supplier', zh: '建採購退貨單，選倉庫和供應商' },
      { en: 'Enter the items and quantities to return', zh: '填要退的貨品和數量' },
      { en: 'Stock is deducted only after Confirm Return', zh: 'Confirm Return 之後庫存才扣減' },
    ],
    primary: { label: 'Purchase returns', to: { name: 'attendance-inventory-purchase-returns' } },
  },
  {
    title: { en: 'See what to reorder', zh: '看還剩多少' },
    steps: [
      { en: 'Dashboard shows low stock, invoices to issue and unpaid invoices', zh: 'Dashboard 看低庫存、待開票和未收款' },
      { en: 'In Stock Overview, red means below the reorder level', zh: '庫存總覽裡，紅色代表低於安全庫存' },
      { en: 'To restock, create a purchase order', zh: '要補貨就去建採購單' },
    ],
    primary: { label: 'Dashboard', to: { name: 'attendance-inventory-dashboard' } },
    secondary: { label: 'Stock Overview', to: { name: 'attendance-inventory' } },
  },
]

const faqs: Faq[] = [
  {
    q: { en: 'Why can\'t I find a size when creating an order?', zh: '開單時為甚麼找不到某個尺寸？' },
    a: {
      en: 'It may be switched off. Open the item and switch the row back on (tick Show inactive on the Items page to see it).',
      zh: '那個規格可能已停用。打開貨品把那一行重新打開（在 Items 頁勾 Show inactive 才看得到）。',
    },
  },
  {
    q: { en: 'Why can\'t I remove a size?', zh: '為甚麼刪不到某個尺寸？' },
    a: { en: 'It already has stock history. Switch it off instead.', zh: '它已有庫存紀錄，只能停用。' },
  },
  {
    q: { en: 'I added a new option type (e.g. Colour) and can\'t save.', zh: '加了新的規格種類（例如顏色）後儲存不到。' },
    a: {
      en: 'Existing variants need a value for the new option. Pick one for each in the table, then Save.',
      zh: '已有的規格要補選新規格的值，在表格逐行選好再儲存。',
    },
  },
  {
    q: { en: 'Can I turn a single item into an item with variants?', zh: '單品可以改成有規格的貨品嗎？' },
    a: {
      en: 'Not yet. Create a new item with variants instead.',
      zh: '暫時不可以，請另外新增一件有規格的貨品。',
    },
  },
  {
    q: { en: 'Where do I add a brand or category?', zh: '在哪裏加品牌或分類？' },
    a: {
      en: 'Inventory › Stock › Categories & Brands, or the ＋ button next to the dropdown in New item.',
      zh: 'Inventory › Stock › Categories & Brands，或在 New item 的下拉旁按 ＋。',
    },
  },
  {
    q: { en: 'Why did the stock not change after I confirmed a delivery order?', zh: '確認出貨單後庫存為甚麼沒變？' },
    a: {
      en: 'Stock is deducted when the invoice is issued, not at delivery.',
      zh: '庫存在發票開立時才扣，出貨單不扣。',
    },
  },
]

const steps: Bi[] = [
  { en: 'Create a warehouse. Its code is printed on document numbers.', zh: '先開倉庫。倉庫編號會印在單號上。' },
  { en: 'Create items with a sale price, purchase price, and reorder level.', zh: '建立貨品：售價、進價、安全庫存。' },
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
      <h1 class="text-h4 font-weight-medium mb-0">
        Start here
      </h1>
      <p class="text-body-1 text-medium-emphasis mb-2">
        從這裡開始
      </p>
      <p class="text-body-1 mb-0">
        Pick the job you need to do now. Remember: stock goes up when a goods receipt is confirmed, and goes down when an invoice is issued. Delivery orders only record what was delivered.
      </p>
      <p class="text-caption text-medium-emphasis d-block mb-0">
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
        Before you start <span class="section-zh">開始前</span>
      </h2>
      <ol class="setup-rail">
        <li
          v-for="(item, index) in setup"
          :key="item.title.en"
        >
          <span
            class="step-index"
            aria-hidden="true"
          >{{ String(index + 1).padStart(2, '0') }}</span>
          <h3 class="text-subtitle-1 font-weight-medium mt-2 mb-0">
            {{ item.title.en }}
          </h3>
          <span class="text-caption text-medium-emphasis d-block mb-2">{{ item.title.zh }}</span>
          <p class="text-body-2 mb-0">
            {{ item.detail.en }}
          </p>
          <span class="text-caption text-medium-emphasis d-block mb-3">{{ item.detail.zh }}</span>
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

    <section
      aria-labelledby="variants-heading"
      class="variants"
    >
      <h2
        id="variants-heading"
        class="section-label"
      >
        Items and variants <span class="section-zh">貨品與規格</span>
      </h2>
      <p class="text-body-1 mb-0">
        Every item is added with <strong>New item</strong>. There are two kinds:
      </p>
      <span class="text-caption text-medium-emphasis d-block mb-3">所有貨品都在「New item」新增，分兩種：</span>

      <div class="kind-grid">
        <VCard
          variant="outlined"
          class="pa-4"
        >
          <h3 class="text-subtitle-1 font-weight-medium mb-0">
            Single item
          </h3>
          <span class="text-caption text-medium-emphasis d-block mb-2">單品</span>
          <p class="text-body-2 mb-0">
            One price, one stock count. E.g. a calculator or a desk lamp.
          </p>
          <span class="text-caption text-medium-emphasis d-block">一個價錢、一個庫存。例如計數機、枱燈。</span>
        </VCard>
        <VCard
          variant="outlined"
          class="pa-4"
        >
          <h3 class="text-subtitle-1 font-weight-medium mb-0">
            Item with variants
          </h3>
          <span class="text-caption text-medium-emphasis d-block mb-2">有規格的貨品</span>
          <p class="text-body-2 mb-0">
            Turn on "This item has variants", enter the options (e.g. Size: S, M, L, XL). A table appears with one row per variant; codes are filled in for you (TSHIRT-S, TSHIRT-M…). Type prices in the table or use Apply to all, then Save.
          </p>
          <span class="text-caption text-medium-emphasis d-block">
            打開「This item has variants」，填規格（例如 尺寸：S、M、L、XL）。系統即時列出每個規格一行，編號自動產生（TSHIRT-S、TSHIRT-M…）。在表格填價錢或按 Apply to all，然後儲存。
          </span>
        </VCard>
      </div>

      <div class="overflow-x-auto mt-4">
        <img
          src="/inventory-variants.svg"
          alt="Items and variants: a School T-shirt item with brand, category and a Size option (S, M, L, XL) fans out into four variants, each with its own price and stock; the XL variant is inactive. A separate single item, a Casio calculator, has one price and one stock count."
          style="max-width: 100%; height: auto; min-width: 560px"
        >
      </div>
      <VBtn
        variant="text"
        size="small"
        prepend-icon="ri-download-line"
        href="/inventory-variants.svg"
        download="inventory-variants.svg"
        class="mt-1"
      >
        Download image 下載圖片
      </VBtn>

      <h3 class="text-subtitle-1 font-weight-medium mt-4 mb-2">
        Good to know <span class="text-medium-emphasis text-body-2">要記住</span>
      </h3>
      <ul class="know-list">
        <li
          v-for="(point, index) in goodToKnow"
          :key="index"
        >
          <span class="text-body-2">{{ point.en }}</span>
          <span class="text-caption text-medium-emphasis d-block">{{ point.zh }}</span>
        </li>
      </ul>
    </section>

    <section aria-labelledby="jobs-heading">
      <h2
        id="jobs-heading"
        class="section-label"
      >
        Jobs <span class="section-zh">要做的事</span>
      </h2>
      <ol class="job-list">
        <li
          v-for="job in jobs"
          :key="job.title.en"
          class="job"
        >
          <div class="job-copy">
            <h3 class="text-subtitle-1 font-weight-medium mb-0">
              {{ job.title.en }}
            </h3>
            <p class="text-caption text-medium-emphasis mb-2">
              {{ job.title.zh }}
            </p>
            <ol class="job-steps">
              <li
                v-for="(step, index) in job.steps"
                :key="index"
              >
                <span class="text-body-2">{{ step.en }}</span>
                <span class="text-caption text-medium-emphasis d-block">{{ step.zh }}</span>
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

    <section aria-labelledby="faq-heading">
      <h2
        id="faq-heading"
        class="section-label"
      >
        FAQ <span class="section-zh">常見問題</span>
      </h2>
      <VExpansionPanels variant="accordion">
        <VExpansionPanel
          v-for="faq in faqs"
          :key="faq.q.en"
        >
          <VExpansionPanelTitle>
            <div>
              <div class="text-body-2 font-weight-medium">
                {{ faq.q.en }}
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ faq.q.zh }}
              </div>
            </div>
          </VExpansionPanelTitle>
          <VExpansionPanelText>
            <p class="text-body-2 mb-0">
              {{ faq.a.en }}
            </p>
            <span class="text-caption text-medium-emphasis d-block">{{ faq.a.zh }}</span>
          </VExpansionPanelText>
        </VExpansionPanel>
      </VExpansionPanels>
    </section>

    <VExpansionPanels class="mt-8">
      <VExpansionPanel title="Full flow diagram 完整流程圖">
        <VExpansionPanelText>
          <div class="overflow-x-auto">
            <img
              src="/inventory-workflow.svg"
              alt="Inventory workflow: item setup (warehouse, categories and brands, items, opening stock), then purchase order to goods receipt to stock, then sales order to invoice to receipt. Delivery orders, credit notes and stocktakes branch off."
              style="max-width: 100%; height: auto; min-width: 640px"
            >
          </div>
        </VExpansionPanelText>
      </VExpansionPanel>
      <VExpansionPanel title="Full sequence 完整順序">
        <VExpansionPanelText>
          <ol class="advanced-steps">
            <li
              v-for="(step, index) in steps"
              :key="index"
            >
              <span class="text-body-2">{{ step.en }}</span>
              <span class="text-caption text-medium-emphasis d-block">{{ step.zh }}</span>
            </li>
          </ol>
        </VExpansionPanelText>
      </VExpansionPanel>
      <VExpansionPanel title="For developers 開發人員">
        <VExpansionPanelText>
          <pre class="dev-diagram">{{ devDiagram }}</pre>
          <ul class="text-body-2 dev-notes">
            <li
              v-for="note in devNotes"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
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

.section-zh {
  margin-inline-start: 0.5rem;
  letter-spacing: 0.05em;
  text-transform: none;
}

.setup-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.kind-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.know-list {
  margin: 0;
  padding-left: 1.15rem;
}

.know-list li + li {
  margin-top: 0.6rem;
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
  margin-top: 0.5rem;
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

.dev-diagram {
  margin: 0 0 1rem;
  padding: 0.75rem 1rem;
  overflow-x: auto;
  font-size: 0.8125rem;
  line-height: 1.5;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.dev-notes {
  margin: 0;
  padding-left: 1.15rem;
}

@media (max-width: 960px) {
  .setup-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kind-grid {
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

@media (max-width: 600px) {
  .setup-rail {
    grid-template-columns: 1fr;
  }
}
</style>
