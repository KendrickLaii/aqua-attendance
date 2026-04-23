import type { WorkingRecordPayload, WorkingRecordListItem } from '@/types/working-section'

export async function getWorkingRecordsAll(page: number, size: number) {
  const res = await $authApi('/working_record/get/all', {
    method: 'GET',
    params: { page, size },
  })
  return res as {
    status_code?: number
    message?: string
    data?: { content?: WorkingRecordListItem[]; count?: number }
  }
}

export async function createWorkingRecord(payload: WorkingRecordPayload) {
  const res = await $authApi('/working_record/create', {
    method: 'POST',
    body: payload,
  })
  return res
}

export async function getWorkingRecordByUuid(uuid: string) {
  const res = await $authApi(`/working_record/get/${uuid}`, {
    method: 'GET',
  })
  return res as {
    status_code?: number
    message?: string
    data?: WorkingRecordListItem
  }
}

export async function updateWorkingRecord(uuid: string, payload: WorkingRecordPayload) {
  const res = await $authApi('/working_record/edit', {
    method: 'PUT',
    body: { ...payload, uuid },
  })
  return res as {
    status_code?: number
    message?: string
    data?: string
  }
}

export async function upsertWorkingRecord(
  uuid: string | null,
  payload: WorkingRecordPayload,
) {
  const res = await $authApi('/working_record/upsert', {
    method: 'POST',
    body: uuid ? { ...payload, uuid } : payload,
  })

  return res as {
    status_code?: number
    message?: string
    data?: string
  }
}

export async function deleteWorkingRecord(uuid: string) {
  const res = await $authApi('/working_record/del',{
      method: 'DELETE',
      body: {
          uuid: uuid,
          data:[`${uuid}`] //update this if handle batch delete
      },
  })
  return res
}
