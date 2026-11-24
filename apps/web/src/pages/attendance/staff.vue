<script setup lang="ts">
import UnitListPage from '@/components/attendance/units/UnitListPage.vue'

definePage({ meta: { action: 'manage', subject: 'StaffAdmin' } })
</script>

<template>
  <UnitListPage fixed-type="staff" />
</template>
