import type {
  BusinessNatureEditPayload,
  BusinessNatureListResponse,
  BusinessNatureMutationResponse,
  BusinessNaturePayload,
} from '@/types/business-nature'

export async function getAllBusinessNature(page: number, size: number) {
  const res = await $authApi('/business_nature/get/all', {
    method: 'GET',
    params: { page, size },
  })
  return res as BusinessNatureListResponse
}

export async function getBusinessNatureByUuid(uuid: string) {
  const res = await $authApi(`/business_nature/get/${uuid}`, {
    method: 'GET',
  })
  return res as BusinessNatureMutationResponse
}

export async function createBusinessNature(payload: BusinessNaturePayload) {
  const res = await $authApi('/business_nature/create', {
    method: 'POST',
    body: payload,
  })
  return res as BusinessNatureMutationResponse
}

export async function updateBusinessNature(uuid: string, payload: BusinessNaturePayload) {
  const req: BusinessNatureEditPayload = { ...payload, uuid }
  const res = await $authApi('/business_nature/edit', {
    method: 'PUT',
    body: req,
  })
  return res as BusinessNatureMutationResponse
}

export async function deleteBusinessNature(uuid: string) {
  const res = await $authApi('/business_nature/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`],
    },
  })
  return res as BusinessNatureMutationResponse
}
