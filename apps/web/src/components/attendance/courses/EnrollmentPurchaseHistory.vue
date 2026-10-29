<script setup lang="ts">
import type { CourseEnrollment } from '@/api/attendance/courses'
import { formatRosterDate, purchaseSummary, sortedPurchases } from '@/utils/courseRosterDisplay'

const props = defineProps<{
  enrollment: CourseEnrollment
}>()

const summary = computed(() => purchaseSummary(props.enrollment))
</script>

<template>
  <div class="purchase-history">
    <div class="text-subtitle-2 mb-1">
      Purchase history
    </div>
    <VTable density="compact">
      <thead>
        <tr>
          <th>Date</th>
          <th>Sessions</th>
          <th>Price</th>
          <th>Status</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="p in sortedPurchases(enrollment)"
          :key="p.id"
        >
          <td>{{ formatRosterDate(p.purchased_at) }}</td>
          <td>{{ p.purchased_quantity }}</td>
          <td>{{ p.unit_price != null ? `× HK$${Number(p.unit_price).toFixed(2)}` : 'price TBD' }}</td>
          <td>
            <VChip
              size="x-small"
              variant="tonal"
              :color="p.billed_invoice_line_id === null ? 'warning' : 'success'"
            >
              {{ p.billed_invoice_line_id === null ? 'unbilled' : 'billed' }}
            </VChip>
          </td>
          <td>{{ p.notes ?? '—' }}</td>
        </tr>
      </tbody>
    </VTable>
    <div class="text-caption text-medium-emphasis mt-1">
      Total {{ summary.total }} sessions · {{ summary.unbilledQty }} unbilled{{ summary.unbilledQty > 0 ? ' — run Generate on the Invoices page to bill them.' : '' }}
    </div>
  </div>
</template>

<style scoped>
.purchase-history {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.03);
}
</style>
