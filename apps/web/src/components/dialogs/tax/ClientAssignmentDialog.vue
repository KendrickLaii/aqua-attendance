<script setup lang="ts">
//api
import { getAllAdministrators } from '@/api/administrator'
//types
import type { AdministratorProperties } from '@/types/administrator'

interface Emit {
    (e: 'update:isDialogVisible', value: boolean): void
    (e: 'success'): void
    (e: 'showAlert', message: string): void
}

const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const clientId = ref<number | null>(null)
const nameSearch = ref('')

const openDialog = (id: number) => {
    isDialogVisible.value = true
    clientId.value = id
}

const itemsPerPage = ref(20)
const page = ref(1)

const headers = [
    { title: 'Name', key: 'username', sortable: false },
    { title: 'Level', key: 'level', sortable: false, width: '200px' },
    { title: 'Entry date', key: 'created_at', sortable: false, width: '150px' },
    { title: 'Actions', key: 'actions', sortable: false, width: '120px', align: 'center' as const },
]

// Expose method to parent component
defineExpose({
    openDialog
})

const formSubmit = async () => {
    console.log(clientId.value)
}

const resetData = () => {
    // Close dialog - this will unmount all tab components due to v-if
    isDialogVisible.value = false
    
    // Reset data after dialog is closed
    nextTick(() => {
        clientId.value = null
        nameSearch.value = ''
    })
}
// 👉 Fetching administrators
const responseData = ref<AdministratorProperties>()
const tableLoading = ref(false)
const fetchData = async () => {
    tableLoading.value = true
  try {
    const response = await getAllAdministrators(page.value, itemsPerPage.value)
    responseData.value = response as AdministratorProperties
    console.log("👉getAllAdministrators response: ",responseData.value)
  } catch (error: any) {
    console.error("👉getAllAdministrators error: ", error)
    // get status code from error object, if not found, set to 500
    const statusCode = error?.statusCode || error?.status || error?.response?.status || 500
    // set default value, ensure the computed property returns an empty array
    responseData.value = {
      status_code: statusCode,
      message: 'Failed to fetch data',
      data: {
        content: [],
        count: 0,
      },
    } as AdministratorProperties
  }
  tableLoading.value = false
}

// Initial fetch
await fetchData()

// Watch for pagination changes
watch([page, itemsPerPage], () => {
    fetchData()
})

const formatDate = (date: string) => {
    if (!date) return ''
    const dateObj = new Date(date)
    return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// filter table items by search (name, role as job title)
const tableItems = computed(() => {
    const list = responseData.value?.data?.content ?? []
    const q = (nameSearch.value ?? '').trim().toLowerCase()
    if (!q) return list
    return list.filter(
        (item: { username?: string; role?: string }) =>
            (item.username ?? '').toLowerCase().includes(q) 
            // ||
            // (item.role ?? '').toLowerCase().includes(q)
    )
})
</script>
    
<template>
    <VDialog
    scrollable
    :width="$vuetify.display.smAndDown ? 'auto' : 1000"
    v-model="isDialogVisible"
    >
    <VCard class="pa-sm-6 pa-4">
        <div class="d-flex justify-space-between align-center mb-4">
            <h5 class="text-h5">
                Job assignment
            </h5>
            <!-- 👉 dialog close btn -->
            <DialogCloseBtn
                variant="text"
                size="default"
                @click="resetData"
            />
        </div>

        <VDivider />
        
        <VCardText class="pt-5 card-content">
                <div class="d-flex justify-space-between align-center mb-2">
                    <VTextField
                        v-model="nameSearch"
                        label="Search by name..."
                        placeholder="Enter name"
                        density="compact"
                        max-width="400px"
                        prepend-inner-icon="ri-search-line"
                        clearable
                        hide-details
                    />
                    <VSpacer />
                    <VBtn
                        color="primary"
                    >
                        Refresh
                    </VBtn>
                </div>
                <VDataTableServer
                    v-model:items-per-page="itemsPerPage"
                    v-model:page="page"
                    :items="tableItems"
                    :items-length="tableItems.length"
                    :headers="headers"
                    height="50vh"
                    :loading="tableLoading"
                >
                <template #item.created_at="{ item }">
                    {{ formatDate(item.created_at || '') }}
                </template>
                <template #item.level="{ item }">
                    <VSelect
                    :items="['Level 1', 'Level 2', 'Level 3']"
                    item-title="text"
                    item-value="value"
                    label="Level"
                    density="compact"
                    placeholder="Select Level"
                    clearable
                    />
                </template>
                <template #item.actions="{ item }">
                    <!-- Remove access -->
                    <IconBtn
                        size="small"
                        >
                        <VIcon color="error" icon="ri-delete-bin-line" />
                    </IconBtn>
                </template>
                </VDataTableServer>
        </VCardText>
        <V-Divider />
        <!-- 👉footer buttons -->
        <VCardActions class="d-flex justify-end flex-wrap gap-4 py-3 px-3">
            <VBtn
                color="secondary"
                variant="outlined"
                @click="resetData"
            >
                Cancel
            </VBtn>

            <VBtn
                type="submit"
                variant="elevated"
                color="primary"
                @click="formSubmit"
            >
                    Submit
                <VIcon
                    end
                    icon="ri-check-line"
                    class="flip-in-rtl"
                />
            </VBtn>
        </VCardActions>
    </VCard>
    </VDialog>
</template>
<style lang="scss" scoped>
// dialog pagination center
// .card-content{
//     margin-bottom: -20px!important;
// }
:deep(.v-card-text.card-content){
    padding-left: 0px!important;
    padding-right: 0px!important;
}
</style>
