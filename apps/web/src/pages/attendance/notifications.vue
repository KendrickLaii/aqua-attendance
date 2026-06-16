<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listNotificationsWithTotal, markNotificationRead, markNotificationUnread } from '@/api/attendance/notifications'
import type { Notification } from '@/api/attendance/notifications'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const NOTIF_PAGE_SIZE = 50

const authStore = useAttendanceAuthStore()
const router = useRouter()

const notifications = ref<Notification[]>([])
const totalCount = ref(0)
const unreadCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filterRead = ref('')
const page = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / NOTIF_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const readOptions = [
  { title: 'All', value: '' },
  { title: 'Unread', value: 'unread' },
  { title: 'Read', value: 'read' },
]

const priorityColorMap: Record<string, string> = {
  low: 'grey',
  medium: 'info',
  high: 'warning',
  urgent: 'error',
}

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} notification${total === 1 ? '' : 's'}`
  if (unreadCount.value > 0)
    label += ` · ${unreadCount.value} unread`
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  await loadNotifications()
})

async function loadNotifications(isRefresh = false, resetPage = false) {
  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const isReadParam = filterRead.value === 'read'
      ? true
      : filterRead.value === 'unread'
        ? false
        : undefined

    const result = await listNotificationsWithTotal({
      is_read: isReadParam,
      page: page.value,
      page_size: NOTIF_PAGE_SIZE,
    })

    notifications.value = result.items
    totalCount.value = result.total
    unreadCount.value = result.items.filter(n => !n.is_read).length
  }
  catch (e) {
    console.error('Failed to load notifications', e)
    loadError.value = formatApiError(e, 'Failed to load notifications.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

watch(filterRead, () => {
  loadNotifications(true, true)
})

async function toggleRead(n: Notification) {
  try {
    if (n.is_read)
      await markNotificationUnread(n.id)
    else
      await markNotificationRead(n.id)

    n.is_read = !n.is_read
    n.read_at = n.is_read ? new Date().toISOString() : null
  }
  catch (e) {
    console.error('Failed to update read status', e)
    loadError.value = formatApiError(e, 'Could not update status')
  }
}

async function markAllAsRead() {
  const unread = notifications.value.filter(n => !n.is_read)
  if (unread.length === 0)
    return
  try {
    await Promise.all(unread.map(n => markNotificationRead(n.id)))
    notifications.value.forEach((n) => {
      if (!n.is_read) {
        n.is_read = true
        n.read_at = new Date().toISOString()
      }
    })
    unreadCount.value = 0
  }
  catch (e) {
    console.error('Failed to mark all as read', e)
    loadError.value = formatApiError(e, 'Could not mark all as read')
  }
}

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadNotifications(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadNotifications(true)
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <h1 class="text-h5 font-weight-bold">
          Notifications
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex flex-wrap gap-2"
      >
        <VSelect
          v-model="filterRead"
          :items="readOptions"
          item-title="title"
          item-value="value"
          label="Filter"
          density="compact"
          hide-details
          class="filter-field"
        />
        <VBtn
          v-if="unreadCount > 0"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="tabler-mail-opened"
          @click="markAllAsRead"
        >
          Mark all read
        </VBtn>
        <VBtn
          icon
          variant="text"
          :loading="refreshing"
          @click="loadNotifications(true)"
        >
          <VIcon>tabler-refresh</VIcon>
        </VBtn>
      </VCol>
    </VRow>

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-2"
    />

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ loadError }}
    </VAlert>

    <VList
      v-if="notifications.length > 0"
      lines="two"
      density="compact"
    >
      <VListItem
        v-for="n in notifications"
        :key="n.id"
        :class="{ 'bg-surface-variant': !n.is_read }"
      >
        <template #prepend>
          <VIcon
            :color="priorityColorMap[n.priority] ?? 'grey'"
            size="small"
          >
            tabler-bell
          </VIcon>
        </template>
        <VListItemTitle :class="{ 'font-weight-bold': !n.is_read }">
          {{ n.title }}
          <VChip
            :color="priorityColorMap[n.priority] ?? 'grey'"
            size="x-small"
            label
            class="ms-2"
          >
            {{ n.priority }}
          </VChip>
        </VListItemTitle>
        <VListItemSubtitle class="text-caption">
          {{ n.message }}
        </VListItemSubtitle>
        <template #append>
          <div class="d-flex align-center">
            <span class="text-caption text-medium-emphasis me-3">
              {{ n.created_at.slice(0, 16).replace('T', ' ') }}
            </span>
            <VBtn
              icon
              size="small"
              variant="text"
              :color="n.is_read ? 'grey' : 'primary'"
              :title="n.is_read ? 'Mark unread' : 'Mark read'"
              @click="toggleRead(n)"
            >
              <VIcon>{{ n.is_read ? 'tabler-mail-opened' : 'tabler-mail' }}</VIcon>
            </VBtn>
          </div>
        </template>
      </VListItem>
    </VList>

    <div
      v-if="notifications.length === 0 && !loading"
      class="text-center py-12"
    >
      <VIcon
        size="64"
        color="medium-emphasis"
        class="mb-4"
      >
        tabler-bell-off
      </VIcon>
      <div class="text-h6 text-medium-emphasis mb-1">
        No notifications
      </div>
      <div class="text-body-2 text-medium-emphasis">
        You're all caught up
      </div>
    </div>

    <div class="d-flex align-center justify-space-between mt-3">
      <span class="text-caption text-medium-emphasis">{{ totalCount }} total</span>
      <div class="d-flex align-center gap-2">
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasPrevPage"
          @click="goToPrevPage"
        >
          <VIcon>tabler-chevron-left</VIcon>
        </VBtn>
        <span class="text-caption">{{ page }} / {{ totalPages }}</span>
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasNextPage"
          @click="goToNextPage"
        >
          <VIcon>tabler-chevron-right</VIcon>
        </VBtn>
      </div>
    </div>
  </VContainer>
</template>

<style scoped lang="scss">
.filter-field {
  inline-size: 140px;
}
</style>
